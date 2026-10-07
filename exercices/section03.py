"""Section 3, corrige commente.

Les commentaires expliquent le pourquoi, pas le comment : le comment est
dans le code.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from doc42.client import texte_de
from doc42.config import DOSSIER_CORPUS, MAX_TOKENS_DEFAUT, MODELE_DEFAUT
from doc42.corpus import Document, charger_corpus

RACINE = Path(__file__).resolve().parent.parent
JEU_DEFAUT = RACINE / "evals" / "attendu.json"

CLES = ("type", "date", "parties", "echeances")
CLES_ECHEANCE = ("date", "montant_ht")
TYPES = (
    "contrat",
    "avenant",
    "facture",
    "proces-verbal",
    "note de service",
    "politique interne",
    "procedure",
    "cahier des charges",
    "rapport d'incident",
    "compte rendu",
    "autre",
)

# Le meme contrat, ecrit en JSON Schema : c'est ce que le modele lit dans le
# prompt, et c'est ce que valider() verifie dans le code. Une seule source.
SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": list(CLES),
    "additionalProperties": False,
    "properties": {
        "type": {"enum": list(TYPES)},
        "date": {"type": ["string", "null"], "format": "date"},
        "parties": {"type": "array", "items": {"type": "string"}},
        "echeances": {
            "type": "array",
            "items": {
                "type": "object",
                "required": list(CLES_ECHEANCE),
                "additionalProperties": False,
                "properties": {
                    "date": {"type": "string", "format": "date"},
                    "montant_ht": {"type": ["number", "null"]},
                },
            },
        },
    },
}


# Exercice 1 : le prompt systeme structure

# L'exemple est fictif expres. Un exemple tire du jeu de test donnerait la
# reponse au modele pour ce document-la et gonflerait la mesure.
_EXEMPLE_DOCUMENT = """# Contrat de maintenance : Omega Imprimerie
Type : contrat
Date de signature : 3 mars 2025
Parties : Hexalis SAS et Omega Imprimerie SARL
Le prix de 9 000 euros HT est payable en deux fois : 4 500 euros HT au 31/03/2025
et 4 500 euros HT au 30/09/2025."""

_EXEMPLE_SORTIE = {
    "type": "contrat",
    "date": "2025-03-03",
    "parties": ["Hexalis SAS", "Omega Imprimerie SARL"],
    "echeances": [
        {"date": "2025-03-31", "montant_ht": 4500},
        {"date": "2025-09-30", "montant_ht": 4500},
    ],
}


def construire_systeme(exemple: bool = True) -> str:
    # Chaque bloc a une seule responsabilite. Quand une mesure se degrade, on
    # sait quel bloc on vient de toucher ; dans un paragraphe unique, on ne
    # le sait pas.
    role = (
        "<role>\n"
        "Tu es l'extracteur de metadonnees de Doc42. Tu lis un document interne "
        "d'Hexalis et tu en restitues les metadonnees sous forme d'un objet JSON.\n"
        "</role>"
    )
    contexte = (
        "<context>\n"
        "Les documents sont des contrats, avenants, factures, proces-verbaux, notes, "
        "politiques et procedures. Ton JSON est lu par un programme, pas par un humain : "
        "il est valide contre un schema et toute sortie non conforme est rejetee.\n"
        "</context>"
    )
    # Les regles de date, de parties et d'echeances sont celles du jeu de
    # test. Si le prompt et le jeu ne disent pas la meme chose, on mesure
    # un malentendu, pas la qualite du prompt.
    instructions = (
        "<instructions>\n"
        "1. Lis le document en entier avant de repondre.\n"
        f"2. type : une valeur parmi {', '.join(TYPES)}.\n"
        "3. date : la date du document au format AAAA-MM-JJ. Date de signature pour un "
        "contrat ou un avenant, date d'emission pour une facture, sinon la date d'en-tete. "
        "Jamais la date d'un evenement decrit dans le document. null si elle est absente.\n"
        "4. parties : les organisations engagees par un contrat, un avenant ou une facture, "
        "avec leur forme juridique telle qu'ecrite. Liste vide pour les autres types.\n"
        "5. echeances : chaque date a laquelle une somme est payable ou facturee, avec "
        "montant_ht, le montant hors taxes fixe par ce document (null s'il ne le precise "
        "pas). Une echeance recurrente est developpee en une date par occurrence sur la "
        "duree du document.\n"
        "6. Les dates limites d'actions, les jalons, les budgets et les delais de paiement "
        "generaux ne sont pas des echeances.\n"
        "</instructions>"
    )
    contraintes = (
        "<constraints>\n"
        "- Reponds uniquement par l'objet JSON, sans texte avant ou apres, sans balise de "
        "code.\n"
        "- N'invente rien : une information absente du document vaut null, ou une liste "
        'vide. Un document sans echeance de paiement donne "echeances": [].\n'
        "- Respecte exactement ce schema, sans cle supplementaire :\n"
        f"{json.dumps(SCHEMA, ensure_ascii=False)}\n"
        "</constraints>"
    )
    blocs = [role, contexte, instructions, contraintes]
    if exemple:
        # Un exemple vaut dix adjectifs : il fixe la forme des dates, des
        # montants (nombres, pas chaines) et des noms de parties.
        blocs.append(
            "<examples>\n<example>\n"
            f"<document>\n{_EXEMPLE_DOCUMENT}\n</document>\n"
            f"<sortie>\n{json.dumps(_EXEMPLE_SORTIE, ensure_ascii=False)}\n</sortie>\n"
            "</example>\n</examples>"
        )
    return "\n\n".join(blocs)


# Exercice 2 : decoder sans se fier au modele


def extraire_json(texte: str) -> dict[str, Any]:
    nettoye = texte.strip()
    # « Uniquement du JSON » n'empeche pas toujours une balise ```json ou une
    # phrase d'introduction. On les retire au lieu d'esperer qu'elles
    # n'arrivent qu'en developpement.
    bloc = re.search(r"```(?:json)?\s*(.*?)```", nettoye, re.DOTALL)
    if bloc:
        nettoye = bloc.group(1).strip()
    debut, fin = nettoye.find("{"), nettoye.rfind("}")
    if debut == -1 or fin < debut:
        raise ValueError("aucun objet JSON dans la reponse")
    try:
        donnees = json.loads(nettoye[debut : fin + 1])
    except json.JSONDecodeError as erreur:
        raise ValueError(f"JSON invalide : {erreur}") from erreur
    if not isinstance(donnees, dict):
        # ValueError et non TypeError : pour l'appelant, c'est le meme echec
        # (« pas d'objet JSON exploitable »), rattrape au meme endroit.
        raise ValueError("la racine du JSON doit etre un objet")  # noqa: TRY004
    return donnees


# Exercice 3 : valider contre le schema


def _date_iso(valeur: Any) -> bool:
    # Le motif seul accepterait 2027-02-30 ; fromisoformat seul accepterait
    # d'autres formes selon la version de Python. Les deux ensemble.
    if not isinstance(valeur, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valeur):
        return False
    try:
        date.fromisoformat(valeur)
    except ValueError:
        return False
    return True


def _nombre(valeur: Any) -> bool:
    # True est un int en Python : sans ce test, "montant_ht": true passerait.
    return isinstance(valeur, int | float) and not isinstance(valeur, bool)


def valider(donnees: Any) -> list[str]:
    # On renvoie TOUTES les erreurs, pas la premiere : elles partent telles
    # quelles dans la relance, et le modele corrige mieux quand il voit tout.
    if not isinstance(donnees, dict):
        return ["la racine doit etre un objet JSON"]
    erreurs = [f"cle manquante : {cle}" for cle in CLES if cle not in donnees]
    erreurs += [f"cle inattendue : {cle}" for cle in donnees if cle not in CLES]

    if "type" in donnees and donnees["type"] not in TYPES:
        erreurs.append(
            f"type inconnu : {donnees['type']!r} (valeurs permises : {', '.join(TYPES)})"
        )
    if "date" in donnees and donnees["date"] is not None and not _date_iso(donnees["date"]):
        erreurs.append(f"date invalide : {donnees['date']!r} (format AAAA-MM-JJ ou null)")
    if "parties" in donnees:
        parties = donnees["parties"]
        if not isinstance(parties, list) or not all(
            isinstance(p, str) and p.strip() for p in parties
        ):
            erreurs.append("parties doit etre une liste de noms (chaines non vides)")
    if "echeances" in donnees:
        echeances = donnees["echeances"]
        if not isinstance(echeances, list):
            erreurs.append("echeances doit etre une liste")
        else:
            for rang, echeance in enumerate(echeances, start=1):
                if not isinstance(echeance, dict) or set(echeance) != set(CLES_ECHEANCE):
                    erreurs.append(
                        f"echeance {rang} : cles attendues exactement date et montant_ht"
                    )
                    continue
                if not _date_iso(echeance["date"]):
                    erreurs.append(f"echeance {rang} : date invalide {echeance['date']!r}")
                montant = echeance["montant_ht"]
                if montant is not None and (not _nombre(montant) or montant < 0):
                    erreurs.append(
                        f"echeance {rang} : montant_ht doit etre un nombre positif ou null, "
                        f"pas {montant!r}"
                    )
    return erreurs


# Exercice 4 : extraire, avec relance


class ErreurExtraction(Exception):
    def __init__(self, erreurs: list[str], brut: str) -> None:
        super().__init__("; ".join(erreurs))
        self.erreurs = erreurs
        self.brut = brut


def bloc_document(document: Document) -> str:
    return f'<document id="{document.id}">\n{document.texte}\n</document>'


def message_document(document: Document) -> str:
    # Le document d'abord, la consigne ensuite : sur un texte long, la
    # question placee a la fin est mieux suivie. Les balises separent sans
    # ambiguite ce qui est a lire de ce qui est a faire.
    return (
        f"{bloc_document(document)}\n\n"
        "Extrais les metadonnees de ce document. Reponds uniquement par l'objet JSON."
    )


def message_relance(erreurs: list[str]) -> str:
    liste = "\n".join(f"- {e}" for e in erreurs)
    return (
        f"Ta reponse n'est pas valide :\n<erreurs>\n{liste}\n</erreurs>\n"
        "Renvoie uniquement l'objet JSON corrige, conforme au schema."
    )


def extraire(
    client: Any,
    document: Document,
    systeme: str | None = None,
    *,
    prefill: bool = False,
    tentatives: int = 3,
    modele: str = MODELE_DEFAUT,
) -> dict[str, Any]:
    systeme = construire_systeme() if systeme is None else systeme
    messages: list[dict[str, Any]] = [{"role": "user", "content": message_document(document)}]
    brut = ""
    erreurs: list[str] = []
    for _ in range(tentatives):
        # Le prefill n'entre jamais dans l'historique : on le rajoute a chaque
        # envoi, apres la derniere consigne.
        envoyes = messages + ([{"role": "assistant", "content": "{"}] if prefill else [])
        reponse = client.messages.create(
            model=modele,
            max_tokens=MAX_TOKENS_DEFAUT,
            system=systeme,
            messages=envoyes,
        )
        # Avec prefill, le modele CONTINUE apres « { » : l'accolade n'est pas
        # dans sa reponse, c'est a nous de la remettre.
        brut = ("{" if prefill else "") + texte_de(reponse)
        try:
            donnees = extraire_json(brut)
            erreurs = valider(donnees)
        except ValueError as erreur:
            erreurs = [str(erreur)]
        if not erreurs:
            return donnees
        # La relance montre au modele sa propre reponse et ce qui ne va pas.
        # Redemander la meme chose sans dire pourquoi donne souvent la meme
        # erreur. Le contenu vide est refuse par l'API, d'ou le substitut.
        messages = messages + [
            {"role": "assistant", "content": brut or "(reponse vide)"},
            {"role": "user", "content": message_relance(erreurs)},
        ]
    # Pas de relance sur une erreur de l'API (400, 429...) : elle remonte
    # telle quelle. La relance corrige un contenu, pas un transport.
    raise ErreurExtraction(erreurs, brut)


# Exercice 5 : le jeu de test


def charger_jeu(
    chemin: str | Path = JEU_DEFAUT, dossier: str | Path = DOSSIER_CORPUS
) -> list[dict[str, Any]]:
    cas = json.loads(Path(chemin).read_text(encoding="utf-8"))["cas"]
    connus = {d.id for d in charger_corpus(dossier)}
    vus: set[str] = set()
    for un_cas in cas:
        identifiant = un_cas["document"]
        # Un jeu de test faux est pire que pas de jeu : il fait echouer un bon
        # prompt et reussir un mauvais. On le valide avant de s'en servir.
        if identifiant not in connus:
            raise ValueError(f"{identifiant} : document absent du corpus")
        if identifiant in vus:
            raise ValueError(f"{identifiant} : document en double dans le jeu")
        vus.add(identifiant)
        erreurs = valider(un_cas["attendu"])
        if erreurs:
            raise ValueError(f"{identifiant} : attendu invalide ({'; '.join(erreurs)})")
    return cas


# Exercice 6 : noter un cas


@dataclass
class Resultat:
    document: str
    json_valide: bool
    cles_ok: bool
    valeurs_ok: bool
    ecarts: list[str] = field(default_factory=list)

    @property
    def reussi(self) -> bool:
        return self.json_valide and self.cles_ok and self.valeurs_ok


@dataclass
class Rapport:
    resultats: list[Resultat]

    @property
    def taux(self) -> float:
        if not self.resultats:
            return 0.0
        return sum(r.reussi for r in self.resultats) / len(self.resultats)

    @property
    def echecs(self) -> list[Resultat]:
        return [r for r in self.resultats if not r.reussi]


FORMES_JURIDIQUES = {"sa", "sas", "sasu", "sarl", "eurl", "sci"}


def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents.casefold()).split())


def _partie(nom: str) -> str:
    # « Hexalis » et « HEXALIS SAS » designent la meme organisation. Comparer
    # les chaines brutes ferait echouer un bon prompt sur un detail de forme.
    return " ".join(m for m in _normaliser(nom).split() if m not in FORMES_JURIDIQUES)


def _meme_montant(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return _nombre(a) and _nombre(b) and abs(a - b) < 0.01


def _comparer_echeances(obtenu: Any, attendu: list[dict[str, Any]]) -> list[str]:
    if not isinstance(obtenu, list) or not all(isinstance(e, dict) and "date" in e for e in obtenu):
        return ["echeances : format invalide"]
    obtenues = {e["date"]: e.get("montant_ht") for e in obtenu}
    attendues = {e["date"]: e["montant_ht"] for e in attendu}
    ecarts = []
    # Inventee et manquante sont deux defauts differents. Le premier est le
    # plus grave : une date inventee dans un JSON valide passe tous les
    # controles de forme (le prefill contraint le format, pas le contenu).
    inventees = sorted(set(obtenues) - set(attendues), key=str)
    manquantes = sorted(set(attendues) - set(obtenues))
    if inventees:
        ecarts.append(f"echeances inventees : {', '.join(map(str, inventees))}")
    if manquantes:
        ecarts.append(f"echeances manquantes : {', '.join(manquantes)}")
    for jour in sorted(set(obtenues) & set(attendues)):
        if not _meme_montant(obtenues[jour], attendues[jour]):
            ecarts.append(
                f"montant au {jour} : obtenu {obtenues[jour]!r}, attendu {attendues[jour]!r}"
            )
    return ecarts


def evaluer_cas(document: str, brut: str, attendu: dict[str, Any]) -> Resultat:
    # Critere 1 : le JSON est valide.
    try:
        obtenu = extraire_json(brut)
    except ValueError as erreur:
        return Resultat(document, False, False, False, [str(erreur)])

    # Critere 2 : les cles attendues sont presentes.
    manquantes = [cle for cle in CLES if cle not in obtenu]
    ecarts = [f"cles manquantes : {', '.join(manquantes)}"] if manquantes else []

    # Critere 3 : les valeurs correspondent, cle par cle, apres normalisation.
    valeurs: list[str] = []
    if "type" in obtenu and _normaliser(str(obtenu["type"])) != _normaliser(attendu["type"]):
        valeurs.append(f"type : obtenu {obtenu['type']!r}, attendu {attendu['type']!r}")
    if "date" in obtenu and obtenu["date"] != attendu["date"]:
        valeurs.append(f"date : obtenu {obtenu['date']!r}, attendu {attendu['date']!r}")
    if "parties" in obtenu:
        parties = obtenu["parties"]
        if not isinstance(parties, list) or not all(isinstance(p, str) for p in parties):
            valeurs.append("parties : format invalide")
        elif {_partie(p) for p in parties} != {_partie(p) for p in attendu["parties"]}:
            valeurs.append(f"parties : obtenu {parties}, attendu {attendu['parties']}")
    if "echeances" in obtenu:
        valeurs += _comparer_echeances(obtenu["echeances"], attendu["echeances"])

    return Resultat(document, True, not manquantes, not valeurs, ecarts + valeurs)


# Exercice 7 : evaluer un prompt sur tout le jeu


def evaluer(
    client: Any,
    jeu: list[dict[str, Any]],
    systeme: str | None = None,
    *,
    prefill: bool = False,
    tentatives: int = 1,
    modele: str = MODELE_DEFAUT,
    dossier: str | Path = DOSSIER_CORPUS,
) -> Rapport:
    # Une seule tentative par defaut : on mesure le PROMPT. Avec la relance,
    # on mesure le prompt plus son rattrapage, et un mauvais prompt peut
    # sembler bon au prix de deux fois plus d'appels.
    corpus = {d.id: d for d in charger_corpus(dossier)}
    resultats = []
    for cas in jeu:
        try:
            donnees = extraire(
                client,
                corpus[cas["document"]],
                systeme,
                prefill=prefill,
                tentatives=tentatives,
                modele=modele,
            )
            brut = json.dumps(donnees, ensure_ascii=False)
        except ErreurExtraction as erreur:
            # La reponse fautive est notee quand meme : on veut savoir si
            # elle a echoue sur la forme, les cles ou les valeurs.
            brut = erreur.brut
        resultats.append(evaluer_cas(cas["document"], brut, cas["attendu"]))
    return Rapport(resultats)


def resume(rapport: Rapport) -> str:
    total = len(rapport.resultats)
    reussis = total - len(rapport.echecs)
    lignes = [f"Taux de reussite : {reussis}/{total} ({rapport.taux * 100:.0f} %)"]
    if not rapport.echecs:
        lignes.append("Aucun echec.")
    else:
        lignes.append("Echecs :")
        lignes += [f"- {r.document} : {'; '.join(r.ecarts)}" for r in rapport.echecs]
    return "\n".join(lignes)


# Bonus : le juge

SYSTEME_JUGE = (
    "<role>\nTu evalues une extraction de metadonnees faite par un autre modele.\n</role>\n\n"
    "<instructions>\n"
    "1. Compare l'extraction au document, champ par champ.\n"
    "2. Releve toute valeur absente du document (invention) et toute echeance de paiement "
    "oubliee.\n"
    "3. Raisonne dans <analyse>, puis donne une note entiere de 1 a 5 dans <note>, "
    "5 signifiant exacte et complete.\n"
    "</instructions>"
)


def juger(client: Any, document: Document, extraction: dict[str, Any]) -> int:
    # Ici, le raisonnement pas a pas vaut ses tokens : juger est une tache de
    # comparaison, pas une extraction simple. La note en balise se recupere
    # sans ambiguite meme apres un long raisonnement.
    reponse = client.messages.create(
        model=MODELE_DEFAUT,
        max_tokens=MAX_TOKENS_DEFAUT,
        system=SYSTEME_JUGE,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{bloc_document(document)}\n\n"
                    f"<extraction>\n{json.dumps(extraction, ensure_ascii=False)}\n</extraction>"
                    "\n\nNote cette extraction."
                ),
            }
        ],
    )
    trouve = re.search(r"<note>\s*(\d+)\s*</note>", texte_de(reponse))
    if not trouve or not 1 <= int(trouve.group(1)) <= 5:
        # Une note illisible n'est pas une note moyenne : on refuse de deviner.
        raise ValueError("le juge n'a pas rendu de note entre 1 et 5 dans <note>")
    return int(trouve.group(1))


def divergences(juge: dict[str, int], humain: dict[str, int], ecart_max: int = 1) -> list[str]:
    # Le juge herite des biais du modele qu'il evalue. Avant de lui confier
    # un tri en masse, on mesure ou il s'ecarte de votre propre jugement.
    return [
        document
        for document, note in humain.items()
        if document not in juge or abs(juge[document] - note) > ecart_max
    ]
