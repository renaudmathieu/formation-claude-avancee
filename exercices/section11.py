"""Section 11, projet final. Le contrat commun aux trois variantes.

Cette section n'est pas une serie d'exercices courts : c'est une journee de
projet. Vous choisissez une variante (A support, B analyseur de documents
metier, C assistant de code), vous l'ecrivez dans doc42/variantes/, et vous
la presentez. Ce fichier contient ce que TOUTE variante livree doit savoir
faire, quelle que soit sa logique metier : c'est la definition de termine,
rendue testable.

Completez les fonctions marquees TODO dans l'ordre de la journee, puis lancez :

    uv run pytest tests/test_section11.py -v

Les types (Variante, Bornes, Reponse, CasEval, RapportEval) sont donnes : ce
sont les formes du contrat, ne les changez pas. Votre variante les reutilise.

Ordre conseille, cale sur le tableau 11.2 :
  0 h 00   exercice 1 (specification) et 2 (anonymisation du corpus)
  1 h 00   exercices 3 a 6 (la variante, ses garde-fous, son chemin nominal)
  4 h 00   exercices 7 et 8 (le chiffre de reussite, le livrable)
"""

from __future__ import annotations

import json  # noqa: F401
import re
import uuid  # noqa: F401
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime  # noqa: F401
from pathlib import Path
from typing import Any

import anthropic  # noqa: F401  (pour rattraper anthropic.APIError)

from doc42.client import texte_de  # noqa: F401
from doc42.config import (  # noqa: F401
    FACTEUR_CACHE_ECRIT,
    FACTEUR_CACHE_LU,
    MAX_TOKENS_DEFAUT,
    MODELE_DEFAUT,
    TARIFS,
)
from doc42.outils import mots, normaliser  # noqa: F401

# ---------------------------------------------------------------------------
# Les formes du contrat. Donnees, ne pas modifier.
# ---------------------------------------------------------------------------

Confirmer = Callable[[str, dict[str, Any]], bool]


def refuser(nom: str, entree: dict[str, Any]) -> bool:
    """Confirmation par defaut : non. Une action irreversible ne passe jamais seule."""
    return False


@dataclass
class Variante:
    """Ce qu'une variante declare : son prompt, ses outils, ses actions irreversibles.

    - outils : les definitions envoyees a l'API (name, description, input_schema)
    - executer(nom, entree) -> str : execute un outil, comme doc42.outils.executer
    - irreversibles : les noms d'outils qui exigent une confirmation humaine
    """

    nom: str
    systeme: str
    outils: list[dict[str, Any]]
    executer: Callable[[str, dict[str, Any]], str]
    irreversibles: frozenset[str] = frozenset()
    modele: str = MODELE_DEFAUT


@dataclass
class Bornes:
    """Les garde-fous chiffres d'une requete."""

    max_tours: int = 6
    max_caracteres: int = 2000
    budget_dollars: float = 0.10


@dataclass
class Reponse:
    """Ce que toute variante rend, quelle que soit sa logique interne.

    - sources : identifiants de documents cites ET effectivement renvoyes par un outil
    - escalade : True quand la variante passe la main a un humain
    - raison : pourquoi elle passe la main ("hors_bornes", "tours", "budget",
      "erreur", "sans_source"), vide sinon
    """

    texte: str
    sources: list[str] = field(default_factory=list)
    escalade: bool = False
    raison: str = ""
    tours: int = 0
    cout: float = 0.0
    requete_id: str = ""


@dataclass
class CasEval:
    """Un cas du jeu d'evaluation.

    - attendus : morceaux de texte qui doivent figurer dans la reponse
    - sources : identifiants qui doivent figurer dans Reponse.sources
    - escalade : True si la bonne reponse est de passer la main
    """

    question: str
    attendus: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    escalade: bool = False


@dataclass
class RapportEval:
    total: int
    reussis: int
    echecs: list[tuple[str, str]] = field(default_factory=list)
    cout: float = 0.0

    @property
    def taux(self) -> float:
        return self.reussis / self.total if self.total else 0.0

    def resume(self) -> str:
        return f"{self.reussis}/{self.total} cas reussis ({self.taux:.0%}), cout {self.cout:.4f} $"


