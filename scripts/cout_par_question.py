"""Print what each question cost, from the trace file.

Usage: uv run python -m scripts.cout_par_question [fichier.jsonl]
"""

import sys
from pathlib import Path

from escale.trace import TRACE_PATH, cost_per_question, read_records


def report(records: list[dict]) -> str:
    questions = cost_per_question(records)
    lines = [
        f"{'question':<10}{'appels':>7}{'entrée':>9}{'sortie':>8}{'cache':>8}{'coût $':>10}  prompt"
    ]
    for question_id, row in sorted(questions.items(), key=lambda item: -item[1]["cost_usd"]):
        lines.append(
            f"{question_id:<10}{row['calls']:>7}{row['input_tokens']:>9}{row['output_tokens']:>8}"
            f"{row['cache_read_tokens']:>8}{row['cost_usd']:>10.4f}  {row['prompt_version']}"
        )
    total = sum(row["cost_usd"] for row in questions.values())
    lines.append(f"{len(questions)} question(s), {len(records)} appel(s), total {total:.4f} $")
    return "\n".join(lines)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else TRACE_PATH
    if not path.is_file():
        raise SystemExit(f"Aucune trace dans {path} : lancer d'abord l'agent.")
    print(report(read_records(path)))


if __name__ == "__main__":
    main()
