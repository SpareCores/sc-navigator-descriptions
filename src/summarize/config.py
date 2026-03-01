"""
Constants, prompts, and LLM client for server summary generation.
"""

import os
from pathlib import Path

from instructor import from_provider

DATA_FOLDER = os.environ.get("DATA_FOLDER", default="data")
os.makedirs(DATA_FOLDER, exist_ok=True)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
system_prompt = (_PROMPTS_DIR / "system.md").read_text()
user_prompt = (_PROMPTS_DIR / "user.md").read_text()

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
    "stress-ng single-core CPU performance": {"benchmark_id": "stress_ng:best1"},
    "stress-ng multi-core CPU performance": {"benchmark_id": "stress_ng:bestn"},
    "memory bandwidth read-only small block (16kb - cached)": {
        "benchmark_id": "bw_mem",
        "config": {"operation": "rd", "size": 0.016384},
        "unit": "GB/sec",
        "transform": lambda x: x / 1024,
    },
    "memory bandwidth read-only large block (256mb - potentially uncached)": {
        "benchmark_id": "bw_mem",
        "config": {"operation": "rd", "size": 256.0},
        "unit": "GB/sec",
        "transform": lambda x: x / 1024,
    },
    "memory bandwidth write large block (256mb - potentially uncached)": {
        "benchmark_id": "bw_mem",
        "config": {"operation": "wr", "size": 256.0},
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
    "geekbench single-core score": {
        "benchmark_id": "geekbench:score",
        "config": {"cores": "Single-Core Performance"},
    },
    "geekbench multi-core score": {
        "benchmark_id": "geekbench:score",
        "config": {"cores": "Multi-Core Performance"},
    },
    "geekbench compiling software with clang": {
        "benchmark_id": "geekbench:clang",
        "config": {"cores": "Multi-Core Performance"},
    },
    "geekbench ray tracing": {
        "benchmark_id": "geekbench:ray_tracer",
        "config": {"cores": "Multi-Core Performance"},
    },
    "geekbench image processing": {
        "benchmark_id": "geekbench:object_remover",
        "config": {"cores": "Multi-Core Performance"},
    },
    "geekbench text processing": {
        "benchmark_id": "geekbench:text_processing",
        "config": {"cores": "Multi-Core Performance"},
    },
    "passmark cpu score": {"benchmark_id": "passmark:cpu_mark"},
    "passmark memory score": {"benchmark_id": "passmark:memory_mark"},
    "passmark database operations": {"benchmark_id": "passmark:database_operations"},
    "redis SET operations": {
        "benchmark_id": "redis:rps-extrapolated",
        "config": {"operation": "SET", "pipeline": 512.0},
        "unit": "million operations/sec",
        "transform": lambda x: x / 1_000_000,
    },
    "static web serving throughput": {
        "benchmark_id": "static_web:throughput",
        "config": {"connections_per_vcpus": 8.0, "size": "256k"},
        "unit": "GB/sec",
        "transform": lambda x: x / 1024 / 1024 / 1024,
    },
    "llm inference speed for prompt processing using 135M model": {
        "benchmark_id": "llm_speed:prompt_processing",
        "config": {"model": "SmolLM-135M.Q4_K_M.gguf", "tokens": 128},
        "unit": "tokens/sec",
    },
    "llm inference speed for text generation using 135M model": {
        "benchmark_id": "llm_speed:text_generation",
        "config": {"model": "SmolLM-135M.Q4_K_M.gguf", "tokens": 128},
        "unit": "tokens/sec",
    },
    "llm inference speed for prompt processing using 70B model": {
        "benchmark_id": "llm_speed:prompt_processing",
        "config": {"model": "Llama-3.3-70B-Instruct-Q4_K_M.gguf", "tokens": 128},
        "unit": "tokens/sec",
    },
    "llm inference speed for text generation using 70B model": {
        "benchmark_id": "llm_speed:text_generation",
        "config": {"model": "Llama-3.3-70B-Instruct-Q4_K_M.gguf", "tokens": 128},
        "unit": "tokens/sec",
    },
}
