"""Section 10, corrige commente.

Les commentaires expliquent le pourquoi, pas le comment : le comment est
dans le code. L'objectif de l'atelier est de rendre Doc42 observable et
borne sans changer une ligne de sa logique metier : tout ce qui suit
s'enroule autour de doc42.client, rien ne le remplace.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import anthropic

from doc42.client import REJOUABLES, appel_simple, avec_reprise
from doc42.config import (
    FACTEUR_CACHE_ECRIT,
    FACTEUR_CACHE_LU,
    MAX_TOKENS_DEFAUT,
    MODELE_DEFAUT,
    MODELE_PROFOND,
    MODELE_RAPIDE,
    RACINE,
    SYSTEME_DOC42,
    TARIFS,
)

# ---------------------------------------------------------------------------
# Exercice 1 : le cout d'un appel
# ---------------------------------------------------------------------------


def _jetons(usage: Any, champ: str) -> int:
    # Le SDK rend None (et non 0) pour les champs de cache quand le cache
    # n'a pas servi. "or 0" evite un TypeError au pire moment : en prod.
    return int(getattr(usage, champ, 0) or 0)


def cout_appel(modele: str, usage: Any) -> float:
    if modele not in TARIFS:
        # Un cout silencieusement nul serait pire qu'une erreur : le tableau
        # de bord afficherait une fonctionnalite gratuite.
        raise ValueError(f"Pas de tarif pour {modele!r} dans doc42.config.TARIFS.")
    entree, sortie = TARIFS[modele]
    # input_tokens n'inclut PAS les jetons de cache : ce sont trois postes
    # distincts. Oublier l'ecriture en cache (le piege de l'exemple Notion)
    # sous-estime precisement l'appel qui coute le plus cher, le premier.
    total = (
        _jetons(usage, "input_tokens") * entree
        + _jetons(usage, "cache_read_input_tokens") * entree * FACTEUR_CACHE_LU
        + _jetons(usage, "cache_creation_input_tokens") * entree * FACTEUR_CACHE_ECRIT
        + _jetons(usage, "output_tokens") * sortie
    )
    return total / 1_000_000


# ---------------------------------------------------------------------------
# Exercice 2 : un log JSON par appel
# ---------------------------------------------------------------------------

# Au moins 8 caracteres apres le prefixe : on masque une vraie cle, pas la
# mention "sk-ant-..." d'une documentation.
MOTIF_CLE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")


def masquer_secrets(texte: str) -> str:
    return MOTIF_CLE.sub("sk-ant-***", texte)


def maintenant_utc() -> datetime:
    return datetime.now(UTC)


def nouvel_identifiant() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


class ClientInstrumente:
    """Se presente comme un client Anthropic : client.messages.create(**kwargs).

    C'est ce qui permet de le brancher sur doc42.client sans le modifier.
    """

    CONTEXTE = ("feature", "prompt_version", "user_id", "question_id")

    def __init__(
        self,
        client: Any,
        ecrire: Callable[[str], None],
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
        self.ecrire = ecrire
        self.feature = feature
        self.prompt_version = prompt_version
        self.user_id = user_id
        self.question_id = question_id
        self.horloge = horloge
        self.chrono = chrono
        self.generer_id = generer_id
        self.messages = self

    def avec(self, **contexte: Any) -> ClientInstrumente:
        inconnus = set(contexte) - set(self.CONTEXTE)
        if inconnus:
            raise TypeError(f"Contexte inconnu : {sorted(inconnus)}")
        copie = copy.copy(self)
        for cle, valeur in contexte.items():
            setattr(copie, cle, valeur)
        copie.messages = copie
        return copie

    def create(self, **kwargs: Any) -> Any:
        # Que des metadonnees : ni messages ni system. Un log qui contient la
        # conversation est une fuite de donnees personnelles qui dort sur disque.
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
        # Horloge monotone pour la duree : l'horloge murale peut reculer
        # (synchronisation NTP) et donnerait des latences negatives.
        debut = self.chrono()
        try:
            reponse = self.client.messages.create(**kwargs)
        except Exception as erreur:
            # Attraper large est legitime ICI parce qu'on relance aussitot :
            # on observe, on ne decide pas. Le tri rejouable ou pas reste a
            # avec_reprise.
            ligne.update(
                level="error",
                success=False,
                latency_ms=round((self.chrono() - debut) * 1000),
                cost_usd=0.0,
                error_type=type(erreur).__name__,
                # Un message d'erreur peut citer un en-tete ou une cle : on masque.
                error_message=masquer_secrets(str(erreur)),
            )
            self.ecrire(json.dumps(ligne, ensure_ascii=False))
            raise

        latence = round((self.chrono() - debut) * 1000)
        usage = reponse.usage
        try:
            # Le modele DEMANDE fait foi pour le tarif : c'est celui de la config.
            cout: float | None = round(cout_appel(ligne["model"], usage), 6)
        except ValueError:
            # L'observabilite ne doit jamais casser le produit : un modele sans
            # tarif donne un cout inconnu, pas une exception a l'utilisateur.
            cout = None
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


# ---------------------------------------------------------------------------
# Exercice 3 : agreger les journaux
# ---------------------------------------------------------------------------


def _centile(valeurs: list[float], p: float) -> float | None:
    # Methode du rang le plus proche : simple, sans interpolation, et c'est ce
    # que font la plupart des outils d'alerte.
    if not valeurs:
        return None
    triees = sorted(valeurs)
    rang = max(1, math.ceil(p / 100 * len(triees)))
    return triees[rang - 1]


def agreger(lignes: Iterable[str | dict[str, Any]]) -> dict[str, Any]:
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
        # Une question peut couter plusieurs appels (boucle d'outils, agent,
        # reprises) : c'est le question_id qui les relie. Sans lui, un appel
        # isole est sa propre question.
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


# ---------------------------------------------------------------------------
# Exercice 4 : les trois leviers de cout
# ---------------------------------------------------------------------------

# Levier 1 : le moins cher qui fait le travail. Trier, classer, extraire ne
# demandent pas le modele de travail.
FEATURES_LEGERES = frozenset({"classification", "extraction", "routage", "moderation"})


def choisir_modele(feature: str) -> str:
    if feature in FEATURES_LEGERES:
        return MODELE_RAPIDE
    if feature == "raisonnement_critique":
        return MODELE_PROFOND
    # Une fonctionnalite inconnue va sur le defaut, pas sur le profond :
    # monter en gamme se decide apres un echec constate, pas par prudence.
    return MODELE_DEFAUT


# Levier 3 : max_tokens est un plafond, pas une cible, mais un plafond trop
# haut laisse deriver les reponses. Ces valeurs viennent des mesures : on
# regarde output_tokens au p99 dans les journaux, on ajoute une marge.
MAX_TOKENS_PAR_FEATURE: dict[str, int] = {
    "classification": 16,
    "routage": 16,
    "extraction": 400,
    "question": 600,
    "synthese": 900,
}


def parametres(
    feature: str, question: str, corpus_reference: str = "", systeme: str = SYSTEME_DOC42
) -> dict[str, Any]:
    # Levier 2 : le cache ne marche que sur un prefixe STRICTEMENT identique.
    # Tout ce qui est stable (systeme, corpus) vient d'abord, le point de
    # cache est pose sur le dernier bloc stable, la question vient apres.
    # Un horodatage ou un nom d'utilisateur dans system casserait le cache
    # sans aucun message d'erreur : on ne le voit que sur la facture.
    # Note : sous la taille minimale cacheable du modele, cache_control est
    # ignore sans erreur. cache_creation_input_tokens dans les logs le dira.
    blocs: list[dict[str, Any]] = [{"type": "text", "text": systeme}]
    if corpus_reference:
        blocs.append({"type": "text", "text": corpus_reference})
    blocs[-1]["cache_control"] = {"type": "ephemeral"}
    return {
        "model": choisir_modele(feature),
        "max_tokens": MAX_TOKENS_PAR_FEATURE.get(feature, MAX_TOKENS_DEFAUT),
        "system": blocs,
        "messages": [{"role": "user", "content": question}],
    }


# ---------------------------------------------------------------------------
# Exercice 5 : reprise, disjoncteur, reponse degradee
# ---------------------------------------------------------------------------

MESSAGE_DEGRADE = (
    "Doc42 est momentanement indisponible. Votre question n'est pas perdue : "
    "reessayez dans une minute."
)


class CircuitOuvert(Exception):
    """Le disjoncteur refuse l'appel sans contacter l'API."""


class Disjoncteur:
    def __init__(
        self, seuil: int = 5, delai_s: float = 60.0, chrono: Callable[[], float] = time.monotonic
    ) -> None:
        self.seuil = seuil
        self.delai_s = delai_s
        self.chrono = chrono
        self.etat = "ferme"
        self.echecs = 0
        self.ouvert_depuis: float | None = None

    def appeler(self, appel: Callable[[], Any]) -> Any:
        if self.etat == "ouvert":
            if self.chrono() - self.ouvert_depuis < self.delai_s:
                # Echouer tout de suite, c'est le service rendu : pas de
                # requete de plus sur une API deja a genoux, et l'utilisateur
                # a sa reponse degradee en une milliseconde au lieu de 30 s.
                raise CircuitOuvert("Circuit ouvert : appel refuse sans contacter l'API.")
            # Le delai est ecoule : on laisse passer UN appel d'essai.
            self.etat = "semi_ouvert"
        try:
            resultat = appel()
        except REJOUABLES:
            # Seules les pannes du service comptent. Un 400 est un bug de
            # notre code : couper le circuit le masquerait derriere un
            # message degrade au lieu de le faire corriger.
            self.echecs += 1
            if self.etat == "semi_ouvert" or self.echecs >= self.seuil:
                self.etat = "ouvert"
                self.ouvert_depuis = self.chrono()
            raise
        self.etat = "ferme"
        self.echecs = 0
        return resultat


def creer_client_production(
    cle: str | None = None,
    *,
    base_url: str | None = None,
    http_client: Any = None,
    timeout: float = 30.0,
) -> anthropic.Anthropic:
    # max_retries=0 : le SDK rejoue deja deux fois par defaut. Empile sous
    # avec_reprise, cela fait 3 x 5 = 15 requetes pour une seule question,
    # et des attentes que nos journaux ne voient pas.
    # timeout explicite : sans lui, un client reste pendu des minutes quand
    # l'API ralentit (anti-pattern de la section 10.1).
    # cle=None : le SDK lit ANTHROPIC_API_KEY. La cle vient de l'environnement
    # ou du gestionnaire de secrets, jamais du code.
    return anthropic.Anthropic(
        api_key=cle,
        base_url=base_url,
        http_client=http_client,
        max_retries=0,
        timeout=timeout,
    )


def repondre(
    client: Any,
    question: str,
    disjoncteur: Disjoncteur,
    tentatives: int = 3,
    dormir: Callable[[float], None] = time.sleep,
) -> str:
    # Le disjoncteur est A L'INTERIEUR de la reprise : chaque tentative compte,
    # et des que le circuit s'ouvre, CircuitOuvert (non rejouable) arrete la
    # reprise net au lieu de dormir pour rien.
    def une_tentative() -> str:
        return disjoncteur.appeler(lambda: appel_simple(client, question))

    try:
        return avec_reprise(une_tentative, tentatives=tentatives, dormir=dormir)
    except (CircuitOuvert, *REJOUABLES):
        # Une panne devient un message. Le reste (400, 401, bug) remonte :
        # ce sont des erreurs a corriger, pas a cacher.
        return MESSAGE_DEGRADE


# ---------------------------------------------------------------------------
# Exercice 6 : prompts versionnes
# ---------------------------------------------------------------------------

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


def charger_prompt(
    nom: str, version: str = "courante", dossier: str | Path = DOSSIER_PROMPTS
) -> Prompt:
    dossier = Path(dossier)
    registre = json.loads((dossier / "registre.json").read_text(encoding="utf-8"))
    if nom not in registre:
        raise KeyError(f"Prompt inconnu : {nom}")
    entree = registre[nom]
    version = entree["courante"] if version == "courante" else version
    if version not in entree["versions"]:
        raise KeyError(f"Version inconnue pour {nom} : {version}")
    brut = (dossier / f"{nom}.{version}.md").read_bytes()
    empreinte = hashlib.sha256(brut).hexdigest()
    if empreinte != entree["versions"][version]:
        # Une version publiee est immuable. Si on la retouche, les logs
        # d'hier et d'aujourd'hui portent la meme etiquette pour deux prompts
        # differents, et toute comparaison de metriques devient fausse.
        raise ValueError(
            f"{nom}.{version}.md a ete modifie apres publication. "
            "Creez une nouvelle version au lieu de retoucher celle-ci."
        )
    return Prompt(nom, version, brut.decode("utf-8").strip(), empreinte)


# ---------------------------------------------------------------------------
# Exercice 7 : quota par utilisateur et validation d'entree
# ---------------------------------------------------------------------------

LONGUEUR_MAX_QUESTION = 10_000


class QuotaDepasse(Exception):
    """L'utilisateur a epuise son quota du jour (a traduire en HTTP 429)."""


