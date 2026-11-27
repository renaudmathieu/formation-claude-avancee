#!/bin/bash
# Check every Escale checkpoint: tests, lint, and the mod from etape/07-mod onwards.
# Usage: from a full clone, on the formateur branch, with a clean working tree:
#   scripts/verifier-branches.sh
# Nothing here calls the Anthropic or Voyage API: pytest uses a fake client, and
# `claude plugin validate` / `claude plugin test` run offline.
set -u

# branch|expected pytest summary (without the duration)
ATTENDU=(
  "main|10 passed, 9 skipped"
  "etape/00-depart|10 passed, 9 skipped"
  "etape/01-premier-appel|15 passed, 9 skipped"
  "etape/02-client|37 passed, 1 skipped"
  "etape/03-prompts|51 passed, 1 skipped"
  "etape/04-tools|91 passed"
  "etape/05-claude-code|125 passed"
  "etape/06-mcp|152 passed"
  "etape/07-mod|153 passed"
  "etape/08-agent|179 passed, 2 skipped"
  "etape/09-rag|224 passed, 2 skipped"
  "etape/10-prod|270 passed, 2 skipped"
  "etape/11-final|275 passed, 2 skipped"
)
# From this branch onwards the mod exists and is checked.
PREMIERE_BRANCHE_MOD="etape/07-mod"
MOD="outils/compteur-escale"

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "KO : tracked files modified, commit or stash first."; exit 2
fi
depart=$(git branch --show-current)
echec=0
avec_mod=0

for ligne in "${ATTENDU[@]}"; do
  branche=${ligne%%|*}; attendu=${ligne#*|}
  [ "$branche" = "$PREMIERE_BRANCHE_MOD" ] && avec_mod=1
  git switch -q "$branche" || { echo "KO $branche : introuvable"; echec=1; continue; }
  uv sync -q
  resultat=$(uv run pytest -q 2>&1 | tail -n 1)
  if [[ "$resultat" == "$attendu in "* ]] && uv run ruff check -q . >/dev/null; then
    echo "OK $branche : $resultat"
  else
    echo "KO $branche : $resultat (attendu : $attendu, ou lint en echec)"; echec=1
  fi
  if [ "$avec_mod" = 1 ]; then
    if ! command -v claude >/dev/null; then
      echo "KO $branche : claude introuvable, mod non verifie"; echec=1
    elif claude plugin validate "$MOD" >/dev/null 2>&1 && claude plugin test "$MOD" >/dev/null 2>&1; then
      echo "OK $branche : mod, plugin validate et plugin test"
    else
      echo "KO $branche : mod ($MOD), relancer claude plugin validate et claude plugin test pour le detail"; echec=1
    fi
  fi
done

git switch -q "$depart"
exit $echec
