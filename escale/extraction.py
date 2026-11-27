"""Extract the expenses of a receipt, as structured data."""

import json
from pathlib import Path

from escale.llm import send, text_of, with_retry

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
CATEGORIES = ["hotel", "train", "taxi", "restaurant", "other"]

# Structured outputs need an object at the top level, so the list sits under "expenses".
SCHEMA = {
    "type": "object",
    "properties": {
        "expenses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "AAAA-MM-JJ"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "amount_eur": {"type": "number"},
                    "vendor": {"type": "string"},
                },
                "required": ["date", "category", "amount_eur", "vendor"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["expenses"],
    "additionalProperties": False,
}


def load_prompt(version: str) -> str:
    """Return the text of `prompts/extraction.<version>.md`."""
    path = PROMPTS_DIR / f"extraction.{version}.md"
    if not path.is_file():
        raise ValueError(f"Version de prompt inconnue : {version}")
    return path.read_text(encoding="utf-8")


def extract_expenses(client, text: str, version: str = "v2") -> list[dict]:
    """Return the expenses found in a receipt, or [] when there is no readable amount."""
    messages = [{"role": "user", "content": text}]
    response = with_retry(
        lambda: send(client, messages, system=load_prompt(version), schema=SCHEMA)
    )
    # A cut answer is not valid JSON: say so instead of failing in json.loads.
    if response.stop_reason in ("max_tokens", "refusal"):
        raise ValueError(f"Extraction impossible (stop_reason={response.stop_reason}).")
    expenses = json.loads(text_of(response))["expenses"]
    # The schema forces a number, so a missing amount may come back as 0: keep only real ones.
    return [expense for expense in expenses if expense["amount_eur"] > 0]
