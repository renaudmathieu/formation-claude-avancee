"""Lecture du corpus de documents internes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from doc42.config import DOSSIER_CORPUS


@dataclass(frozen=True)
class Document:
    """Un document du corpus : son identifiant est son nom de fichier sans extension."""

    id: str
    titre: str
    texte: str
    chemin: Path


def charger_corpus(dossier: str | Path = DOSSIER_CORPUS) -> list[Document]:
    """Charge les documents Markdown d'un dossier, tries par identifiant.

    Le titre est la premiere ligne commencant par « # ». Les PDF sont ignores :
    ils se lisent par l'API (section 2), pas par ce chargeur.
    """
    documents = []
    for chemin in sorted(Path(dossier).glob("*.md")):
        texte = chemin.read_text(encoding="utf-8")
        titre = next(
            (ligne[2:].strip() for ligne in texte.splitlines() if ligne.startswith("# ")),
            chemin.stem,
        )
        documents.append(Document(id=chemin.stem, titre=titre, texte=texte, chemin=chemin))
    return documents


def trouver(document_id: str, dossier: str | Path = DOSSIER_CORPUS) -> Document | None:
    """Renvoie le document d'identifiant donne, ou None."""
    return next((d for d in charger_corpus(dossier) if d.id == document_id), None)
