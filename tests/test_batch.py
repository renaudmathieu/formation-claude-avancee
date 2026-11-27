"""The back-office batch, without any agent run."""

from pathlib import Path

from escale import batch
from escale.config import ROOT


def test_receipts_are_listed_in_a_stable_order():
    found = batch.receipts(ROOT / "data" / "justificatifs")

    assert found[0].name == "01-hotel-lyon.md"
    assert found == sorted(found)


def test_each_receipt_gets_its_own_output_file():
    task = batch.task_for(Path("data/justificatifs/03-taxi-nuit.md"))

    assert "data/justificatifs/03-taxi-nuit.md" in task
    assert "sortie/verdicts/03-taxi-nuit.md" in task
    assert "absente" in task


def test_summary_counts_failures_and_adds_up_the_cost():
    outcomes = [
        batch.Outcome("01-hotel-lyon.md", True, 4, 0.03, "success"),
        batch.Outcome("09-taxi-illisible.md", False, 6, 0.2, "error_max_budget_usd"),
    ]

    text = batch.summary(outcomes)

    assert "error_max_budget_usd" in text
    assert text.splitlines()[-1] == "2 justificatifs, 1 en échec, coût total 0.2300 $"
