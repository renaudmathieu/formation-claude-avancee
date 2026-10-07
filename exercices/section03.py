"""Section 3, atelier. Sept exercices et un bonus, une heure et quart.

Completez les fonctions marquees TODO, puis lancez :

    uv run pytest tests/test_section03.py -v

Les enonces sont dans les docstrings. Vous n'avez pas besoin de revenir
sur Notion pendant l'atelier.

Le fil de l'atelier : Doc42 extrait les metadonnees d'un document en JSON
(type, date, parties, echeances de paiement), et vous savez dire a quel taux
de reussite. Le jeu de test de reference est dans evals/attendu.json : a
l'etape 3, ecrivez d'abord le votre a la main, PUIS comparez avec celui-ci.
"""

from __future__ import annotations

import json  # noqa: F401
import re  # noqa: F401
import unicodedata  # noqa: F401  (utile pour comparer des noms sans accents)
from dataclasses import dataclass, field
from datetime import date  # noqa: F401
from pathlib import Path
from typing import Any

from doc42.client import texte_de  # noqa: F401  (concatene les blocs texte, section 2)
from doc42.config import DOSSIER_CORPUS, MAX_TOKENS_DEFAUT, MODELE_DEFAUT  # noqa: F401
from doc42.corpus import Document, charger_corpus  # noqa: F401

RACINE = Path(__file__).resolve().parent.parent
JEU_DEFAUT = RACINE / "evals" / "attendu.json"

# Le contrat de sortie. Ne le modifiez pas : le jeu de test est ecrit contre lui.
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

# Le meme contrat en JSON Schema, a inserer tel quel dans votre prompt.
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


def construire_systeme(exemple: bool = True) -> str:
    """Exercice 1 (etape 2). Le prompt systeme structure de l'extraction.

    Les conventions a transmettre au modele sont celles du jeu de test
    (lisez le champ "description" de evals/attendu.json) :
      - date : AAAA-MM-JJ ; signature pour un contrat ou un avenant, emission
        pour une facture, sinon la date d'en-tete ; jamais la date d'un
        evenement decrit dans le document ; null si absente
      - parties : organisations engagees par un contrat, un avenant ou une
        facture, liste vide pour les autres types
      - echeances : dates auxquelles une somme est payable ou facturee, avec
        montant_ht (hors taxes, null si le document ne le precise pas) ; une
        echeance recurrente est developpee sur la duree du document

    Attendu :
      - cinq blocs balises, dans cet ordre : <role>, <context>, <instructions>,
        <constraints>, <examples> (chacun ouvert ET ferme)
      - <instructions> contient des instructions numerotees (« 1. », « 2. »...)
      - chaque cle de CLES et chaque valeur de TYPES apparait dans le prompt
      - <constraints> exige un document sans echeance => "echeances": [] (ou
        « liste vide »), et contient le SCHEMA (json.dumps)
      - <examples> contient un exemple : un court document FICTIF et sa sortie,
        un seul objet JSON dans le bloc, et cet objet passe valider()
      - l'exemple n'emprunte rien au jeu de test (aucune partie du jeu autre
        qu'Hexalis) : sinon vous donnez la reponse et la mesure est faussee
      - exemple=False : meme prompt, sans le bloc <examples> (etape 6)
    """
    # TODO
    raise NotImplementedError


def extraire_json(texte: str) -> dict[str, Any]:
    """Exercice 2. Decode l'objet JSON d'une reponse, sans faire confiance au modele.

    Demander « uniquement du JSON » ne suffit pas toujours : la reponse peut
    arriver entouree de ```json ... ```, ou precedee d'une phrase.

    Attendu :
      - accepte un JSON nu, un JSON entre balises de code (```json ou ```),
        un JSON entoure de texte
      - leve ValueError (et rien d'autre) si aucun objet JSON valide n'est
        trouve, si le JSON est tronque, ou si la racine n'est pas un objet
      - retourne un dict
    """
    # TODO
    raise NotImplementedError


