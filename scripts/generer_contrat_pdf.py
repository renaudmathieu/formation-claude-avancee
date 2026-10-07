"""Régénère corpus/contrat_exemple.pdf à partir de corpus/contrat_alpha.md.

Le PDF sert aux exercices de la section 2 (pièces jointes) : c'est le même contrat
que le Markdown, pour comparer une lecture en texte et une lecture de PDF.

    uv run --with reportlab python scripts/generer_contrat_pdf.py
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / "corpus" / "contrat_alpha.md"
CIBLE = RACINE / "corpus" / "contrat_exemple.pdf"


def main() -> None:
    styles = getSampleStyleSheet()
    elements = []
    for ligne in SOURCE.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            elements.append(Spacer(1, 6))
        elif ligne.startswith("# "):
            elements.append(Paragraph(ligne[2:], styles["Title"]))
        elif ligne.startswith("## "):
            elements.append(Paragraph(ligne[3:], styles["Heading2"]))
        elif ligne.startswith("- "):
            elements.append(Paragraph("• " + ligne[2:], styles["BodyText"]))
        else:
            elements.append(Paragraph(ligne, styles["BodyText"]))
    document = SimpleDocTemplate(str(CIBLE), pagesize=A4, title="Contrat Alpha Logistique")
    document.build(elements)
    print(f"PDF écrit : {CIBLE}")


if __name__ == "__main__":
    main()
