"""Compare les trois paliers de modeles sur la meme tache (section 1, etapes 3 et 4).

Appelle la vraie API : il faut ANTHROPIC_API_KEY dans .env. Six appels courts.

    uv run python -m scripts.comparer_modeles
    uv run python -m scripts.comparer_modeles contrat_alpha --concis

(avec -m depuis la racine du depot, pour que le paquet doc42 soit importable)

Affiche deux tableaux Markdown (resume d'un document, puis tache triviale) a
coller dans NOTES.md. La colonne Qualite est a remplir a la main.
"""

from __future__ import annotations

import argparse
import time
from typing import Any

import anthropic

from doc42.config import (
    MAX_TOKENS_DEFAUT,
    MODELE_DEFAUT,
    MODELE_PROFOND,
    MODELE_RAPIDE,
    TARIFS,
    verifier,
)
from doc42.corpus import trouver

MODELES = (MODELE_RAPIDE, MODELE_DEFAUT, MODELE_PROFOND)
CONSIGNE_RESUME = "Resume ce document en trois puces factuelles."
CONSIGNE_RECLAMATION = "Ce message est-il une reclamation ? Reponds par oui ou non."
MESSAGE_TRIVIAL = "Troisieme relance : la facture F2026-118 est toujours fausse."
SYSTEME_CONCIS = "Reponds en trois puces, sans introduction."


def cout_estime(modele: str, entree: int, sortie: int) -> float:
    """Cout en dollars, tarifs de doc42.config par million de tokens."""
    tarif_entree, tarif_sortie = TARIFS[modele]
    return (entree * tarif_entree + sortie * tarif_sortie) / 1_000_000


def mesurer(client: Any, modele: str, consigne: str, systeme: str | None) -> list[str]:
    """Un appel, une ligne de tableau : modele, entree, sortie, cout, duree."""
    parametres: dict[str, Any] = {
        "model": modele,
        "max_tokens": MAX_TOKENS_DEFAUT,
        "messages": [{"role": "user", "content": consigne}],
    }
    if systeme is not None:
        parametres["system"] = systeme
    debut = time.perf_counter()
    reponse = client.messages.create(**parametres)
    duree = time.perf_counter() - debut
    usage = reponse.usage
    cout = cout_estime(modele, usage.input_tokens, usage.output_tokens)
    texte = "".join(bloc.text for bloc in reponse.content if bloc.type == "text")
    print(f"\n--- {modele} ({reponse.stop_reason})\n{texte}")
    return [
        modele,
        str(usage.input_tokens),
        str(usage.output_tokens),
        f"{cout:.6f}",
        f"{duree:.2f}",
        "",
    ]


def tableau(lignes: list[list[str]]) -> str:
    entete = (
        "| Modele | Entree | Sortie | Cout ($) | Duree (s) | Qualite |\n|---|---|---|---|---|---|"
    )
    return "\n".join([entete, *("| " + " | ".join(ligne) + " |" for ligne in lignes)])


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("document", nargs="?", default="note_rh_teletravail")
    parseur.add_argument("--concis", action="store_true", help="bonus : prompt systeme concis")
    arguments = parseur.parse_args()

    verifier()
    document = trouver(arguments.document)
    if document is None:
        raise SystemExit(f"Document introuvable dans le corpus : {arguments.document}")

    client = anthropic.Anthropic()
    systeme = SYSTEME_CONCIS if arguments.concis else None
    taches = {
        f"Resume de {document.id}": f"{CONSIGNE_RESUME}\n\n{document.texte}",
        "Tache triviale": f"{CONSIGNE_RECLAMATION}\n\nMessage : {MESSAGE_TRIVIAL}",
    }
    resultats = {
        titre: [mesurer(client, modele, consigne, systeme) for modele in MODELES]
        for titre, consigne in taches.items()
    }
    for titre, lignes in resultats.items():
        print(f"\n## {titre}\n\n{tableau(lignes)}")


if __name__ == "__main__":
    main()
