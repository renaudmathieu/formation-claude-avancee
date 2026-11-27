"""Check the expenses of an expense report against the ceilings of the travel policy."""

import re
from dataclasses import dataclass

from escale.extraction import extract_expenses
from escale.tools import policy

# Where to look in the policy for each category: one or more searches, best result of each.
# The ceilings are never written here: they are read in the policy pages, so that a change
# in the policy changes the verdict.
POLICY_QUERIES = {
    "hotel": ["plafond par nuit hébergement"],
    "restaurant": ["plafond déjeuner dîner", "repas d'affaires client"],
    "taxi": ["taxi VTC plafond course"],
}
AMOUNT = re.compile(r"(\d+(?:[.,]\d+)?)\s*€")

COMPLIANT = "conforme"
OVER = "au-dessus du plafond"
TO_CHECK = "à vérifier"
NO_CEILING = "sans plafond"


@dataclass(frozen=True)
class Finding:
    """The verdict on one expense, with the policy page that justifies it."""

    expense: dict
    verdict: str
    detail: str
    page: str | None = None


def ceilings_for(category: str) -> tuple[list[float], list[str]]:
    """Return the ceilings found in the policy for a category, and the pages they come from."""
    ceilings, pages = [], []
    for query in POLICY_QUERIES.get(category, []):
        results = policy.search(query, limit=1)
        if not results:
            continue
        amounts = AMOUNT.findall(results[0]["excerpt"])
        ceilings += [float(amount.replace(",", ".")) for amount in amounts]
        if results[0]["page"] not in pages:
            pages.append(results[0]["page"])
    return ceilings, pages


def check_expense(expense: dict) -> Finding:
    """Compare one expense with the ceilings of its category."""
    ceilings, pages = ceilings_for(expense["category"])
    if not ceilings:
        return Finding(expense, NO_CEILING, "aucun plafond trouvé dans la politique")
    page = " + ".join(pages)
    amount = expense["amount_eur"]
    if amount > max(ceilings):
        return Finding(expense, OVER, f"plafond le plus haut : {max(ceilings):g} €", page)
    if amount <= min(ceilings):
        return Finding(expense, COMPLIANT, f"plafond : {min(ceilings):g} €", page)
    # Between two ceilings (Paris or not, lunch or dinner...): the receipt does not say which
    # one applies. Say so instead of guessing.
    options = " ou ".join(f"{ceiling:g} €" for ceiling in sorted(set(ceilings)))
    return Finding(expense, TO_CHECK, f"information manquante, plafond possible : {options}", page)


def check_note(client, text: str, version: str = "v2") -> list[Finding]:
    """Extract the expenses of an expense report (section 3), then check each one."""
    return [check_expense(expense) for expense in extract_expenses(client, text, version)]


def format_finding(finding: Finding) -> str:
    """Write one verdict as a line for the terminal, citing the policy page."""
    expense = finding.expense
    line = (
        f"{finding.verdict.upper()} : {expense['date']} {expense['category']} "
        f"{expense['vendor']} {expense['amount_eur']:.2f} € ({finding.detail})"
    )
    return f"{line}, page {finding.page}" if finding.page else line
