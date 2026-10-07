"""Section 11, corrige commente : le contrat commun aux trois variantes.

Les commentaires expliquent le pourquoi, pas le comment : le comment est
dans le code. La variante de reference (analyseur de documents metier) est
livree au checkpoint etape/11-final, dans doc42/variantes/.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anthropic

from doc42.client import texte_de
from doc42.config import (
    FACTEUR_CACHE_ECRIT,
    FACTEUR_CACHE_LU,
    MAX_TOKENS_DEFAUT,
    MODELE_DEFAUT,
    TARIFS,
)
from doc42.outils import mots, normaliser

# ---------------------------------------------------------------------------
# Les formes du contrat, identiques dans l'exercice.
# ---------------------------------------------------------------------------

Confirmer = Callable[[str, dict[str, Any]], bool]


def refuser(nom: str, entree: dict[str, Any]) -> bool:
    """Confirmation par defaut : non. Une action irreversible ne passe jamais seule."""
    return False


@dataclass
class Variante:
    """Ce qu'une variante declare : son prompt, ses outils, ses actions irreversibles."""

    nom: str
    systeme: str
    outils: list[dict[str, Any]]
    executer: Callable[[str, dict[str, Any]], str]
    irreversibles: frozenset[str] = frozenset()
    modele: str = MODELE_DEFAUT


@dataclass
class Bornes:
    """Les garde-fous chiffres d'une requete."""

    max_tours: int = 6
    max_caracteres: int = 2000
    budget_dollars: float = 0.10


@dataclass
class Reponse:
    """Ce que toute variante rend, quelle que soit sa logique interne."""

    texte: str
    sources: list[str] = field(default_factory=list)
    escalade: bool = False
    raison: str = ""
    tours: int = 0
    cout: float = 0.0
    requete_id: str = ""


@dataclass
class CasEval:
    """Un cas du jeu d'evaluation."""

    question: str
    attendus: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    escalade: bool = False


@dataclass
class RapportEval:
    total: int
    reussis: int
    echecs: list[tuple[str, str]] = field(default_factory=list)
    cout: float = 0.0

    @property
    def taux(self) -> float:
        return self.reussis / self.total if self.total else 0.0

    def resume(self) -> str:
        return f"{self.reussis}/{self.total} cas reussis ({self.taux:.0%}), cout {self.cout:.4f} $"


SECTIONS_SPEC = {
    "quoi": "Quoi",
    "critere": "Critere de reussite",
    "hors perimetre": "Hors perimetre",
    "risque": "Risque principal",
}
NOMBRES_EN_LETTRES = {
    "deux",
    "trois",
    "quatre",
    "cinq",
    "six",
    "sept",
    "huit",
    "neuf",
    "dix",
    "onze",
    "douze",
    "quinze",
    "vingt",
    "trente",
    "cinquante",
    "cent",
    "mille",
    "moitie",
    "tiers",
    "quart",
}
MIN_CAS = 10
MOTS_IRREVERSIBLES = {
    "ecrit",
    "ecrire",
    "cree",
    "creer",
    "supprime",
    "supprimer",
    "envoie",
    "envoyer",
    "modifie",
    "modifier",
    "paie",
    "payer",
}
MOTIF_SOURCE = re.compile(r"\[([A-Za-z0-9_.-]+)\]")


# ---------------------------------------------------------------------------
# Exercice 1 : la specification d'une page
# ---------------------------------------------------------------------------


