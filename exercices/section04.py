"""Section 4, atelier. Tool use : six exercices et un bonus, une heure et quart.

Completez les elements marques TODO, puis lancez :

    uv run pytest tests/test_section04.py -v

Les deux outils de Doc42 existent deja dans doc42/outils.py :
chercher_documents(requete, limite, dossier) et creer_fiche(titre, contenu, dossier).
Vous n'avez pas a les reecrire. Ce que vous ecrivez ici, c'est tout ce qui
les entoure : la description que Claude lit, l'execution protegee, et la
boucle tool_use -> tool_result -> reponse finale.

Les enonces sont dans les docstrings. Vous n'avez pas besoin de revenir
sur Notion pendant l'atelier.
"""

from __future__ import annotations

import time  # noqa: F401  (vous en aurez besoin pour le bonus)
from collections.abc import Callable
from pathlib import Path
from typing import Any

from doc42.config import (  # noqa: F401
    DOSSIER_CORPUS,
    DOSSIER_FICHES,
    MODELE_DEFAUT,
    SYSTEME_DOC42,
)
from doc42.outils import chercher_documents, creer_fiche  # noqa: F401

# Un executeur prend (nom de l'outil, entree) et renvoie (contenu, est_une_erreur).
Executeur = Callable[[str, dict[str, Any]], tuple[str, bool]]

# Le message renvoye quand la boucle s'arrete sans reponse finale. Donne, ne pas modifier.
MESSAGE_BORNE = "Nombre maximum de tours atteint sans reponse finale."

# La description cassee de l'etape 3. Donnee, ne pas modifier.
DESCRIPTION_MEDIOCRE = "Recherche des documents."


# Exercice 1
# TODO : ecrivez les definitions des deux outils, chercher_documents et creer_fiche.
#
# Une definition, c'est {"name", "description", "input_schema"}. La description
# est le vrai code : c'est la seule chose que Claude lit pour decider s'il appelle
# l'outil. Elle doit dire trois choses :
#   - ce que fait l'outil ;
#   - QUAND l'utiliser (sans le « quand », Claude repond de memoire) ;
#   - ce qu'il renvoie.
#
# Attendu :
#   - chercher_documents : parametre "requete" (string, obligatoire) et "limite"
#     (integer, facultatif, borne par minimum 1 et maximum 10 dans le schema)
#   - creer_fiche : parametres "titre" et "contenu" (string, tous deux obligatoires) ;
#     la description dit que l'outil ECRIT un fichier et qu'on ne l'utilise que sur
#     demande explicite de l'utilisateur
#   - chaque parametre a sa propre description, avec un exemple si possible
#   - les noms correspondent exactement aux fonctions de doc42/outils.py
#
# Ecrivez-les vous-meme avant de regarder doc42.outils.DEFINITIONS, puis comparez.
OUTILS: list[dict[str, Any]] = []


def avec_description(
    outils: list[dict[str, Any]], nom: str, description: str
) -> list[dict[str, Any]]:
    """Exercice 2. Retourne une COPIE de `outils` ou l'outil `nom` a une autre description.

    Sert a l'experience centrale de la section (etape 3) : casser la description
    de chercher_documents, reposer la meme question, observer.

    Attendu :
      - la liste retournee contient les memes outils, dans le meme ordre
      - seul l'outil `nom` change, et seulement sa description
      - `outils` n'est PAS modifie, ni la liste ni les dictionnaires qu'elle contient
        (sinon votre experience casse aussi la definition de reference pour la suite)
      - un nom inconnu leve KeyError : une experience qui ne change rien en silence
        vous ferait conclure a tort que la description ne compte pas
    """
    # TODO
    raise NotImplementedError


def executer_outil(
    nom: str,
    entree: dict[str, Any],
    dossier_corpus: str | Path = DOSSIER_CORPUS,
    dossier_fiches: str | Path = DOSSIER_FICHES,
) -> tuple[str, bool]:
    """Exercice 3. Execute un outil et retourne (contenu, est_une_erreur). Ne leve jamais.

    Un input_schema guide le modele, il ne valide rien pour vous : `entree` vient
    de Claude, traitez-la comme une saisie utilisateur.

    Attendu :
      - chercher_documents : appelle doc42.outils.chercher_documents avec
        dossier=dossier_corpus ; chaque resultat est rendu sous la forme
        "[id] titre" puis l'extrait ; aucun resultat donne
        ("Aucun document ne correspond a cette requete.", False) : une recherche
        vide est une reponse, pas une erreur
      - creer_fiche : appelle doc42.outils.creer_fiche avec dossier=dossier_fiches
        et retourne un texte qui contient le chemin de la fiche creee
      - entree invalide => (message, True), et le message nomme le parametre fautif :
          * "requete" absente, vide ou qui n'est pas une chaine
          * "limite" presente mais pas un entier, ou hors de 1 a 10
          * "titre" ou "contenu" absent, vide ou qui n'est pas une chaine
      - outil inconnu => (message qui contient le nom demande, True)
      - toute exception pendant l'execution => (message qui nomme l'outil, True).
        L'erreur repart vers Claude, qui peut reformuler ou prevenir l'utilisateur ;
        elle ne fait pas planter la boucle.
    """
    # TODO
    raise NotImplementedError


