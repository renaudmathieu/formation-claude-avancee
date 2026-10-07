"""Prompts versionnes de Doc42 (section 10).

    prompts/
      registre.json          {nom: {"courante": "v1", "versions": {"v1": "<sha256>"}}}
      <nom>.v1.md, .v2.md... une version publiee ne se retouche plus
      CHANGELOG.md           pourquoi chaque version (convention de la section 3)

L'identifiant nom@version#empreinte part dans chaque ligne de journal
(prompt_version) : une regression se relie a la version qui l'a introduite.

    uv run python -m doc42.prompts            verifie le registre
    uv run python -m doc42.prompts publier doc42_systeme nouveau.md
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from doc42.config import RACINE

DOSSIER_PROMPTS = RACINE / "prompts"


@dataclass(frozen=True)
class Prompt:
    nom: str
    version: str
    texte: str
    empreinte: str

    @property
    def identifiant(self) -> str:
        return f"{self.nom}@{self.version}#{self.empreinte[:8]}"


def _registre(dossier: Path) -> dict:
    chemin = dossier / "registre.json"
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def charger_prompt(
    nom: str, version: str = "courante", dossier: str | Path = DOSSIER_PROMPTS
) -> Prompt:
    """Charge un prompt et verifie qu'il n'a pas ete retouche depuis sa publication.

    Raises:
        KeyError: Nom ou version absents du registre.
        ValueError: Le fichier ne correspond plus a l'empreinte publiee.
    """
    dossier = Path(dossier)
    registre = _registre(dossier)
    if nom not in registre:
        raise KeyError(f"Prompt inconnu : {nom}")
    entree = registre[nom]
    version = entree["courante"] if version == "courante" else version
    if version not in entree["versions"]:
        raise KeyError(f"Version inconnue pour {nom} : {version}")
    brut = (dossier / f"{nom}.{version}.md").read_bytes()
    empreinte = hashlib.sha256(brut).hexdigest()
    if empreinte != entree["versions"][version]:
        raise ValueError(
            f"{nom}.{version}.md a ete modifie apres publication. "
            "Creez une nouvelle version au lieu de retoucher celle-ci."
        )
    return Prompt(nom, version, brut.decode("utf-8").strip(), empreinte)


def publier_prompt(
    nom: str, texte: str, dossier: str | Path = DOSSIER_PROMPTS, courante: bool = False
) -> Prompt:
    """Publie une nouvelle version (v1, v2...) et l'enregistre dans le registre.

    Par defaut la nouvelle version n'est PAS courante : on la bascule apres
    l'avoir evaluee (section 3), en changeant "courante" dans registre.json.
    """
    dossier = Path(dossier)
    registre = _registre(dossier)
    entree = registre.setdefault(nom, {"courante": None, "versions": {}})
    version = f"v{len(entree['versions']) + 1}"
    chemin = dossier / f"{nom}.{version}.md"
    dossier.mkdir(parents=True, exist_ok=True)
    if chemin.exists():
        raise FileExistsError(f"{chemin} existe deja : registre et dossier sont desynchronises.")
    chemin.write_text(texte.strip() + "\n", encoding="utf-8")
    entree["versions"][version] = hashlib.sha256(chemin.read_bytes()).hexdigest()
    if courante or entree["courante"] is None:
        entree["courante"] = version
    (dossier / "registre.json").write_text(
        json.dumps(registre, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return charger_prompt(nom, version, dossier)


def verifier_registre(dossier: str | Path = DOSSIER_PROMPTS) -> list[str]:
    """Charge toutes les versions publiees ; rend la liste des problemes (vide si tout va bien)."""
    problemes = []
    for nom, entree in _registre(Path(dossier)).items():
        for version in entree["versions"]:
            try:
                charger_prompt(nom, version, dossier)
            except (KeyError, ValueError, OSError) as erreur:
                problemes.append(f"{nom}.{version} : {erreur}")
    return problemes


def main(arguments: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if arguments is None else arguments
    if arguments[:1] == ["publier"] and len(arguments) == 3:
        prompt = publier_prompt(arguments[1], Path(arguments[2]).read_text(encoding="utf-8"))
        print(f"Publie : {prompt.identifiant} (non courante)")
        return 0
    if arguments:
        print("Usage : python -m doc42.prompts [publier <nom> <fichier>]", file=sys.stderr)
        return 2
    problemes = verifier_registre()
    if problemes:
        for probleme in problemes:
            print(probleme, file=sys.stderr)
        return 1
    for nom in _registre(DOSSIER_PROMPTS):
        print(f"{nom} : courante = {charger_prompt(nom).identifiant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