MIN_CAS = 10

# Les citations de sources suivent la convention de doc42.outils.executer :
# un identifiant de document entre crochets, par exemple [contrat_alpha].
MOTIF_SOURCE = re.compile(r"\[([A-Za-z0-9_.-]+)\]")


# ---------------------------------------------------------------------------
# Exercice 1 : la specification d'une page (0 h 00)
# ---------------------------------------------------------------------------


def verifier_specification(texte: str) -> list[str]:
    """Verifie la specification d'une page avant la revue de 0 h 30.

    La specification est un Markdown avec quatre sections de niveau ## ou ### :
    Quoi, Critere de reussite, Hors perimetre, Risque principal.

    Retourne la liste des problemes, vide si la specification est recevable.

    Attendu :
      - chaque section absente ou vide est signalee, en citant son nom
        (« Section manquante : Risque principal »)
      - les titres se comparent normalises (doc42.outils.normaliser) : « Hors
        périmètre » et « Ce qui est hors perimetre » sont acceptes, et
        « Comment on saura que ça marche » vaut « Critere de reussite »
      - le mot se cherche en debut de mot : « Pourquoi » n'est pas « Quoi »
      - Quoi contient un exemple d'entree et un exemple de sortie (les mots
        « entree » et « sortie », normalises) ; sinon un probleme cite « Quoi »
      - le critere est chiffre : un chiffre, ou un nombre en lettres
        (« huit questions sur dix »), « un » et « une » ne comptent pas ; sinon
        un probleme contient le mot « chiffre »
      - Hors perimetre contient au moins trois elements de liste (lignes
        commencant par -, * ou 1.) ; sinon un probleme cite « Hors perimetre »
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 2 : anonymiser avant d'envoyer (0 h 00, avec votre corpus)
# ---------------------------------------------------------------------------


def anonymiser(texte: str) -> tuple[str, int]:
    """Masque les donnees personnelles detectables, retourne (texte, nombre de masques).

    Attendu :
      - adresse e-mail -> [EMAIL]
      - telephone francais (06 12 34 56 78, 01.23.45.67.89, +33 6 12 34 56 78)
        -> [TELEPHONE]
      - IBAN francais (FR76 3000 6000 0112 3456 7890 189, avec ou sans espaces)
        -> [IBAN]
      - les dates (15/01/2027) et les montants (16 000 euros) restent intacts

    Piege : un IBAN contient des suites de chiffres qu'une regle de telephone
    attrape. Traitez l'IBAN en premier.

    Ce que la fonction ne fait pas : les noms propres. Une regle les raterait
    ou effacerait « Alpha Logistique ». Ils demandent une relecture humaine,
    a faire AVANT la formation (piege « corpus non prepare »).
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 3 : une variante qui declare ses garde-fous (1 h 00)
# ---------------------------------------------------------------------------


