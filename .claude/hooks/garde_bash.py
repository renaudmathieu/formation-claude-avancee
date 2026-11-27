"""PreToolUse hook: block destructive shell commands, whatever the permission mode.

The deny rules in settings.json match a command by its prefix. This hook reads the
whole command line, so `bash -c "rm -rf sortie"` is caught as well.
Exit code 2 blocks the call and sends stderr back to Claude.
"""

import json
import re
import sys

RULES = [
    (r"\brm\s+(?:-\S+\s+)*-\w*[rR]", "suppression récursive (rm -r)"),
    (r"\bgit\s+push\b.*(?:--force|\s-f\b)", "git push forcé"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard"),
    (r"\bdrop\s+(?:table|database)\b", "DROP TABLE ou DROP DATABASE"),
    (r"(?<![\w.])\.env(?!\.example)(?![\w-])", "lecture du fichier .env"),
]


def verdict(command: str) -> str | None:
    """Return the reason to block `command`, or None to let it run."""
    for pattern, reason in RULES:
        if re.search(pattern, command, flags=re.IGNORECASE):
            return reason
    return None


def main() -> int:
    event = json.load(sys.stdin)
    command = event.get("tool_input", {}).get("command", "")
    reason = verdict(command)
    if reason is None:
        return 0
    print(
        f"Commande bloquée par le hook garde_bash : {reason}. "
        "Propose une alternative sans risque ou demande à l'utilisateur de la lancer lui-même.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
