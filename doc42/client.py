"""Client de reference de Doc42, repris en sections 4 et 8.

C'est le corrige de la section 2, range dans le paquet pour que les sections
suivantes s'appuient dessus meme si votre propre exercice n'est pas termine.
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

# Rejouer peut donner un resultat different : limite de debit, erreur serveur, reseau.
# Une 400 ou une 401 donneraient exactement la meme erreur.
REJOUABLES: tuple[type[Exception], ...] = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,
)


def creer_client() -> anthropic.Anthropic:
    """Le vrai client. La cle vient de ANTHROPIC_API_KEY (fichier .env)."""
    return anthropic.Anthropic()


def texte_de(reponse: Any) -> str:
    """Concatene les blocs texte d'une reponse ; content[0] peut etre un tool_use."""
    return "".join(bloc.text for bloc in reponse.content if bloc.type == "text")


def avec_reprise(
    appel: Callable[[], Any],
    tentatives: int = 5,
    dormir: Callable[[float], None] = time.sleep,
) -> Any:
    """Rejoue `appel` en attente exponentielle avec bruit, pour les seules erreurs rejouables."""
    derniere: Exception | None = None
    for essai in range(tentatives):
        try:
            return appel()
        except REJOUABLES as erreur:
            derniere = erreur
            if essai == tentatives - 1:
                break
            dormir(2**essai + random.uniform(0, 1))
    raise derniere


def appel_simple(client: Any, question: str, systeme: str = SYSTEME_DOC42) -> str:
    """Une question, une reponse texte."""
    reponse = client.messages.create(
        model=MODELE_DEFAUT,
        max_tokens=MAX_TOKENS_DEFAUT,
        system=systeme,
        messages=[{"role": "user", "content": question}],
    )
    return texte_de(reponse)


class Conversation:
    """Conversation multi-tours : l'API est sans etat, l'historique est ici."""

    def __init__(self, client: Any, systeme: str = SYSTEME_DOC42) -> None:
        self.client = client
        self.systeme = systeme
        self.messages: list[dict[str, Any]] = []

    def demander(self, texte: str) -> str:
        self.messages.append({"role": "user", "content": texte})
        reponse = self.client.messages.create(
            model=MODELE_DEFAUT,
            max_tokens=MAX_TOKENS_DEFAUT,
            system=self.systeme,
            messages=self.messages,
        )
        sortie = texte_de(reponse)
        self.messages.append({"role": "assistant", "content": sortie})
        return sortie


def bloc_fichier(chemin: str | Path) -> dict[str, Any]:
    """Le bloc de contenu d'un PDF ou d'une image, type MIME deduit de l'extension."""
    chemin = Path(chemin)
    type_mime, _ = mimetypes.guess_type(chemin.name)
    if type_mime is None:
        raise ValueError(f"Type MIME indetermine pour {chemin.name}")
    donnees = base64.b64encode(chemin.read_bytes()).decode()
    genre = "document" if type_mime == "application/pdf" else "image"
    return {"type": genre, "source": {"type": "base64", "media_type": type_mime, "data": donnees}}


def analyser_document(client: Any, chemin: str | Path, question: str) -> str:
    """Envoie un fichier puis la question (le fichier d'abord), renvoie la reponse texte."""
    reponse = client.messages.create(
        model=MODELE_DEFAUT,
        max_tokens=2048,
        system=SYSTEME_DOC42,
        messages=[
            {"role": "user", "content": [bloc_fichier(chemin), {"type": "text", "text": question}]}
        ],
    )
    return texte_de(reponse)
