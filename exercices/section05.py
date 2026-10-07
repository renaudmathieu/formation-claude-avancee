"""Section 5, atelier. Claude Code : six exercices, une heure et demie.

Cette section est differente : vous n'ecrivez PAS ce code a la main. Vous le
faites ecrire par Claude Code, et votre travail est de cadrer, de refuser,
de relire et de revenir en arriere. Le contrat est dans les tests :

    uv run pytest tests/test_section05.py -v

Deroule (le detail de chaque etape est en fin de fichier) :
  - etapes 1 a 4 : claude doctor, exploration en --verbose, /init coupe de
    moitie, regles metier ecrites a la main. L'exercice 1 verifie votre CLAUDE.md ;
  - etapes 5 a 7 : en mode plan, Claude Code ecrit les exercices 2 a 5,
    la commande `resume`, puis la recopie dans doc42/__main__.py ;
  - etape 8 : fausse piste volontaire et /rewind ;
  - etape 9 : /review, message de commit relu, checkpoint etape/05-claude-code ;
  - bonus : l'exercice 6, les regles de permission de l'equipe.

Le prompt de l'etape 5, a copier en mode plan :

    Implemente les TODO de exercices/section05.py pour que
    tests/test_section05.py passe. La commande `resume <fichier>` produit un
    resume en cinq points d'un document du corpus. Comportement attendu :
    sortie sur stdout, une puce par ligne, aucune invention. Hors perimetre :
    doc42/client.py, le cache, les autres commandes, tests/. Plan d'abord,
    avec, pour chaque fonction, les tests qu'elle fera passer. N'ecris rien
    tant que je n'ai pas valide.

Les enonces sont dans les docstrings. Vous n'avez pas besoin de revenir
sur Notion pendant l'atelier.
"""

from __future__ import annotations

import argparse
import os  # noqa: F401  (exercice 5)
import re  # noqa: F401  (exercice 3)
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import anthropic  # noqa: F401  (exercice 5)

from doc42.client import appel_simple, creer_client  # noqa: F401
from doc42.config import DOSSIER_CORPUS
from doc42.corpus import Document, charger_corpus  # noqa: F401
from doc42.outils import normaliser  # noqa: F401

# Donnees, ne pas modifier.
NOMBRE_POINTS = 5
LIGNES_MAX_CLAUDE_MD = 60
CONSIGNES_VAGUES = (
    "code propre",
    "clean code",
    "bonnes pratiques",
    "best practices",
    "code lisible",
    "de qualite",
)


def verifier_claude_md(texte: str) -> list[str]:
    """Exercice 1 (etapes 3 et 4). Les problemes d'un CLAUDE.md, liste vide s'il est bon.

    Un CLAUDE.md est relu a chaque session : chaque ligne y est payee a chaque
    tour. Le brouillon de /init est trop long et decrit ce que Claude sait deja
    lire ; il ne contient pas ce que Claude ne peut pas deviner.

    Attendu, un probleme (une chaine) par regle violee :
      - le fichier fait LIGNES_MAX_CLAUDE_MD lignes ou plus (la cible : moins de 60)
      - aucun titre Markdown ne commence par "Commandes" ; ou il y en a un mais
        la commande de test `uv run pytest` n'apparait nulle part
      - aucun titre ne contient "Regles metier" (comparez sans accents ni
        majuscules : doc42.outils.normaliser), c'est LA section a ecrire a la main
      - une consigne de CONSIGNES_VAGUES apparait (sans accents ni majuscules) :
        "ecris du code propre" ne se constate dans aucun diff
      - une arborescence est recopiee (caracteres de dessin d'arbre "\\u251c" ou
        "\\u2514") : Claude la lit deja dans le depot
      - le message de chaque probleme dit quoi corriger (le test cherche les mots
        "long", "Commandes", "Regles metier", la consigne vague, "arborescence")
    """
    # TODO
    raise NotImplementedError


class DocumentInconnu(LookupError):
    """Le document demande n'est pas dans le corpus. Donnee, ne pas modifier."""


