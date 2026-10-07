"""Section 6, atelier. Doc42 devient un serveur MCP, une heure trente.

Completez les fonctions marquees TODO, puis lancez :

    uv run pytest tests/test_section06.py -v

Le SDK Python officiel `mcp` est en version 2.x : FastMCP s'y appelle
MCPServer (from mcp.server.mcpserver import MCPServer). Si un exemple trouve
en ligne importe mcp.server.fastmcp, c'est du code 1.x.

Les tests parlent a votre serveur par un vrai client MCP du SDK, connecte en
memoire : aucun processus lance, aucun reseau. Les etapes qui se jouent dans
Claude Code (3, 4, 5, 6, 7) sont decrites en fin de fichier.

Les enonces sont dans les docstrings. Vous n'avez pas besoin de revenir
sur Notion pendant l'atelier.
"""

from __future__ import annotations

import json  # noqa: F401  (pour la ressource de l'etape 2)
import logging
from pathlib import Path
from typing import Annotated, Any  # noqa: F401  (pour valider les arguments)

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations  # noqa: F401
from pydantic import Field  # noqa: F401

from doc42 import outils  # noqa: F401
from doc42.config import DOSSIER_CORPUS, DOSSIER_FICHES
from doc42.corpus import charger_corpus  # noqa: F401

# Le nom du serveur fait partie du nom des outils cote Claude Code
# (mcp__doc42__creer_fiche). Ne le changez pas : la section 7 en depend.
NOM_SERVEUR = "doc42"

URI_DOCUMENTS = "doc42://documents"

# En stdio, stdout est le canal du protocole. Journalisez avec ce logger
# (il ecrit sur stderr), jamais avec print().
journal = logging.getLogger("doc42.mcp")


def ajouter_recherche(serveur: MCPServer, corpus: str | Path = DOSSIER_CORPUS) -> None:
    """Etape 1 : enregistre l'outil `chercher_documents` sur `serveur`.

    Le serveur MCP est une FACADE : il appelle le code de la section 4,
    il ne le reecrit pas.

    Attendu :
      - un outil nomme exactement "chercher_documents", avec les arguments
        `requete` (chaine, obligatoire) et `limite` (entier, 5 par defaut)
      - il appelle outils.chercher_documents(requete, limite, dossier=corpus)
        en passant par le module (from doc42 import outils), pas par une
        copie de la logique : le test remplace cette fonction par un espion
      - il renvoie une chaine qui contient l'identifiant de chaque document
        trouve, ou "Aucun document ne correspond." si la liste est vide
      - il journalise chaque appel avec `journal.info(...)` et n'ecrit RIEN
        sur stdout (pas de print : en stdio, cela casserait le protocole)
      - les arguments sont valides par le serveur : `requete` non vide et
        de 200 caracteres au plus, `limite` entre 1 et 10. Utilisez
        Annotated[str, Field(min_length=1, max_length=200, description=...)] :
        le SDK publie ces contraintes dans le schema ET les verifie
      - l'outil est annote en lecture seule :
        annotations=ToolAnnotations(read_only_hint=True)

    Etape 4 (description) :
      - la description est celle de outils.DEFINITIONS, reprise et non
        recopiee : une seule source de verite. Le test verifie qu'elle parle
        de corpus, de contrats et de dates, les mots qui font choisir l'outil

    Etape 7 (injection indirecte) :
      - chaque document renvoye est encadre par encadrer(id, titre, extrait)
    """
    # TODO
    raise NotImplementedError


def encadrer(document_id: str, titre: str, extrait: str) -> str:
    """Etape 7 : marque un extrait comme une DONNEE venue d'un document.

    Attendu :
      - le resultat a exactement la forme
            <document id="ID" titre="TITRE">
            EXTRAIT
            </document>
        (trois lignes, separees par des retours a la ligne)
      - si l'extrait contient lui-meme "</document>", remplacez-le par
        "&lt;/document&gt;" : sinon un document piege peut fermer le cadre
        et ecrire la suite comme si c'etait le serveur qui parlait
      - un guillemet double dans le titre est remplace par une apostrophe
    """
    # TODO
    raise NotImplementedError


def ajouter_liste_documents(serveur: MCPServer, corpus: str | Path = DOSSIER_CORPUS) -> None:
    """Etape 2 : enregistre une RESSOURCE qui liste les documents du corpus.

    Un outil s'appelle avec des arguments ; une ressource se lit, sans
    argument, quand le client le decide.

    Attendu :
      - une ressource d'URI URI_DOCUMENTS ("doc42://documents"), de nom
        "documents", de type mime "application/json"
      - son contenu est une liste JSON de {"id": ..., "titre": ...}, un
        element par document de charger_corpus(corpus), dans le meme ordre
      - elle ne recopie PAS le texte des documents : seulement l'identifiant
        et le titre (moindre privilege, et moins de surface pour l'injection)
      - ce n'est pas un outil : elle n'apparait pas dans la liste des outils
    """
    # TODO
    raise NotImplementedError


