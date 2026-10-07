"""Observabilite de Doc42 : un log JSON par appel, avec son cout (section 10).

Le ClientInstrumente se presente comme un client Anthropic : on le passe a
doc42.client (appel_simple, Conversation, analyser_document) et aux boucles
des sections 4 et 8 sans modifier leur code.

Agreger un journal :

    uv run python -m doc42.observabilite journaux/appels.jsonl

Le journal ne contient que des metadonnees (modele, tokens, cout, latence,
version de prompt), jamais le texte des conversations ni une cle API.
"""

from __future__ import annotations

import copy
import json
import logging
import math
import re
import sys
import time
import uuid
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from doc42.config import FACTEUR_CACHE_ECRIT, FACTEUR_CACHE_LU, TARIFS

JOURNAL = logging.getLogger("doc42.appels")

# Au moins 8 caracteres apres le prefixe : une vraie cle, pas "sk-ant-..." dans une doc.
MOTIF_CLE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")


def masquer_secrets(texte: str) -> str:
    """Remplace toute cle API Anthropic par "sk-ant-***"."""
    return MOTIF_CLE.sub("sk-ant-***", texte)


def _jetons(usage: Any, champ: str) -> int:
    # Le SDK rend None pour les champs de cache inutilises.
    return int(getattr(usage, champ, 0) or 0)


def cout_appel(modele: str, usage: Any) -> float:
    """Cout en dollars d'un appel : entree, sortie, cache lu, cache ecrit.

    Raises:
        ValueError: Si le modele n'a pas de tarif dans doc42.config.TARIFS.
    """
    if modele not in TARIFS:
        raise ValueError(f"Pas de tarif pour {modele!r} dans doc42.config.TARIFS.")
    entree, sortie = TARIFS[modele]
    # input_tokens n'inclut pas les tokens de cache : trois postes distincts.
    total = (
        _jetons(usage, "input_tokens") * entree
        + _jetons(usage, "cache_read_input_tokens") * entree * FACTEUR_CACHE_LU
        + _jetons(usage, "cache_creation_input_tokens") * entree * FACTEUR_CACHE_ECRIT
        + _jetons(usage, "output_tokens") * sortie
    )
    return total / 1_000_000


def maintenant_utc() -> datetime:
    return datetime.now(UTC)


def nouvel_identifiant() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def _vers_logging(ligne: str) -> None:
    JOURNAL.info(ligne)


def journal_fichier(chemin: str | Path) -> Callable[[str], None]:
    """Un `ecrire` qui ajoute chaque ligne a un fichier JSON Lines.

    Placez ce fichier hors du depot ou dans un dossier ignore par Git.
    """
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)

    def ecrire(ligne: str) -> None:
        with chemin.open("a", encoding="utf-8") as fichier:
            fichier.write(ligne + "\n")

    return ecrire


def lire_journal(chemin: str | Path) -> Iterator[str]:
    with Path(chemin).open(encoding="utf-8") as fichier:
        yield from fichier


