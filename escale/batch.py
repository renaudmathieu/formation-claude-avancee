"""Back-office batch: check a folder of receipts with the SDK agent, no human in the loop.

Each receipt gets its own headless run, with the guards of `escale/agent_sdk.py`: no shell,
no web, writing only inside sortie/, and no booking (nobody is there to confirm one).
A run that fails or goes over budget does not stop the others. The summary ends with the
total cost, so the batch can be priced before it is scheduled every night.

Run: `uv run --extra sdk python -m escale.batch data/justificatifs`.
"""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from escale.agent_sdk import build_options

BUDGET_PER_RECEIPT_USD = 0.20


@dataclass(frozen=True)
class Outcome:
    receipt: str
    ok: bool
    turns: int
    cost_usd: float
    detail: str


def receipts(folder: Path) -> list[Path]:
    """The receipts of a folder, in a stable order."""
    return sorted(folder.glob("*.md"))


def task_for(receipt: Path) -> str:
    """The instruction given to the agent for one receipt."""
    return (
        f"Lis le justificatif {receipt.as_posix()} et vérifie-le avec la politique de voyage "
        "(search_travel_policy). Écris ton verdict dans "
        f"sortie/verdicts/{receipt.stem}.md : conforme, hors politique ou illisible, avec la "
        "page de la politique appliquée. Une information absente est déclarée absente."
    )


def summary(outcomes: list[Outcome]) -> str:
    """One line per receipt, then the totals."""
    lines = [
        f"{'ok ' if o.ok else 'ERR'} {o.receipt:<28} {o.turns:>2} tours {o.cost_usd:.4f} $  {o.detail}"
        for o in outcomes
    ]
    total = sum(o.cost_usd for o in outcomes)
    failed = sum(not o.ok for o in outcomes)
    lines.append(f"{len(outcomes)} justificatifs, {failed} en échec, coût total {total:.4f} $")
    return "\n".join(lines)


async def check_one(receipt: Path) -> Outcome:
    from claude_agent_sdk import ResultMessage, query

    options = build_options(budget_usd=BUDGET_PER_RECEIPT_USD)
    try:
        async for message in query(prompt=task_for(receipt), options=options):
            if isinstance(message, ResultMessage):
                return Outcome(
                    receipt.name,
                    not message.is_error,
                    message.num_turns,
                    message.total_cost_usd or 0.0,
                    message.subtype,
                )
    except Exception as error:  # noqa: BLE001
        # One broken run must not stop the batch.
        return Outcome(receipt.name, False, 0, 0.0, f"erreur : {error}")
    return Outcome(receipt.name, False, 0, 0.0, "aucun résultat")


async def run(folder: Path) -> list[Outcome]:
    # One receipt after the other: simpler to read, and it stays under the rate limits.
    return [await check_one(receipt) for receipt in receipts(folder)]


def main() -> int:
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        print("Usage : uv run --extra sdk python -m escale.batch <dossier>")
        return 2
    load_dotenv()
    outcomes = asyncio.run(run(Path(sys.argv[1])))
    print(summary(outcomes))
    return 0 if all(o.ok for o in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
