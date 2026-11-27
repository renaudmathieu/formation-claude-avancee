#!/bin/bash
# Stop hook: Claude does not conclude on red tests.
# One retry only, then the human takes over.
# The tests use a fake API client, so this hook costs no API call.
INPUT=$(cat)
cd "$CLAUDE_PROJECT_DIR" || exit 0

# Red on purpose, decided by the human (tests-first phase): let it through
[ -f .claude/rouge-attendu ] && exit 0

# Nothing changed in the code or the tests: nothing to check
[ -z "$(git status --porcelain -- escale tests)" ] && exit 0

# Green tests: Claude may stop
OUT=$(uv run pytest -q 2>&1) && exit 0

# Already retried once by this hook: hand over to the human
if echo "$INPUT" | grep -q '"stop_hook_active": *true'; then
  echo '{"systemMessage": "Tests toujours rouges après une relance : reprenez la main."}'
  exit 0
fi

# Red tests: block the stop and send the evidence back to Claude
echo "Les tests sont rouges, ne conclus pas. Sortie de pytest :" >&2
echo "$OUT" | tail -n 30 >&2
exit 2
