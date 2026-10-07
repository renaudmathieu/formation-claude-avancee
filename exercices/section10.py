"""Section 10, atelier. Sept exercices, une heure trente.

Objectif : rendre Doc42 observable et borne, sans changer une ligne de sa
logique metier. Tout ce que vous ecrivez ici s'enroule autour de
doc42.client ; vous ne modifiez pas doc42.client.

Completez les fonctions marquees TODO, puis lancez :

    uv run pytest tests/test_section10.py -v

Les enonces sont dans les docstrings. Vous n'avez pas besoin de revenir
sur Notion pendant l'atelier.

Regle de l'atelier : tout ce qui depend du temps (horloge murale,
chronometre, attente, identifiant aleatoire) est INJECTE en parametre.
C'est ce qui rend les tests deterministes et instantanes.
"""

from __future__ import annotations

import copy
import hashlib  # noqa: F401  (exercice 6)
import json  # noqa: F401  (exercices 2, 3 et 6)
import math  # noqa: F401  (exercice 3)
import re  # noqa: F401  (exercice 2)
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import anthropic  # noqa: F401  (exercice 5)

from doc42.client import REJOUABLES, appel_simple, avec_reprise  # noqa: F401
from doc42.config import (  # noqa: F401
    FACTEUR_CACHE_ECRIT,
    FACTEUR_CACHE_LU,
    MAX_TOKENS_DEFAUT,
    MODELE_DEFAUT,
    MODELE_PROFOND,
    MODELE_RAPIDE,
    RACINE,
    SYSTEME_DOC42,
    TARIFS,
)

# ---------------------------------------------------------------------------
# Exercice 1 : le cout d'un appel
# ---------------------------------------------------------------------------


