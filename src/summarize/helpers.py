"""
Helper functions for building server payloads and calling the LLM.
"""

import logging
from functools import cache
from json import dumps

import numpy as np
from instructor.v2.core.errors import InstructorRetryException

from . import config, database
from .config import INTERESTING_BENCHMARKS, INTERESTING_CPU_FLAGS, MODEL_CONFIG
from .models import ServerSummary

logger = logging.getLogger(__name__)


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
        for b in database.benchmarks_by_id.get(benchmark_id, [])
        if conf is None or b.config == conf
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
    benchmark_id = benchmark_mapping["benchmark_id"]
    conf = benchmark_mapping.get("config")
    values = [
        b.score
        for b in database.benchmarks_by_server.get((vendor_id, server_id), [])
        if b.benchmark_id == benchmark_id and (conf is None or b.config == conf)
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
        "cpu_threads_per_core": (
            server.vcpus / server.cpu_cores if server.cpu_cores else None
        ),
        "cpu_allocation": server.cpu_allocation,
        "cpu_speed": str(server.cpu_speed) + " GHz" if server.cpu_speed else None,
        "cpu_manufacturer": server.cpu_manufacturer,
        "cpu_family": server.cpu_family,
        "cpu_model": server.cpu_model,
        "cpu_cache_size": {
            "l1d": (
                str(int(server.cpu_l1d_cache)) + " KB" if server.cpu_l1d_cache else None
            ),
            "l2": (
                (
                    str(int(server.cpu_l2_cache / 1024))
                    if server.cpu_l2_cache > 1024
                    else str(
                        round(
                            server.cpu_l2_cache / 1024,
                            2,
                        )
                    )
                )
                + " MB"
                if server.cpu_l2_cache
                else None
            ),
            "l3": (
                str(int(server.cpu_l3_cache / 1024)) + " MB"
                if server.cpu_l3_cache
                else None
            ),
        },
        "cpu_flags_extra_availability": _categorized_cpu_flags(server.cpu_flags),
        "memory_amount": (
            str(
                round(
                    server.memory_amount / 1024, 0 if server.memory_amount > 1024 else 1
                )
            )
            + " GB"
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
        # TODO rename internal GPU fields to accelerator as well when needed
        "gpu_count": server.accelerator_count,
        "gpu_manufacturer": server.accelerator_manufacturer,
        "gpu_family": server.accelerator_family,
        "gpu_model": server.accelerator_model,
        "gpu_vram_total": (
            str(round(server.accelerator_memory_total / 1024)) + " GB"
            if server.accelerator_memory_total
            else None
        ),
        "local_storage_size": (
            str(round(server.storage_size)) + " GB" if server.storage_size else "None"
        ),
        "local_storage_type": (
            server.storage_type.value if server.storage_type else None
        ),
        "network_bandwidth_baseline": (
            str(round(server.network_speed_baseline)) + " Gbps"
            if server.network_speed_baseline
            else None
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
    """Call LLM to produce ServerSummary from server payload.

    Retries are handled here instead of by instructor, because instructor's
    Gemini reask sends the validation error as a model turn, which the API
    rejects with "Requests ending with a model turn are not supported".

    TODO: drop this manual retry loop and go back to instructor's own
    `max_retries` once instructor 1.18 is released, which includes the fix
    for https://github.com/567-labs/instructor/issues/2631
    """
    messages = [
        {"role": "system", "content": config.system_prompt},
        {"role": "user", "content": config.user_prompt + dumps(server_dict, indent=2)},
    ]
    max_attempts = MODEL_CONFIG["max_retries"]
    for attempt in range(1, max_attempts + 1):
        try:
            return config.client.create(
                response_model=ServerSummary,
                messages=messages,
                generation_config={
                    "temperature": MODEL_CONFIG["temperature"],
                    "top_p": MODEL_CONFIG["top_p"],
                },
                max_retries=1,
            )
        except InstructorRetryException as e:
            error = e.failed_attempts[-1].exception if e.failed_attempts else e
            logger.warning(
                "LLM call failed (attempt %d of %d): %s", attempt, max_attempts, error
            )
            if attempt == max_attempts:
                raise
            if e.last_completion is not None and e.last_completion.text:
                messages.append({"role": "model", "content": e.last_completion.text})
                messages.append(
                    {
                        "role": "user",
                        "content": f"Your previous response failed validation:\n{error}\n"
                        "Fix these errors and respond again.",
                    }
                )
