"""Faux client Anthropic, deterministe et hors ligne, partage par tous les tests.

Il enregistre tout ce qu'on lui envoie : les tests verifient l'envoi, pas la
reponse du modele. On evalue le code du stagiaire, pas Claude.

Deux facons de choisir ce qu'il repond :
  - par defaut, une regle simple (les echeances si on parle d'echeance ou de paiement) ;
  - avec client.programmer(r1, r2, ...), une file de reponses rendues dans l'ordre,
    pour scenariser une boucle d'outils ou un agent.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Self


@dataclass
class BlocTexte:
    text: str
    type: str = "text"


@dataclass
class BlocOutil:
    """Un bloc tool_use, tel que le SDK le rend."""

    name: str
    input: dict[str, Any]
    id: str = "toolu_faux_1"
    type: str = "tool_use"


@dataclass
class Usage:
    input_tokens: int = 42
    output_tokens: int = 17
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class FausseReponse:
    content: list[Any]
    usage: Usage = field(default_factory=Usage)
    stop_reason: str = "end_turn"
    model: str = "faux"


def texte(contenu: str, **kwargs: Any) -> FausseReponse:
    """Une reponse texte simple."""
    return FausseReponse(content=[BlocTexte(contenu)], **kwargs)


def outil(
    nom: str, entree: dict[str, Any], id: str = "toolu_faux_1", **kwargs: Any
) -> FausseReponse:
    """Une reponse qui demande un appel d'outil (stop_reason tool_use)."""
    return FausseReponse(
        content=[BlocOutil(name=nom, input=entree, id=id)], stop_reason="tool_use", **kwargs
    )


class FauxFlux:
    def __init__(self, morceaux: list[str]) -> None:
        self._morceaux = morceaux
        self._consomme = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    @property
    def text_stream(self):
        self._consomme = True
        yield from self._morceaux

    def get_final_message(self) -> FausseReponse:
        if not self._consomme:
            raise RuntimeError(
                "get_final_message() appele avant d'avoir consomme le flux. "
                "usage n'est complet qu'a la fin."
            )
        return FausseReponse(content=[BlocTexte("".join(self._morceaux))])


class FauxMessages:
    def __init__(self, parent: FauxClient) -> None:
        self.parent = parent

    def create(self, **kwargs: Any) -> FausseReponse:
        self.parent.enregistrer(kwargs)
        return self.parent.reponse_pour(kwargs)

    def stream(self, **kwargs: Any) -> FauxFlux:
        self.parent.enregistrer(kwargs)
        return FauxFlux(["Doc42 ", "analyse ", "le document."])

    def count_tokens(self, **kwargs: Any) -> Any:
        self.parent.enregistrer(kwargs)
        total = (
            len(aplatir(kwargs.get("messages", []))) // 4 + len(str(kwargs.get("system", ""))) // 4
        )
        return Usage(input_tokens=total, output_tokens=0)


class FauxClient:
    """Enregistre tout ce qu'on lui envoie et rend des reponses deterministes."""

    def __init__(self) -> None:
        self.appels: list[dict[str, Any]] = []
        self.messages = FauxMessages(self)
        self._file: list[Any] = []

    def programmer(self, *reponses: Any) -> FauxClient:
        """Ajoute des reponses a rendre dans l'ordre, avant la regle par defaut.

        Une reponse peut etre une exception : elle est alors levee a l'appel.
        """
        self._file.extend(reponses)
        return self

    def enregistrer(self, kwargs: dict[str, Any]) -> None:
        # Copie profonde : l'historique du stagiaire est mute apres l'appel,
        # sans copie on observerait l'etat final et pas l'etat envoye.
        self.appels.append(copy.deepcopy(kwargs))

    def reponse_pour(self, kwargs: dict[str, Any]) -> FausseReponse:
        if self._file:
            suivante = self._file.pop(0)
            if isinstance(suivante, BaseException):
                raise suivante
            return suivante
        aplati = aplatir(kwargs.get("messages", []))
        if "echeance" in aplati.lower() or "paiement" in aplati.lower():
            return texte("Echeances : 15/01/2027, 15/04/2027 et 15/07/2027.")
        return texte("Reponse de Doc42.")


def aplatir(messages: list[dict[str, Any]]) -> str:
    """Tout le texte d'une liste de messages, blocs texte et resultats d'outils compris."""
    morceaux: list[str] = []
    for message in messages:
        contenu = message.get("content")
        if isinstance(contenu, str):
            morceaux.append(contenu)
        elif isinstance(contenu, list):
            for bloc in contenu:
                if not isinstance(bloc, dict):
                    bloc = getattr(bloc, "__dict__", {})
                if bloc.get("type") == "text":
                    morceaux.append(bloc.get("text", ""))
                elif bloc.get("type") == "tool_result":
                    resultat = bloc.get("content", "")
                    morceaux.append(resultat if isinstance(resultat, str) else str(resultat))
    return "\n".join(morceaux)


def erreur_sdk(classe: type[Exception]) -> Exception:
    """Fabrique une exception du SDK sans passer par son constructeur.

    Les exceptions du SDK exigent un objet reponse HTTP complet. On s'en
    passe : ce qui compte pour le test, c'est le TYPE de l'exception.
    """
    erreur = classe.__new__(classe)
    Exception.__init__(erreur, classe.__name__)
    return erreur
