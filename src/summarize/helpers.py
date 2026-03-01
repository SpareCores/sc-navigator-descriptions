"""
Helper functions for building server payloads and calling the LLM.
"""

from functools import cache
from json import dumps

import numpy as np

from . import config, database
from .config import INTERESTING_BENCHMARKS, INTERESTING_CPU_FLAGS
from .models import ServerSummary


def _categorized_cpu_flags(server_flags) -> dict:
    out = {}
    for category, flags in INTERESTING_CPU_FLAGS.items():
        out[category] = {}
        for flag in flags:
            out[category][flag] = flag in server_flags
    return out


@cache
def get_benchmark_stats(benchmark_category: str) -> dict:
    """Reference percentiles for a benchmark category."""
    benchmark_mapping = INTERESTING_BENCHMARKS[benchmark_category]
    benchmark_id, conf = (
        benchmark_mapping["benchmark_id"],
        benchmark_mapping.get("config"),
    )
    values = [
        b.score
        for b in database.benchmarks
        if b.benchmark_id == benchmark_id
        and (b.config == conf if conf is not None else True)
    ]
    if not values:
        raise ValueError(
            f"No reference stats found for benchmark category: {benchmark_category}"
        )
    return {
        "p90": np.percentile(values, 90),
        "p75": np.percentile(values, 75),
        "p25": np.percentile(values, 25),
        "p10": np.percentile(values, 10),
    }


def get_benchmark_stats_for_server(
    vendor_id: str, server_id: str, benchmark_category: str
) -> tuple[str, str]:
    """Get benchmark stats for a server and return tier and value string."""
    reference_stats = get_benchmark_stats(benchmark_category)
    benchmark_mapping = INTERESTING_BENCHMARKS[benchmark_category]
    values = [
        b.score
        for b in database.benchmarks
        if (
            b.vendor_id == vendor_id
            and b.server_id == server_id
            and b.benchmark_id == benchmark_mapping["benchmark_id"]
            and (
                b.config == benchmark_mapping.get("config")
                if benchmark_mapping.get("config") is not None
                else True
            )
        )
    ]
    if len(values) == 0:
        return ("no data available", None)
    value_raw = np.mean(values)
    if value_raw > reference_stats["p90"]:
        tier = "top tier (top 10%)"
    elif value_raw > reference_stats["p75"]:
        tier = "strong (top 25%)"
    elif value_raw > reference_stats["p25"]:
        tier = "average (middle 50%)"
    elif value_raw > reference_stats["p10"]:
        tier = "weak (bottom 25%)"
    else:
        tier = "poor (bottom 10%)"
    value_display = value_raw
    if benchmark_mapping.get("transform") is not None:
        value_display = benchmark_mapping["transform"](value_raw)
    value_str = str(round(value_display, 2))
    if benchmark_mapping.get("unit") is not None:
        value_str = f"{value_str} {benchmark_mapping['unit']}"
    return (tier, value_str)


def _get_price_for_server(server_id: str, prices: list) -> object | None:
    return next((p for p in prices if p.server_id == server_id), None)


def _server_spec_dict(server, price) -> dict:
    """Build the server spec dict (no benchmarks yet)."""
    return {
        "vendor_name": server.vendor.name,
        "server_name": server.name,
        "server_family": server.family,
        "basic_description": server.description,
        "hypervisor": server.hypervisor,
        "cpu_architecture": server.cpu_architecture,
        "cpu_vcpus": server.vcpus,
        "cpu_physical_cores": server.cpu_cores,
        "cpu_threads_per_core": server.vcpus / server.cpu_cores,
        "cpu_allocation": server.cpu_allocation,
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
        "gpu_vram_total": (
            str(round(server.gpu_memory_total / 1024)) + " GB"
            if server.gpu_memory_total
            else None
        ),
        "local_storage_size": (
            str(round(server.storage_size)) + " GB" if server.storage_size else "None"
        ),
        "local_storage_type": (
            server.storage_type.value if server.storage_type else None
        ),
        "network_bandwidth": (
            str(round(server.network_speed)) + " Gbps" if server.network_speed else None
        ),
        "complimentary_public_ipv4_addresses": server.ipv4,
        "min_ondemand_price_per_hour": (
            str(round(price.price, 4)) + " " + price.currency
            if price is not None
            else None
        ),
        "benchmarks": {},
    }


def build_server_payload(server, price) -> dict:
    """Full server dict for LLM input: specs + benchmark results, nulls dropped."""
    server_dict = _server_spec_dict(server, price)
    for benchmark_name in INTERESTING_BENCHMARKS:
        category, value = get_benchmark_stats_for_server(
            server.vendor_id, server.server_id, benchmark_name
        )
        server_dict["benchmarks"][benchmark_name] = {
            "value": value,
            "category": category,
        }
    return {k: v for k, v in server_dict.items() if v is not None}


def generate_summary(server_dict: dict) -> ServerSummary:
    """Call LLM to produce ServerSummary from server payload."""
    resp = config.client.create(
        response_model=ServerSummary,
        messages=[
            {"role": "system", "content": config.system_prompt},
            {
                "role": "user",
                "content": config.user_prompt + dumps(server_dict, indent=2),
            },
        ],
        generation_config={
            "temperature": 0.25,
            "top_p": 1.0,
        },
    )
    return resp