def _sections(texte: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    courante: str | None = None
    for ligne in texte.splitlines():
        if re.match(r"#{2,3} ", ligne):
            titre = normaliser(ligne.lstrip("#").strip())
            # « Comment on saura que ca marche » est la formulation de la page
            # Notion ; on l'accepte comme synonyme de « critere ».
            if "comment on saura" in titre:
                titre = "critere"
            # Debut de mot seulement : « Pourquoi » ne doit pas passer pour « Quoi ».
            courante = next((c for c in SECTIONS_SPEC if re.search(rf"\b{c}", titre)), None)
            if courante:
                sections[courante] = []
            continue
        if courante and ligne.strip():
            sections[courante].append(ligne.strip())
    return sections


def verifier_specification(texte: str) -> list[str]:
    problemes: list[str] = []
    sections = _sections(texte)
    for cle, titre in SECTIONS_SPEC.items():
        if cle not in sections:
            problemes.append(f"Section manquante : {titre}")
        elif not sections[cle]:
            problemes.append(f"Section vide : {titre}")

    quoi = normaliser(" ".join(sections.get("quoi", [])))
    if "quoi" in sections and not ("entree" in quoi and "sortie" in quoi):
        problemes.append("Quoi : il manque un exemple d'entree et un exemple de sortie attendue")

    # Un critere sans chiffre est une opinion : on ne saura pas dire a 6 h
    # si c'est reussi ou non.
    # « Huit questions sur dix » est chiffre aussi : on accepte les nombres en
    # lettres, sauf « un » et « une », trop courants pour prouver quoi que ce soit.
    critere = " ".join(sections.get("critere", []))
    chiffre = re.search(r"\d", critere) or NOMBRES_EN_LETTRES & set(mots(critere))
    if "critere" in sections and not chiffre:
        problemes.append("Critere de reussite : il n'est pas chiffre")

    # La partie que tout le monde saute, et celle qui sauve la journee.
    items = [
        ligne for ligne in sections.get("hors perimetre", []) if re.match(r"[-*]|\d+\.", ligne)
    ]
    if "hors perimetre" in sections and len(items) < 3:
        problemes.append(f"Hors perimetre : {len(items)} element(s), il en faut au moins 3")
    return problemes


# ---------------------------------------------------------------------------
# Exercice 2 : anonymiser avant d'envoyer
# ---------------------------------------------------------------------------

# L'ordre compte : un IBAN contient des suites de chiffres qu'on prendrait
# sinon pour un numero de telephone.
MOTIFS_PERSONNELS = [
    (re.compile(r"\bFR\d{2}(?: ?[0-9A-Z]{4}){5} ?[0-9A-Z]{3}\b"), "[IBAN]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "[EMAIL]"),
    (re.compile(r"(?<![\d/])(?:\+33 ?|0)[1-9](?:[ .-]?\d{2}){4}(?![\d/])"), "[TELEPHONE]"),
]


def anonymiser(texte: str) -> tuple[str, int]:
    total = 0
    for motif, jeton in MOTIFS_PERSONNELS:
        texte, n = motif.subn(jeton, texte)
        total += n
    # Les noms propres ne sont pas detectes : une regle les raterait ou
    # effacerait « Alpha Logistique ». Ils demandent une relecture humaine.
    return texte, total


# ---------------------------------------------------------------------------
# Exercice 3 : une variante qui declare ses garde-fous
# ---------------------------------------------------------------------------


def verifier_variante(variante: Variante) -> list[str]:
    problemes: list[str] = []
    if not variante.nom.strip():
        problemes.append("La variante n'a pas de nom")
    if not variante.outils:
        problemes.append("La variante ne declare aucun outil")
    if variante.modele not in TARIFS:
        problemes.append(
            f"Modele {variante.modele} absent de TARIFS : le cout d'une requete serait incalculable"
        )

    noms = set()
    for definition in variante.outils:
        nom = definition.get("name", "")
        noms.add(nom)
        if not definition.get("description", "").strip():
            problemes.append(f"Outil {nom} : description manquante, c'est elle que le modele lit")
        if definition.get("input_schema", {}).get("type") != "object":
            problemes.append(f"Outil {nom} : input_schema doit etre de type object")
        # Un outil qui ecrit et qu'on n'a pas declare irreversible passera
        # sans confirmation : c'est l'oubli le plus couteux de la journee.
        ecrit = MOTS_IRREVERSIBLES & set(mots(definition.get("description", "")))
        if ecrit and nom not in variante.irreversibles:
            problemes.append(f"Outil {nom} : il semble irreversible mais n'est pas declare")

    # Un garde-fou sur un nom mal orthographie ne se declenche jamais, et
    # rien ne le signale : c'est un garde-fou fantome.
    for nom in sorted(variante.irreversibles - noms):
        problemes.append(f"Garde-fou fantome : {nom} est declare irreversible mais n'existe pas")
    return problemes


# ---------------------------------------------------------------------------
# Exercice 4 : ce que coute une requete
# ---------------------------------------------------------------------------


def cout_appel(modele: str, usage: Any) -> float:
    if modele not in TARIFS:
        # Un cout inconnu n'est pas un cout nul : renvoyer 0 ferait passer
        # n'importe quelle requete sous le budget.
        raise ValueError(f"Tarif inconnu pour {modele}, completez TARIFS dans doc42/config.py")
    prix_entree, prix_sortie = TARIFS[modele]
    # Le SDK peut renvoyer None pour les champs de cache.
    lu = getattr(usage, "cache_read_input_tokens", 0) or 0
    ecrit = getattr(usage, "cache_creation_input_tokens", 0) or 0
    total = (
        (usage.input_tokens or 0) * prix_entree
        + (usage.output_tokens or 0) * prix_sortie
        + lu * prix_entree * FACTEUR_CACHE_LU
        + ecrit * prix_entree * FACTEUR_CACHE_ECRIT
    )
    return total / 1_000_000


class Journal:
    def __init__(self, chemin: str | Path | None = None) -> None:
        self.chemin = Path(chemin) if chemin else None
        self.entrees: list[dict[str, Any]] = []

    def enregistrer(self, requete_id: str, modele: str, usage: Any) -> dict[str, Any]:
        entree = {
            "date": datetime.now(UTC).isoformat(timespec="seconds"),
            "requete": requete_id,
            "modele": modele,
            "entree": usage.input_tokens or 0,
            "sortie": usage.output_tokens or 0,
            "cache_lu": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_ecrit": getattr(usage, "cache_creation_input_tokens", 0) or 0,
            "cout": cout_appel(modele, usage),
        }
        self.entrees.append(entree)
        if self.chemin:
            # Une ligne JSON par appel : lisible par un humain, agregeable par
            # un script, et un crash au milieu ne corrompt pas les lignes deja ecrites.
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            with self.chemin.open("a", encoding="utf-8") as fichier:
                fichier.write(json.dumps(entree, ensure_ascii=False) + "\n")
        return entree

    def cout_requete(self, requete_id: str) -> float:
        # Une requete utilisateur, c'est plusieurs appels (tri, outils, reponse).
        # C'est leur somme qui dit ce que coute une question.
        return sum(e["cout"] for e in self.entrees if e["requete"] == requete_id)

    def cout_total(self) -> float:
        return sum(e["cout"] for e in self.entrees)


# ---------------------------------------------------------------------------
# Exercice 5 : executer un outil derriere ses garde-fous
# ---------------------------------------------------------------------------


def resultat_outil(bloc: Any, variante: Variante, confirmer: Confirmer = refuser) -> dict[str, Any]:
    resultat: dict[str, Any] = {"type": "tool_result", "tool_use_id": bloc.id}
    connus = {d["name"] for d in variante.outils}
    if bloc.name not in connus:
        return {**resultat, "content": f"Outil inconnu : {bloc.name}", "is_error": True}

    if bloc.name in variante.irreversibles and not confirmer(bloc.name, bloc.input):
        # On le dit au modele, sinon il annoncera a l'utilisateur une fiche
        # ou un ticket qui n'existe pas.
        return {
            **resultat,
            "content": f"Action {bloc.name} refusee par l'utilisateur. Elle n'a pas ete executee.",
            "is_error": True,
        }

    try:
        contenu = variante.executer(bloc.name, bloc.input)
    except Exception as erreur:  # noqa: BLE001
        # Une erreur d'outil est une information pour le modele, pas un crash
        # de l'application : il peut reformuler ou dire qu'il ne sait pas.
        return {
            **resultat,
            "content": f"Erreur de l'outil {bloc.name} : {erreur}",
            "is_error": True,
        }
    return {**resultat, "content": contenu}


# ---------------------------------------------------------------------------
# Exercice 6 : repondre, borne, source, et savoir passer la main
# ---------------------------------------------------------------------------


def _escalade(raison: str, detail: str, **kwargs: Any) -> Reponse:
    texte = f"Je ne peux pas repondre de facon fiable ({detail}). Je transmets a un humain."
    return Reponse(texte=texte, escalade=True, raison=raison, **kwargs)


def repondre(
    client: Any,
    variante: Variante,
    question: str,
    *,
    journal: Journal | None = None,
    confirmer: Confirmer = refuser,
    bornes: Bornes | None = None,
) -> Reponse:
    bornes = bornes or Bornes()
    # Pas de journal fourni : on en cree un quand meme. Le cout d'une requete
    # n'est pas une option qu'on active en production.
    journal = journal if journal is not None else Journal()
    requete_id = uuid.uuid4().hex[:12]

    # La borne d'entree se verifie AVANT l'appel : refuser apres avoir paye
    # ne protege rien.
    if len(question) > bornes.max_caracteres:
        return _escalade(
            "hors_bornes",
            f"question de {len(question)} caracteres, limite {bornes.max_caracteres}",
            requete_id=requete_id,
        )

    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    vus: set[str] = set()
    for tour in range(1, bornes.max_tours + 1):
        try:
            reponse = client.messages.create(
                model=variante.modele,
                max_tokens=MAX_TOKENS_DEFAUT,
                system=variante.systeme,
                tools=variante.outils,
                messages=messages,
            )
        except anthropic.APIError as erreur:
            # Les reprises sont l'affaire du client (section 2). Ici, une
            # erreur qui remonte devient une escalade explicite, pas une trace.
            return _escalade(
                "erreur",
                f"erreur de l'API : {type(erreur).__name__}",
                tours=tour,
                cout=journal.cout_requete(requete_id),
                requete_id=requete_id,
            )
        journal.enregistrer(requete_id, variante.modele, reponse.usage)
        cout = journal.cout_requete(requete_id)

        if reponse.stop_reason != "tool_use":
            texte = texte_de(reponse)
            # Une source n'est retenue que si un outil l'a vraiment renvoyee :
            # un identifiant cite mais jamais lu est une citation inventee.
            cites = list(dict.fromkeys(MOTIF_SOURCE.findall(texte)))
            sources = [s for s in cites if s in vus]
            return Reponse(
                texte=texte,
                sources=sources,
                escalade=not sources,
                raison="" if sources else "sans_source",
                tours=tour,
                cout=cout,
                requete_id=requete_id,
            )

        # Le budget se verifie avant de relancer un tour, pas apres la reponse
        # finale : celle-ci est deja payee, autant la rendre.
        if cout > bornes.budget_dollars:
            return _escalade(
                "budget",
                f"budget de {bornes.budget_dollars} $ depasse",
                tours=tour,
                cout=cout,
                requete_id=requete_id,
            )

        resultats = [
            resultat_outil(bloc, variante, confirmer)
            for bloc in reponse.content
            if bloc.type == "tool_use"
        ]
        for resultat in resultats:
            if not resultat.get("is_error"):
                vus.update(MOTIF_SOURCE.findall(resultat["content"]))
        # Tous les resultats dans UN message user : deux messages user
        # consecutifs seraient refuses par l'API.
        messages.append({"role": "assistant", "content": reponse.content})
        messages.append({"role": "user", "content": resultats})

    return _escalade(
        "tours",
        f"limite de {bornes.max_tours} tours atteinte",
        tours=bornes.max_tours,
        cout=journal.cout_requete(requete_id),
        requete_id=requete_id,
    )


# ---------------------------------------------------------------------------
# Exercice 7 : le jeu d'evaluation et son chiffre
# ---------------------------------------------------------------------------


def charger_cas(chemin: str | Path) -> list[CasEval]:
    cas: list[CasEval] = []
    for numero, ligne in enumerate(Path(chemin).read_text(encoding="utf-8").splitlines(), 1):
        if not ligne.strip():
            continue
        try:
            donnees = json.loads(ligne)
        except json.JSONDecodeError as erreur:
            raise ValueError(f"ligne {numero} : JSON invalide ({erreur.msg})") from erreur
        if not str(donnees.get("question", "")).strip():
            raise ValueError(f"ligne {numero} : champ question manquant")
        cas.append(
            CasEval(
                question=donnees["question"],
                attendus=list(donnees.get("attendus", [])),
                sources=list(donnees.get("sources", [])),
                escalade=bool(donnees.get("escalade", False)),
            )
        )
    return cas


def _verdict(cas: CasEval, reponse: Reponse) -> str:
    """La raison de l'echec, ou une chaine vide si le cas est reussi."""
    if cas.escalade:
        # Savoir dire « je ne sais pas » se mesure comme le reste.
        return "" if reponse.escalade else "devait passer la main et a repondu"
    if reponse.escalade:
        return f"a passe la main ({reponse.raison})"
    texte = normaliser(reponse.texte)
    manquants = [a for a in cas.attendus if normaliser(a) not in texte]
    if manquants:
        return f"attendu absent : {', '.join(manquants)}"
    sources = [s for s in cas.sources if s not in reponse.sources]
    if sources:
        return f"source non citee : {', '.join(sources)}"
    return ""


def evaluer(repondre: Callable[[str], Reponse], cas: list[CasEval]) -> RapportEval:
    if len(cas) < MIN_CAS:
        # En dessous, un cas vaut plus de dix points : le chiffre ne dit rien.
        raise ValueError(f"Jeu d'evaluation trop petit : {len(cas)} cas, il en faut {MIN_CAS}")
    rapport = RapportEval(total=len(cas), reussis=0)
    for un_cas in cas:
        try:
            reponse = repondre(un_cas.question)
        except Exception as erreur:  # noqa: BLE001
            # Un cas qui plante est un resultat, pas un echec de l'evaluation.
            rapport.echecs.append((un_cas.question, f"exception : {type(erreur).__name__}"))
            continue
        rapport.cout += reponse.cout
        raison = _verdict(un_cas, reponse)
        if raison:
            rapport.echecs.append((un_cas.question, raison))
        else:
            rapport.reussis += 1
    return rapport


# ---------------------------------------------------------------------------
# Exercice 8 : le livrable, verifie comme le ferait un collegue
# ---------------------------------------------------------------------------


def verifier_livrable(
    dossier: str | Path,
    *,
    readme: str = "README.md",
    spec: str = "docs/specification.md",
    cas: str = "evals/cas.jsonl",
) -> list[str]:
    dossier = Path(dossier)
    problemes: list[str] = []

    chemin_readme = dossier / readme
    if not chemin_readme.exists():
        problemes.append(f"README absent : {readme}")
    else:
        contenu = chemin_readme.read_text(encoding="utf-8")
        # Ce qu'un collegue tape dans un depot propre, dans l'ordre.
        for attendu, pourquoi in (
            ("uv sync", "installer les dependances"),
            ("ANTHROPIC_API_KEY", "configurer la cle"),
            ("uv run", "lancer l'application"),
        ):
            if attendu not in contenu:
                problemes.append(f"README : {attendu} absent ({pourquoi})")

    gitignore = dossier / ".gitignore"
    lignes = gitignore.read_text(encoding="utf-8").split() if gitignore.exists() else []
    if ".env" not in lignes:
        problemes.append(".gitignore : .env n'est pas ignore, la cle partirait avec le depot")

    chemin_spec = dossier / spec
    if not chemin_spec.exists():
        problemes.append(f"Specification absente : {spec}")
    else:
        problemes += [
            f"Specification : {p}"
            for p in verifier_specification(chemin_spec.read_text(encoding="utf-8"))
        ]

    chemin_cas = dossier / cas
    if not chemin_cas.exists():
        problemes.append(f"Jeu d'evaluation absent : {cas}")
    else:
        try:
            n = len(charger_cas(chemin_cas))
        except ValueError as erreur:
            problemes.append(f"Jeu d'evaluation : {erreur}")
        else:
            if n < MIN_CAS:
                problemes.append(f"Jeu d'evaluation : {n} cas, il en faut {MIN_CAS}")
    return problemes