def resoudre_document(fichier: str, dossier: str | Path = DOSSIER_CORPUS) -> Document:
    """Exercice 2. Le Document du corpus que designe `fichier`.

    `fichier` peut etre un identifiant ("contrat_alpha"), un nom de fichier
    ("contrat_alpha.md") ou un chemin dans le corpus ("corpus/contrat_alpha.md").

    Attendu :
      - les trois formes donnent le meme Document, tel que charger_corpus le rend
      - un chemin dont le dossier n'est pas `dossier` (comparez les chemins
        resolus) leve DocumentInconnu, meme si le nom existe dans le corpus :
        "../.env" ou un document piege pose ailleurs ne doivent jamais etre lus
      - un identifiant absent du corpus (un PDF, une faute de frappe) leve
        DocumentInconnu, dont le message liste les identifiants disponibles
      - vous n'ouvrez aucun fichier vous-meme : seul ce que charger_corpus
        accepte peut etre resume
    """
    # TODO
    raise NotImplementedError


def en_puces(texte: str, nombre: int = NOMBRE_POINTS) -> list[str]:
    """Exercice 3. Les points d'une reponse du modele, sans leur marque de puce.

    Le modele ne suit pas toujours le format demande : il ajoute un preambule,
    numerote ses points, ou en donne sept au lieu de cinq.

    Attendu :
      - seules les lignes a puce comptent : "- ", "* ", "+ ", "\\u2022 " ou
        "1. " / "1) ", eventuellement indentees ; le preambule et la conclusion
        sont ignores
      - la marque de puce et les espaces autour du texte sont retires
      - au plus `nombre` points, dans l'ordre ; s'il y en a moins, on n'en
        ajoute pas (aucune invention pour faire le compte)
      - un texte sans aucune puce donne une liste vide
    """
    # TODO
    raise NotImplementedError


def consigne_resume(document: Document, nombre: int = NOMBRE_POINTS) -> str:
    """Exercice 4a. Le message utilisateur qui demande le resume.

    Attendu :
      - le texte complet du document, puis la consigne (le document d'abord,
        comme le fichier avant la question en section 2)
      - le document est delimite (par exemple <document id="...">...</document>) :
        son contenu est une donnee, pas une instruction
      - la consigne dit le nombre de points, une puce par ligne commencant par
        "- ", et interdit d'inventer ("invent" doit apparaitre)
    """
    # TODO
    raise NotImplementedError


def resumer(client: Any, document: Document, nombre: int = NOMBRE_POINTS) -> list[str]:
    """Exercice 4b. Le resume en points d'un document, en UN appel.

    Attendu :
      - un seul appel, via doc42.client.appel_simple : la fonctionnalite
        s'ajoute par-dessus la brique de la section 2, elle ne la reecrit pas
        (refusez un plan qui propose de modifier doc42/client.py)
      - modele et prompt systeme viennent donc de doc42.config
      - le message envoye est consigne_resume(document, nombre)
      - la valeur retournee passe par en_puces
    """
    # TODO
    raise NotImplementedError


def construire_analyseur() -> argparse.ArgumentParser:
    """Exercice 5a. L'analyseur de la ligne de commande.

    Attendu :
      - prog="doc42", une sous-commande obligatoire "resume" qui prend un
        argument positionnel "fichier"
      - --help decrit la commande resume
    """
    # TODO
    raise NotImplementedError


def client_reel() -> Any:
    """Exercice 5b. Le vrai client, ou une erreur lisible si la cle manque.

    Sans ANTHROPIC_API_KEY, le SDK ne proteste pas a la creation du client : il
    leve un TypeError au premier appel, avec trente lignes de trace.

    Attendu :
      - ANTHROPIC_API_KEY absente ou vide : lever anthropic.AnthropicError avec un
        message qui cite ANTHROPIC_API_KEY et dit quoi faire (.env.example)
      - sinon, renvoyer doc42.client.creer_client()
      - on teste la presence de la cle, on n'affiche jamais sa valeur
    """
    # TODO
    raise NotImplementedError