def verifier_variante(variante: Variante) -> list[str]:
    """Verifie qu'une variante est recevable avant de la brancher. Retourne les problemes.

    Attendu :
      - nom vide, aucun outil : signale
      - modele absent de TARIFS : signale, avec le mot « TARIFS » (sans tarif,
        le cout d'une requete est incalculable)
      - un outil sans description : signale, avec le mot « description »
      - un input_schema dont le type n'est pas "object" : signale
      - garde-fou fantome : un nom de variante.irreversibles qui ne correspond
        a aucun outil (une faute de frappe, et la confirmation ne se declenche
        jamais) : signale, en citant ce nom
      - un outil dont la description contient un verbe d'ecriture (ecrit,
        cree, supprime, envoie, modifie, paie, a l'infinitif ou conjugue) et
        qui n'est pas declare irreversible : signale, en citant l'outil.
        Comparez des mots (doc42.outils.mots) : « decrit » contient « ecrit »
        mais n'est pas une ecriture.
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 4 : ce que coute une requete (1 h 00)
# ---------------------------------------------------------------------------


def cout_appel(modele: str, usage: Any) -> float:
    """Cout en dollars d'un appel, a partir de reponse.usage.

    Attendu :
      - tarifs et facteurs de cache viennent de doc42.config (TARIFS est en
        dollars par million de tokens)
      - cout = entree * prix_entree + sortie * prix_sortie
             + cache_lu * prix_entree * FACTEUR_CACHE_LU
             + cache_ecrit * prix_entree * FACTEUR_CACHE_ECRIT
      - un champ de cache a None compte pour 0 (le SDK le fait)
      - un modele absent de TARIFS leve ValueError : un cout inconnu n'est
        pas un cout nul
    """
    # TODO
    raise NotImplementedError


class Journal:
    """Le journal des appels : ce qui permet de dire ce que coute une requete.

    Attendu :
      - enregistrer(requete_id, modele, usage) ajoute a self.entrees un dict
        avec au moins : date, requete, modele, entree, sortie, cache_lu,
        cache_ecrit, cout ; et le retourne
      - si un chemin est donne, chaque entree est AUSSI ajoutee au fichier,
        une ligne JSON par appel (creez le dossier parent au besoin)
      - cout_requete(requete_id) : la somme des couts des appels de cette
        requete (une question utilisateur fait souvent plusieurs appels)
      - cout_total() : la somme de tout
    """

    def __init__(self, chemin: str | Path | None = None) -> None:
        self.chemin = Path(chemin) if chemin else None
        self.entrees: list[dict[str, Any]] = []

    def enregistrer(self, requete_id: str, modele: str, usage: Any) -> dict[str, Any]:
        # TODO
        raise NotImplementedError

    def cout_requete(self, requete_id: str) -> float:
        # TODO
        raise NotImplementedError

    def cout_total(self) -> float:
        # TODO
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 5 : executer un outil derriere ses garde-fous (1 h 00)
# ---------------------------------------------------------------------------


def resultat_outil(bloc: Any, variante: Variante, confirmer: Confirmer = refuser) -> dict[str, Any]:
    """Execute le bloc tool_use et retourne le bloc tool_result a renvoyer au modele.

    Attendu :
      - le resultat est {"type": "tool_result", "tool_use_id": bloc.id,
        "content": <texte>} et porte "is_error": True en cas de probleme
      - outil inconnu de la variante : is_error, rien n'est execute
      - outil de variante.irreversibles : on appelle confirmer(nom, entree)
        AVANT d'executer ; sur refus, rien n'est execute et le contenu dit que
        l'action a ete refusee (le mot « refusee »), avec is_error
      - outil en lecture : execute sans demander de confirmation
      - une exception levee par variante.executer devient un tool_result
        is_error qui contient le message de l'erreur, pas un crash
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 6 : repondre, borne, source, et savoir passer la main (1 h 00)
# ---------------------------------------------------------------------------


