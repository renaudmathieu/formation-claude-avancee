"""Single source of truth for everything that changes over time: models and prices.

Rule of the course: a model id or a price never appears outside this file.
Values checked on 2026-11-26.
"""

import os
from pathlib import Path

MODEL_FAST = "claude-haiku-5-5"
MODEL_DEFAULT = "claude-sonnet-5-5"
MODEL_SMART = "claude-opus-5-5"
MODEL_TOP = "claude-fable-5-2"

# Output ceiling of one call. It is a limit, not a budget.
MAX_TOKENS = 16000

# USD per million tokens: (input, output).
PRICES = {
    MODEL_FAST: (0.10, 0.50),
    MODEL_DEFAULT: (2.0, 10.0),
    MODEL_SMART: (4.0, 20.0),
    MODEL_TOP: (8.0, 40.0),
}
# Reading the prompt cache costs 0.1x the input price, writing it costs 1.25x.
CACHE_READ_FACTOR = 0.1
CACHE_WRITE_FACTOR = 1.25

# Agent guards. Both can be changed per run (arguments) or per machine (environment).
EFFORTS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_EFFORT = "high"
DEFAULT_BUDGET_USD = 0.50

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "politique-voyage"


def default_model() -> str:
    """Return the working model: `ESCALE_MODEL` if set, else MODEL_DEFAULT."""
    return os.environ.get("ESCALE_MODEL") or MODEL_DEFAULT


def agent_effort() -> str:
    """Return the effort of the agent: `ESCALE_EFFORT` if set, else DEFAULT_EFFORT."""
    effort = os.environ.get("ESCALE_EFFORT") or DEFAULT_EFFORT
    if effort not in EFFORTS:
        raise ValueError(f"Effort inconnu : {effort}. Valeurs possibles : {', '.join(EFFORTS)}.")
    return effort


def agent_budget() -> float:
    """Return the budget of one agent run in USD: `ESCALE_BUDGET_USD` if set, else the default."""
    raw = os.environ.get("ESCALE_BUDGET_USD")
    return float(raw) if raw else DEFAULT_BUDGET_USD


def cost_usd(model: str, usage) -> float:
    """Return the cost in USD of one call, from its `usage` object."""
    if model not in PRICES:
        # A silent 0 would make the wrong model look free.
        raise ValueError(f"Pas de tarif pour {model} : l'ajouter dans escale/config.py.")
    price_in, price_out = PRICES[model]
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    total = (
        usage.input_tokens * price_in
        + usage.output_tokens * price_out
        + cache_read * price_in * CACHE_READ_FACTOR
        + cache_write * price_in * CACHE_WRITE_FACTOR
    )
    return total / 1_000_000


def verifier() -> None:
    """Check the environment before a session, then print the default model."""
    problems = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        problems.append("ANTHROPIC_API_KEY manquante : la renseigner dans .env.")
    if not DATA_DIR.is_dir():
        problems.append(f"Dossier de données absent : {DATA_DIR}")
    if problems:
        raise RuntimeError("\n".join(problems))
    print(f"Environnement prêt. Modèle par défaut : {default_model()}")
