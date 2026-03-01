"""
Generate human-friendly, plain English summaries for all servers.
"""

import logging
import os
from functools import cache
from json import dumps

import click
import numpy as np
from sc_crawler.table_fields import Status
from sc_crawler.tables import BenchmarkScore, Server, ServerPrice, Vendor
from sc_data import db
from sqlalchemy.orm import contains_eager
from sqlmodel import Session, create_engine, func, select

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

DATA_FOLDER = os.environ.get("DATA_FOLDER", default="data")
os.makedirs(DATA_FOLDER, exist_ok=True)

INTERESTING_CPU_FLAGS = {
    "Advanced Vector Extensions and Advanced Matrix Extensions": [
        "avx",
        "avx512f",
        "avx512_vnni",
        "avx_vnni",
        "avx512_bf16",
        "amx_tile",
        "amx_int8",
    ],
    "Cryptography": ["aes", "vaes", "sha_ni"],
    "Integers and bit manipulation": ["bmi2", "adx", "fma"],
    "Topology": ["ht", "xtopology", "x2apic"],
    "Memory and cache control": ["clflushopt", "clwb", "wbnoinvd", "flush_l1d"],
    "Virtualization": ["vmx", "svm", "hypervisor"],
    "Security": ["ibrs", "ssbd", "ibt", "tme"],
}
INTERESTING_BENCHMARKS = {
    "single-core CPU performance": {"benchmark_id": "stress_ng:best1", "config": None},
    "multi-core CPU performance": {"benchmark_id": "stress_ng:bestn", "config": None},
    "memory bandwidth read-only small block (16kb - cached)": {
        "benchmark_id": "bw_mem",
        "config": {"operation": "rd", "size": 0.016384},
        "unit": "GB/sec",
        "transform": lambda x: x / 1024,
    },
    "memory bandwidth read-only large block (8mb - potentially uncached)": {
        "benchmark_id": "bw_mem",
        "config": {"operation": "rd", "size": 8.0},
        "unit": "GB/sec",
        "transform": lambda x: x / 1024,
    },
    "gzip compression single-threaded": {
        "benchmark_id": "compression_text:compress",
        "config": {"algo": "gzip", "compression_level": 5, "threads": 1},
        "unit": "GB/sec",
        "transform": lambda x: x / 1024 / 1024,
    },
    "zstd decompression single-threaded": {
        "benchmark_id": "compression_text:decompress",
        "config": {"algo": "zstd", "compression_level": 1, "threads": 0},
        "unit": "GB/sec",
        "transform": lambda x: x / 1024 / 1024,
    },
    "geekbench score": {"benchmark_id": "geekbench:score", "config": None},
    "passmark cpu score": {"benchmark_id": "passmark:cpu_mark", "config": None},
    "passmark memory score": {"benchmark_id": "passmark:memory_mark", "config": None},
    "llm inference speed for prompt processing using 135M model": {
        "benchmark_id": "llm_speed:prompt_processing",
        "config": {
            "framework_version": "51f311e0",
            "model": "SmolLM-135M.Q4_K_M.gguf",
            "tokens": 128,
        },
        "unit": "tokens/sec",
    },
    "llm inference speed for text generation using 135M model": {
        "benchmark_id": "llm_speed:text_generation",
        "config": {
            "framework_version": "51f311e0",
            "model": "SmolLM-135M.Q4_K_M.gguf",
            "tokens": 128,
        },
        "unit": "tokens/sec",
    },
    "llm inference speed for prompt processing using 70B model": {
        "benchmark_id": "llm_speed:prompt_processing",
        "config": {
            "framework_version": "51f311e0",
            "model": "Llama-3.3-70B-Instruct-Q4_K_M.gguf",
            "tokens": 128,
        },
        "unit": "tokens/sec",
    },
    "llm inference speed for text generation using 70B model": {
        "benchmark_id": "llm_speed:text_generation",
        "config": {
            "framework_version": "51f311e0",
            "model": "Llama-3.3-70B-Instruct-Q4_K_M.gguf",
            "tokens": 128,
        },
        "unit": "tokens/sec",
    },
}

_benchmarks: list[BenchmarkScore] = []


@cache
def get_benchmark_stats(benchmark_category: str):
    benchmark_mapping = INTERESTING_BENCHMARKS[benchmark_category]
    benchmark_id, config = (
        benchmark_mapping["benchmark_id"],
        benchmark_mapping["config"],
    )
    values = [
        benchmark.score
        for benchmark in _benchmarks
        if benchmark.benchmark_id == benchmark_id
        and (benchmark.config == config if config is not None else True)
    ]
    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "p90": np.percentile(values, 90),  # top 10%
        "p75": np.percentile(values, 75),
        "p25": np.percentile(values, 25),
        "p10": np.percentile(values, 10),
    }


