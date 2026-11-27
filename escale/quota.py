"""A daily spending limit per user. The ledger is the trace file: nothing else to keep in sync."""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path


class QuotaExceededError(Exception):
    """The user has spent their share for today."""


def utc_today() -> date:
    return datetime.now(UTC).date()


class Quota:
    def __init__(self, trace_path: Path, max_usd: float, today: Callable[[], date] = utc_today):
        self.trace_path = trace_path
        self.max_usd = max_usd
        self.today = today

    def spent_today(self, user: str) -> float:
        """Add up the cost of today's calls of a user, as written by the tracer."""
        if not self.trace_path.is_file():
            return 0.0
        day = self.today().isoformat()
        total = 0.0
        for line in self.trace_path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # a torn line must not lock everybody out
            if record.get("user") == user and record.get("time", "").startswith(day):
                total += record.get("cost_usd") or 0.0
        return total

    def check(self, user: str) -> None:
        """Raise before a call if the user is over their limit."""
        spent = self.spent_today(user)
        if spent >= self.max_usd:
            raise QuotaExceededError(
                f"Quota journalier atteint pour {user} : {spent:.2f} $ dépensés sur "
                f"{self.max_usd:.2f} $. Il se renouvelle demain."
            )
