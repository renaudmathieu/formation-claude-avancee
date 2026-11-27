"""Section 11: the documents of the final project and the course README are there and honest."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRANCHES = [
    "etape/00-depart",
    "etape/01-premier-appel",
    "etape/02-client",
    "etape/03-prompts",
    "etape/04-tools",
    "etape/05-claude-code",
    "etape/06-mcp",
    "etape/07-mod",
    "etape/08-agent",
    "etape/09-rag",
    "etape/10-prod",
    "etape/11-final",
]


def test_the_final_project_offers_three_variants():
    text = (ROOT / "docs" / "projet-final.md").read_text(encoding="utf-8")

    for variant in ("A. Assistant de support", "B. Analyseur de documents", "C. Assistant de code"):
        assert f"### {variant}" in text


def test_the_one_page_spec_has_its_five_parts():
    text = (ROOT / "docs" / "projet-final.md").read_text(encoding="utf-8")

    for part in ("Quoi", "Comment on saura", "Hors périmètre", "Le risque principal", "Le harnais"):
        assert f"## {part}\n" in text


def test_the_readme_lists_every_checkpoint_branch():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert [branch for branch in BRANCHES if f"`{branch}`" not in readme] == []


def test_the_readme_has_installation_commands_and_troubleshooting():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for title in ("## Installation", "## Commandes", "## Les checkpoints", "## En cas de panne"):
        assert title in readme


def test_no_em_dash_in_the_tracked_text_files():
    files = subprocess.run(
        ["git", "ls-files", "*.md", "*.py", "*.json", "*.sh", "*.tsx"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    # Built from its code point so that this file does not contain the character itself.
    dash = chr(0x2014)

    assert [name for name in files if dash in (ROOT / name).read_text(encoding="utf-8")] == []