def cout_appel(modele: str, usage: Any) -> float:
    """Le cout en dollars d'un appel, a partir de son `usage`.

    On ne peut pas optimiser ce qu'on ne mesure pas : ce chiffre est la base
    de tout le reste de l'atelier.

    Attendu :
      - les tarifs viennent de doc42.config.TARIFS : (entree, sortie) en dollars
        par MILLION de tokens, pour le modele demande
      - quatre postes, car input_tokens n'inclut PAS les tokens de cache :
          input_tokens                 x tarif d'entree
          cache_read_input_tokens      x tarif d'entree x FACTEUR_CACHE_LU
          cache_creation_input_tokens  x tarif d'entree x FACTEUR_CACHE_ECRIT
          output_tokens                x tarif de sortie
      - un champ absent ou None compte pour 0 (le SDK rend None quand le
        cache n'a pas servi)
      - un modele absent de TARIFS leve ValueError

    Piege : l'exemple de la page Notion oublie l'ecriture en cache. C'est
    pourtant le premier appel, le plus cher.
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 2 : un log JSON par appel
# ---------------------------------------------------------------------------


def masquer_secrets(texte: str) -> str:
    """Remplace toute cle API Anthropic du texte par "sk-ant-***".

    Attendu :
      - une cle, c'est "sk-ant-" suivi d'au moins 8 caracteres parmi
        lettres, chiffres, "_" et "-" ; elle devient "sk-ant-***"
      - "sk-ant-..." (une mention dans une doc) reste intact
      - le reste du texte est inchange

    Cette fonction sert deux fois : avant d'ecrire un message d'erreur dans
    un journal, et pour verifier qu'aucun fichier du depot ne contient de cle.
    """
    # TODO
    raise NotImplementedError


def maintenant_utc() -> datetime:
    return datetime.now(UTC)


def nouvel_identifiant() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


class ClientInstrumente:
    """Un enrobage du client qui journalise chaque appel en une ligne JSON.

    Il se presente comme un client Anthropic (instrumente.messages.create),
    ce qui permet de le passer tel quel a doc42.client.appel_simple,
    Conversation, etc. : c'est ainsi qu'on le branche sur TOUS les appels
    existants sans toucher a leur code.

    Le constructeur et `avec` sont fournis. Vous ecrivez `create`.
    """

    CONTEXTE = ("feature", "prompt_version", "user_id", "question_id")

    def __init__(
        self,
        client: Any,
        ecrire: Callable[[str], None],
        *,
        feature: str = "question",
        prompt_version: str = "non_versionne",
        user_id: str | None = None,
        question_id: str | None = None,
        horloge: Callable[[], datetime] = maintenant_utc,
        chrono: Callable[[], float] = time.perf_counter,
        generer_id: Callable[[], str] = nouvel_identifiant,
    ) -> None:
        self.client = client
        self.ecrire = ecrire
        self.feature = feature
        self.prompt_version = prompt_version
        self.user_id = user_id
        self.question_id = question_id
        self.horloge = horloge
        self.chrono = chrono
        self.generer_id = generer_id
        # L'astuce qui rend le wrapper transparent : client.messages.create
        # devient self.create.
        self.messages = self

    def avec(self, **contexte: Any) -> ClientInstrumente:
        """Une copie qui partage client et journal, avec un autre contexte.

        Exemple : instrumente.avec(feature="classification", question_id="q7").
        """
        inconnus = set(contexte) - set(self.CONTEXTE)
        if inconnus:
            raise TypeError(f"Contexte inconnu : {sorted(inconnus)}")
        copie = copy.copy(self)
        for cle, valeur in contexte.items():
            setattr(copie, cle, valeur)
        copie.messages = copie
        return copie

    def create(self, **kwargs: Any) -> Any:
        """Appelle self.client.messages.create(**kwargs), journalise, rend la reponse.

        Attendu :
          - la reponse est rendue intacte, les kwargs passent sans modification
          - exactement UN appel a self.ecrire par appel, avec une ligne
            json.dumps(...) (une seule ligne, sans retour a la ligne)
          - champs de la ligne, avec ces noms (ceux de la page Notion, que
            Datadog ou Loki savent indexer) :
              timestamp      self.horloge().isoformat(timespec="milliseconds")
              event          "claude_call"
              request_id     self.generer_id()
              question_id, user_id, feature, prompt_version   le contexte
              model, max_tokens                               depuis kwargs
              latency_ms     (chrono() apres - chrono() avant) en ms, arrondi
              level          "info" ou "error"
              success        True ou False
          - en cas de succes, en plus :
              input_tokens, output_tokens, cache_read_input_tokens,
              cache_creation_input_tokens   (None compte pour 0)
              stop_reason
              cost_usd       cout_appel(model DEMANDE, usage), arrondi a 6
                             decimales ; None si le modele n'a pas de tarif
                             (l'observabilite ne doit jamais casser l'appel)
          - en cas d'exception : la ligne porte success False, error_type
            (nom de la classe), error_message passe par masquer_secrets,
            cost_usd 0.0 ; puis l'exception est RELANCEE telle quelle
          - JAMAIS le contenu de messages ni de system dans la ligne

        Piege : un log qui contient la conversation complete est une fuite
        de donnees personnelles et une explosion de stockage.
        """
        # TODO
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 3 : agreger les journaux
# ---------------------------------------------------------------------------


def agreger(lignes: Iterable[str | dict[str, Any]]) -> dict[str, Any]:
    """Le bilan d'un journal : combien coute une question a Doc42 ?

    `lignes` contient des dictionnaires ou des chaines JSON (une ligne d'un
    fichier .jsonl). Les chaines vides sont ignorees, ainsi que les lignes
    dont event n'est pas "claude_call".

    Attendu, les cles du dictionnaire rendu :
      - "appels"                  nombre de lignes claude_call
      - "echecs"                  nombre de lignes avec success faux
      - "couts_inconnus"          lignes reussies dont cost_usd est None
      - "cout_total_usd"          somme des cost_usd (None compte pour 0)
      - "par_feature"             {feature: {"appels": n, "cout_usd": x}}
      - "par_version"             {prompt_version: {"appels": n, "cout_usd": x}}
      - "questions"               nombre de questions distinctes : on regroupe
                                  par question_id ; une ligne sans question_id
                                  est sa propre question (cle : request_id)
      - "cout_moyen_question_usd" cout total / nombre de questions (0.0 si aucune)
      - "latence_p50_ms", "latence_p99_ms"
                                  centiles des latency_ms non None, methode du
                                  rang le plus proche : la valeur de rang
                                  ceil(p / 100 x n) dans la liste triee
                                  (None s'il n'y a aucune latence)

    Piege : divisez par le nombre de QUESTIONS, pas d'appels. Une question
    a Doc42 coute souvent plusieurs appels (classification, outils, reprises).
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 4 : les trois leviers de cout
# ---------------------------------------------------------------------------


