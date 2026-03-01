"""
Generate human-friendly, plain English summaries for all servers.
"""

import logging
from hashlib import sha256
from json import dumps, load
from os import makedirs
from pathlib import Path

import click

from src.summarize import database
from src.summarize.config import DATA_FOLDER, MODEL_CONFIG, system_prompt, user_prompt
from src.summarize.helpers import (
    _get_price_for_server,
    build_server_payload,
    generate_summary,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


@click.command()
@click.option(
    "--n", type=int, default=None, help="Limit the number of servers to process"
)
def main(n):
    logger.info("Loading servers from database...")
    database.load(n)
    logger.info(
        f"Loaded {len(database.servers)} servers, {len(database.benchmarks)} benchmarks, {len(database.prices)} prices"
    )

    for server in database.servers:
        server_folder = (
            Path(DATA_FOLDER) / server.vendor.vendor_id / server.api_reference
        )
        makedirs(server_folder, exist_ok=True)
        logger.info(f"Processing server: {server.name}")

        folder = server_folder / "descriptions"
        makedirs(folder, exist_ok=True)

        price = _get_price_for_server(server.server_id, database.prices)
        server_dict = build_server_payload(server, price)

        hashes = {
            "input": sha256(dumps(server_dict, indent=2).encode()).hexdigest(),
            "model_config": sha256(dumps(MODEL_CONFIG, indent=2).encode()).hexdigest(),
            "system_prompt": sha256(system_prompt.encode()).hexdigest(),
            "user_prompt": sha256(user_prompt.encode()).hexdigest(),
        }
        hashes["combined"] = sha256(dumps(hashes, indent=2).encode()).hexdigest()

        try:
            with open(folder / "hashes.json", "r") as f:
                existing_hashes = load(f)
        except FileNotFoundError:
            existing_hashes = {}
        if existing_hashes.get("combined") == hashes.get("combined"):
            logger.info(f"Skipping server: {server.name} (hashes match)")
            continue

        with open(folder / "input.json", "w") as f:
            f.write(dumps(server_dict, indent=2))
        with open(folder / "model.json", "w") as f:
            f.write(dumps(MODEL_CONFIG, indent=2))
        with open(folder / "system_prompt.md", "w") as f:
            f.write(system_prompt)
        with open(folder / "user_prompt.md", "w") as f:
            f.write(user_prompt)
        with open(folder / "hashes.json", "w") as f:
            f.write(dumps(hashes, indent=2))

        summary = generate_summary(server_dict)
        with open(folder / "output.json", "w") as f:
            f.write(dumps(summary.model_dump(), indent=2))


if __name__ == "__main__":
    main()
