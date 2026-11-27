"""Observability: every API call becomes one JSON line, so that cost and failures can be read.

`TracedClient` wraps the real client. Everything else (llm.py, the agent) uses it like the real
one, which is why it is the only place that has to know about logging, quotas and secrets.

A line holds numbers and names, never the prompt or the answer: personal data and secrets have no
reason to be in a log. Error messages are masked, because an API error can quote a key.
"""

import json
import os
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from escale.config import ROOT, cost_usd, current_user
from escale.quota import Quota

TRACE_PATH = ROOT / ".escale" / "trace.jsonl"
SECRET_VARIABLES = ("ANTHROPIC_API_KEY", "VOYAGE_API_KEY")
KEY_SHAPE = re.compile(r"\b(?:sk-ant|pa)-[A-Za-z0-9_\-]{6,}")
MAX_ERROR_CHARS = 200


def mask_secrets(text: str) -> str:
    """Hide anything that looks like a key, and the exact keys of the environment."""
    for name in SECRET_VARIABLES:
        value = os.environ.get(name)
        if value:
            text = text.replace(value, "[clé masquée]")
    return KEY_SHAPE.sub("[clé masquée]", text)


class TracedClient:
    """Same `client.beta.messages.create` and `.stream` as the SDK client, plus a log line."""

    def __init__(
        self,
        client,
        *,
        path: Path = TRACE_PATH,
        user: str | None = None,
        prompt_version: str = "none",
        quota: Quota | None = None,
        clock=time.monotonic,
    ):
        self.client = client
        self.path = path
        self.user = user or current_user()
        self.prompt_version = prompt_version
        self.quota = quota
        self.clock = clock
        self.question_id = self.new_question()
        self.beta = SimpleNamespace(
            messages=SimpleNamespace(create=self._create, stream=self._stream)
        )

    def new_question(self) -> str:
        """Start a new question: the calls that follow are added up together."""
        self.question_id = uuid.uuid4().hex[:8]
        return self.question_id

    def check_quota(self) -> None:
        if self.quota:
            self.quota.check(self.user)

    def _create(self, **request):
        self.check_quota()
        started = self.clock()
        try:
            response = self.client.beta.messages.create(**request)
        except Exception as error:
            self.log(request, None, started, error)
            raise
        self.log(request, response, started)
        return response

    def _stream(self, **request):
        return TracedStream(self, request)

    def log(self, request: dict, response, started: float, error: Exception | None = None) -> None:
        """Write one line. A log that cannot be written never stops the agent."""
        record = {
            "time": datetime.now(UTC).isoformat(timespec="seconds"),
            "user": self.user,
            "question_id": self.question_id,
            "prompt_version": self.prompt_version,
            "model": getattr(response, "model", None) or request.get("model"),
            "status": "error" if error else "ok",
            "duration_ms": round((self.clock() - started) * 1000),
        }
        if error:
            record["error"] = f"{type(error).__name__}: {mask_secrets(str(error))}"[
                :MAX_ERROR_CHARS
            ]
        if response is not None:
            usage = response.usage
            record.update(
                stop_reason=response.stop_reason,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                cost_usd=price_or_none(record["model"], usage),
            )
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as write_error:
            print(f"[trace] Écriture impossible : {write_error}")


def price_or_none(model: str, usage) -> float | None:
    """A model without a price is logged without a cost, not with a wrong one."""
    try:
        return round(cost_usd(model, usage), 6)
    except ValueError:
        return None


class TracedStream:
    """Context manager around `client.beta.messages.stream(...)`: logs when the stream ends."""

    def __init__(self, tracer: TracedClient, request: dict):
        self.tracer = tracer
        self.request = request

    def __enter__(self):
        self.tracer.check_quota()
        self.started = self.tracer.clock()
        self.inner = self.tracer.client.beta.messages.stream(**self.request)
        self.stream = self.inner.__enter__()
        return self.stream

    def __exit__(self, *exc_info):
        final, error = None, exc_info[1]
        if error is None:
            try:
                final = self.stream.get_final_message()
            except Exception as final_error:  # noqa: BLE001
                error = final_error
        self.tracer.log(self.request, final, self.started, error)
        return self.inner.__exit__(*exc_info)


# --- reading the log -------------------------------------------------------------------------


def read_records(path: Path = TRACE_PATH) -> list[dict]:
    """Read the log, ignoring a line that is not valid JSON."""
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def cost_per_question(records: list[dict]) -> dict[str, dict]:
    """Group the calls by question: how many calls, how many tokens, how much money."""
    questions: dict[str, dict] = {}
    for record in records:
        row = questions.setdefault(
            record.get("question_id", "?"),
            {
                "calls": 0,
                "errors": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cost_usd": 0.0,
                "user": record.get("user"),
                "prompt_version": record.get("prompt_version"),
            },
        )
        row["calls"] += 1
        row["errors"] += record.get("status") == "error"
        for key in ("input_tokens", "output_tokens", "cache_read_tokens"):
            row[key] += record.get(key) or 0
        row["cost_usd"] += record.get("cost_usd") or 0.0
    return questions
