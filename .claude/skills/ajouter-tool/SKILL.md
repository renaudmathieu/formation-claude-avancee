---
description: Ajoute un tool à l'agent Escale en suivant la procédure du projet (définition, gestion d'erreur, test, enregistrement). Utiliser quand on demande un nouveau tool ou une nouvelle capacité pour l'agent.
argument-hint: [ce que le tool doit faire]
allowed-tools: Read Edit Write Bash(uv run pytest *) Bash(uv run ruff *)
---

## Demande
$ARGUMENTS

## Procédure
1. Lire `escale/toolbox.py`, `escale/tools/weather.py` et `escale/assistant.py`. S'aligner sur ces modèles.
2. Si la demande est floue, ou si le tool écrit ou envoie quelque chose, poser la question avant d'écrire du code.
3. Écrire le test d'abord dans `tests/`, avec `tests/fakes.py`, sans réseau ni clé. Couvrir au moins le cas nominal et une panne.
4. Créer le tool dans `escale/tools/`, en renvoyant un objet `Tool` :
   - une description en français qui dit quand l'utiliser, pas seulement ce qu'il fait ;
   - un schéma avec `strict: true`, `required` et `additionalProperties: false` ;
   - un `handler` qui renvoie du texte et lève `ToolError` en cas de panne.
5. L'ajouter dans `build_toolbox()` de `escale/assistant.py`.
6. Lancer `uv run pytest -q` et `uv run ruff check .`, puis rapporter le résultat exact.

## Règles
- Un tool d'écriture reste limité à `sortie/` avec `resolve_inside`.
- Pas d'appel à la Messages API dans un tool.
- Ne pas lancer l'agent pour vérifier : chaque exécution consomme du crédit API. Proposer la commande à l'humain.
