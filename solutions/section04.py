"""Section 4, corrige commente.

Les commentaires expliquent le pourquoi, pas le comment : le comment est
dans le code.
"""

from __future__ import annotations

import copy
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from doc42.config import DOSSIER_CORPUS, DOSSIER_FICHES, MODELE_DEFAUT, SYSTEME_DOC42
from doc42.outils import chercher_documents, creer_fiche

Executeur = Callable[[str, dict[str, Any]], tuple[str, bool]]

MESSAGE_BORNE = "Nombre maximum de tours atteint sans reponse finale."

DESCRIPTION_MEDIOCRE = "Recherche des documents."

# Chaque description repond a trois questions : que fait l'outil, QUAND l'utiliser,
# que renvoie-t-il. Le « quand » est ce qui fait la difference entre un outil
# appele et un outil ignore au profit d'une reponse de memoire.
OUTILS: list[dict[str, Any]] = [
    {
        "name": "chercher_documents",
        "description": (
            "Recherche par mots-cles dans le corpus de documents internes d'Hexalis "
            "(contrats, avenants, factures, proces-verbaux, notes, procedures). "
            "Utilise cet outil des que la question porte sur le contenu d'un document "
            "interne (dates, montants, parties, decisions, regles), AVANT de repondre : "
            "ne reponds jamais de memoire sur ces sujets. Renvoie les documents les plus "
            "pertinents, chacun avec son identifiant, son titre et un extrait."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "requete": {
                    "type": "string",
                    "description": "Mots-cles en francais, par exemple 'echeances contrat Alpha'.",
                },
                "limite": {
                    "type": "integer",
                    "description": "Nombre maximal de documents a renvoyer, entre 1 et 10 (5 par defaut).",
                    # Les bornes dans le schema guident le modele ; executer_outil
                    # les verifie quand meme, le schema ne valide rien.
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
            "Cree une fiche de synthese au format Markdown dans le dossier des fiches. "
            "Cette action ecrit un fichier : ne l'utilise que si l'utilisateur demande "
            "explicitement une fiche, et seulement apres avoir cherche les informations "
            "avec chercher_documents. Renvoie le chemin du fichier cree."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titre": {
                    "type": "string",
                    "description": "Titre court de la fiche, par exemple 'Echeances contrat Alpha'.",
                },
                "contenu": {
                    "type": "string",
                    "description": "Corps de la fiche en Markdown : les points cles, avec leurs sources.",
                },
            },
            "required": ["titre", "contenu"],
        },
    },
]


def avec_description(
    outils: list[dict[str, Any]], nom: str, description: str
) -> list[dict[str, Any]]:
    # Copie profonde : une copie de la liste seule partagerait les dictionnaires,
    # et l'experience abimerait OUTILS pour tout le reste de la session.
    copie = copy.deepcopy(outils)
    for definition in copie:
        if definition["name"] == nom:
            definition["description"] = description
            return copie
    raise KeyError(f"Outil inconnu : {nom}")


def _chaine_non_vide(entree: dict[str, Any], cle: str) -> str | None:
    """Le message d'erreur si entree[cle] n'est pas une chaine non vide, sinon None."""
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
    try:
        if nom == "chercher_documents":
            if erreur := _chaine_non_vide(entree, "requete"):
                return erreur, True
            limite = entree.get("limite", 5)
            # bool est un sous-type de int en Python : True passerait pour 1.
            if isinstance(limite, bool) or not isinstance(limite, int) or not 1 <= limite <= 10:
                return "Parametre 'limite' invalide : un entier entre 1 et 10 est attendu.", True
            resultats = chercher_documents(entree["requete"], limite, dossier=dossier_corpus)
            if not resultats:
                # Une recherche vide est une reponse valide, pas une panne : Claude doit
                # pouvoir dire « rien trouve » sans croire que l'outil est casse.
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

        # Le nom de l'outil vient du modele : il peut en inventer un.
        return f"Outil inconnu : {nom}. Outils disponibles : chercher_documents, creer_fiche.", True
    except Exception as erreur:  # noqa: BLE001
        # On renvoie l'erreur a Claude plutot que de faire planter la boucle :
        # il peut reformuler sa requete ou prevenir l'utilisateur.
        return f"Erreur pendant l'execution de {nom} : {erreur}", True


def resultats_outils(reponse: Any, executer: Executeur) -> list[dict[str, Any]]:
    resultats = []
    # Tous les blocs tool_use, pas seulement le premier : un tool_use sans
    # tool_result fait refuser l'appel suivant.
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


def _texte_de(reponse: Any) -> str:
    # Jamais content[0].text : avec des outils, le premier bloc peut etre un
    # tool_use ou un bloc de raisonnement.
    return "".join(bloc.text for bloc in reponse.content if bloc.type == "text")


def demander(
    client: Any,
    question: str,
    outils: list[dict[str, Any]] | None = None,
    executer: Executeur | None = None,
    tours_max: int = 6,
    tool_choice: dict[str, Any] | None = None,
) -> str:
    outils = OUTILS if outils is None else outils
    executer = executer_outil if executer is None else executer
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

    options: dict[str, Any] = {}
    if tool_choice is not None:
        # Le SDK n'accepte pas tool_choice=None : on omet la cle.
        options["tool_choice"] = tool_choice

    for _ in range(tours_max):
        reponse = client.messages.create(
            model=MODELE_DEFAUT,
            max_tokens=2048,
            system=SYSTEME_DOC42,
            tools=outils,
            messages=messages,
            **options,
        )

        if reponse.stop_reason != "tool_use":
            return _texte_de(reponse)

        # La reponse assistant entre telle quelle dans l'historique : les
        # tool_result du message suivant renvoient a ses blocs par leur id.
        messages.append({"role": "assistant", "content": reponse.content})
        # Un seul message user pour tous les resultats du tour : deux messages
        # user consecutifs casseraient l'alternance des roles.
        messages.append({"role": "user", "content": resultats_outils(reponse, executer)})

    # Sans cette borne, une boucle d'outils peut tourner indefiniment, surtout
    # si un outil renvoie toujours une erreur, et consommer le budget sans conclure.
    return MESSAGE_BORNE


def journaliser(executer: Executeur, journal: list[dict[str, Any]]) -> Executeur:
    def executer_journalise(nom: str, entree: dict[str, Any]) -> tuple[str, bool]:
        # perf_counter et non time.time : c'est une horloge monotone, faite
        # pour mesurer des durees, insensible aux recalages de l'heure systeme.
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
