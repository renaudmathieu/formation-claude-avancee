"""Score an extraction prompt version on the hand-written cases of `attendu.json`.

Usage: uv run python -m evals.run v2
Each run calls the real API once per receipt.
"""

import json
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from escale.extraction import extract_expenses

ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = Path(__file__).resolve().parent / "attendu.json"
RECEIPTS_DIR = ROOT / "data" / "justificatifs"


def load_cases(path: Path = CASES_FILE) -> list[dict]:
    """Load the cases and check that every receipt file exists."""
    cases = json.loads(path.read_text(encoding="utf-8"))["cas"]
    for case in cases:
        if not (RECEIPTS_DIR / f"{case['justificatif']}.md").is_file():
            raise ValueError(f"{case['justificatif']} : justificatif absent")
    return cases


def same_expense(got: dict, expected: dict) -> bool:
    """Compare two expenses: the vendor ignores case and spaces, the amount ignores cents noise."""
    return (
        got["date"] == expected["date"]
        and got["category"] == expected["category"]
        and abs(got["amount_eur"] - expected["amount_eur"]) < 0.01
        and got["vendor"].strip().casefold() == expected["vendor"].strip().casefold()
    )


def score_case(got: list[dict], expected: list[dict]) -> list[str]:
    """Return the differences between two lists of expenses, in any order. [] means a pass."""
    remaining = list(got)
    problems = []
    for wanted in expected:
        match = next((item for item in remaining if same_expense(item, wanted)), None)
        if match is None:
            problems.append(f"manquante : {wanted}")
        else:
            remaining.remove(match)
    # An invented expense is as wrong as a missing one: it ends up on someone's reimbursement.
    problems += [f"en trop : {item}" for item in remaining]
    return problems


def run(client, version: str, cases: list[dict] | None = None) -> dict[str, list[str]]:
    """Extract every receipt and return the problems found, by receipt name."""
    results = {}
    for case in cases if cases is not None else load_cases():
        text = (RECEIPTS_DIR / f"{case['justificatif']}.md").read_text(encoding="utf-8")
        try:
            got = extract_expenses(client, text, version)
        except ValueError as error:
            results[case["justificatif"]] = [f"erreur : {error}"]
            continue
        results[case["justificatif"]] = score_case(got, case["attendu"])
    return results


def report(results: dict[str, list[str]], version: str) -> str:
    """Format the pass rate and the failures."""
    passed = sum(1 for problems in results.values() if not problems)
    lines = [f"Prompt {version} : {passed}/{len(results)} réussis ({passed / len(results):.0%})"]
    for name, problems in results.items():
        if problems:
            lines.append(f"  ECHEC {name}")
            lines += [f"    {problem}" for problem in problems]
    return "\n".join(lines)


def main() -> None:
    load_dotenv()
    version = sys.argv[1] if len(sys.argv) > 1 else "v2"
    print(report(run(anthropic.Anthropic(), version), version))


if __name__ == "__main__":
    main()
