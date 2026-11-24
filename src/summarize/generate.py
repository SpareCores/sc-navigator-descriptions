"""
Generate human-friendly, plain English summaries for all servers.

By default, the Gemini Batch API is used, which takes hours to complete, so
each run does the following:

1. Check our batch jobs, and stop if any is still in progress.
2. Collect the results of the finished batch jobs, and save the valid ones.
   A job is deleted only when collecting it saves nothing new, i.e. after its
   results were committed by an earlier run, so a failed commit is recovered.
3. Submit a new batch job with all servers still having a missing or outdated
   description (including the ones that failed validation).

Run it periodically (e.g. hourly) until all descriptions are up to date.
Use `--sync` to call the API directly instead (e.g. for testing).
"""

import logging
from hashlib import sha256
from json import dumps, load
from os import makedirs
from pathlib import Path

import click
from pydantic import ValidationError

from src.summarize import database, llm
from src.summarize.config import DATA_FOLDER, MODEL_CONFIG, system_prompt, user_prompt
from src.summarize.helpers import build_server_payload, get_price_for_server
from src.summarize.models import ServerSummary

logger = logging.getLogger("src.summarize")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def _hashes(server_dict: dict) -> dict:
    hashes = {
        "input": sha256(dumps(server_dict, indent=2).encode()).hexdigest(),
        "model_config": sha256(dumps(MODEL_CONFIG, indent=2).encode()).hexdigest(),
        "system_prompt": sha256(system_prompt.encode()).hexdigest(),
        "user_prompt": sha256(user_prompt.encode()).hexdigest(),
    }
    hashes["combined"] = sha256(dumps(hashes, indent=2).encode()).hexdigest()
    return hashes


# relative price change below which we keep using the previously described price
PRICE_TOLERANCE = 0.25


def _stable_price(new: str | None, old: str | None) -> str | None:
    """Price to describe the server with, ignoring noise in the pricing data.

    Prices of some vendors (e.g. Alibaba Cloud) keep disappearing and
    reappearing as availability changes, or jump a bit as the cheapest region
    changes. The LLM only discusses cost qualitatively, so these changes are
    not worth a new description: keep the old price unless the new one is
    meaningfully different.
    """
    if old is None:
        return new
    if new is None:
        return old
    new_value, new_currency = new.split()
    old_value, old_currency = old.split()
    if new_currency != old_currency:
        return new
    if abs(float(new_value) - float(old_value)) <= PRICE_TOLERANCE * float(old_value):
        return old
    return new


def _load_json(path: Path) -> dict:
    try:
        with open(path) as f:
            return load(f)
    except FileNotFoundError:
        return {}


def find_outdated_servers() -> dict[str, dict]:
    """Servers without an up-to-date description.

    Keyed by `vendor/server/combined_hash`, so batch results can be matched
    to the exact inputs they were generated from.
    """
    outdated = {}
    for server in database.servers:
        folder = (
            Path(DATA_FOLDER)
            / server.vendor.vendor_id
            / server.api_reference
            / "descriptions"
        )
        price = _stable_price(
            get_price_for_server(server.server_id, database.prices),
            _load_json(folder / "input.json").get("min_ondemand_price_per_hour"),
        )
        server_dict = build_server_payload(server, price)
        hashes = _hashes(server_dict)
        existing_hashes = _load_json(folder / "hashes.json")
        if existing_hashes.get("combined") == hashes["combined"]:
            continue
        key = f"{server.vendor.vendor_id}/{server.api_reference}/{hashes['combined']}"
        outdated[key] = {"folder": folder, "input": server_dict, "hashes": hashes}
    return outdated


def save(server: dict, text: str | None) -> bool:
    """Validate the LLM answer and save it with all its inputs."""
    if text is None:
        return False
    try:
        summary = ServerSummary.model_validate_json(text)
    except ValidationError as e:
        logger.warning(f"Invalid answer for {server['folder']}, retrying later: {e}")
        return False
    folder = server["folder"]
    makedirs(folder, exist_ok=True)
    files = {
        "input.json": dumps(server["input"], indent=2),
        "model.json": dumps(MODEL_CONFIG, indent=2),
        "system_prompt.md": system_prompt,
        "user_prompt.md": user_prompt,
        "output.json": dumps(summary.model_dump(mode="json"), indent=2),
        # written last, so a failed save is retried on the next run
        "hashes.json": dumps(server["hashes"], indent=2),
    }
    for name, content in files.items():
        with open(folder / name, "w") as f:
            f.write(content)
    return True


@click.command()
@click.option(
    "-n",
    type=int,
    default=None,
    help="Limit the number of servers to process (default: all servers)",
)
@click.option(
    "--status",
    is_flag=True,
    help="Only show our batch jobs, without loading the database or changing anything.",
)
@click.option(
    "--sync",
    is_flag=True,
    help="Call the API directly for each server instead of using the Batch API.",
)
def main(n, status, sync):
    if not sync:
        logger.debug("Looking up batch jobs...")
        jobs = llm.list_batches()
        logger.info(f"Found {len(jobs)} batch job(s)")
        for job in jobs:
            logger.info(
                f"Batch job {job.name}: {job.state}, created at {job.create_time}, "
                f"updated at {job.update_time}: {llm.batch_progress(job)}"
            )
        if status:
            return
        if any(job.state not in llm.BATCH_DONE for job in jobs):
            logger.info("Nothing to do while a batch job is in progress")
            return

    logger.debug("Loading servers from database...")
    database.load(n)
    outdated = find_outdated_servers()
    logger.info(
        f"Found {len(outdated):,} outdated description(s) "
        f"out of {len(database.servers):,} server(s)"
    )

    if sync:
        saved = 0
        for i, (key, server) in enumerate(outdated.items(), start=1):
            logger.debug(f"Generating summary {i:,}/{len(outdated):,}: {key}")
            saved += save(server, llm.generate_sync(llm.build_request(server["input"])))
        logger.info(f"Saved {saved:,} description(s)")
        return

    retried = set()
    for job in jobs:
        if job.state in llm.BATCH_DONE_OK:
            results = llm.batch_results(job)
            saved = 0
            # results for servers that changed since submitting the job are
            # skipped, and failed ones stay outdated to be submitted again below
            for key, text in results.items():
                if key not in outdated:
                    continue
                if save(outdated[key], text):
                    del outdated[key]
                    saved += 1
                else:
                    retried.add(key)
            logger.info(
                f"Saved {saved:,} description(s) from {len(results):,} result(s) "
                f"of batch job {job.name}"
            )
            if saved:
                logger.info(f"Keeping batch job {job.name} until a later run")
                continue
        else:
            logger.warning(f"Batch job {job.name} ended with {job.state}: {job.error}")
        llm.delete_batch(job)

    # a retried key might have been saved meanwhile from another batch job
    retried &= outdated.keys()
    if outdated:
        job = llm.submit_batch(
            {
                key: llm.build_request(server["input"])
                for key, server in outdated.items()
            }
        )
        logger.info(
            f"Submitted batch job {job.name} with {len(outdated):,} request(s): "
            f"{len(retried):,} retried, {len(outdated) - len(retried):,} new"
        )


if __name__ == "__main__":
    main()
