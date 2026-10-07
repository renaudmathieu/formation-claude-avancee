"""Variante B de reference : analyseur de documents metier.

Ce qui change par rapport a Doc42 (page Notion, 11.1) :
  - l'extraction structuree est renforcee : un outil force (tool_choice)
    rend des champs types, et chaque valeur extraite est confrontee au texte
    source, sans appel a l'API ;
  - la comparaison entre documents se fait sur les extractions, champ par
    champ, au lieu de demander au modele de comparer deux textes ;
  - la fiabilite de l'extraction est mesuree sur un jeu de reference.

Ce qui ne change pas : la recherche lexicale (doc42.outils), creer_fiche
derriere une confirmation humaine, la boucle bornee et le journal du socle.

Usage (voir docs/projet-final.md) :

    uv run python -m doc42.variantes.analyseur demander "Echeances du contrat Alpha ?"
    uv run python -m doc42.variantes.analyseur extraire contrat_alpha
    uv run python -m doc42.variantes.analyseur comparer contrat_alpha avenant_alpha_01
    uv run python -m doc42.variantes.analyseur evaluer
    uv run python -m doc42.variantes.analyseur verifier
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from functools import partial
from pathlib import Path
from typing import Any

from doc42 import outils
from doc42.client import avec_reprise, creer_client
from doc42.config import (
    DOSSIER_CORPUS,
    DOSSIER_FICHES,
    MAX_TOKENS_DEFAUT,
    MODELE_DEFAUT,
    RACINE,
    SYSTEME_DOC42,
    verifier,
)
from doc42.corpus import Document, charger_corpus, trouver
from doc42.outils import normaliser

from .socle import (
    Bornes,
    Journal,
    RapportEval,
    Reponse,
    Variante,
    anonymiser,
    charger_cas,
    evaluer,
    repondre,
    verifier_livrable,
    verifier_variante,
)

NOM = "analyseur"

# Le livrable de la variante, tel que verifier_livrable le controle.
README = "docs/projet-final.md"
SPECIFICATION = "docs/specification-analyseur.md"
CAS = "evals/analyseur_cas.jsonl"
REFERENCE_EXTRACTION = "evals/analyseur_extraction.jsonl"

# Le journal va dans fiches/, deja ignore par git : un depot propre ne
# transporte pas les couts de son auteur.
JOURNAL = Path(os.environ.get("DOC42_JOURNAL", DOSSIER_FICHES / "journal-analyseur.jsonl"))

# Un document entier peut faire exploser le contexte : on borne la lecture.
MAX_LECTURE = 6000

SYSTEME_ANALYSEUR = SYSTEME_DOC42 + (
    " Cite chaque document utilise par son identifiant entre crochets, par exemple "
    "[contrat_alpha]. Si l'information n'est pas dans les documents, dis-le en une phrase "
    "et ne cite aucun document. Ecris les dates au format JJ/MM/AAAA. "
    "Ne cree une fiche que si l'utilisateur le demande explicitement."
)

OUTIL_LIRE: dict[str, Any] = {
    "name": "lire_document",
    "description": (
        "Lit le texte integral d'un document du corpus a partir de son identifiant, tel que "
        "renvoye entre crochets par chercher_documents. A utiliser quand l'extrait ne suffit "
        "pas pour repondre avec certitude. Lecture seule."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "Identifiant du document, par exemple 'contrat_alpha'.",
            }
        },
        "required": ["document_id"],
    },
}

OUTIL_EXTRACTION: dict[str, Any] = {
    "name": "enregistrer_extraction",
    "description": "Enregistre les champs extraits d'un document interne d'Hexalis.",
    "input_schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "description": "Le type indique par le document (ligne 'Type :'), en minuscules.",
            },
            "date": {
                "type": ["string", "null"],
                "description": (
                    "La date du document (signature, emission, redaction ou mise a jour), "
                    "au format JJ/MM/AAAA. Pas la date d'un evenement decrit dans le document."
                ),
            },
            "echeances": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Toutes les dates de paiement mentionnees, au format JJ/MM/AAAA. "
                    "Liste vide si le document n'en donne aucune sous forme de date."
                ),
            },
            "montant_total_ht": {
                "type": ["number", "null"],
                "description": (
                    "Le montant annuel ou total HT en vigueur selon le document, en euros. "
                    "null si le document ne fixe pas de prix."
                ),
            },
        },
        "required": ["type", "date", "echeances", "montant_total_ht"],
    },
}

SYSTEME_EXTRACTION = (
    "Tu extrais des champs de documents internes. Tu n'inventes rien : un champ absent "
    "du document vaut null ou une liste vide. Tu reponds uniquement par l'outil "
    "enregistrer_extraction."
)

CHAMPS = ("type", "date", "echeances", "montant_total_ht")
MOIS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}


# ---------------------------------------------------------------------------
# La variante : outils et declaration
# ---------------------------------------------------------------------------


def executer(
    nom: str,
    entree: dict[str, Any],
    dossier: str | Path = DOSSIER_CORPUS,
    fiches: str | Path = DOSSIER_FICHES,
) -> str:
    """Execute un outil de la variante. Tout ce qui part vers l'API est anonymise."""
    if nom == "chercher_documents":
        resultats = outils.chercher_documents(entree["requete"], entree.get("limite", 5), dossier)
        if not resultats:
            return "Aucun document ne correspond."
        texte = "\n\n".join(f"[{r['id']}] {r['titre']}\n{r['extrait']}" for r in resultats)
        return anonymiser(texte)[0]
    if nom == "lire_document":
        document = trouver(entree["document_id"], dossier)
        if document is None:
            raise ValueError(f"document inconnu : {entree['document_id']}")
        return anonymiser(f"[{document.id}] {document.titre}\n{document.texte[:MAX_LECTURE]}")[0]
    if nom == "creer_fiche":
        return f"Fiche creee : {outils.creer_fiche(entree['titre'], entree['contenu'], fiches)}"
    raise KeyError(f"Outil inconnu : {nom}")


