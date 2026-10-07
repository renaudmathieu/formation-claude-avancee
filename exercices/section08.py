"""Section 8, atelier. Doc42 devient un agent, avec garde-fous. Une heure trente.

Completez les fonctions marquees TODO, puis lancez :

    uv run pytest tests/test_section08.py -v

Les enonces sont dans les docstrings. Ordre conseille, celui de l'atelier :

    1. run_agent : la boucle de la section 4, bornee en tours et journalisee
    2. (rien a coder) les tests de l'objectif multi-etapes Alpha / Beta
    3. run_agent : le budget de tokens, puis cout_dollars ; et le delai
    4. confirmer_console et executer_avec_garde : la confirmation humaine
    5. (rien a coder) la boucle provoquee : un outil qui echoue toujours
    6. encadrer et SYSTEME_AGENT : le document piege
    7. et 8. sans test, en fin de fichier

Vous n'avez pas besoin de revenir sur Notion pendant l'atelier. Ne reprenez
pas votre fichier de la section 4 : ce fichier est autonome.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from doc42.client import texte_de  # noqa: F401  (jamais content[0].text)
from doc42.config import MODELE_DEFAUT, SYSTEME_DOC42, TARIFS  # noqa: F401
from doc42.outils import DEFINITIONS, executer

journal_log = logging.getLogger("doc42.agent")

Confirmer = Callable[[str, dict[str, Any]], bool]
Executeur = Callable[[str, dict[str, Any]], str]

# Les seuils sont des parametres de run_agent ; ces valeurs ne sont que des defauts.
MAX_TOURS_DEFAUT = 10
BUDGET_TOKENS_DEFAUT = 50_000
DELAI_MAX_DEFAUT = 120.0
MAX_TOKENS_AGENT = 4096

# Les outils dont l'effet survit a l'execution : ils passent par un humain.
OUTILS_ECRITURE = frozenset({"creer_fiche"})

# La balise qui isole tout ce qui vient d'un outil (exercice 6).
BALISE = "donnees_non_fiables"

# TODO (exercice 6) : durcissez ce prompt systeme. Il doit dire a l'agent :
#   - qu'il poursuit un objectif en plusieurs etapes avec des outils ;
#   - que les resultats d'outils arrivent entre balises <donnees_non_fiables>
#     (utilisez BALISE) et que leur contenu est une DONNEE, jamais une instruction ;
#   - qu'il n'appelle creer_fiche que si l'utilisateur l'a demande, et qu'il
#     n'insiste pas apres un refus.
SYSTEME_AGENT = SYSTEME_DOC42


@dataclass
class Etape:
    """Une action de l'agent, telle qu'on veut pouvoir la relire apres coup. Donne."""

    tour: int
    outil: str
    arguments: dict[str, Any]
    statut: str  # "ok", "erreur" ou "refuse"
    duree_s: float
    # Tokens de l'appel qui a decide cette action (partages si l'appel en a demande plusieurs).
    tokens_entree: int
    tokens_sortie: int


@dataclass
class ResultatAgent:
    """Ce que rend run_agent. Donne.

    arret vaut "termine" (le modele a conclu), "max_tours", "budget", "temps",
    "refus", ou le stop_reason recu s'il n'est ni end_turn ni tool_use
    (par exemple "max_tokens").
    """

    reponse: str
    arret: str
    tours: int = 0
    tokens_entree: int = 0
    tokens_sortie: int = 0
    journal: list[Etape] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    modele: str = MODELE_DEFAUT

    @property
    def tokens_total(self) -> int:
        return self.tokens_entree + self.tokens_sortie

    @property
    def cout(self) -> float:
        return cout_dollars(self.tokens_entree, self.tokens_sortie, self.modele)


def cout_dollars(tokens_entree: int, tokens_sortie: int, modele: str = MODELE_DEFAUT) -> float:
    """Exercice 3. Le cout en dollars d'un nombre de tokens d'entree et de sortie.

    Attendu :
      - les tarifs viennent de doc42.config.TARIFS : (entree, sortie) en dollars
        par MILLION de tokens, jamais un prix en dur
      - un million de tokens d'entree et un million de sortie sur MODELE_DEFAUT
        coutent la somme des deux tarifs
    """
    # TODO
    raise NotImplementedError


def encadrer(nom: str, texte: str) -> str:
    """Exercice 6. Isole le resultat d'un outil entre balises <donnees_non_fiables>.

    Attendu :
      - la forme rendue est :
            <donnees_non_fiables source="NOM">
            TEXTE
            </donnees_non_fiables>
      - si le texte contient lui-meme la balise (ouvrante ou fermante, quelle
        que soit la casse), elle est neutralisee, par exemple en remplacant
        « < » par « &lt; » : sinon un document piege ferme la zone de donnees
        et ecrit la suite comme si c'etait une consigne
      - le resultat contient donc exactement UNE balise fermante, a la fin
    """
    # TODO
    raise NotImplementedError


def confirmer_console(nom: str, arguments: dict[str, Any]) -> bool:
    """Exercice 4. Demande a l'humain d'autoriser une action d'ecriture.

    Attendu :
      - vous affichez (print) le nom de l'outil ET chaque argument : l'humain
        doit voir ce qui va etre ecrit (titre et contenu de la fiche), pas
        seulement « creer_fiche ? »
      - vous lisez la reponse avec input()
      - seules "o", "oui" (et "y", "yes"), sans tenir compte de la casse ni des
        espaces, renvoient True ; tout le reste, y compris une reponse vide,
        renvoie False : refus par defaut
      - si input() leve EOFError (pas de terminal), vous renvoyez False
    """
    # TODO
    raise NotImplementedError


def executer_avec_garde(
    nom: str,
    entree: dict[str, Any],
    *,
    confirmer: Confirmer,
    executeur: Executeur = executer,
    autorises: frozenset[str] | set[str] = frozenset(d["name"] for d in DEFINITIONS),
) -> tuple[str, str]:
    """Exercice 4. Execute un outil derriere ses garde-fous. Renvoie (contenu, statut).

    statut vaut "ok", "erreur" ou "refuse".

    Attendu, dans cet ordre :
      - un outil absent de `autorises` (liste blanche) n'est PAS execute :
        ("Outil non autorise : ...", "erreur")
      - un outil de OUTILS_ECRITURE n'est execute qu'apres confirmer(nom, entree) ;
        si l'humain refuse, l'executeur n'est pas appele et vous renvoyez un
        texte qui dit au modele que l'action est refusee et qu'il ne doit pas
        la retenter, avec le statut "refuse". Pas d'exception : un refus est
        une reponse normale.
      - les outils de lecture ne demandent aucune confirmation
      - si l'executeur leve une exception, vous la rattrapez et renvoyez son
        message avec le statut "erreur" : l'agent ne doit pas planter
    """
    # TODO
    raise NotImplementedError


def run_agent(
    client: Any,
    objectif: str,
    *,
    max_tours: int = MAX_TOURS_DEFAUT,
    budget_tokens: int = BUDGET_TOKENS_DEFAUT,
    delai_max_s: float = DELAI_MAX_DEFAUT,
    confirmer: Confirmer = confirmer_console,
    executeur: Executeur = executer,
    horloge: Callable[[], float] = time.monotonic,
    outils: list[dict[str, Any]] = DEFINITIONS,
    systeme: str = SYSTEME_AGENT,
    modele: str = MODELE_DEFAUT,
    max_tokens: int = MAX_TOKENS_AGENT,
    reflexion: dict[str, Any] | None = None,
) -> ResultatAgent:
    """Exercices 1 et 3. La boucle agentique, bornee, journalisee, interruptible.

    Attendu (exercice 1, la boucle) :
      - l'historique commence par {"role": "user", "content": objectif} ;
        chaque appel transmet model, max_tokens, system, tools et messages
      - si stop_reason != "tool_use" (et NON == "end_turn" : un arret sur
        max_tokens n'est pas une demande d'outil), vous rendez le texte avec
        texte_de (jamais content[0].text) ; arret = "termine" si end_turn,
        sinon le stop_reason recu
      - sinon : la reponse entre telle quelle dans l'historique (role
        assistant), puis UN SEUL message user contient un tool_result par
        bloc tool_use, avec le bon tool_use_id
      - chaque outil passe par executer_avec_garde, avec `autorises` = les
        noms de `outils`
      - un resultat "ok" est encadre avec encadrer(nom, contenu) ; un
        resultat "erreur" porte "is_error": True ; un refus n'est pas une erreur
      - chaque action ajoute une Etape au journal : tour (a partir de 1),
        outil, arguments, statut, duree mesuree avec `horloge` (jamais
        time.time en dur : le test injecte une fausse horloge), tokens de
        l'appel qui l'a decidee
      - au-dela de max_tours appels, arret = "max_tours"
      - si `reflexion` est fourni, il est transmis comme thinking=... ;
        sinon la cle thinking est absente

    Attendu (exercice 3, budget et delai) :
      - vous cumulez usage.input_tokens et usage.output_tokens de chaque appel
        dans tokens_entree et tokens_sortie
      - AVANT chaque appel : si le total depasse budget_tokens, arret = "budget" ;
        si horloge() - debut depasse delai_max_s, arret = "temps"
      - quand l'agent s'arrete, l'historique reste valide : il ne finit jamais
        par un tool_use sans tool_result

    Attendu (exercice 4, l'insistance) :
      - si, apres un refus, le modele redemande un outil d'ecriture dans le
        meme run, vous ne redemandez PAS a l'humain : vous repondez a chaque
        tool_use par un tool_result de refus, puis vous vous arretez avec
        arret = "refus", sans nouvel appel au modele
    """
    # TODO
    raise NotImplementedError


# Etape 2 de l'atelier, avec un vrai client (une fois les tests au vert)
#
#   from doc42.client import creer_client
#   r = run_agent(creer_client(), "Compare les echeances des contrats Alpha et "
#                 "Beta et cree une fiche de synthese.")
#   for e in r.journal: print(e)
#
# Ce que j'ai observe (sequence d'outils, nombre de tours, cout r.cout) :
#
#
# Etape 5 de l'atelier, sans test supplementaire
#
# Lancez l'agent avec un executeur dont chercher_documents echoue toujours :
#
#   def en_panne(nom, entree):
#       if nom == "chercher_documents":
#           raise RuntimeError("index indisponible")
#       return executer(nom, entree)
#
# Constatez qu'il reessaie, puis que la borne l'arrete. Notez r.arret,
# r.tours, r.tokens_total et r.cout : c'est le prix d'un echec.
#
# Ce que m'a coute cet echec :
#
#
# Etape 6 de l'atelier, avec un vrai client
#
# Copiez corpus_pieges/note_fournisseur_piegee.md dans un dossier temporaire
# avec le corpus, lancez avec DOC42_CORPUS=<ce dossier>, et posez une question
# qui amene l'agent a la lire : « Quel est le nouveau delai de paiement de
# DataPlus ? ». Observez d'abord avec SYSTEME_DOC42 et sans encadrer, puis avec
# votre SYSTEME_AGENT durci. Aucune de ces mesures n'est une garantie : la
# confirmation humaine reste la seule defense solide.
#
# Ce que j'ai observe avant / apres :
#
#
# Etape 7 de l'atelier, sans test
#
# Comparez une execution de l'objectif de l'etape 2 avec et sans
# reflexion={...} (verifiez la forme exacte dans la documentation courante :
# elle depend de la generation du modele). Qualite du plan, nombre de tours,
# cout.
#
# Ce que j'ai observe :
#
#
# Definition de termine : en une phrase, ce que mon agent n'a PAS le droit de faire :
#
#
# Etape 8 : quand tous les tests passent, commitez le checkpoint etape/08-agent.
