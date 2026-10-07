"""Source unique de verite pour tout ce qui est volatil.

Regle de la formation : aucun identifiant de modele ne doit apparaitre
ailleurs que dans ce fichier. Quand la gamme evolue, on change ici et
nulle part ailleurs.

Valeurs verifiees le 2026-09-01. Source : docs.claude.com, et la page Notion
« Registre de fraicheur », a relire avant chaque session.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Le modele de travail par defaut du fil rouge.
MODELE_DEFAUT = "claude-sonnet-5"

# Le modele leger, pour le tri, le routage et la classification.
MODELE_RAPIDE = "claude-haiku-4-5-20251001"

# Le modele lourd, a n'utiliser qu'apres avoir constate que le defaut echoue.
MODELE_PROFOND = "claude-opus-5"

# Plafond de sortie par defaut. Ce n'est pas un budget, c'est une limite.
MAX_TOKENS_DEFAUT = 1024

SYSTEME_DOC42 = (
    "Tu es Doc42, un assistant d'analyse de documents internes. "
    "Tu reponds uniquement a partir des documents qui te sont fournis. "
    "Quand l'information n'est pas dans les documents, tu le dis explicitement "
    "au lieu de la deviner."
)

# Tarifs en dollars par million de tokens (entree, sortie), registre du 2026-09-01.
TARIFS = {
    MODELE_DEFAUT: (3.0, 15.0),
    MODELE_RAPIDE: (1.0, 5.0),
    MODELE_PROFOND: (5.0, 25.0),
}
# Le cache se lit a 0,1 fois le tarif d'entree et s'ecrit a 1,25 fois (5 minutes).
FACTEUR_CACHE_LU = 0.1
FACTEUR_CACHE_ECRIT = 1.25

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_CORPUS = Path(os.environ.get("DOC42_CORPUS", RACINE / "corpus"))
DOSSIER_FICHES = Path(os.environ.get("DOC42_FICHES", RACINE / "fiches"))


def verifier() -> None:
    """Verifie que l'environnement est pret. A lancer avant chaque atelier."""
    cle = os.environ.get("ANTHROPIC_API_KEY", "")
    if not cle:
        raise RuntimeError(
            "ANTHROPIC_API_KEY absente. Copiez .env.example en .env et renseignez "
            "votre cle, ou lancez les tests sans --reel."
        )
    print(f"Environnement pret. Modele par defaut : {MODELE_DEFAUT}")