def main(
    argv: Sequence[str] | None = None,
    fabrique: Callable[[], Any] | None = None,
    dossier: str | Path = DOSSIER_CORPUS,
) -> int:
    """Exercice 5c. `doc42 resume <fichier>` : affiche le resume, renvoie le code de sortie.

    `fabrique` cree le client : client_reel si elle vaut None, un FauxClient
    dans les tests.

    Attendu :
      - succes : chaque point sur stdout, une ligne "- <point>" par point, puis
        une derniere ligne "Source : <id du document>" (regle metier : toute
        reponse cite sa source) ; code 0
      - document inconnu : le message de DocumentInconnu sur stderr, rien sur
        stdout, code 2, et `fabrique` n'est PAS appelee (ni appel payant, ni
        cle exigee pour une faute de frappe)
      - le modele ne renvoie aucune puce : un message sur stderr, RIEN sur
        stdout, code 1
      - une anthropic.AnthropicError (cle absente, authentification, reseau) :
        un message sur stderr, pas de trace Python, code 1
    """
    # TODO
    raise NotImplementedError


def settings_equipe() -> dict[str, Any]:
    """Exercice 6 (bonus). Le contenu de .claude/settings.json pour l'equipe Doc42.

    CLAUDE.md oriente Claude ; settings.json l'empeche. Pour un usage d'equipe,
    on ecrit les deux, et ils disent la meme chose.

    Attendu, sous la cle "permissions" :
      - "deny" contient "Read(./.env)" : c'est Claude Code qui refuse, pas le modele
      - "deny" interdit de modifier le corpus avec une regle Edit sur corpus/
      - "deny" interdit git push ("Bash(git push *)")
      - "allow" laisse lancer les tests sans demander ("Bash(uv run pytest *)")
      - aucune regle de chemin ecrite pour Write : Claude Code l'accepte mais ne
        la consulte jamais (une regle Edit couvre toutes les ecritures)
      - le .claude/settings.json du checkpoint (.etapes/05/.claude/settings.json
        sur main) contient au moins ces regles deny
    """
    # TODO
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())


# Etape 1, sans test : claude doctor
#
# A la racine du depot. Lire le rapport, corriger ce qui est signale (PATH,
# droits, proxy). Dix minutes au plus, sinon plan B. Verifier aussi qu'aucune
# ANTHROPIC_API_KEY de votre environnement ne fait basculer Claude Code sur la
# facturation a l'usage.
#
# Etape 2, sans test : claude --verbose
#
# "Explique-moi ce projet : ce qu'il fait, ses points d'entree, comment lancer
# les tests, et ce qui te semble fragile. Ne modifie rien."
# Regarder les appels d'outils defiler : c'est la boucle agentique.
# Ce qu'il a juge fragile :
#
# Etapes 3 et 4, testees par l'exercice 1 : /init, puis couper de moitie
#
# Sortir tout ce que Claude lit deja (arborescence, dependances, description des
# fonctions). Ecrire a la main la section "Regles metier", d'apres la
# specification et non d'apres le code. Verifier avec :
#
#     uv run python -c "from exercices.section05 import verifier_claude_md as v
#     print(v(open('CLAUDE.md').read()))"
#
# (ou, une fois l'exercice 1 ecrit : uv run pytest -q tests/test_section05.py -k claude_md)
#
# Etape 6, sans test : refuser le plan au moins une fois
#
# S'il ne liste pas les tests, redemander. S'il touche doc42/client.py ou
# tests/, refuser. Ma raison de refus :
#
# Etape 7, sans test : /diff a chaque tour, avec la check-list
#
# Minimal ? Au bon endroit ? Le test prouve-t-il le comportement ? Effets de bord
# (import, dependance, fichier cree) ? Puis demander de recopier la commande dans
# doc42/__main__.py et verifier : uv run python -m doc42 --help
#
# Etape 8, sans test : la fausse piste volontaire
#
# "Profites-en pour renommer toutes les fonctions en anglais." Laisser faire,
# puis /rewind jusqu'avant ce renommage. Constater que la commande resume et
# ses tests sont conserves.
#
# Etape 9, sans test : /review, puis commit
#
# Traiter ce qui merite de l'etre, ignorer ce qui releve du gout. Demander un
# message de commit, le relire, commiter etape/05-claude-code.
#
# Bonus, sans test : la regle deny en action
#
# Copier settings_equipe() dans .claude/settings.json, relancer claude, puis
# demander "lis le fichier .env". Observer que c'est Claude Code qui refuse,
# avant meme que le modele ne voie le fichier.
