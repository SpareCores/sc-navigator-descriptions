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
from sc_crawler.tables import BenchmarkScore, Server, Vendor
from sc_data import db
from sqlalchemy.orm import contains_eager
from sqlmodel import Session, create_engine, select

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

DATA_FOLDER = os.environ.get("DATA_FOLDER", default="data")
os.makedirs(DATA_FOLDER, exist_ok=True)

INTERESTING_CPU_FLAGS = {
    "SIMD and data science/machine learning": [
        "avx",
        "avx512f",
        "avx512_vnni",
        "avx_vnni",
        "avx512_bf16",
        "amx_tile",
        "amx_int8",
    ],
    "crypto": ["aes", "vaes", "sha_ni"],
    "integeres and bit manipulation": ["bmi2", "adx", "fma"],
    "topology": ["ht", "xtopology", "x2apic"],
    "memory and cache control": ["clflushopt", "clwb", "wbnoinvd", "flush_l1d"],
    "virtualization": ["vmx", "svm", "hypervisor"],
    "security": ["ibrs", "ssbd", "ibt", "tme"],
}
INTERESTING_BENCHMARKS = {
    "single-core CPU performance": {"benchmark_id": "stress_ng:best1", "config": None},
    "multi-core CPU performance": {"benchmark_id": "stress_ng:bestn", "config": None},
    "memory bandwidth read-only small block (16kb - cached)": {
        "benchmark_id": "bw_mem",
        "config": {"operation": "rd", "size": 0.016384},
    },
    "memory bandwidth read-only large block (8mb - potentially uncached)": {
        "benchmark_id": "bw_mem",
        "config": {"operation": "rd", "size": 8.0},
    },
    "gzip compression single-threaded": {
        "benchmark_id": "compression_text:compress",
        "config": {"algo": "gzip", "compression_level": 5, "threads": 1},
    },
    "zstd decompression single-threaded": {
        "benchmark_id": "compression_text:decompress",
        "config": {"algo": "zstd", "compression_level": 1, "threads": 0},
    },
    "geekbench score": {"benchmark_id": "geekbench:score", "config": None},
    "passmark cpu score": {"benchmark_id": "passmark:cpu_mark", "config": None},
    "passmark memory score": {"benchmark_id": "passmark:memory_mark", "config": None},
    "llm inference speed for text generation using 2B model": {
        "benchmark_id": "llm_speed:prompt_processing",
        "config": {
            "framework_version": "51f311e0",
            "model": "gemma-2b.Q4_K_M.gguf",
            "tokens": 128,
        },
    },
    "llm inference speed for text generation using 2B model": {
        "benchmark_id": "llm_speed:text_generation",
        "config": {
            "framework_version": "51f311e0",
            "model": "gemma-2b.Q4_K_M.gguf",
            "tokens": 128,
        },
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
    print(benchmark_category)
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
    if np.mean(values) > reference_stats["p90"]:
        return "elite (top 10%) performer server"
    elif np.mean(values) > reference_stats["p75"]:
        return "strong (top 10-25%) performer server"
    elif np.mean(values) > reference_stats["p25"]:
        return "average (25-75% percentile) performer server"
    elif np.mean(values) > reference_stats["p10"]:
        return "weak (bottom 10-25%) performer server"
    else:
        return "poor (bottom 10%) performer server"


def _categorized_cpu_flags(server_flags):
    out = {}
    for category, flags in INTERESTING_CPU_FLAGS.items():
        present = [f for f in flags if f in server_flags]
        if present:
            out[category] = present
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

    _benchmarks = benchmarks

    for server in servers:
        print(server.name)
        benchmark_scores = [
            benchmark
            for benchmark in _benchmarks
            if benchmark.server_id == server.server_id
        ]
        print(len(benchmark_scores))
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
            "cpu_l1_cache_bytes": server.cpu_l1_cache,
            "cpu_l2_cache_bytes": server.cpu_l2_cache,
            "cpu_l3_cache_bytes": server.cpu_l3_cache,
            "cpu_flags_extra_availability": _categorized_cpu_flags(server.cpu_flags),
            "memory_amount_mb": server.memory_amount,
            "memory_amount_mb_per_core": server.memory_amount / server.vcpus,
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
            "benchmarks": {},
        }
        # drop null values
        server_dict = {k: v for k, v in server_dict.items() if v is not None}
        # add benchmark scores
        for benchmark_category, benchmark_mapping in INTERESTING_BENCHMARKS.items():
            result = get_benchmark_stats_for_server(
                server.server_id,
                benchmark_category,
            )
            if result is not None:
                server_dict["benchmarks"][benchmark_category] = result
        print(server_dict)
        print(dumps(server_dict, indent=2))


if __name__ == "__main__":
    main()