class ClientInstrumente:
    """Enrobe un client Anthropic et journalise chaque messages.create en JSON.

    Tout ce qui depend du temps est injectable (horloge, chrono, generer_id)
    pour des tests deterministes. Sans `ecrire`, les lignes partent dans le
    logger "doc42.appels".
    """

    CONTEXTE = ("feature", "prompt_version", "user_id", "question_id")

    def __init__(
        self,
        client: Any,
        ecrire: Callable[[str], None] | None = None,
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
        self.ecrire = ecrire or _vers_logging
        self.feature = feature
        self.prompt_version = prompt_version
        self.user_id = user_id
        self.question_id = question_id
        self.horloge = horloge
        self.chrono = chrono
        self.generer_id = generer_id
        self.messages = self

    def avec(self, **contexte: Any) -> ClientInstrumente:
        """Une copie qui partage client et journal, avec un autre contexte."""
        inconnus = set(contexte) - set(self.CONTEXTE)
        if inconnus:
            raise TypeError(f"Contexte inconnu : {sorted(inconnus)}")
        copie = copy.copy(self)
        for cle, valeur in contexte.items():
            setattr(copie, cle, valeur)
        copie.messages = copie
        return copie

    def create(self, **kwargs: Any) -> Any:
        ligne: dict[str, Any] = {
            "timestamp": self.horloge().isoformat(timespec="milliseconds"),
            "event": "claude_call",
            "request_id": self.generer_id(),
            "question_id": self.question_id,
            "user_id": self.user_id,
            "feature": self.feature,
            "prompt_version": self.prompt_version,
            "model": kwargs.get("model"),
            "max_tokens": kwargs.get("max_tokens"),
        }
        debut = self.chrono()
        try:
            reponse = self.client.messages.create(**kwargs)
        except Exception as erreur:
            # On observe puis on relance : le tri rejouable ou non reste a avec_reprise.
            ligne.update(
                level="error",
                success=False,
                latency_ms=round((self.chrono() - debut) * 1000),
                cost_usd=0.0,
                error_type=type(erreur).__name__,
                error_message=masquer_secrets(str(erreur)),
            )
            self.ecrire(json.dumps(ligne, ensure_ascii=False))
            raise

        latence = round((self.chrono() - debut) * 1000)
        usage = reponse.usage
        try:
            cout: float | None = round(cout_appel(ligne["model"], usage), 6)
        except ValueError:
            cout = None  # l'observabilite ne casse jamais l'appel
        ligne.update(
            level="info",
            success=True,
            latency_ms=latence,
            input_tokens=_jetons(usage, "input_tokens"),
            output_tokens=_jetons(usage, "output_tokens"),
            cache_read_input_tokens=_jetons(usage, "cache_read_input_tokens"),
            cache_creation_input_tokens=_jetons(usage, "cache_creation_input_tokens"),
            stop_reason=getattr(reponse, "stop_reason", None),
            cost_usd=cout,
        )
        self.ecrire(json.dumps(ligne, ensure_ascii=False))
        return reponse


def _centile(valeurs: list[float], p: float) -> float | None:
    if not valeurs:
        return None
    triees = sorted(valeurs)
    return triees[max(1, math.ceil(p / 100 * len(triees))) - 1]


def agreger(lignes: Iterable[str | dict[str, Any]]) -> dict[str, Any]:
    """Bilan d'un journal : cout total, par fonctionnalite, par version, par question."""
    appels: list[dict[str, Any]] = []
    for ligne in lignes:
        if isinstance(ligne, str):
            if not ligne.strip():
                continue
            ligne = json.loads(ligne)
        if ligne.get("event") == "claude_call":
            appels.append(ligne)

    par_feature: dict[str, dict[str, float]] = {}
    par_version: dict[str, dict[str, float]] = {}
    par_question: dict[str, float] = {}
    total = 0.0
    for appel in appels:
        cout = appel.get("cost_usd") or 0.0
        total += cout
        for cle, table in (("feature", par_feature), ("prompt_version", par_version)):
            case = table.setdefault(str(appel.get(cle)), {"appels": 0, "cout_usd": 0.0})
            case["appels"] += 1
            case["cout_usd"] += cout
        question = appel.get("question_id") or appel.get("request_id")
        par_question[question] = par_question.get(question, 0.0) + cout

    for table in (par_feature, par_version):
        for case in table.values():
            case["cout_usd"] = round(case["cout_usd"], 6)
    latences = [a["latency_ms"] for a in appels if a.get("latency_ms") is not None]
    return {
        "appels": len(appels),
        "echecs": sum(1 for a in appels if not a.get("success")),
        "couts_inconnus": sum(1 for a in appels if a.get("success") and a.get("cost_usd") is None),
        "cout_total_usd": round(total, 6),
        "par_feature": par_feature,
        "par_version": par_version,
        "questions": len(par_question),
        "cout_moyen_question_usd": round(total / len(par_question), 6) if par_question else 0.0,
        "latence_p50_ms": _centile(latences, 50),
        "latence_p99_ms": _centile(latences, 99),
    }


def main(arguments: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 1:
        print("Usage : python -m doc42.observabilite <journal.jsonl>", file=sys.stderr)
        return 2
    print(json.dumps(agreger(lire_journal(arguments[0])), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
