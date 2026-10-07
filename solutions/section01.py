"""Section 1, corrige commente.

Les commentaires expliquent le pourquoi, pas le comment : le comment est
dans le code.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from doc42.config import (
    MAX_TOKENS_DEFAUT,
    MODELE_DEFAUT,
    MODELE_PROFOND,
    MODELE_RAPIDE,
    TARIFS,
)
from doc42.corpus import Document
from doc42.outils import normaliser

# --- Donne : ne pas modifier -------------------------------------------------

MODELES: tuple[str, ...] = (MODELE_RAPIDE, MODELE_DEFAUT, MODELE_PROFOND)

QUESTION_PREMIER_APPEL = "Presente-toi en une phrase."
CONSIGNE_RESUME = "Resume ce document en trois puces factuelles."
CONSIGNE_RECLAMATION = "Ce message est-il une reclamation ? Reponds par oui ou non."
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


# --- Corrige -----------------------------------------------------------------


def _texte_de(reponse: Any) -> str:
    # content[0].text suffirait aujourd'hui. On concatene quand meme : en
    # section 4, une reponse peut commencer par un bloc tool_use, et l'index
    # 0 tomberait sans bruit sur le mauvais bloc.
    return "".join(bloc.text for bloc in reponse.content if bloc.type == "text")


def diagnostiquer(
    environ: Mapping[str, str] | None = None,
    version: tuple[int, ...] = tuple(sys.version_info[:2]),
) -> list[str]:
    # L'environnement est injectable : un test qui lirait os.environ dirait
    # "vert" chez le formateur et "rouge" chez le stagiaire.
    environ = os.environ if environ is None else environ
    problemes: list[str] = []

    cle = environ.get("ANTHROPIC_API_KEY", "")
    if not cle:
        problemes.append(
            "ANTHROPIC_API_KEY absente : copiez .env.example en .env et renseignez votre cle."
        )
    elif not cle.startswith("sk-ant-") or any(c in cle for c in " \"'"):
        # On decrit le defaut, jamais la valeur : ce message finira dans un
        # terminal partage ou un ticket, et une cle affichee est une cle a revoquer.
        problemes.append(
            "ANTHROPIC_API_KEY mal formee : elle doit commencer par sk-ant- "
            "et ne contenir ni espace ni guillemet."
        )

    if tuple(version[:2]) < (3, 12):
        problemes.append("Python 3.12+ requis pour le fil rouge Doc42.")

    # Un modele sans tarif rendrait le tableau comparatif faux. Autant le
    # savoir avant l'atelier qu'au milieu.
    for modele in MODELES:
        if modele not in TARIFS:
            problemes.append(f"Pas de tarif pour {modele} dans doc42.config.TARIFS.")

    return problemes


def premier_appel(client: Any, question: str = QUESTION_PREMIER_APPEL) -> tuple[str, Any, str]:
    # Le modele vient de config.py : le jour ou la gamme change, on modifie
    # un fichier, pas dix.
    reponse = client.messages.create(
        model=MODELE_DEFAUT,
        max_tokens=MAX_TOKENS_DEFAUT,
        messages=[{"role": "user", "content": question}],
    )
    # usage des le premier appel : le reflexe de regarder ce que coute un
    # appel s'installe maintenant ou jamais. stop_reason dit si la reponse
    # est complete ("end_turn") ou coupee ("max_tokens").
    return _texte_de(reponse), reponse.usage, reponse.stop_reason


def cout_estime(modele: str, tokens_entree: int, tokens_sortie: int) -> float:
    if modele not in TARIFS:
        # Un cout de zero passerait inapercu dans le tableau et ferait gagner
        # le mauvais modele. Mieux vaut une erreur qui dit quoi corriger.
        raise ValueError(f"Pas de tarif pour {modele} : mettez a jour TARIFS dans doc42.config.")
    entree, sortie = TARIFS[modele]
    # Les tarifs sont exprimes par MILLION de tokens.
    return (tokens_entree * entree + tokens_sortie * sortie) / 1_000_000


def mesurer(
    client: Any,
    modele: str,
    consigne: str,
    horloge: Callable[[], float] = time.perf_counter,
    systeme: str | None = None,
) -> Mesure:
    parametres: dict[str, Any] = {
        "model": modele,
        # Meme plafond pour tous : sinon on compare des plafonds, pas des modeles.
        "max_tokens": MAX_TOKENS_DEFAUT,
        "messages": [{"role": "user", "content": consigne}],
    }
    # On n'envoie pas system=None : le parametre est facultatif, et l'absence
    # n'est pas la meme chose qu'une valeur nulle pour l'API.
    if systeme is not None:
        parametres["system"] = systeme

    # perf_counter et non time.time : il est monotone, une mise a l'heure
    # de la machine ne fausse pas la mesure. Et il est injecte, pour que le
    # test soit deterministe.
    debut = horloge()
    reponse = client.messages.create(**parametres)
    fin = horloge()

    usage = reponse.usage
    return Mesure(
        modele=modele,
        texte=_texte_de(reponse),
        tokens_entree=usage.input_tokens,
        tokens_sortie=usage.output_tokens,
        duree=fin - debut,
        cout=cout_estime(modele, usage.input_tokens, usage.output_tokens),
        stop_reason=reponse.stop_reason,
    )


def comparer(
    client: Any,
    consigne: str,
    modeles: Sequence[str] = MODELES,
    horloge: Callable[[], float] = time.perf_counter,
    systeme: str | None = None,
) -> list[Mesure]:
    # Une seule variable a la fois : le modele. Consigne, systeme et plafond
    # sont identiques, sinon on ne sait plus ce qu'on mesure.
    return [mesurer(client, modele, consigne, horloge, systeme) for modele in modeles]


def tableau(mesures: Sequence[Mesure]) -> str:
    lignes = [
        "| Modele | Entree | Sortie | Cout ($) | Duree (s) | Qualite |",
        "|---|---|---|---|---|---|",
    ]
    for m in mesures:
        # La qualite reste vide : c'est un jugement humain, et c'est lui qui
        # decide si l'ecart de cout est justifie.
        lignes.append(
            f"| {m.modele} | {m.tokens_entree} | {m.tokens_sortie} "
            f"| {m.cout:.6f} | {m.duree:.2f} |  |"
        )
    return "\n".join(lignes)


# Le tableau de la section 1.1, en code. C'est un point de depart, pas une
# verite : la section 10 le remplacera par une regle mesuree.
_ROUTAGE: dict[str, str] = {
    "tri": MODELE_RAPIDE,
    "classification": MODELE_RAPIDE,
    "routage": MODELE_RAPIDE,
    "moderation": MODELE_RAPIDE,
    "support": MODELE_RAPIDE,
    "analyse": MODELE_DEFAUT,
    "redaction": MODELE_DEFAUT,
    # Le tableau dit "Sonnet / Opus" : on part du defaut, on monte si besoin.
    "code": MODELE_DEFAUT,
    "raisonnement": MODELE_PROFOND,
    "recherche": MODELE_PROFOND,
    "agent": MODELE_PROFOND,
}


def choisir_modele(tache: str) -> str:
    # Par defaut, le plus leger : sur une tache simple, le modele le plus
    # cher ne repond pas mieux, il repond plus cher.
    return _ROUTAGE.get(normaliser(tache).strip(), MODELE_RAPIDE)


def monter_en_gamme(modele: str) -> str | None:
    # On monte d'un palier quand on a CONSTATE un echec, pas par precaution.
    if modele not in MODELES:
        raise ValueError(f"Modele inconnu : {modele}. Les paliers sont dans doc42.config.")
    rang = MODELES.index(modele)
    return MODELES[rang + 1] if rang + 1 < len(MODELES) else None
