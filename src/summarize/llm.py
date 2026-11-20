"""
Gemini API calls: building requests, sync generation, and the Batch API.

Requests are written in the REST `GenerateContentRequest` format, so the same
request can be sent directly (sync) or as a line of a batch JSONL file.
"""

import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from google import genai
from google.genai.types import JobState

from .config import MODEL_CONFIG, system_prompt, user_prompt
from .models import ServerSummary

logger = logging.getLogger(__name__)

# prefix of our batch jobs' display name, used to find them later
BATCH_PREFIX = "sc-navigator-descriptions"

BATCH_DONE_OK = {JobState.JOB_STATE_SUCCEEDED, JobState.JOB_STATE_PARTIALLY_SUCCEEDED}
BATCH_DONE_FAILED = {
    JobState.JOB_STATE_FAILED,
    JobState.JOB_STATE_CANCELLED,
    JobState.JOB_STATE_EXPIRED,
}
BATCH_DONE = BATCH_DONE_OK | BATCH_DONE_FAILED

_client = None


def client() -> genai.Client:
    """Gemini client, created on first use (reads GEMINI_API_KEY)."""
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


def build_request(server_dict: dict) -> dict:
    """GenerateContentRequest for a server payload, in REST JSON format."""
    return {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt + json.dumps(server_dict, indent=2)}],
            }
        ],
        "generationConfig": {
            "temperature": MODEL_CONFIG["temperature"],
            "topP": MODEL_CONFIG["top_p"],
            "responseMimeType": "application/json",
            "responseJsonSchema": ServerSummary.model_json_schema(),
        },
    }


def _response_text(response: dict) -> str:
    """Answer text from a GenerateContentResponse in REST JSON format."""
    parts = response["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def generate_sync(request: dict) -> str:
    """Send a single request directly and return the raw answer text."""
    config = {"system_instruction": request["systemInstruction"]["parts"][0]["text"]}
    generation_config = request["generationConfig"]
    config.update(
        temperature=generation_config["temperature"],
        top_p=generation_config["topP"],
        response_mime_type=generation_config["responseMimeType"],
        response_json_schema=generation_config["responseJsonSchema"],
    )
    response = client().models.generate_content(
        model=MODEL_CONFIG["model"],
        contents=request["contents"][0]["parts"][0]["text"],
        config=config,
    )
    return response.text


def list_batches() -> list:
    """Our batch jobs, in any state."""
    return [
        job
        for job in client().batches.list()
        if (job.display_name or "").startswith(BATCH_PREFIX)
    ]


def submit_batch(requests: dict[str, dict]):
    """Upload the requests (keyed by an id) as JSONL and start a batch job."""
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "requests.jsonl"
        with open(path, "w") as f:
            f.writelines(
                json.dumps({"key": key, "request": request}) + "\n"
                for key, request in requests.items()
            )
        uploaded = client().files.upload(
            file=path, config={"display_name": BATCH_PREFIX, "mime_type": "jsonl"}
        )
    job = client().batches.create(
        model=MODEL_CONFIG["model"],
        src=uploaded.name,
        config={"display_name": BATCH_PREFIX},
    )
    return job


def batch_results(job) -> dict[str, str | None]:
    """Answer text of each request in a finished batch job, keyed by its id.

    Requests that failed on the API side are returned with a None value.
    """
    content = client().files.download(file=job.dest.file_name)
    results = {}
    usage = {"promptTokenCount": 0, "candidatesTokenCount": 0, "thoughtsTokenCount": 0}
    for line in content.decode().splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        for field in usage:
            usage[field] += (
                item.get("response", {}).get("usageMetadata", {}).get(field, 0)
            )
        try:
            results[item["key"]] = _response_text(item["response"])
        except (KeyError, IndexError):
            logger.warning(f"No answer for {item.get('key')}: {item.get('error')}")
            results[item.get("key")] = None
    logger.info(
        f"Token usage of batch job {job.name}: "
        f"{usage['promptTokenCount']} input, "
        f"{usage['candidatesTokenCount']} output, "
        f"{usage['thoughtsTokenCount']} thinking"
    )
    return results


def delete_batch(job) -> None:
    client().batches.delete(name=job.name)