def repondre(
    client: Any,
    variante: Variante,
    question: str,
    *,
    journal: Journal | None = None,
    confirmer: Confirmer = refuser,
    bornes: Bornes | None = None,
) -> Reponse:
    """La boucle commune a toutes les variantes : outils, bornes, sources, escalade.

    Attendu :
      - un requete_id unique par appel de repondre (uuid), repris dans la Reponse
      - sans journal fourni, un Journal() est cree quand meme
      - question plus longue que bornes.max_caracteres : escalade "hors_bornes",
        SANS aucun appel a l'API
      - chaque appel envoie model=variante.modele, max_tokens=MAX_TOKENS_DEFAUT,
        system=variante.systeme, tools=variante.outils, messages=...
      - chaque appel est journalise (journal.enregistrer) avec son usage
      - stop_reason "tool_use" : si le cout de la requete depasse deja
        bornes.budget_dollars, escalade "budget" sans relancer ; sinon chaque
        tool_use passe par resultat_outil, puis on ajoute le message assistant
        (reponse.content) et UN message user avec tous les tool_result
      - autre stop_reason : reponse finale. Les sources sont les identifiants
        cites entre crochets dans le texte (MOTIF_SOURCE) ET presents dans un
        tool_result sans erreur ; un identifiant cite mais jamais renvoye est
        une citation inventee, on l'ecarte. Sans aucune source : escalade
        "sans_source" (le texte du modele est conserve)
      - bornes.max_tours appels sans reponse finale : escalade "tours"
      - anthropic.APIError a l'appel : escalade "erreur"
      - Reponse.tours = nombre d'appels faits, Reponse.cout = cout de la requete

    Une escalade porte un texte qui le dit, par exemple : « Je ne peux pas
    repondre de facon fiable (limite de 6 tours atteinte). Je transmets a un
    humain. »
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 7 : le jeu d'evaluation et son chiffre (4 h 00)
# ---------------------------------------------------------------------------


def charger_cas(chemin: str | Path) -> list[CasEval]:
    """Charge un jeu d'evaluation JSONL : un objet par ligne.

    Exemple de ligne :
      {"question": "Echeances Alpha ?", "attendus": ["15/04/2027"], "sources": ["contrat_alpha"]}
      {"question": "CA de Beta en 2025 ?", "escalade": true}

    Attendu :
      - les lignes vides sont ignorees
      - attendus, sources et escalade sont optionnels
      - une ligne sans question, ou qui n'est pas du JSON, leve ValueError
        avec son numero (« ligne 2 : ... »)
    """
    # TODO
    raise NotImplementedError


def evaluer(repondre: Callable[[str], Reponse], cas: list[CasEval]) -> RapportEval:
    """Passe chaque cas a `repondre` et compte les reussites.

    `repondre` est une fonction question -> Reponse : en pratique
    lambda q: repondre(client, variante, q, ...).

    Attendu :
      - moins de MIN_CAS cas : ValueError (en dessous de dix, un cas vaut plus
        de dix points et le chiffre ne dit rien)
      - cas.escalade True : reussi si et seulement si la reponse passe la main
      - sinon : reussi si la reponse ne passe pas la main, contient chaque
        attendu (comparaison normalisee : accents et casse ignores) et cite
        chaque source attendue
      - une exception levee par repondre compte comme un echec et
        n'interrompt pas l'evaluation
      - rapport.echecs : (question, raison) pour chaque echec
      - rapport.cout : somme des Reponse.cout
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 8 : le livrable, verifie comme le ferait un collegue (6 h 00)
# ---------------------------------------------------------------------------


def verifier_livrable(
    dossier: str | Path,
    *,
    readme: str = "README.md",
    spec: str = "docs/specification.md",
    cas: str = "evals/cas.jsonl",
) -> list[str]:
    """Verifie qu'un depot propre contient de quoi lancer et juger la variante.

    Attendu, chaque manque etant un probleme dans la liste retournee :
      - le README existe et contient « uv sync », « ANTHROPIC_API_KEY » et
        « uv run » : un collegue doit pouvoir lancer sans vous
      - .gitignore contient une ligne .env (sinon la cle part avec le depot)
      - la specification existe (« Specification absente ») et passe
        verifier_specification, ses problemes prefixes par « Specification : »
      - le jeu d'evaluation existe, se charge avec charger_cas et compte au
        moins MIN_CAS cas (« 5 cas, il en faut 10 »)
    """
    # TODO
    raise NotImplementedError


# Etape 11.2, sans test : la revue de cadrage (0 h 30)
#
# Faites relire votre specification par un pair, puis par le formateur.
# verifier_specification dit si elle est complete, pas si elle est realiste.
# La question a poser au relecteur : « qu'est-ce que je coupe si a 3 h 30 le
# chemin nominal ne marche pas ? »
#
# Ce que le relecteur a coupe :
#
#
# Etape du point d'etape (3 h 30), sans test
#
# Mesurez avant d'optimiser : lancez evaluer sur votre jeu de cas, notez le
# chiffre et le cout total. Vous en aurez besoin pour la presentation.
#
# Chiffre a 3 h 30 :            Cout du jeu complet :
# Blocage nomme :
#
#
# Etape de la presentation (6 h 00), sans test
#
# Dix minutes : la specification, une demonstration du chemin nominal, une
# escalade (une question hors corpus), le chiffre d'evaluation et le cout par
# requete lus dans le journal. Prevoyez une capture de secours.
#
# La question qu'on m'a posee sur mes choix :
#
# Ma reponse :
#
#
# Commitez le checkpoint etape/11-final une fois verifier_livrable vide.
