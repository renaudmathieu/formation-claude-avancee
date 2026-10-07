"""Section 2, corrige commente.

Les commentaires expliquent le pourquoi, pas le comment : le comment est
dans le code.
"""

from __future__ import annotations

import base64
import mimetypes
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anthropic

from doc42.config import MAX_TOKENS_DEFAUT, MODELE_DEFAUT, SYSTEME_DOC42


def _texte_de(reponse: Any) -> str:
    # On concatene tous les blocs texte au lieu de prendre content[0].text.
    # Des la Section 4, une reponse peut commencer par un bloc tool_use et
    # cet index sauterait silencieusement sur le mauvais bloc.
    return "".join(bloc.text for bloc in reponse.content if bloc.type == "text")


def appel_simple(client: Any, question: str) -> str:
    reponse = client.messages.create(
        model=MODELE_DEFAUT,
        max_tokens=MAX_TOKENS_DEFAUT,
        system=SYSTEME_DOC42,
        messages=[{"role": "user", "content": question}],
    )
    return _texte_de(reponse)


class Conversation:
    def __init__(self, client: Any, systeme: str = SYSTEME_DOC42) -> None:
        self.client = client
        self.systeme = systeme
        self.messages: list[dict[str, Any]] = []

    def demander(self, texte: str) -> str:
        self.messages.append({"role": "user", "content": texte})

        # L'appel est fait AVANT d'ajouter la reponse assistant. Si l'appel
        # echoue, l'historique se termine sur un message user, ce qui est un
        # etat valide pour reessayer. Ajouter une reponse fictive casserait
        # l'alternance des roles au tour suivant.
        reponse = self.client.messages.create(
            model=MODELE_DEFAUT,
            max_tokens=MAX_TOKENS_DEFAUT,
            system=self.systeme,
            messages=self.messages,
        )

        sortie = _texte_de(reponse)
        self.messages.append({"role": "assistant", "content": sortie})
        return sortie


def appel_en_flux(client: Any, question: str) -> tuple[str, Any]:
    morceaux: list[str] = []
    with client.messages.stream(
        model=MODELE_DEFAUT,
        max_tokens=MAX_TOKENS_DEFAUT,
        system=SYSTEME_DOC42,
        messages=[{"role": "user", "content": question}],
    ) as flux:
        for fragment in flux.text_stream:
            morceaux.append(fragment)
            print(fragment, end="", flush=True)
        # get_final_message() n'est valide qu'apres avoir consomme le flux.
        # C'est la seule facon d'obtenir un usage complet.
        final = flux.get_final_message()
    return "".join(morceaux), final.usage


# La question a poser pour chaque exception : rejouer la meme requete
# peut-il donner un resultat different ?
#   429 : oui, la limite se libere avec le temps.
#   500 et 529 : oui, le probleme est cote serveur.
#   Connexion : oui, le reseau peut revenir.
#   400 : non, la requete est malformee, elle le restera.
#   401 : non, la cle est invalide, elle le restera.
REJOUABLES: tuple[type[Exception], ...] = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,
)


def avec_reprise(
    appel: Callable[[], Any],
    tentatives: int = 5,
    dormir: Callable[[float], None] = time.sleep,
) -> Any:
    derniere: Exception | None = None
    for essai in range(tentatives):
        try:
            return appel()
        except REJOUABLES as erreur:
            derniere = erreur
            if essai == tentatives - 1:
                break
            # Le bruit aleatoire evite que tous les processus reessaient a la
            # meme seconde et reconstruisent le pic qui a cause le 429.
            dormir(2**essai + random.uniform(0, 1))
    raise derniere


def analyser_document(client: Any, chemin: str | Path, question: str) -> str:
    chemin = Path(chemin)
    type_mime, _ = mimetypes.guess_type(chemin.name)
    if type_mime is None:
        raise ValueError(f"Type MIME indetermine pour {chemin.name}")

    donnees = base64.b64encode(chemin.read_bytes()).decode()
    genre = "document" if type_mime == "application/pdf" else "image"

    reponse = client.messages.create(
        model=MODELE_DEFAUT,
        max_tokens=2048,
        system=SYSTEME_DOC42,
        messages=[
            {
                "role": "user",
                # Le contenu devient une LISTE de blocs des qu'un fichier est joint.
                # Le fichier passe avant la question : le modele lit dans l'ordre.
                "content": [
                    {
                        "type": genre,
                        "source": {"type": "base64", "media_type": type_mime, "data": donnees},
                    },
                    {"type": "text", "text": question},
                ],
            }
        ],
    )
    return _texte_de(reponse)
