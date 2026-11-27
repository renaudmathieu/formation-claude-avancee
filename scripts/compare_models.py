"""Run the same two tasks on three models and print tokens, duration and cost.

Usage: uv run python -m scripts.compare_models
Each run calls the real API: it costs a few cents.
"""

import time
from dataclasses import dataclass

import anthropic
from dotenv import load_dotenv

from escale.config import DATA_DIR, MODEL_DEFAULT, MODEL_FAST, MODEL_SMART, cost_usd
from escale.llm import send, text_of

MODELS = (MODEL_FAST, MODEL_DEFAULT, MODEL_SMART)

SUMMARY_TASK = "Résume cette page de la politique de voyage en trois puces.\n\n{page}"
CLASSIFICATION_TASK = (
    "Ce message est-il une demande de remboursement ? Réponds par oui ou non.\n\n"
    "Message : Bonjour, je voudrais être remboursé de mon taxi de mardi soir, "
    "le justificatif est en pièce jointe."
)


@dataclass
class Measure:
    """One row of the comparison table."""

    task: str
    model: str
    input_tokens: int
    output_tokens: int
    seconds: float
    cost: float
    answer: str


def measure(client, task_name, prompt, model, clock=time.perf_counter) -> Measure:
    """Send `prompt` to `model` and record tokens, duration and cost."""
    start = clock()
    response = send(client, [{"role": "user", "content": prompt}], model=model)
    seconds = clock() - start
    return Measure(
        task=task_name,
        model=model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        seconds=seconds,
        cost=cost_usd(model, response.usage),
        answer=text_of(response),
    )


def compare(client, clock=time.perf_counter) -> list[Measure]:
    """Run both tasks on every model."""
    page = (DATA_DIR / "hebergement.md").read_text(encoding="utf-8")
    tasks = {
        "résumé": SUMMARY_TASK.format(page=page),
        "classification": CLASSIFICATION_TASK,
    }
    return [
        measure(client, name, prompt, model, clock)
        for name, prompt in tasks.items()
        for model in MODELS
    ]


def format_table(rows: list[Measure]) -> str:
    """Return the measures as an aligned text table."""
    header = (
        f"{'tâche':<15}{'modèle':<20}{'entrée':>8}{'sortie':>8}{'durée (s)':>11}{'coût ($)':>11}"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        lines.append(
            f"{row.task:<15}{row.model:<20}{row.input_tokens:>8}{row.output_tokens:>8}"
            f"{row.seconds:>11.2f}{row.cost:>11.5f}"
        )
    return "\n".join(lines)


def main() -> None:
    load_dotenv()
    rows = compare(anthropic.Anthropic())
    print(format_table(rows))
    for row in rows:
        print(f"\n[{row.task} / {row.model}]\n{row.answer}")


if __name__ == "__main__":
    main()
