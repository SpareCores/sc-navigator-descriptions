"""
Generate human-friendly, plain English summaries for all servers.
"""

import logging
import os
from json import dumps

import click
from sc_crawler.tables import Server, Vendor
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
    engine = create_engine(f"sqlite:///{db.path}")
    query = select(Server)
    if n is not None:
        query = query.limit(n)

    query = query.join(Vendor).options(contains_eager(Server.vendor))

    with Session(engine) as session:
        servers = session.exec(query).all()

    for server in servers:
        print(server.name)
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
        }
        # TODO drop null values
        print(server_dict)
        print(dumps(server_dict, indent=2))


if __name__ == "__main__":
    main()
