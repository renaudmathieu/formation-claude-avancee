"""Mesure un prompt d'extraction sur le jeu de test (section 3).

    uv run python evals/lancer.py                    # prompt courant (v2)
    uv run python evals/lancer.py --prompt v1        # le prompt de l'etape 1
    uv run python evals/lancer.py --sans-exemple     # v2 sans few-shot
    uv run python evals/lancer.py --prefill --modele rapide
    uv run python evals/lancer.py --tentatives 3     # avec relance

Un changement a la fois, une mesure a chaque fois. Reportez le taux dans
prompts/CHANGELOG.md. Appelle la vraie API : il faut ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Lance comme un script, Python ne voit que evals/ : on ajoute la racine.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ordre fige : hors checkpoint, ruff ne trouve pas doc42.extraction et le classe a part.
# isort: off
from doc42.client import creer_client
from doc42.config import MODELE_DEFAUT, MODELE_PROFOND, MODELE_RAPIDE, verifier
from doc42.extraction import (
    JEU_DEFAUT,
    VERSION_COURANTE,
    charger_jeu,
    charger_prompt,
    evaluer,
    resume,
)
# isort: on

MODELES = {"defaut": MODELE_DEFAUT, "rapide": MODELE_RAPIDE, "profond": MODELE_PROFOND}


def analyser(argv: list[str] | None = None) -> argparse.Namespace:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--prompt", default=VERSION_COURANTE, help="v1, v2... ou un chemin")
    parseur.add_argument("--sans-exemple", action="store_true", help="retire <examples>")
    parseur.add_argument("--prefill", action="store_true", help="preremplit la reponse par {")
    parseur.add_argument("--modele", choices=sorted(MODELES), default="defaut")
    parseur.add_argument("--tentatives", type=int, default=1, help="1 = sans relance")
    parseur.add_argument("--jeu", default=str(JEU_DEFAUT))
    return parseur.parse_args(argv)


def main(argv: list[str] | None = None, client: Any = None) -> int:
    options = analyser(argv)
    if client is None:
        try:
            verifier()
        except RuntimeError as erreur:
            print(erreur, file=sys.stderr)
            return 2
        client = creer_client()
    systeme = charger_prompt(options.prompt, exemple=not options.sans_exemple)
    jeu = charger_jeu(options.jeu)

    print(
        f"Prompt {options.prompt}{' sans exemple' if options.sans_exemple else ''}, "
        f"modele {MODELES[options.modele]}, prefill {'oui' if options.prefill else 'non'}, "
        f"{options.tentatives} tentative(s), {len(jeu)} documents."
    )
    rapport = evaluer(
        client,
        jeu,
        systeme,
        prefill=options.prefill,
        tentatives=options.tentatives,
        modele=MODELES[options.modele],
    )
    for resultat in rapport.resultats:
        print(f"  {'ok   ' if resultat.reussi else 'ECHEC'}  {resultat.document}")
    print()
    print(resume(rapport))
    return 0


if __name__ == "__main__":
    sys.exit(main())
