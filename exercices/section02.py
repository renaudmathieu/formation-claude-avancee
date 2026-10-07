"""Section 2, atelier. Cinq exercices, une heure.

Completez les fonctions marquees TODO, puis lancez :

    uv run pytest tests/test_section02.py -v

Les enonces sont dans les docstrings. Vous n'avez pas besoin de revenir
sur Notion pendant l'atelier.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anthropic  # noqa: F401  (vous en aurez besoin pour REJOUABLES)

from doc42.config import MAX_TOKENS_DEFAUT, MODELE_DEFAUT, SYSTEME_DOC42  # noqa: F401


def appel_simple(client: Any, question: str) -> str:
    """Envoie `question` a Claude et retourne le TEXTE de la reponse.

    Attendu :
      - modele, max_tokens et system viennent de doc42.config, jamais en dur
      - la valeur retournee est une chaine, pas l'objet reponse
      - vous concatenez tous les blocs de type "text" plutot que de prendre
        content[0].text (des la Section 4, content[0] peut etre un tool_use)
    """
    # TODO
    raise NotImplementedError


class Conversation:
    """Conversation multi-tours.

    L'API est sans etat. Si vous n'accumulez pas l'historique vous-meme,
    le troisieme tour ne saura pas ce qui a ete dit au premier.

    Attendu :
      - self.messages accumule les tours user ET assistant, dans l'ordre
      - demander() retourne le texte et met a jour l'historique
      - deux messages "user" consecutifs sont refuses par l'API : si un appel
        echoue, n'ajoutez pas de reponse assistant fictive
    """

    def __init__(self, client: Any, systeme: str = SYSTEME_DOC42) -> None:
        self.client = client
        self.systeme = systeme
        self.messages: list[dict[str, Any]] = []

    def demander(self, texte: str) -> str:
        # TODO
        raise NotImplementedError


def appel_en_flux(client: Any, question: str) -> tuple[str, Any]:
    """Affiche la reponse au fil de l'eau et retourne (texte complet, usage).

    Attendu :
      - vous utilisez client.messages.stream (pas .create)
      - vous affichez chaque fragment avec print(..., end="", flush=True)
      - vous recuperez usage via get_final_message(), APRES la boucle

    Piege : usage n'est complet qu'a la fin.
    """
    # TODO
    raise NotImplementedError


# TODO : completez ce tuple. Question a vous poser pour chaque exception :
# est-ce que rejouer la meme requete a une chance de donner un resultat
# different ? Si non, elle n'a rien a faire ici.
REJOUABLES: tuple[type[Exception], ...] = ()


def avec_reprise(
    appel: Callable[[], Any],
    tentatives: int = 5,
    dormir: Callable[[float], None] = time.sleep,
) -> Any:
    """Rejoue `appel` en attente exponentielle avec bruit aleatoire.

    Attendu :
      - seules les exceptions de REJOUABLES sont rattrapees
      - une BadRequestError (400) remonte immediatement, sans aucun essai
        supplementaire : le test le verifie explicitement
      - l'attente est 2**essai plus un bruit aleatoire entre 0 et 1 seconde
      - vous appelez `dormir`, pas time.sleep directement : le test injecte
        une fonction factice pour ne pas attendre reellement
    """
    # TODO
    raise NotImplementedError


def analyser_document(client: Any, chemin: str | Path, question: str) -> str:
    """Envoie un PDF ou une image avec une question, retourne la reponse.

    Attendu :
      - le contenu du message est une LISTE de blocs, pas une chaine
      - le bloc du fichier est place AVANT le bloc texte
      - media_type est deduit de l'extension, pas code en dur
      - un PDF utilise le type "document", une image le type "image"
    """
    # TODO
    raise NotImplementedError


# Etape 6 de l'atelier, sans test
#
# Demandez a Claude : "ecris-moi une fonction de retry pour l'API Anthropic"
# Comparez sa reponse a votre exercice 4. Dans la grande majorite des cas,
# la reponse generee attrape toutes les exceptions sans distinguer les
# rejouables des non rejouables.
#
# Ce que j'ai observe :
#
# Ce que je corrigerais avant de le mettre en production :
