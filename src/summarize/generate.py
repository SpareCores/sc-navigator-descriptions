"""
Generate human-friendly, plain English summaries for all servers.
"""

import logging
import os
from functools import cache
from json import dumps

import click
import numpy as np
from instructor import from_provider
from pydantic import BaseModel, field_validator
from sc_crawler.table_fields import Status
from sc_crawler.tables import BenchmarkScore, Server, ServerPrice, Vendor
from sc_data import db
from sqlalchemy.orm import contains_eager
from sqlmodel import Session, create_engine, func, select

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

DATA_FOLDER = os.environ.get("DATA_FOLDER", default="data")
os.makedirs(DATA_FOLDER, exist_ok=True)

# #############################################################################
# LLM configuration


class ServerSummary(BaseModel):
    # tagline
    w20: str
    # meta description
    c150: str
    # OG description
    c200: str
    # full description
    w150: str

    @field_validator("w20")
    def validate_w20(cls, v: str) -> str:
        n = len(v.strip().split())
        assert 15 <= n <= 25, f"w20 must be 15-25 words, got {n}"
        return v

    @field_validator("c150")
    def validate_c150(cls, v: str) -> str:
        n = len(v.strip())
        assert 125 <= n <= 175, f"c150 must be 125-175 characters, got {n}"
        return v

    @field_validator("c200")
    def validate_c200(cls, v: str) -> str:
        n = len(v.strip())
        assert 175 <= n <= 225, f"c200 must be 175-225 characters, got {n}"
        return v

    @field_validator("w150")
    def validate_w150(cls, v: str) -> str:
        n = len(v.strip().split())
        assert 125 <= n <= 175, f"w150 must be 125-175 words, got {n}"
        return v


system_prompt = open("src/summarize/prompts/system.md").read()
user_prompt = open("src/summarize/prompts/user.md").read()

# client = from_provider("google/gemini-2.5-pro")
# client = from_provider("google/gemini-3.1-pro-preview")
# client = from_provider("google/gemini-3-flash-preview")
client = from_provider("google/gemini-2.5-flash")

# #############################################################################
# Server lookup configuration


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
        return ("top tier (top 10%)", value_str)
    elif value > reference_stats["p75"]:
        return ("strong (top 25%)", value_str)
    elif value > reference_stats["p25"]:
        return ("average (middle 50%)", value_str)
    elif value > reference_stats["p10"]:
        return ("weak (bottom 25%)", value_str)
    else:
        return ("poor (bottom 10%)", value_str)


def _categorized_cpu_flags(server_flags):
    out = {}
    for category, flags in INTERESTING_CPU_FLAGS.items():
        out[category] = {}
        for flag in flags:
            out[category][flag] = flag in server_flags
    return out


# #############################################################################
# Main function


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
            "cpu_speed": str(server.cpu_speed) + " GHz" if server.cpu_speed else None,
            "cpu_manufacturer": server.cpu_manufacturer,
            "cpu_family": server.cpu_family,
            "cpu_model": server.cpu_model,
            "cpu_cache_size": {
                "l1d": str(int(server.cpu_l1_cache / 1024)) + " KB",
                "l2": str(int(server.cpu_l2_cache / 1024 / 1024)) + " MB",
                "l3": str(int(server.cpu_l3_cache / 1024 / 1024)) + " MB",
            },
            "cpu_flags_extra_availability": _categorized_cpu_flags(server.cpu_flags),
            "memory_amount": (
                str(round(server.memory_amount / 1024)) + " GB"
                if server.memory_amount
                else None
            ),
            "memory_amount_per_core": (
                str(round(server.memory_amount / 1024 / server.vcpus, 2)) + " GB"
                if server.memory_amount
                else None
            ),
            "memory_generation": server.memory_generation,
            "memory_speed": (
                str(round(server.memory_speed / 1000)) + " GHz"
                if server.memory_speed
                else None
            ),
            "gpu_count": server.gpu_count,
            "gpu_manufacturer": server.gpu_manufacturer,
            "gpu_family": server.gpu_family,
            "gpu_model": server.gpu_model,
            "gpu_vram_total": str(round(server.gpu_memory_total / 1024)) + " GB",
            "local_storage_size": (
                str(round(server.storage_size)) + " GB"
                if server.storage_size
                else "None"
            ),
            "local_storage_type": (
                server.storage_type.value if server.storage_type else None
            ),
            "network_bandwidth": (
                str(round(server.network_speed)) + " Gbps"
                if server.network_speed
                else None
            ),
            "complimentary_public_ipv4_addresses": server.ipv4,
            "min_ondemand_price_per_hour": (
                str(round(price.price, 2)) + " USD" if price is not None else None
            ),
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

        resp = client.create(
            response_model=ServerSummary,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_prompt + dumps(server_dict, indent=2),
                },
            ],
            generation_config={
                "temperature": 0.25,
                "top_p": 1.0,
            },
        )
        pp(resp.model_dump())


if __name__ == "__main__":
    main()