def resultats_outils(reponse: Any, executer: Executeur) -> list[dict[str, Any]]:
    """Exercice 4. Les blocs tool_result qui repondent a TOUS les tool_use de `reponse`.

    Claude peut demander plusieurs outils dans une meme reponse (appels paralleles).
    Chaque bloc tool_use doit recevoir son tool_result, sinon l'appel suivant est
    refuse par l'API.

    Attendu :
      - un bloc {"type": "tool_result", "tool_use_id", "content", "is_error"}
        par bloc tool_use, dans le meme ordre
      - tool_use_id reprend l'id du bloc tool_use correspondant
      - les blocs qui ne sont pas des tool_use (texte, raisonnement) sont ignores
      - `executer(nom, entree)` est appele une fois par bloc tool_use
    """
    # TODO
    raise NotImplementedError


def demander(
    client: Any,
    question: str,
    outils: list[dict[str, Any]] | None = None,
    executer: Executeur | None = None,
    tours_max: int = 6,
    tool_choice: dict[str, Any] | None = None,
) -> str:
    """Exercice 5. La boucle de tool use complete. Retourne le texte de la reponse finale.

    `outils` vaut OUTILS par defaut, `executer` vaut executer_outil par defaut.

    Attendu :
      - chaque appel envoie model=MODELE_DEFAUT, system=SYSTEME_DOC42, tools=outils
        et l'historique complet des messages
      - tool_choice n'est transmis a l'API que s'il est fourni (pas de cle a None)
      - tant que stop_reason vaut "tool_use" :
          * la reponse assistant est ajoutee a l'historique TELLE QUELLE (tous ses blocs,
            y compris les tool_use : les tool_result y font reference par leur id)
          * TOUS les tool_result du tour partent dans UN SEUL message user
      - sinon, on retourne la concatenation des blocs texte. Jamais le texte du seul
        premier bloc (indice 0) : il peut etre un bloc de raisonnement ou un tool_use
      - au plus `tours_max` appels a l'API ; au-dela, on retourne MESSAGE_BORNE.
        Sans borne, c'est votre budget qui sert de borne.
    """
    # TODO
    raise NotImplementedError


def journaliser(executer: Executeur, journal: list[dict[str, Any]]) -> Executeur:
    """Exercice 6, bonus. Enveloppe `executer` pour journaliser chaque appel d'outil.

    Vous en aurez besoin en section 10 (observabilite).

    Attendu :
      - retourne un executeur de meme signature, qui rend exactement ce que rend `executer`
      - chaque appel ajoute a `journal` un dict {"nom", "entree", "duree", "is_error"},
        duree en secondes (float), mesuree avec time.perf_counter
    """
    # TODO
    raise NotImplementedError


# Etape 2 de l'atelier, sans test (necessite la vraie API)
#
#   from doc42.client import creer_client
#   print(demander(creer_client(), "Quelles sont les echeances du contrat Alpha ?"))
#
# Ce que Claude a cherche (requete passee a l'outil) :
#
# Ce qu'il a repondu :
#
#
# Etape 3 de l'atelier, sans test : casser la description (l'experience centrale)
#
#   cassee = avec_description(OUTILS, "chercher_documents", DESCRIPTION_MEDIOCRE)
#   print(demander(creer_client(), "Quelles sont les echeances du contrat Alpha ?", outils=cassee))
#
# Reposez la question plusieurs fois avec chaque version. Comptez les appels a
# chercher_documents (le bonus journaliser() vous y aide).
#
# Avec la description complete, Claude a appele l'outil ... fois sur ... essais.
# Avec la description mediocre, ... fois sur ... essais.
# Ce que Claude a repondu quand il n'a pas appele l'outil :
#
#
# Etape 4 de l'atelier, sans test : deux outils enchaines
#
#   demander(client, "Fais-moi une fiche sur les echeances du contrat Alpha.")
#
# Ordre des appels observe (chercher puis creer ?) :
# Ce que contient la fiche ecrite dans fiches/ :
#
#
# Etape 5 de l'atelier, sans test : un document qui n'existe pas
#
#   demander(client, "Que dit le contrat Omega sur les penalites ?")
#
# Attention : la recherche est lexicale, "contrat" suffit a ramener des documents.
# Claude recoit donc des contrats qui ne sont pas Omega. Dit-il que le contrat
# Omega n'existe pas, ou invente-t-il ? Les erreurs franches (outil inconnu,
# entree invalide) sont couvertes par les tests de l'exercice 3.
#
# Ce que j'ai observe :
#
#
# Etape 6 de l'atelier, sans test : tours_max=1 sur la question de l'etape 4
#
# Message obtenu :
# Pourquoi cette borne doit exister avant d'en avoir besoin en production :
#
#
# Etape 7 de l'atelier, sans test : tool_choice
#
#   demander(client, "Bonjour, qui es-tu ?", tool_choice={"type": "any"})
#   demander(client, "Quelles sont les echeances du contrat Alpha ?", tool_choice={"type": "none"})
#
# Avec "any" sur une question qui n'en a pas besoin :
# Avec "none" sur une question qui en a besoin :
#
#
# Avant de commiter etape/04-tools : verifiez qu'aucun acces au premier bloc par
# indice ne subsiste dans le code. Les seules occurrences admises sont celles des
# commentaires et des docstrings qui mettent en garde contre ce piege.
#
#   grep -rn --include=*.py 'content\[0\]\.text' doc42/ exercices/
#
# Et une question pour la section 8 : creer_fiche ECRIT un fichier. Qui devrait
# confirmer avant qu'elle s'execute ?
