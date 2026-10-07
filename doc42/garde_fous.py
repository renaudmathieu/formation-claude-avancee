"""Garde-fous de production de Doc42 (section 10).

Routage de modele, prompt cache, max_tokens par fonctionnalite, disjoncteur,
reponse degradee, quota par utilisateur, validation d'entree. La logique
metier de doc42.client ne change pas : on l'entoure.

Exemple :

    from doc42.garde_fous import Disjoncteur, Quota, client_de_production, repondre
    from doc42.prompts import charger_prompt

    prompt = charger_prompt("doc42_systeme")
    client = client_de_production("journaux/appels.jsonl", prompt_version=prompt.identifiant)
    print(repondre(client, "Quelles echeances ?", Disjoncteur(), quota=Quota(),
                   utilisateur="u42", systeme=prompt.texte))
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import anthropic

from doc42 import observabilite
from doc42.client import REJOUABLES, avec_reprise, texte_de
from doc42.config import (
    MAX_TOKENS_DEFAUT,
    MODELE_DEFAUT,
    MODELE_PROFOND,
    MODELE_RAPIDE,
    SYSTEME_DOC42,
)

# --- Les trois leviers de cout ----------------------------------------------

FEATURES_LEGERES = frozenset({"classification", "extraction", "routage", "moderation"})

# Valeurs a recaler sur les journaux : output_tokens au p99, plus une marge.
MAX_TOKENS_PAR_FEATURE: dict[str, int] = {
    "classification": 16,
    "routage": 16,
    "extraction": 400,
    "question": 600,
    "synthese": 900,
}


def choisir_modele(feature: str) -> str:
    """Le modele le moins cher qui fait le travail."""
    if feature in FEATURES_LEGERES:
        return MODELE_RAPIDE
    if feature == "raisonnement_critique":
        return MODELE_PROFOND
    return MODELE_DEFAUT


def parametres(
    feature: str, question: str, corpus_reference: str = "", systeme: str = SYSTEME_DOC42
) -> dict[str, Any]:
    """Les kwargs de messages.create : modele route, prefixe stable cache, max_tokens borne.

    Le prefixe (systeme puis corpus) ne contient rien de variable : un
    horodatage ou un nom d'utilisateur y annulerait le cache sans prevenir.
    """
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


# --- Disjoncteur et reponse degradee ------------------------------------------

MESSAGE_DEGRADE = (
    "Doc42 est momentanement indisponible. Votre question n'est pas perdue : "
    "reessayez dans une minute."
)


class CircuitOuvert(Exception):
    """Le disjoncteur refuse l'appel sans contacter l'API."""


class Disjoncteur:
    """Circuit breaker : ferme, ouvert apres `seuil` pannes, semi-ouvert apres `delai_s`."""

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
                raise CircuitOuvert("Circuit ouvert : appel refuse sans contacter l'API.")
            self.etat = "semi_ouvert"
        try:
            resultat = appel()
        except REJOUABLES:
            # Seules les pannes du service comptent ; un 400 est un bug a corriger.
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
    """Client sans reprise interne (avec_reprise s'en charge) et avec un timeout.

    cle=None : le SDK lit ANTHROPIC_API_KEY (fichier .env ou gestionnaire de secrets).
    """
    return anthropic.Anthropic(
        api_key=cle, base_url=base_url, http_client=http_client, max_retries=0, timeout=timeout
    )


def client_de_production(
    chemin_journal: str | Path | None = None, **contexte: Any
) -> observabilite.ClientInstrumente:
    """Le client de production instrumente, journal JSON Lines optionnel."""
    ecrire = observabilite.journal_fichier(chemin_journal) if chemin_journal else None
    return observabilite.ClientInstrumente(creer_client_production(), ecrire, **contexte)


# --- Quota et validation d'entree ---------------------------------------------

LONGUEUR_MAX_QUESTION = 10_000


class QuotaDepasse(Exception):
    """L'utilisateur a epuise son quota du jour (a traduire en HTTP 429)."""


class Quota:
    """Quota quotidien par utilisateur, en requetes et en dollars. Jour UTC de `horloge`."""

    def __init__(
        self,
        requetes_par_jour: int = 100,
        budget_usd_par_jour: float = 1.0,
        horloge: Callable[[], datetime] = observabilite.maintenant_utc,
    ) -> None:
        self.requetes_par_jour = requetes_par_jour
        self.budget_usd_par_jour = budget_usd_par_jour
        self.horloge = horloge
        self._jour: date | None = None
        self._compteurs: dict[str, dict[str, float]] = {}

    def _du_jour(self, utilisateur: str) -> dict[str, float]:
        jour = self.horloge().date()
        if jour != self._jour:
            self._jour = jour
            self._compteurs = {}
        return self._compteurs.setdefault(utilisateur, {"requetes": 0, "cout_usd": 0.0})

    def reserver(self, utilisateur: str) -> None:
        """Avant l'appel. Leve QuotaDepasse si une limite du jour est atteinte."""
        compteur = self._du_jour(utilisateur)
        if compteur["requetes"] >= self.requetes_par_jour:
            raise QuotaDepasse(f"{utilisateur} : {self.requetes_par_jour} requetes aujourd'hui.")
        if compteur["cout_usd"] >= self.budget_usd_par_jour:
            raise QuotaDepasse(f"{utilisateur} : budget de {self.budget_usd_par_jour} $ atteint.")
        compteur["requetes"] += 1

    def imputer(self, utilisateur: str, cout_usd: float | None) -> None:
        """Apres l'appel. Ne leve jamais : l'appel a eu lieu."""
        self._du_jour(utilisateur)["cout_usd"] += cout_usd or 0.0


def valider_question(question: str) -> str:
    """Rend la question nettoyee, ou leve ValueError si vide ou trop longue."""
    if not isinstance(question, str):
        raise TypeError("La question doit etre une chaine.")
    propre = question.strip()
    if not propre:
        raise ValueError("Question vide : rien a envoyer.")
    if len(propre) > LONGUEUR_MAX_QUESTION:
        raise ValueError(f"Question trop longue ({len(propre)} > {LONGUEUR_MAX_QUESTION}).")
    return propre


# --- Le point d'entree de production ------------------------------------------


def repondre(
    client: Any,
    question: str,
    disjoncteur: Disjoncteur,
    tentatives: int = 3,
    dormir: Callable[[float], None] = time.sleep,
    *,
    quota: Quota | None = None,
    utilisateur: str = "anonyme",
    feature: str = "question",
    systeme: str = SYSTEME_DOC42,
    corpus_reference: str = "",
) -> str:
    """Repond a une question avec tous les garde-fous, ou rend MESSAGE_DEGRADE en cas de panne.

    Raises:
        ValueError: Question vide ou trop longue (avant tout appel).
        QuotaDepasse: Quota du jour epuise (avant tout appel).
        anthropic.APIStatusError: Erreur non rejouable (400, 401...) : un bug a corriger.
    """
    question = valider_question(question)
    if quota is not None:
        quota.reserver(utilisateur)
    kwargs = parametres(feature, question, corpus_reference, systeme)

    def une_tentative() -> Any:
        # Le disjoncteur est dans la reprise : CircuitOuvert arrete les tentatives.
        return disjoncteur.appeler(lambda: client.messages.create(**kwargs))

    try:
        reponse = avec_reprise(une_tentative, tentatives=tentatives, dormir=dormir)
    except (CircuitOuvert, *REJOUABLES):
        return MESSAGE_DEGRADE

    if quota is not None:
        try:
            cout: float | None = observabilite.cout_appel(kwargs["model"], reponse.usage)
        except ValueError:
            cout = None
        quota.imputer(utilisateur, cout)
    return texte_de(reponse)
