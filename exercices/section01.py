"""Section 1, atelier. Huit exercices courts, quarante minutes.

Completez les fonctions marquees TODO, puis lancez :

    uv run pytest tests/test_section01.py -v

Les enonces sont dans les docstrings. Vous n'avez pas besoin de revenir
sur Notion pendant l'atelier.

Regle de la section : aucun identifiant de modele dans ce fichier. Ils
viennent tous de doc42/config.py, et un test le verifie.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from doc42.config import (  # noqa: F401
    MAX_TOKENS_DEFAUT,
    MODELE_DEFAUT,
    MODELE_PROFOND,
    MODELE_RAPIDE,
    TARIFS,
)
from doc42.corpus import Document
from doc42.outils import normaliser  # noqa: F401  (utile pour choisir_modele)

# --- Donne : ne pas modifier -------------------------------------------------

# Les trois paliers compares, du plus leger au plus capable.
MODELES: tuple[str, ...] = (MODELE_RAPIDE, MODELE_DEFAUT, MODELE_PROFOND)

QUESTION_PREMIER_APPEL = "Presente-toi en une phrase."
CONSIGNE_RESUME = "Resume ce document en trois puces factuelles."
CONSIGNE_RECLAMATION = "Ce message est-il une reclamation ? Reponds par oui ou non."
# Bonus de l'atelier : le meme resume, avec une consigne de forme dans le systeme.
SYSTEME_CONCIS = "Reponds en trois puces, sans introduction."


@dataclass
class Mesure:
    """Une ligne du tableau comparatif."""

    modele: str
    texte: str
    tokens_entree: int
    tokens_sortie: int
    duree: float  # en secondes
    cout: float  # en dollars
    stop_reason: str


def consigne_resume(document: Document) -> str:
    """La tache de l'etape 3 : la consigne, puis le document a resumer."""
    return f"{CONSIGNE_RESUME}\n\n{document.texte}"


def consigne_reclamation(message: str) -> str:
    """La tache triviale de l'etape 4."""
    return f"{CONSIGNE_RECLAMATION}\n\nMessage : {message}"


# --- Exercices ---------------------------------------------------------------


def diagnostiquer(
    environ: Mapping[str, str] | None = None,
    version: tuple[int, ...] = tuple(sys.version_info[:2]),
) -> list[str]:
    """Liste les problemes d'environnement. Une liste vide veut dire : pret.

    doc42.config.verifier() ne regarde que la presence de la cle. Vous allez
    le completer, sans modifier config.py.

    Attendu :
      - `environ` vaut os.environ quand il est None ; le test injecte un
        dictionnaire pour ne pas dependre de votre machine
      - ANTHROPIC_API_KEY absente ou vide : un probleme qui contient
        "ANTHROPIC_API_KEY"
      - presente mais mal formee (ne commence pas par "sk-ant-", ou contient
        un espace ou un guillemet, erreurs classiques de copier-coller) :
        un probleme qui contient "ANTHROPIC_API_KEY"
      - `version` inferieure a (3, 12) : un probleme qui contient "3.12"
      - chacun des trois MODELES doit avoir un tarif dans TARIFS, sinon un
        probleme qui nomme le modele
      - JAMAIS la valeur de la cle dans un message : un diagnostic finit
        dans un terminal partage, une capture d'ecran ou un ticket
    """
    # TODO
    raise NotImplementedError


def premier_appel(client: Any, question: str = QUESTION_PREMIER_APPEL) -> tuple[str, Any, str]:
    """Le premier appel de la formation. Retourne (texte, usage, stop_reason).

    Attendu :
      - model et max_tokens viennent de doc42.config (MODELE_DEFAUT,
        MAX_TOKENS_DEFAUT), jamais une chaine ecrite ici
      - un seul message, role "user", contenu `question`
      - usage est l'objet usage de la reponse, tel quel : vous le lirez a
        voix haute (input_tokens, output_tokens)
      - stop_reason vient de la reponse, ne le supposez pas : "max_tokens"
        veut dire que la reponse a ete coupee

    Piege : content[0].text fonctionne ici et cassera en section 4, quand
    une reponse pourra commencer par un bloc d'outil. Prenez l'habitude de
    concatener les blocs de type "text".
    """
    # TODO
    raise NotImplementedError


def cout_estime(modele: str, tokens_entree: int, tokens_sortie: int) -> float:
    """Cout d'un appel, en dollars.

    Attendu :
      - les tarifs viennent de TARIFS : (entree, sortie) en dollars par
        MILLION de tokens
      - un modele absent de TARIFS leve ValueError avec un message qui dit
        quoi faire (mettre a jour doc42.config), plutot qu'un cout de zero
        qui fausserait le tableau sans bruit
    """
    # TODO
    raise NotImplementedError