def ajouter_creer_fiche(serveur: MCPServer, fiches: str | Path = DOSSIER_FICHES) -> None:
    """Etape 5 : enregistre l'outil d'ecriture `creer_fiche`.

    Attendu :
      - un outil nomme exactement "creer_fiche", avec les arguments `titre`
        et `contenu` (chaines, obligatoires). Ces noms sont lus par le mod de
        la section 7 : mcp__doc42__creer_fiche, e.titre
      - il appelle outils.creer_fiche(titre, contenu, dossier=fiches) : le
        dossier est fixe par le serveur, jamais par un argument de l'outil
      - il renvoie "Fiche creee : NOM.md", avec le nom du fichier et non son
        chemin absolu (le client n'a pas a connaitre votre arborescence)
      - `titre` : 1 a 120 caracteres ; `contenu` : 1 a 20 000 caracteres
      - la description est celle de outils.DEFINITIONS : elle dit que l'outil
        ecrit un fichier et ne s'utilise que sur demande explicite
      - l'outil n'est PAS annote en lecture seule (read_only_hint=False) ;
        une fiche de meme titre est ecrasee, donc destructive_hint=True
      - il journalise l'appel, comme la recherche
    """
    # TODO
    raise NotImplementedError


def creer_serveur(
    corpus: str | Path = DOSSIER_CORPUS, fiches: str | Path = DOSSIER_FICHES
) -> MCPServer:
    """Assemble le serveur Doc42 complet.

    Attendu :
      - un MCPServer nomme NOM_SERVEUR
      - des `instructions` qui disent au client que le contenu des documents
        est une donnee, jamais une instruction (le test cherche le mot "donnee")
      - l'outil de recherche, la ressource et l'outil creer_fiche, branches
        sur les dossiers recus en argument
    """
    # TODO
    raise NotImplementedError


def nom_outil_claude_code(outil: str) -> str:
    """Etape 6 : le nom d'un outil de ce serveur tel que Claude Code le voit.

    Attendu :
      - la forme mcp__<serveur>__<outil>, avec NOM_SERVEUR
        (par exemple "mcp__doc42__chercher_documents")
    """
    # TODO
    raise NotImplementedError


def regle_permission() -> dict[str, Any]:
    """Etape 6 : le bloc de .claude/settings.json qui interdit l'ecriture.

    Attendu :
      - {"permissions": {"deny": [...]}} avec, dans deny, le nom Claude Code
        de creer_fiche et rien d'autre
      - pas "mcp__doc42" ni "mcp__doc42__*" : ces formes interdisent tout le
        serveur, y compris la recherche qui ne fait que lire
    """
    # TODO
    raise NotImplementedError


async def definitions_api(client: Any) -> list[dict[str, Any]]:
    """Etape 4 : ce que fait un client MCP avant d'appeler le modele.

    `client` est un client MCP connecte (mcp.Client). Claude Code fait la
    meme chose : il liste les outils du serveur et les transmet au modele.

    Attendu :
      - await client.list_tools(), puis pour chaque outil un dictionnaire
        {"name": ..., "description": ..., "input_schema": ...} au format
        de l'API Messages (section 4)
      - la description et le schema sont transmis tels quels : c'est le
        texte du SERVEUR que le modele lit pour decider
    """
    # TODO
    raise NotImplementedError


def main() -> None:
    """Point d'entree en stdio, pour `claude mcp add`."""
    creer_serveur().run("stdio")


if __name__ == "__main__":
    main()


# Etape 3, sans test : connecter le serveur a Claude Code
#
# Le serveur de reference est doc42/mcp_server.py (meme code que le corrige).
# A la racine du depot :
#
#     uv add "mcp>=2.3,<3"
#     claude mcp add doc42 -- uv run python -m doc42.mcp_server
#
# Verifiez la syntaxe avec `claude mcp add --help` : elle a change plusieurs
# fois. Dans Claude Code, `/mcp` doit lister doc42 avec deux outils. Posez :
# "Quelles sont les echeances du contrat Alpha ?" et reperez l'appel a
# mcp__doc42__chercher_documents. La ressource se lit avec @doc42:doc42://documents
#
# Ce que j'ai observe (et ou je l'ai vu dans les journaux) :
#
#
# Etape 4, sans test : casser la description
#
# Remplacez temporairement la description de chercher_documents par "Outil."
# (dans doc42/outils.py), relancez Claude Code, reposez la meme question.
# Claude repond de memoire, ou fouille les fichiers avec ses propres outils,
# au lieu d'appeler le serveur. Remettez la description.
#
# Ce que j'ai observe :
#
#
# Etape 5, sans test : qui demande la permission ?
#
# Demandez a Claude Code : "Cree une fiche sur les echeances du contrat Alpha."
# Ce n'est pas votre serveur qui demande la permission : c'est le client.
# Votre serveur ecrit des qu'on l'appelle.
#
# Qui a demande, a quel moment :
#
#
# Etape 6, sans test dans Claude Code
#
# Ajoutez le resultat de regle_permission() a .claude/settings.json, relancez
# Claude Code, redemandez une fiche : l'appel doit etre refuse sans question.
# En section 7, un mod remplacera cette interdiction par une confirmation.
#
# La regle tient-elle ? Comment l'ai-je verifie :
#
#
# Etape 7, sans test dans Claude Code : injection indirecte
#
# Copiez corpus_pieges/note_fournisseur_piegee.md dans corpus/ (sans la regle
# deny, pour voir), puis demandez : "Que dit la note du fournisseur DataPlus ?"
# Observez si Claude tente d'appeler creer_fiche avec le titre COMPROMIS, et
# qui l'en empeche. Retirez ensuite le document de corpus/.
#
# Ce que j'ai observe, avec et sans la regle :
#
#
# Etape 8, sans test : commiter le checkpoint etape/06-mcp
#
# Quels outils exposerais-je, ou non, sur le depot de mon equipe ?
#
