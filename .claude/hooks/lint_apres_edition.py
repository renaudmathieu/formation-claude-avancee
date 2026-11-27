"""PostToolUse hook: every Python file Claude writes goes through ruff.

Fixable problems are fixed and the file is formatted. What ruff cannot fix is sent
back to Claude (exit code 2), which must correct it before going on.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def ruff(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args], capture_output=True, text=True, check=False
    )


def main() -> int:
    event = json.load(sys.stdin)
    path = Path(event.get("tool_input", {}).get("file_path", ""))
    if path.suffix != ".py" or not path.is_file():
        return 0
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project and not path.resolve().is_relative_to(Path(project).resolve()):
        return 0

    ruff("check", "--fix", "--quiet", str(path))
    ruff("format", "--quiet", str(path))
    result = ruff("check", "--quiet", str(path))
    if result.returncode == 0:
        return 0
    print(f"ruff signale des erreurs dans {path.name}, corrige-les :", file=sys.stderr)
    print(result.stdout.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