def valider(donnees: Any) -> list[str]:
    """Exercice 3. Valide des donnees contre le contrat (SCHEMA).

    Retourne la liste de TOUTES les erreurs, en francais, chacune nommant la
    cle fautive. Liste vide si tout est conforme. Ne leve jamais d'exception :
    ces messages partent tels quels dans la relance (exercice 4).

    Attendu :
      - racine : un dict, sinon une erreur
      - cles : chaque cle de CLES presente, aucune cle en plus
      - type : une valeur de TYPES (exactement)
      - date : chaine AAAA-MM-JJ qui est une vraie date (2027-02-30 est
        refusee), ou None
      - parties : liste de chaines non vides
      - echeances : liste d'objets ayant exactement les cles date et
        montant_ht ; date au format AAAA-MM-JJ (obligatoire) ; montant_ht
        nombre positif ou None. Attention : True est un int en Python.
    """
    # TODO
    raise NotImplementedError


class ErreurExtraction(Exception):
    """Levee quand l'extraction reste invalide apres toutes les tentatives.

    erreurs : les erreurs de la derniere tentative ; brut : son texte brut.
    """

    def __init__(self, erreurs: list[str], brut: str) -> None:
        super().__init__("; ".join(erreurs))
        self.erreurs = erreurs
        self.brut = brut


def extraire(
    client: Any,
    document: Document,
    systeme: str | None = None,
    *,
    prefill: bool = False,
    tentatives: int = 3,
    modele: str = MODELE_DEFAUT,
) -> dict[str, Any]:
    """Exercice 4 (etapes 2 et 6). Extrait les metadonnees d'un document, avec relance.

    Attendu :
      - system vaut construire_systeme() si `systeme` est None ; model vaut
        `modele`, max_tokens vient de doc42.config
      - le message user contient document.texte entre <document ...> et
        </document>, PUIS la consigne (le document avant la question)
      - la reponse est decodee par extraire_json() et validee par valider()
      - si elle est invalide (JSON ou schema) : relance. On ajoute a
        l'historique la reponse fautive (role assistant) puis un message user
        qui liste les erreurs, et on rappelle l'API ; au plus `tentatives`
        appels au total, puis ErreurExtraction(erreurs, brut)
      - une erreur de l'API (400, 429...) n'est PAS relancee : elle remonte
      - prefill=True : chaque envoi se termine par {"role": "assistant",
        "content": "{"}. Le modele continue APRES l'accolade : remettez-la
        devant sa reponse avant de decoder.

    Piege : les modeles recents (famille 4.6 et suivantes) refusent le
    prefill avec une erreur 400. Pour l'etape 6, mesurez-le avec un modele
    qui l'accepte (MODELE_RAPIDE, a verifier dans la documentation du modele).
    """
    # TODO
    raise NotImplementedError


def charger_jeu(
    chemin: str | Path = JEU_DEFAUT, dossier: str | Path = DOSSIER_CORPUS
) -> list[dict[str, Any]]:
    """Exercice 5 (etape 3). Charge le jeu de test ET le verifie.

    Format : {"description": "...", "cas": [{"document": id, "note": "...",
    "attendu": {...}}, ...]}. Retourne la liste "cas".

    Attendu :
      - ValueError si un document n'existe pas dans le corpus `dossier`
      - ValueError si un document apparait deux fois
      - ValueError, avec l'identifiant du document dans le message, si un
        attendu ne passe pas valider()

    Un jeu de test faux est pire que pas de jeu : il fait echouer un bon
    prompt et reussir un mauvais.
    """
    # TODO
    raise NotImplementedError


@dataclass
class Resultat:
    """Le verdict sur un document. Donne, a ne pas modifier."""

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
    """Le verdict sur tout le jeu. Donne, a ne pas modifier."""

    resultats: list[Resultat]

    @property
    def taux(self) -> float:
        if not self.resultats:
            return 0.0
        return sum(r.reussi for r in self.resultats) / len(self.resultats)

    @property
    def echecs(self) -> list[Resultat]:
        return [r for r in self.resultats if not r.reussi]


