"""
Generate human-friendly, plain English summaries for all servers.
"""

import logging
from hashlib import sha256
from json import dumps, load
from os import makedirs
from pathlib import Path
from time import monotonic

import click

from src.summarize import database
from src.summarize.config import DATA_FOLDER, MODEL_CONFIG, system_prompt, user_prompt
from src.summarize.helpers import (
    _get_price_for_server,
    build_server_payload,
    generate_summary,
)

logger = logging.getLogger("src.summarize")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


@click.command()
@click.option(
    "-n",
    type=int,
    default=None,
    help="Limit the number of servers to process (default: all servers)",
)
@click.option(
    "--max-minutes",
    type=float,
    default=None,
    help=(
        "Maximum runtime budget in minutes. Exit cleanly before this is reached, "
        "leaving a safety buffer of 5%% of the budget or 15 minutes, whichever is "
        "larger (useful to avoid a hard CI cancellation, e.g. GitHub Actions' 6h limit)."
    ),
)
def main(n, max_minutes):
    start = monotonic()
    deadline = None
    if max_minutes is not None:
        max_seconds = max_minutes * 60
        buffer_seconds = max(0.05 * max_seconds, 15 * 60)
        deadline = start + max_seconds - buffer_seconds
        logger.debug(
            f"Runtime budget: {max_minutes} min, "
            f"buffer: {buffer_seconds / 60:.1f} min, "
            f"will stop after {(max_seconds - buffer_seconds) / 60:.1f} min"
        )

    logger.debug("Loading servers from database...")
    database.load(n)
    logger.debug(
        f"Loaded {len(database.servers)} servers, {len(database.benchmarks)} benchmarks, {len(database.prices)} prices"
    )

    total = len(database.servers)
    for i, server in enumerate(database.servers, start=1):
        if deadline is not None and monotonic() >= deadline:
            logger.info(
                f"Runtime budget of {max_minutes} min nearly reached after "
                f"{(monotonic() - start) / 60:.1f} min; "
                f"stopping early at server {i}/{total} (processed {i - 1})"
            )
            break

        server_folder = (
            Path(DATA_FOLDER) / server.vendor.vendor_id / server.api_reference
        )
        makedirs(server_folder, exist_ok=True)
        logger.debug(f"Processing server {i}/{total}: {server.name}")

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
            logger.debug(f"Skipping server: {server.name} (hashes match)")
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

        logger.debug(f"Generating summary via LLM for server: {server.name}")
        summary = generate_summary(server_dict)
        logger.info(f"Generated summary for server: {server.name}")
        with open(folder / "output.json", "w") as f:
            f.write(dumps(summary.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