def variante(dossier: str | Path = DOSSIER_CORPUS, fiches: str | Path = DOSSIER_FICHES) -> Variante:
    """La declaration de la variante B."""
    chercher, creer = outils.DEFINITIONS
    return Variante(
        nom=NOM,
        systeme=SYSTEME_ANALYSEUR,
        outils=[chercher, OUTIL_LIRE, creer],
        executer=partial(executer, dossier=dossier, fiches=fiches),
        irreversibles=frozenset({"creer_fiche"}),
        modele=MODELE_DEFAUT,
    )


# ---------------------------------------------------------------------------
# Extraction structuree et verification contre la source
# ---------------------------------------------------------------------------


def extraire(
    client: Any, document: Document, journal: Journal, requete_id: str | None = None
) -> dict[str, Any]:
    """Extrait les CHAMPS d'un document par un outil force, et normalise le resultat."""
    requete_id = requete_id or uuid.uuid4().hex[:12]
    texte = anonymiser(document.texte)[0]
    reponse = avec_reprise(
        lambda: client.messages.create(
            model=MODELE_DEFAUT,
            max_tokens=MAX_TOKENS_DEFAUT,
            system=SYSTEME_EXTRACTION,
            tools=[OUTIL_EXTRACTION],
            # L'outil force garantit une sortie conforme au schema : pas de JSON
            # a extraire d'un texte libre, pas de « Voici l'extraction : ».
            tool_choice={"type": "tool", "name": OUTIL_EXTRACTION["name"]},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f'<document id="{document.id}">\n{texte}\n</document>\n'
                        "Extrais les champs de ce document."
                    ),
                }
            ],
        )
    )
    journal.enregistrer(requete_id, MODELE_DEFAUT, reponse.usage)
    bloc = next((b for b in reponse.content if b.type == "tool_use"), None)
    if bloc is None:
        raise ValueError(f"Aucune extraction rendue pour {document.id}")
    return normaliser_extraction(bloc.input)


def normaliser_extraction(brut: dict[str, Any]) -> dict[str, Any]:
    montant = brut.get("montant_total_ht")
    return {
        "type": str(brut.get("type") or "").strip().lower(),
        "date": brut.get("date") or None,
        "echeances": sorted(set(brut.get("echeances") or [])),
        "montant_total_ht": float(montant) if montant not in (None, "") else None,
    }


