"""Measure the search in the travel policy: recall@5 of three versions on the same questions.

Usage: uv run python -m evals.run_rag [--k 5] [--claude-context]
  1. keywords only (BM25)
  2. hybrid: BM25 + embeddings, merged by RRF
  3. hybrid + context: the same, each chunk indexed with a line that says where it comes from

Embeddings come from Voyage AI when VOYAGE_API_KEY is set. Otherwise an offline stand-in is used,
which only sees spelling: the numbers then show the method, not the real gain of a model.
`--k 1` is a harder test: on a corpus this small, recall@5 is easy. `--claude-context` writes the context with Claude (one call per chunk) instead of from the page.
"""

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

from escale import rag
from escale.config import DATA_DIR

QUESTIONS_FILE = Path(__file__).resolve().parent / "rag_questions.json"

# A search for the evaluation: (question, k) -> pages, best first.
Search = Callable[[str, int], list[str]]


def load_questions(path: Path = QUESTIONS_FILE, folder: Path = DATA_DIR) -> list[dict]:
    """Load the questions and refuse a file that would make the measure lie."""
    questions = json.loads(path.read_text(encoding="utf-8"))["questions"]
    known = {page.stem for page in folder.glob("*.md")}
    seen = set()
    for question in questions:
        if question["id"] in seen:
            raise ValueError(f"Identifiant en double : {question['id']}")
        seen.add(question["id"])
        # A typo in an expected page would count as a failure of the search, not of the file.
        if question["page"] is not None and question["page"] not in known:
            raise ValueError(f"{question['id']} : page attendue inconnue ({question['page']})")
    return questions


def recall_at_k(found: list[str], expected: str, k: int) -> float:
    """1.0 if the expected page is among the first k pages, else 0.0."""
    return 1.0 if expected in found[:k] else 0.0


def evaluate(search: Search, questions: list[dict], k: int = 5) -> dict:
    """Return the recall@k and the ids of the questions that failed.

    Out-of-corpus questions are left out: they test the answer (a refusal), not the search.
    """
    asked = [question for question in questions if question["page"] is not None]
    failures = [q["id"] for q in asked if not recall_at_k(search(q["question"], k), q["page"], k)]
    recall = (len(asked) - len(failures)) / len(asked) if asked else 0.0
    return {"n": len(asked), "recall": recall, "failures": failures}


def versions(
    folder: Path, embedder: rag.Embedder, context=rag.metadata_context
) -> dict[str, Search]:
    """Build the three searches. The questions are the same for all, so the numbers compare."""
    plain = rag.build_index(folder, embedder)
    enriched = rag.build_index(folder, embedder, context)
    return {
        "mots-clés (BM25)": lambda q, k: plain.pages(q, k, "keyword"),
        "hybride": lambda q, k: plain.pages(q, k, "hybrid"),
        "hybride + contexte": lambda q, k: enriched.pages(q, k, "hybrid"),
    }


def claude_context_for(folder: Path):
    """A context function that asks Claude, with the page as the cached prefix."""
    import anthropic

    client = anthropic.Anthropic()
    return lambda chunk: rag.claude_context(
        client, (folder / f"{chunk.page}.md").read_text(encoding="utf-8"), chunk
    )


def report(results: dict[str, dict], k: int = 5) -> str:
    lines = [f"Recall@{k} sur {next(iter(results.values()))['n']} questions"]
    for name, result in results.items():
        failed = ", ".join(result["failures"]) or "aucun"
        lines.append(f"  {name:<22} {result['recall']:.0%}   échecs : {failed}")
    return "\n".join(lines)


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    if os.environ.get("VOYAGE_API_KEY"):
        embedder = rag.voyage_embedder()
    else:
        print("VOYAGE_API_KEY absente : embeddings simulés hors ligne (orthographe seulement).")
        embedder = rag.hashing_embedder()
    context = (
        claude_context_for(DATA_DIR) if "--claude-context" in sys.argv else rag.metadata_context
    )
    k = int(sys.argv[sys.argv.index("--k") + 1]) if "--k" in sys.argv else 5
    questions = load_questions()
    results = {
        name: evaluate(search, questions, k)
        for name, search in versions(DATA_DIR, embedder, context).items()
    }
    print(report(results, k))


if __name__ == "__main__":
    main()