def evaluer_cas(document: str, brut: str, attendu: dict[str, Any]) -> Resultat:
    """Exercice 6 (etapes 4 et 7). Note une reponse brute contre l'attendu.

    Trois criteres : le JSON est valide, les cles attendues sont presentes,
    les valeurs correspondent.

    Attendu :
      - JSON invalide : json_valide, cles_ok et valeurs_ok a False, un ecart
      - cles : cles_ok False si une cle de CLES manque, l'ecart la nomme
      - valeurs, comparees seulement pour les cles presentes :
          type : sans tenir compte de la casse ni des accents
          date : egalite exacte
          parties : comme ensembles, sans casse, accents, ponctuation ni forme
            juridique (« hexalis » == « Hexalis SAS »), l'ordre ne compte pas
          echeances : par date, l'ordre ne compte pas ; montants egaux a un
            centime pres (8052 == 8052.0), None n'egale que None
      - les ecarts nomment la cle et la date fautives. Une echeance absente de
        l'attendu est signalee « inventee », une echeance attendue absente de
        la reponse est signalee « manquante »
      - une reponse mal formee (parties qui n'est pas une liste...) donne un
        ecart, jamais une exception

    Etape 7 : sur un document sans echeance, une date en trop doit faire
    echouer le cas. Le prefill contraint le format, pas le contenu.
    """
    # TODO
    raise NotImplementedError


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
    """Exercice 7 (etape 4). Passe le prompt sur tout le jeu et note chaque cas.

    Attendu :
      - un appel a extraire() par cas, dans l'ordre du jeu, avec le document
        du corpus `dossier` et les options recues
      - si extraire() leve ErreurExtraction, le cas est quand meme note, sur
        la reponse brute fautive (erreur.brut)
      - tentatives vaut 1 par defaut : on mesure le prompt, pas la relance
      - retourne un Rapport avec un Resultat par cas, dans l'ordre
    """
    # TODO
    raise NotImplementedError


def resume(rapport: Rapport) -> str:
    """Exercice 7, suite. Le texte que affiche evals/lancer.py.

    Attendu :
      - une ligne « Taux de reussite : 8/10 (80 %) »
      - puis chaque echec avec son identifiant de document et ses ecarts,
        ou « Aucun echec. »
      - les documents reussis n'apparaissent pas
    """
    # TODO
    raise NotImplementedError


def juger(client: Any, document: Document, extraction: dict[str, Any]) -> int:
    """Bonus. Le pattern juge : un second appel note l'extraction de 1 a 5.

    Attendu :
      - le message user contient le texte du document ET l'extraction en JSON
      - un prompt systeme qui demande de raisonner, puis la note dans
        <note>N</note>
      - modele et max_tokens viennent de doc42.config
      - retourne la note (int). ValueError si la reponse n'a pas de <note>
        ou si la note sort de 1 a 5 : une note illisible n'est pas une note
        moyenne
    """
    # TODO
    raise NotImplementedError


def divergences(juge: dict[str, int], humain: dict[str, int], ecart_max: int = 1) -> list[str]:
    """Bonus, suite. Ou le juge s'ecarte-t-il de votre propre jugement ?

    juge et humain associent un identifiant de document a une note.

    Attendu :
      - les documents notes par l'humain dont la note du juge differe de plus
        de `ecart_max`, ou que le juge n'a pas notes
      - dans l'ordre du dictionnaire humain
    """
    # TODO
    raise NotImplementedError


# Etape 1 de l'atelier, sans test
#
# Avant l'exercice 1, ecrivez un premier prompt sans structure (un paragraphe)
# et lancez-le sur contrat_alpha, facture_F2026-118 et
# rapport_incident_2026-08-12. Notez ce qui varie d'un document a l'autre :
# noms des cles, format des dates, montants en chaines, texte autour du JSON.
#
# PROMPT_V1 = "..."
#
# Ce que j'ai observe :


# Etape 5 de l'atelier, sans test
#
# Mesurez le prompt de l'etape 1 et celui de l'exercice 1 sur les dix
# documents, avec evaluer() et resume() (ou evals/lancer.py). Ecrivez les
# deux chiffres. C'est la premiere fois qu'on remplace une impression par
# une mesure.
#
# Prompt v1 : ../10      Prompt v2 : ../10


# Etape 6 de l'atelier, sans test
#
# Un changement a la fois, une mesure a chaque fois :
#   - v2 + prefill=True (avec un modele qui accepte le prefill) : ../10
#   - v2 sans exemple, construire_systeme(exemple=False) : ../10
# Quel changement a produit le gain ou la perte ?


# Etape 8 de l'atelier, sans test
#
# Versionnez : prompts/extraction.v1.md, prompts/extraction.v2.md et
# prompts/CHANGELOG.md, qui dit pourquoi on est passe de l'un a l'autre et
# ce que la mesure a donne. Le prompt fait partie du code.


# Bonus, sans test
#
# Faites noter les dix extractions par juger(), notez-les vous-meme de 1 a 5,
# puis appelez divergences(). Sur quels documents le juge diverge-t-il ?
# Lui confieriez-vous un tri en masse ? Un cas limite ?
