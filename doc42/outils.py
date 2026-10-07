"""Les deux outils de Doc42 : chercher dans le corpus, creer une fiche.

Implementation de reference, donnee des le depart. La section 4 apprend a les
decrire et a les brancher dans une boucle de tool use ; la section 6 les expose
en serveur MCP ; la section 8 les confie a un agent.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from doc42.config import DOSSIER_CORPUS, DOSSIER_FICHES
from doc42.corpus import charger_corpus

# Les descriptions sont le vrai code : c'est ce que le modele lit pour decider.
DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "chercher_documents",
        "description": (
            "Recherche dans le corpus de documents internes d'Hexalis (contrats, avenants, "
            "factures, proces-verbaux, notes, procedures). A utiliser des qu'une question porte "
            "sur le contenu d'un document : dates, montants, parties, decisions, regles. "
            "Renvoie les documents les plus pertinents avec un extrait."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "requete": {
                    "type": "string",
                    "description": "Les mots-cles a chercher, en francais, par exemple 'echeances contrat Alpha'.",
                },
                "limite": {
                    "type": "integer",
                    "description": "Nombre maximal de documents a renvoyer, entre 1 et 10.",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["requete"],
        },
    },
    {
        "name": "creer_fiche",
        "description": (
            "Cree une fiche de synthese (fichier Markdown) dans le dossier des fiches. "
            "N'utiliser que si l'utilisateur demande explicitement une fiche. "
            "Cette action ecrit un fichier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titre": {"type": "string", "description": "Titre court de la fiche."},
                "contenu": {"type": "string", "description": "Contenu de la fiche, en Markdown."},
            },
            "required": ["titre", "contenu"],
        },
    },
]


def normaliser(texte: str) -> str:
    """Minuscules sans accents, pour comparer des mots."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accents.lower()


def mots(texte: str) -> list[str]:
    """Les mots d'au moins trois lettres d'un texte, normalises."""
    return [m for m in re.findall(r"[a-z0-9/]+", normaliser(texte)) if len(m) >= 3]


def chercher_documents(
    requete: str, limite: int = 5, dossier: str | Path = DOSSIER_CORPUS
) -> list[dict[str, str]]:
    """Recherche lexicale simple : score = nombre d'occurrences des mots de la requete.

    Returns:
        Une liste de {"id", "titre", "extrait"}, du plus pertinent au moins pertinent.
        Les documents sans aucun mot commun ne sont pas renvoyes.
    """
    limite = max(1, min(int(limite), 10))
    termes = set(mots(requete))
    resultats = []
    for document in charger_corpus(dossier):
        contenu = mots(document.texte) + mots(document.titre) * 3
        score = sum(contenu.count(terme) for terme in termes)
        if score:
            resultats.append((score, document))
    resultats.sort(key=lambda paire: (-paire[0], paire[1].id))
    return [
        {"id": d.id, "titre": d.titre, "extrait": extrait(d.texte, termes)}
        for _, d in resultats[:limite]
    ]


def extrait(texte: str, termes: set[str], largeur: int = 700) -> str:
    """Les passages du texte autour des deux lignes les plus pertinentes.

    Une ligne vaut la somme de ses termes, chacun pondere par sa rarete dans le
    document : « echeances », present sur deux lignes, pese plus que « contrat »,
    present partout. On garde la meilleure ligne, puis la meilleure hors de son
    voisinage, car le titre porte souvent les noms propres (« contrat Alpha ») et
    une autre ligne le sujet de la question (« echeances »). Les passages sont
    rendus dans l'ordre du document, separes par « [...] ».
    """
    lignes = [ligne for ligne in texte.splitlines() if ligne.strip()]
    mots_par_ligne = [set(mots(ligne)) for ligne in lignes]
    frequence = {t: sum(t in m for m in mots_par_ligne) for t in termes}
    scores = [
        sum(1 / frequence[t] for t in termes & m) if termes & m else 0.0 for m in mots_par_ligne
    ]

    def fenetre(i: int) -> tuple[int, int]:
        return max(0, i - 1), min(len(lignes), i + 5)

    retenues: list[tuple[int, int]] = []
    for i in sorted(range(len(lignes)), key=lambda i: (-scores[i], i)):
        if not scores[i] or len(retenues) == 2:
            break
        if all(not (a <= i < b) for a, b in retenues):
            retenues.append(fenetre(i))
    if not retenues:
        return " ".join(lignes[:3])[:largeur]
    retenues.sort()
    return " [...] ".join(" ".join(lignes[a:b]) for a, b in retenues)[:largeur]


def creer_fiche(titre: str, contenu: str, dossier: str | Path = DOSSIER_FICHES) -> str:
    """Ecrit fiches/<titre-normalise>.md et renvoie son chemin."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    nom = re.sub(r"[^a-z0-9]+", "-", normaliser(titre)).strip("-") or "fiche"
    chemin = dossier / f"{nom}.md"
    horodatage = datetime.now(UTC).isoformat(timespec="seconds")
    chemin.write_text(
        f"# {titre}\n\n_Cree par Doc42 le {horodatage}_\n\n{contenu}\n", encoding="utf-8"
    )
    return str(chemin)


def executer(nom: str, entree: dict[str, Any]) -> str:
    """Execute un outil par son nom et renvoie un texte pour un bloc tool_result.

    Raises:
        KeyError: Si l'outil est inconnu.
    """
    if nom == "chercher_documents":
        resultats = chercher_documents(entree["requete"], entree.get("limite", 5))
        if not resultats:
            return "Aucun document ne correspond."
        return "\n\n".join(f"[{r['id']}] {r['titre']}\n{r['extrait']}" for r in resultats)
    if nom == "creer_fiche":
        return f"Fiche creee : {creer_fiche(entree['titre'], entree['contenu'])}"
    raise KeyError(f"Outil inconnu : {nom}")