def dates_du_texte(texte: str) -> set[str]:
    """Les dates du texte au format JJ/MM/AAAA, qu'elles soient ecrites en chiffres ou en lettres."""
    texte = normaliser(texte)
    dates = {f"{j}/{m}/{a}" for j, m, a in re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b", texte)}
    motif = r"\b(\d{1,2})(?:er)? (" + "|".join(MOIS) + r") (\d{4})\b"
    for jour, mois, annee in re.findall(motif, texte):
        dates.add(f"{int(jour):02d}/{MOIS[mois]:02d}/{annee}")
    return dates


def montants_du_texte(texte: str) -> set[float]:
    """Les nombres du texte, separateurs de milliers retires (48 000 -> 48000)."""
    compact = re.sub(r"(?<=\d)[   ](?=\d{3}(?!\d))", "", texte)
    return {float(n.replace(",", ".")) for n in re.findall(r"\d+(?:,\d+)?", compact)}


def valeurs_non_sourcees(extraction: dict[str, Any], document: Document) -> list[str]:
    """Les valeurs extraites introuvables dans le texte source.

    C'est le garde-fou de la variante B : une valeur que le document ne
    contient pas a ete inventee ou calculee, et il faut le dire.
    """
    dates = dates_du_texte(document.texte)
    montants = montants_du_texte(document.texte)
    douteuses = []
    if extraction["date"] and extraction["date"] not in dates:
        douteuses.append(f"date {extraction['date']}")
    douteuses += [f"echeance {e}" for e in extraction["echeances"] if e not in dates]
    montant = extraction["montant_total_ht"]
    if montant is not None and not any(abs(montant - m) < 0.01 for m in montants):
        douteuses.append(f"montant {montant:g}")
    return douteuses


def comparer(a: dict[str, Any], b: dict[str, Any]) -> list[tuple[str, Any, Any]]:
    """Les champs qui different entre deux extractions : (champ, valeur a, valeur b).

    La comparaison est deterministe : chaque difference se trace jusqu'a une
    valeur extraite, elle-meme verifiee contre son document.
    """
    return [(champ, a[champ], b[champ]) for champ in CHAMPS if a[champ] != b[champ]]


def noter_extraction(obtenu: dict[str, Any], attendu: dict[str, Any]) -> dict[str, bool]:
    """Champ par champ, l'extraction est-elle conforme a la reference ?"""
    notes = {}
    for champ, valeur in attendu.items():
        if champ == "type":
            notes[champ] = normaliser(obtenu["type"]) == normaliser(valeur)
        elif champ == "echeances":
            notes[champ] = set(obtenu["echeances"]) == set(valeur)
        elif champ == "montant_total_ht":
            o = obtenu["montant_total_ht"]
            notes[champ] = (o is None and valeur is None) or (
                o is not None and valeur is not None and abs(o - valeur) < 0.01
            )
        else:
            notes[champ] = obtenu.get(champ) == valeur
    return notes


def evaluer_extraction(
    client: Any, chemin: str | Path, journal: Journal, dossier: str | Path = DOSSIER_CORPUS
) -> tuple[int, int, list[str]]:
    """Mesure la fiabilite de l'extraction. Retourne (champs corrects, champs notes, remarques)."""
    corrects, total, remarques = 0, 0, []
    lignes = Path(chemin).read_text(encoding="utf-8").splitlines()
    for ligne in filter(str.strip, lignes):
        reference = json.loads(ligne)
        attendu = reference["attendu"]
        total += len(attendu)
        document = trouver(reference["id"], dossier)
        if document is None:
            remarques.append(f"{reference['id']} : document absent du corpus")
            continue
        try:
            obtenu = extraire(client, document, journal)
        except Exception as erreur:  # noqa: BLE001
            remarques.append(f"{document.id} : extraction en echec ({type(erreur).__name__})")
            continue
        for champ, juste in noter_extraction(obtenu, attendu).items():
            if juste:
                corrects += 1
            else:
                remarques.append(
                    f"{document.id}.{champ} : attendu {attendu[champ]!r}, obtenu {obtenu[champ]!r}"
                )
        remarques += [
            f"{document.id} : non sourcee, {v}" for v in valeurs_non_sourcees(obtenu, document)
        ]
    return corrects, total, remarques


# ---------------------------------------------------------------------------
# Ligne de commande
# ---------------------------------------------------------------------------


def demander_confirmation(nom: str, entree: dict[str, Any]) -> bool:
    """La confirmation humaine, dans le terminal. Tout sauf « o » vaut non."""
    print(f"\nDoc42 veut executer {nom} avec : {json.dumps(entree, ensure_ascii=False)[:300]}")
    return input("Confirmer ? [o/N] ").strip().lower() == "o"


def afficher(reponse: Reponse) -> None:
    print(reponse.texte)
    print()
    print(f"Sources verifiees : {', '.join(reponse.sources) or 'aucune'}")
    if reponse.escalade:
        print(f"Escalade : {reponse.raison}")
    print(f"Requete {reponse.requete_id} : {reponse.tours} tour(s), {reponse.cout:.4f} $")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="analyseur", description="Doc42, variante B")
    commandes = parser.add_subparsers(dest="commande", required=True)
    p = commandes.add_parser("demander", help="poser une question sur le corpus")
    p.add_argument("question")
    p = commandes.add_parser("extraire", help="extraire les champs d'un document")
    p.add_argument("document_id")
    p = commandes.add_parser("comparer", help="comparer deux documents champ par champ")
    p.add_argument("document_a")
    p.add_argument("document_b")
    p = commandes.add_parser("evaluer", help="mesurer la variante sur ses jeux d'evaluation")
    p.add_argument("--sans-extraction", action="store_true", help="questions seulement")
    commandes.add_parser("verifier", help="verifier le livrable, hors ligne")
    args = parser.parse_args(argv)

    if args.commande == "verifier":
        problemes = verifier_variante(variante()) + verifier_livrable(
            RACINE, readme=README, spec=SPECIFICATION, cas=CAS
        )
        print("\n".join(problemes) or "Livrable conforme au contrat de la section 11.")
        print(f"Corpus : {len(charger_corpus())} documents dans {DOSSIER_CORPUS}")
        return 1 if problemes else 0

    try:
        verifier()
    except RuntimeError as erreur:
        print(erreur, file=sys.stderr)
        return 2
    client = creer_client()
    journal = Journal(JOURNAL)

    if args.commande == "demander":
        reponse = repondre(
            client, variante(), args.question, journal=journal, confirmer=demander_confirmation
        )
        afficher(reponse)
        return 0

    if args.commande in ("extraire", "comparer"):
        ids = (
            [args.document_id]
            if args.commande == "extraire"
            else [args.document_a, args.document_b]
        )
        documents = [trouver(i) for i in ids]
        if None in documents:
            print(f"Document inconnu parmi : {', '.join(ids)}", file=sys.stderr)
            return 2
        requete_id = uuid.uuid4().hex[:12]
        extractions = [extraire(client, d, journal, requete_id) for d in documents]
        for document, extraction in zip(documents, extractions, strict=True):
            print(f"[{document.id}] {json.dumps(extraction, ensure_ascii=False)}")
            for douteuse in valeurs_non_sourcees(extraction, document):
                print(f"  attention, valeur introuvable dans le document : {douteuse}")
        if args.commande == "comparer":
            print()
            for champ, a, b in comparer(*extractions) or [("aucune difference", "", "")]:
                print(f"{champ} : {a} -> {b}")
        print(f"\nCout : {journal.cout_requete(requete_id):.4f} $")
        return 0

    # evaluer : confirmer=refuser par defaut, une evaluation n'ecrit jamais de fiche.
    la_variante = variante()
    rapport: RapportEval = evaluer(
        lambda q: repondre(client, la_variante, q, journal=journal, bornes=Bornes()),
        charger_cas(RACINE / CAS),
    )
    print(f"Questions : {rapport.resume()}")
    for question, raison in rapport.echecs:
        print(f"  - {question} : {raison}")
    if not args.sans_extraction:
        avant = journal.cout_total()
        corrects, total, remarques = evaluer_extraction(
            client, RACINE / REFERENCE_EXTRACTION, journal
        )
        cout = journal.cout_total() - avant
        print(
            f"Extraction : {corrects}/{total} champs corrects ({corrects / total:.0%}), {cout:.4f} $"
        )
        for remarque in remarques:
            print(f"  - {remarque}")
    print(f"Cout total : {journal.cout_total():.4f} $, journal : {JOURNAL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