class Quota:
    def __init__(
        self,
        requetes_par_jour: int = 100,
        budget_usd_par_jour: float = 1.0,
        horloge: Callable[[], datetime] = maintenant_utc,
    ) -> None:
        self.requetes_par_jour = requetes_par_jour
        self.budget_usd_par_jour = budget_usd_par_jour
        self.horloge = horloge
        self._jour: date | None = None
        self._compteurs: dict[str, dict[str, float]] = {}

    def _du_jour(self, utilisateur: str) -> dict[str, float]:
        # Le jour vient de l'horloge injectee, en UTC : le test peut
        # changer de jour sans attendre minuit.
        jour = self.horloge().date()
        if jour != self._jour:
            self._jour = jour
            self._compteurs = {}
        return self._compteurs.setdefault(utilisateur, {"requetes": 0, "cout_usd": 0.0})

    def reserver(self, utilisateur: str) -> None:
        compteur = self._du_jour(utilisateur)
        if compteur["requetes"] >= self.requetes_par_jour:
            raise QuotaDepasse(f"{utilisateur} : {self.requetes_par_jour} requetes aujourd'hui.")
        if compteur["cout_usd"] >= self.budget_usd_par_jour:
            raise QuotaDepasse(f"{utilisateur} : budget de {self.budget_usd_par_jour} $ atteint.")
        # On compte AVANT l'appel : compter apres laisserait passer une
        # rafale de requetes simultanees.
        compteur["requetes"] += 1

    def imputer(self, utilisateur: str, cout_usd: float | None) -> None:
        # Jamais d'exception ici : l'appel a eu lieu, il est paye. Le
        # depassement sera refuse a la prochaine reservation.
        self._du_jour(utilisateur)["cout_usd"] += cout_usd or 0.0


def valider_question(question: str) -> str:
    if not isinstance(question, str):
        raise TypeError("La question doit etre une chaine.")
    propre = question.strip()
    if not propre:
        raise ValueError("Question vide : rien a envoyer.")
    if len(propre) > LONGUEUR_MAX_QUESTION:
        # Refuser avant l'appel : une entree geante est un cout, pas une question.
        raise ValueError(f"Question trop longue ({len(propre)} > {LONGUEUR_MAX_QUESTION}).")
    return propre