def choisir_modele(feature: str) -> str:
    """Levier 1 : router vers le modele le moins cher qui fait le travail.

    Attendu :
      - "classification", "extraction", "routage", "moderation" -> MODELE_RAPIDE
      - "raisonnement_critique" -> MODELE_PROFOND
      - toute autre fonctionnalite, connue ou non -> MODELE_DEFAUT
      - aucun identifiant de modele en dur : tout vient de doc42.config
    """
    # TODO
    raise NotImplementedError


# Levier 3 : TODO, remplissez ce dictionnaire {feature: max_tokens}.
# Une etiquette de classification tient en quelques tokens ; aucune valeur
# ne depasse MAX_TOKENS_DEFAUT. Dans la vraie vie, ces valeurs viennent des
# journaux : output_tokens au p99, plus une marge.
MAX_TOKENS_PAR_FEATURE: dict[str, int] = {}


def parametres(
    feature: str, question: str, corpus_reference: str = "", systeme: str = SYSTEME_DOC42
) -> dict[str, Any]:
    """Les kwargs de messages.create pour une fonctionnalite, leviers appliques.

    Attendu :
      - "model" : choisir_modele(feature)
      - "max_tokens" : MAX_TOKENS_PAR_FEATURE, ou MAX_TOKENS_DEFAUT si absente
        (une classification ne doit pas depasser 64)
      - "system" : une LISTE de blocs texte, dans cet ordre : le prompt
        systeme, puis le corpus de reference s'il n'est pas vide ; le DERNIER
        bloc porte "cache_control": {"type": "ephemeral"} (levier 2)
      - "messages" : [{"role": "user", "content": question}]
      - deux questions differentes donnent exactement le meme "system"

    Piege : le cache ne fonctionne que sur un prefixe STRICTEMENT identique.
    Un horodatage, un identifiant de session ou un nom d'utilisateur dans
    system l'annule sans aucun message. Vous le verriez sur la facture.
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 5 : reprise, disjoncteur, reponse degradee
# ---------------------------------------------------------------------------

MESSAGE_DEGRADE = (
    "Doc42 est momentanement indisponible. Votre question n'est pas perdue : "
    "reessayez dans une minute."
)


class CircuitOuvert(Exception):
    """Le disjoncteur refuse l'appel sans contacter l'API."""


class Disjoncteur:
    """Circuit breaker : arreter de taper une API en panne.

    Trois etats : "ferme" (tout passe), "ouvert" (tout est refuse sans
    appeler), "semi_ouvert" (un seul appel d'essai apres le delai).

    Le constructeur est fourni. Vous ecrivez `appeler`.
    """

    def __init__(
        self, seuil: int = 5, delai_s: float = 60.0, chrono: Callable[[], float] = time.monotonic
    ) -> None:
        self.seuil = seuil
        self.delai_s = delai_s
        self.chrono = chrono
        self.etat = "ferme"
        self.echecs = 0
        self.ouvert_depuis: float | None = None

    def appeler(self, appel: Callable[[], Any]) -> Any:
        """Execute `appel()` si le circuit le permet.

        Attendu :
          - etat "ouvert" et moins de delai_s ecoulees depuis ouvert_depuis
            (selon self.chrono) : leve CircuitOuvert SANS executer appel()
          - etat "ouvert" et delai ecoule : passe en "semi_ouvert" et tente
          - succes : etat "ferme", echecs remis a 0, rend le resultat
          - exception de REJOUABLES (panne du service) : echecs + 1 ; si
            l'etat etait "semi_ouvert" ou si echecs >= seuil, etat "ouvert"
            et ouvert_depuis = self.chrono() ; puis l'exception est relancee
          - toute autre exception (un 400, un bug) est relancee SANS etre
            comptee : ce n'est pas une panne du service
        """
        # TODO
        raise NotImplementedError


def creer_client_production(
    cle: str | None = None,
    *,
    base_url: str | None = None,
    http_client: Any = None,
    timeout: float = 30.0,
) -> Any:
    """Le vrai client Anthropic, regle pour la production.

    Attendu :
      - anthropic.Anthropic(api_key=cle, base_url=..., http_client=..., ...)
      - max_retries=0 : la reprise est geree par avec_reprise
      - timeout explicite (le parametre `timeout`)
      - cle=None laisse le SDK lire ANTHROPIC_API_KEY : la cle vient de
        l'environnement ou d'un gestionnaire de secrets, jamais du code

    Piege : le SDK rejoue deja 2 fois par defaut. Sous avec_reprise, chaque
    tentative en devient 3, avec des attentes que vos journaux ne voient pas.
    """
    # TODO
    raise NotImplementedError


def repondre(
    client: Any,
    question: str,
    disjoncteur: Disjoncteur,
    tentatives: int = 3,
    dormir: Callable[[float], None] = time.sleep,
) -> str:
    """Repond via doc42.client.appel_simple, ou rend MESSAGE_DEGRADE en cas de panne.

    Attendu :
      - l'appel passe par le disjoncteur, et le tout par avec_reprise
        (doc42.client) avec `tentatives` et `dormir` : le disjoncteur est
        DANS la reprise, pour que CircuitOuvert arrete les tentatives
      - CircuitOuvert ou une exception de REJOUABLES qui a epuise les
        tentatives : on rend MESSAGE_DEGRADE, pas d'exception
      - toute autre exception (400, 401) remonte : c'est un bug a corriger,
        pas une panne a cacher

    Piege : le retry genere sans reflexion fait "except Exception" et
    rejoue cinq fois. Il transforme une erreur de code en facture.
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 6 : prompts versionnes
# ---------------------------------------------------------------------------

# Structure attendue :
#
#   prompts/
#     registre.json        {"doc42_systeme": {"courante": "v2",
#                            "versions": {"v1": "<sha256>", "v2": "<sha256>"}}}
#     doc42_systeme.v1.md
#     doc42_systeme.v2.md
#     CHANGELOG.md         pourquoi chaque version (comme en section 3)
DOSSIER_PROMPTS = RACINE / "prompts"


@dataclass(frozen=True)
class Prompt:
    nom: str
    version: str
    texte: str
    empreinte: str

    @property
    def identifiant(self) -> str:
        """Ce qu'on journalise dans prompt_version : nom@version#8 premiers hex."""
        return f"{self.nom}@{self.version}#{self.empreinte[:8]}"


def charger_prompt(
    nom: str, version: str = "courante", dossier: str | Path = DOSSIER_PROMPTS
) -> Prompt:
    """Charge un prompt versionne depuis `dossier`.

    Attendu :
      - lit dossier/registre.json ; version "courante" -> registre[nom]["courante"]
      - nom ou version absents du registre : KeyError
      - lit les OCTETS de dossier/<nom>.<version>.md ; empreinte = sha256 hexadecimal
      - si l'empreinte differe de celle enregistree : ValueError (une version
        publiee ne se retouche pas, on en cree une nouvelle)
      - texte = contenu decode en UTF-8, sans les blancs de debut et de fin
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 7 : quota par utilisateur et validation d'entree
# ---------------------------------------------------------------------------

LONGUEUR_MAX_QUESTION = 10_000


class QuotaDepasse(Exception):
    """L'utilisateur a epuise son quota du jour (a traduire en HTTP 429)."""


class Quota:
    """Quota quotidien par utilisateur : nombre de requetes et budget en dollars.

    Le jour est celui de self.horloge(), en UTC. Le constructeur est fourni ;
    vous ecrivez `reserver` et `imputer` (et un assistant si vous voulez).
    """

    def __init__(
        self,
        requetes_par_jour: int = 100,
        budget_usd_par_jour: float = 1.0,
        horloge: Callable[[], datetime] = maintenant_utc,
    ) -> None:
        self.requetes_par_jour = requetes_par_jour
        self.budget_usd_par_jour = budget_usd_par_jour
        self.horloge = horloge
        self._jour: date | None = None
        self._compteurs: dict[str, dict[str, float]] = {}

    def reserver(self, utilisateur: str) -> None:
        """A appeler AVANT l'appel a l'API.

        Attendu :
          - si le jour de self.horloge() a change, tous les compteurs repartent a zero
          - QuotaDepasse si l'utilisateur a deja fait requetes_par_jour requetes
            aujourd'hui, ou si son cout du jour atteint budget_usd_par_jour
          - sinon, compte une requete de plus (avant l'appel : compter apres
            laisserait passer une rafale de requetes simultanees)
          - chaque utilisateur a ses propres compteurs
        """
        # TODO
        raise NotImplementedError

    def imputer(self, utilisateur: str, cout_usd: float | None) -> None:
        """A appeler APRES l'appel, avec son cout. Ne leve jamais (None compte 0)."""
        # TODO
        raise NotImplementedError


def valider_question(question: str) -> str:
    """Garde-fou d'entree, avant tout appel.

    Attendu :
      - rend la question sans les blancs de debut et de fin
      - ValueError si elle est vide (apres nettoyage)
      - ValueError si elle depasse LONGUEUR_MAX_QUESTION caracteres
    """
    # TODO
    raise NotImplementedError


# Etape 2 de l'atelier, sans test
#
# Branchez ClientInstrumente sur les scenarios des sections 4 et 8 (un
# journal .jsonl, un question_id par question posee), puis agregez :
#
#     uv run python -m doc42.observabilite journaux/appels.jsonl
#
# Combien coute une question a Doc42 ? Quelle fonctionnalite pese le plus ?
#
# Ce que j'ai mesure (cout moyen d'une question, avant) :
#
# Ce qui m'a surpris :


# Etape 3 de l'atelier, sans test
#
# Appliquez les leviers UN PAR UN contre la vraie API, en mesurant apres
# chacun : 1. routage de la classification, 2. cache du prompt systeme et du
# corpus, 3. max_tokens. Verifiez cache_read_input_tokens dans les journaux :
# s'il reste a 0, votre prefixe n'est pas stable (ou trop court pour etre
# cache). Le test de l'exercice 4 simule la facture ; ici, c'est la vraie.
#
# Cout moyen apres levier 1 :          apres levier 2 :          apres levier 3 :
#
# La qualite a-t-elle bouge ? (relancez le jeu d'evaluation de la section 3)


# Etape 5 de l'atelier, sans test
#
# Publiez deux versions du prompt systeme dans prompts/, faites tourner le
# jeu d'evaluation de la section 3 sur chacune (prompt_version dans le
# journal), puis comparez agreger(...)["par_version"] et les scores.
#
# v1 :                                 v2 :
#
# Celle que je deploie, et pourquoi :


# Etape 7 de l'atelier, sans test
#
# Commitez le checkpoint etape/10-prod. Avant : `git log -p | grep sk-ant-`
# ne doit rien rendre, et .env doit etre dans .gitignore.


# Bonus, sans test
#
# Branchez le journal sur un tableau de bord, meme minimal, et posez les
# trois alertes qui comptent : taux d'erreur (> 1 % sur 5 min), cout
# journalier anormal (> 150 % de la moyenne sur 7 jours), latence p99.
