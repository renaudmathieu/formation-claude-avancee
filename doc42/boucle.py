"""Boucle de tool use de reference de Doc42 (checkpoint etape/04-tools).

C'est le corrige de la section 4, range dans le paquet et rendu reutilisable :
la section 6 y branche les outils d'un serveur MCP (autre `outils`, autre
`executer`), la section 8 y ajoute une confirmation humaine avant creer_fiche
(un `executer` qui demande avant d'agir), la section 10 y ajoute la journalisation.

Usage :

    uv run python -m doc42.boucle "Quelles sont les echeances du contrat Alpha ?"
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from doc42.client import texte_de
from doc42.config import DOSSIER_CORPUS, DOSSIER_FICHES, MODELE_DEFAUT, SYSTEME_DOC42
from doc42.outils import DEFINITIONS, chercher_documents, creer_fiche

# Un executeur prend (nom de l'outil, entree) et renvoie (contenu, est_une_erreur).
# Il ne leve jamais : une erreur d'outil repart vers Claude dans un tool_result.
Executeur = Callable[[str, dict[str, Any]], tuple[str, bool]]

MESSAGE_BORNE = "Nombre maximum de tours atteint sans reponse finale."
TOURS_MAX_DEFAUT = 6
MAX_TOKENS_BOUCLE = 2048


@dataclass
class ResultatBoucle:
    """Ce que rend la boucle : le texte final et de quoi la poursuivre ou l'auditer."""

    texte: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    tours: int = 0
    borne_atteinte: bool = False


def _chaine_non_vide(entree: dict[str, Any], cle: str) -> str | None:
    valeur = entree.get(cle)
    if not isinstance(valeur, str) or not valeur.strip():
        return f"Parametre '{cle}' manquant ou invalide : une chaine non vide est attendue."
    return None


def executer_outil(
    nom: str,
    entree: dict[str, Any],
    dossier_corpus: str | Path = DOSSIER_CORPUS,
    dossier_fiches: str | Path = DOSSIER_FICHES,
) -> tuple[str, bool]:
    """Execute un outil de doc42.outils en validant l'entree. Ne leve jamais."""
    try:
        if nom == "chercher_documents":
            if erreur := _chaine_non_vide(entree, "requete"):
                return erreur, True
            limite = entree.get("limite", 5)
            # bool est un sous-type de int : True passerait pour 1.
            if isinstance(limite, bool) or not isinstance(limite, int) or not 1 <= limite <= 10:
                return "Parametre 'limite' invalide : un entier entre 1 et 10 est attendu.", True
            resultats = chercher_documents(entree["requete"], limite, dossier=dossier_corpus)
            if not resultats:
                # Une recherche vide est une reponse, pas une panne de l'outil.
                return "Aucun document ne correspond a cette requete.", False
            return "\n\n".join(
                f"[{r['id']}] {r['titre']}\n{r['extrait']}" for r in resultats
            ), False

        if nom == "creer_fiche":
            for cle in ("titre", "contenu"):
                if erreur := _chaine_non_vide(entree, cle):
                    return erreur, True
            chemin = creer_fiche(entree["titre"], entree["contenu"], dossier=dossier_fiches)
            return f"Fiche creee : {chemin}", False

        return f"Outil inconnu : {nom}. Outils disponibles : chercher_documents, creer_fiche.", True
    except Exception as erreur:  # noqa: BLE001
        # L'erreur repart vers Claude : il peut reformuler ou prevenir l'utilisateur.
        return f"Erreur pendant l'execution de {nom} : {erreur}", True


def resultats_outils(reponse: Any, executer: Executeur) -> list[dict[str, Any]]:
    """Un tool_result par bloc tool_use de la reponse, dans l'ordre (appels paralleles)."""
    resultats = []
    for bloc in reponse.content:
        if bloc.type != "tool_use":
            continue
        contenu, est_erreur = executer(bloc.name, bloc.input)
        resultats.append(
            {
                "type": "tool_result",
                "tool_use_id": bloc.id,
                "content": contenu,
                "is_error": est_erreur,
            }
        )
    return resultats


def boucle_outils(
    client: Any,
    messages: list[dict[str, Any]],
    *,
    outils: list[dict[str, Any]] | None = None,
    executer: Executeur | None = None,
    tours_max: int = TOURS_MAX_DEFAUT,
    systeme: str = SYSTEME_DOC42,
    modele: str = MODELE_DEFAUT,
    max_tokens: int = MAX_TOKENS_BOUCLE,
    tool_choice: dict[str, Any] | None = None,
) -> ResultatBoucle:
    """Boucle tool_use -> tool_result jusqu'a une reponse finale, au plus `tours_max` appels.

    `messages` n'est pas modifie : l'historique complet (reponses assistant et
    tool_result compris) est rendu dans ResultatBoucle.messages.
    """
    outils = DEFINITIONS if outils is None else outils
    executer = executer_outil if executer is None else executer
    historique = list(messages)
    options: dict[str, Any] = {} if tool_choice is None else {"tool_choice": tool_choice}

    for tour in range(1, tours_max + 1):
        reponse = client.messages.create(
            model=modele,
            max_tokens=max_tokens,
            system=systeme,
            tools=outils,
            messages=historique,
            **options,
        )
        if reponse.stop_reason != "tool_use":
            historique.append({"role": "assistant", "content": reponse.content})
            return ResultatBoucle(texte_de(reponse), historique, tour)

        # La reponse assistant entre telle quelle : les tool_result y renvoient par id.
        historique.append({"role": "assistant", "content": reponse.content})
        # Tous les resultats du tour dans un seul message user.
        historique.append({"role": "user", "content": resultats_outils(reponse, executer)})

    return ResultatBoucle(MESSAGE_BORNE, historique, tours_max, borne_atteinte=True)


def demander(client: Any, question: str, **options: Any) -> str:
    """Une question, la boucle d'outils, le texte final. Options : celles de boucle_outils."""
    return boucle_outils(client, [{"role": "user", "content": question}], **options).texte


def journaliser(executer: Executeur, journal: list[dict[str, Any]]) -> Executeur:
    """Enveloppe un executeur pour noter nom, entree, duree et is_error de chaque appel."""

    def executer_journalise(nom: str, entree: dict[str, Any]) -> tuple[str, bool]:
        debut = time.perf_counter()
        contenu, est_erreur = executer(nom, entree)
        journal.append(
            {
                "nom": nom,
                "entree": entree,
                "duree": time.perf_counter() - debut,
                "is_error": est_erreur,
            }
        )
        return contenu, est_erreur

    return executer_journalise


def main(arguments: list[str] | None = None) -> int:
    from doc42.client import creer_client

    analyseur = argparse.ArgumentParser(description="Pose une question a Doc42, outils compris.")
    analyseur.add_argument("question")
    analyseur.add_argument("--tours-max", type=int, default=TOURS_MAX_DEFAUT)
    args = analyseur.parse_args(arguments)

    journal: list[dict[str, Any]] = []
    resultat = boucle_outils(
        creer_client(),
        [{"role": "user", "content": args.question}],
        executer=journaliser(executer_outil, journal),
        tours_max=args.tours_max,
    )
    for entree in journal:
        statut = "ERREUR" if entree["is_error"] else "ok"
        print(
            f"[outil] {entree['nom']} {entree['entree']} {entree['duree'] * 1000:.0f} ms {statut}",
            file=sys.stderr,
        )
    print(resultat.texte)
    return 1 if resultat.borne_atteinte else 0


if __name__ == "__main__":
    raise SystemExit(main())