def mesurer(
    client: Any,
    modele: str,
    consigne: str,
    horloge: Callable[[], float] = time.perf_counter,
    systeme: str | None = None,
) -> Mesure:
    """Envoie `consigne` a `modele` et retourne une Mesure complete.

    Attendu :
      - max_tokens vaut MAX_TOKENS_DEFAUT, le meme pour tous les modeles,
        sinon la comparaison n'est pas equitable
      - la duree est mesuree avec `horloge`, appelee exactement deux fois :
        juste avant et juste apres l'appel. Jamais time.time() directement :
        le test injecte une horloge factice pour etre deterministe
      - tokens_entree et tokens_sortie viennent de usage, le cout de
        cout_estime()
      - `systeme` n'est transmis (parametre system) que s'il n'est pas None
    """
    # TODO
    raise NotImplementedError


def comparer(
    client: Any,
    consigne: str,
    modeles: Sequence[str] = MODELES,
    horloge: Callable[[], float] = time.perf_counter,
    systeme: str | None = None,
) -> list[Mesure]:
    """La meme consigne a chaque modele, une Mesure par modele, dans l'ordre.

    Attendu :
      - exactement la meme consigne (et le meme systeme) pour tous : on
        compare les modeles, pas les prompts
      - l'ordre du resultat suit l'ordre de `modeles`
    """
    # TODO
    raise NotImplementedError


def tableau(mesures: Sequence[Mesure]) -> str:
    """Le tableau comparatif, en Markdown, a coller dans NOTES.md.

    Attendu, exactement :

        | Modele | Entree | Sortie | Cout ($) | Duree (s) | Qualite |
        |---|---|---|---|---|---|
        | <modele> | <tokens_entree> | <tokens_sortie> | <cout:.6f> | <duree:.2f> |  |

      - une ligne par mesure, dans l'ordre recu, lignes separees par "\\n"
      - la colonne Qualite reste vide (deux espaces entre les barres) : c'est
        votre jugement (utilisable tel quel, a retoucher, inutilisable), pas
        celui du code
    """
    # TODO
    raise NotImplementedError


def choisir_modele(tache: str) -> str:
    """Votre premiere regle de routage, tiree du tableau de la section 1.1.

    Attendu :
      - "tri", "classification", "routage", "moderation", "support"
        -> MODELE_RAPIDE
      - "analyse", "redaction", "code" -> MODELE_DEFAUT
      - "raisonnement", "recherche", "agent" -> MODELE_PROFOND
      - majuscules, accents et espaces autour ne comptent pas :
        " Redaction " et "redaction" ecrit avec son accent donnent le meme
        modele
      - toute autre tache -> MODELE_RAPIDE : on essaie le plus leger d'abord,
        on ne monte que si on constate qu'il echoue
    """
    # TODO
    raise NotImplementedError


def monter_en_gamme(modele: str) -> str | None:
    """Le palier au-dessus de `modele`, ou None s'il n'y en a pas.

    Attendu :
      - MODELE_RAPIDE -> MODELE_DEFAUT -> MODELE_PROFOND -> None
      - un modele inconnu leve ValueError
    """
    # TODO
    raise NotImplementedError


# Etapes 1 a 6 de l'atelier, ce qui ne se teste pas
#
# Etape 1, sans test : uv sync, copier .env.example en .env, puis
#   uv run python -c "from doc42.config import verifier; verifier()"
# Avant de commiter : `git check-ignore .env` doit repondre .env, et
# `git grep -n "sk-ant-"` ne doit rien trouver. Une cle commitee se revoque
# depuis la Console : la retirer du commit ne suffit pas, l'historique la garde.
#
# Etape 2, sans test : passez premier_appel() avec un vrai client
# (anthropic.Anthropic()). Lisez usage et stop_reason a voix haute.
#
# Etape 3, sans test : avec un vrai client,
#   from doc42.corpus import trouver
#   print(tableau(comparer(client, consigne_resume(trouver("note_rh_teletravail")))))
# Collez le tableau dans NOTES.md et remplissez la colonne Qualite.
#
# Etape 4, sans test : meme chose avec
#   consigne_reclamation("Troisieme relance : la facture F2026-118 est toujours fausse.")
# Ce que j'ai observe sur la qualite :
# Ce que j'ai observe sur le cout :
#
# Etape 5, sans test : ma regle de routage, en une phrase, dans NOTES.md
# (elle servira en section 10) :
#
# Bonus, sans test : relancez l'etape 3 avec systeme=SYSTEME_CONCIS.
# Economie de tokens de sortie constatee :
#
# Etape 6 : commiter etape/01-premier-appel.