def get_benchmark_stats_for_server(server_id: str, benchmark_category: str):
    reference_stats = get_benchmark_stats(benchmark_category)
    benchmark_mapping = INTERESTING_BENCHMARKS[benchmark_category]
    values = [
        benchmark.score
        for benchmark in _benchmarks
        if (
            benchmark.server_id == server_id
            and benchmark.benchmark_id == benchmark_mapping["benchmark_id"]
            and (
                benchmark.config == benchmark_mapping["config"]
                if benchmark_mapping["config"] is not None
                else True
            )
        )
    ]
    if len(values) == 0:
        return ("no data available", None)
    value = np.mean(values)
    if benchmark_mapping.get("transform") is not None:
        value = benchmark_mapping["transform"](value)
    value_str = str(round(value, 2))
    if benchmark_mapping.get("unit") is not None:
        value_str = f"{value_str} {benchmark_mapping['unit']}"
    if value > reference_stats["p90"]:
        return ("elite", value_str)
    elif value > reference_stats["p75"]:
        return ("strong", value_str)
    elif value > reference_stats["p25"]:
        return ("average", value_str)
    elif value > reference_stats["p10"]:
        return ("weak", value_str)
    else:
        return ("poor", value_str)


def _categorized_cpu_flags(server_flags):
    out = {}
    for category, flags in INTERESTING_CPU_FLAGS.items():
        out[category] = {}
        for flag in flags:
            out[category][flag] = flag in server_flags
    return out


@click.command()
@click.option(
    "--n", type=int, default=None, help="Limit the number of servers to process"
)
def main(n):
    global _benchmarks
    engine = create_engine(f"sqlite:///{db.path}")
    query = select(Server).where(Server.status == Status.ACTIVE)
    if n is not None:
        query = query.limit(n)

    query = query.join(Vendor).options(contains_eager(Server.vendor))

    with Session(engine) as session:
        servers = session.exec(query).all()
        benchmarks = session.exec(
            select(BenchmarkScore).where(
                BenchmarkScore.server_id.in_([server.server_id for server in servers])
            )
        ).all()
        prices = session.exec(
            select(
                ServerPrice.vendor_id,
                ServerPrice.server_id,
                func.min(ServerPrice.price).label("price"),
            )
            .where(
                ServerPrice.allocation == "ONDEMAND"
                and ServerPrice.status == Status.ACTIVE
            )
            .group_by(ServerPrice.vendor_id, ServerPrice.server_id)
        ).all()

    _benchmarks = benchmarks

    for server in servers:
        print(server.name)
        benchmark_scores = [
            benchmark
            for benchmark in _benchmarks
            if benchmark.server_id == server.server_id
        ]
        price = next(
            (price for price in prices if price.server_id == server.server_id), None
        )
        server_dict = {
            "vendor_name": server.vendor.name,
            "server_name": server.name,
            "server_family": server.family,
            "basic_description": server.description,
            "hypervisor": server.hypervisor,
            "cpu_architecture": server.cpu_architecture,
            "cpu_vcpus": server.vcpus,
            "cpu_physical_cores": server.cpu_cores,
            "cpu_threads_per_core": server.vcpus / server.cpu_cores,
            "cpu_speed_ghz": server.cpu_speed,
            "cpu_manufacturer": server.cpu_manufacturer,
            "cpu_family": server.cpu_family,
            "cpu_model": server.cpu_model,
            "cpu_cache_size": {
                "l1d (kb)": int(server.cpu_l1_cache / 1024),
                "l2 (mb)": int(server.cpu_l2_cache / 1024 / 1024),
                "l3 (mb)": int(server.cpu_l3_cache / 1024 / 1024),
            },
            "cpu_flags_extra_availability": _categorized_cpu_flags(server.cpu_flags),
            "memory_amount_mb": server.memory_amount,
            "memory_amount_mb_per_core": round(server.memory_amount / server.vcpus),
            "memory_generation": server.memory_generation,
            "memory_speed_mhz": server.memory_speed,
            "gpu_count": server.gpu_count,
            "gpu_manufacturer": server.gpu_manufacturer,
            "gpu_family": server.gpu_family,
            "gpu_model": server.gpu_model,
            "gpu_vram_mb_total": server.gpu_memory_total,
            "local_storage_size_gb": server.storage_size,
            "local_storage_type": server.storage_type,
            "network_bandwidth_gbps": server.network_speed,
            "complimentary_public_ipv4_addresses": server.ipv4,
            "price_per_hour_usd": price.price if price is not None else None,
            "benchmarks": {},
        }
        # drop null values
        server_dict = {k: v for k, v in server_dict.items() if v is not None}
        # add benchmark scores
        for benchmark, _ in INTERESTING_BENCHMARKS.items():
            result = get_benchmark_stats_for_server(server.server_id, benchmark)
            category, value = result
            server_dict["benchmarks"][benchmark] = {
                "value": value,
                "category": category,
            }
        print(server_dict)
        print(dumps(server_dict, indent=2))


if __name__ == "__main__":
    main()
