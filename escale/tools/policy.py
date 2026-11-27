"""Search in the travel policy pages (Markdown files, one section per `##` title).

`search` counts shared words: simple, predictable, used by `check`. `lookup` is the search of the
agent and of the MCP server: keywords and meaning together (see `escale/rag.py`).
"""

import json
import os
import re
import unicodedata
from pathlib import Path

from escale import rag
from escale.config import DATA_DIR
from escale.toolbox import Tool

# Words too common to say anything about a question.
STOP_WORDS = {"dans", "pour", "avec", "quel", "quelle", "quels", "sont", "est", "les", "des"}
MAX_LIMIT = 10


def policy_dir() -> Path:
    """Return the folder of policy pages: `ESCALE_POLITIQUE` if set, else the course data."""
    return Path(os.environ.get("ESCALE_POLITIQUE") or DATA_DIR)


def pages() -> list[Path]:
    """List the policy pages, in a stable order."""
    return sorted(policy_dir().glob("*.md"))


def words(text: str) -> set[str]:
    """Lowercase words without accents, so that "hôtel" matches "hotel"."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return {word for word in re.findall(r"[a-z0-9]+", plain) if len(word) >= 3} - STOP_WORDS


def sections(page: Path) -> list[str]:
    """Cut a page into its `##` sections. The page title and intro stay with the first one."""
    parts = re.split(r"(?m)^(?=## )", page.read_text(encoding="utf-8"))
    return [part.strip() for part in parts if part.strip()]


def search(query: str, limit: int = 5) -> list[dict]:
    """Return the sections that share the most words with the query, best first.

    Each result is {"page": name of the page, "excerpt": text of the section}.
    """
    wanted = words(query)
    scored = []
    for page in pages():
        for section in sections(page):
            score = len(wanted & words(section))
            if score:
                scored.append((score, {"page": page.stem, "excerpt": section}))
    # sorted() is stable: equal scores keep the order of the pages.
    scored.sort(key=lambda pair: -pair[0])
    return [result for _, result in scored[: max(1, min(limit, MAX_LIMIT))]]


def lookup(query: str, limit: int = 5, embedder=None) -> list[dict]:
    """Hybrid search (BM25 + embeddings, RRF). Without a Voyage key it is BM25 alone.

    Each result is {"page", "section", "excerpt"}. `limit` is bounded like in `search`.
    """
    return rag.search_policy(query, max(1, min(limit, MAX_LIMIT)), policy_dir(), embedder)


def run_policy_tool(tool_input: dict) -> str:
    """Execute a `search_travel_policy` call and return its result as JSON text."""
    results = lookup(tool_input["query"])
    if not results:
        # An empty search is an answer, not a failure: Claude must say "nothing found".
        return "Aucun passage de la politique ne correspond à cette recherche."
    return json.dumps(results, ensure_ascii=False)


POLICY_TOOL = {
    "name": "search_travel_policy",
    "description": (
        "Cherche dans la politique de voyage de l'entreprise : plafonds d'hôtel et "
        "de repas, classe de train, avion, taxi, voiture, étranger, séminaires, sécurité, notes de "
        "frais. Cette politique est propre à "
        "l'entreprise : utilise cet outil avant de citer une règle ou un montant, et cite la "
        "page utilisée. Renvoie les passages les plus pertinents, chacun avec le nom de sa page "
        "et un extrait."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Question ou mots-clés en français, par exemple : plafond hôtel Paris.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}


def policy_tool() -> Tool:
    """Build the policy search tool."""
    return Tool(definition=POLICY_TOOL, handler=run_policy_tool)
