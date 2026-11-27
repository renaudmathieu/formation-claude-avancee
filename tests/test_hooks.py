"""The PreToolUse and PostToolUse hooks, run as Claude Code runs them: JSON on stdin."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".claude" / "hooks"
SETTINGS = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))


def run_hook(script: str, event: dict, project: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOKS / script)],
        input=json.dumps(event),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
        capture_output=True,
        text=True,
        check=False,
    )


def bash(command: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf sortie",
        "rm -r -f /tmp/x",
        'bash -c "rm -rf ."',
        "git push --force origin main",
        "git push -f",
        "git reset --hard HEAD~3",
        "sqlite3 escale.db 'DROP TABLE notes'",
        "cat .env",
        "grep KEY ./.env",
    ],
)
def test_garde_bash_blocks_destructive_commands(command):
    result = run_hook("garde_bash.py", bash(command))

    assert result.returncode == 2
    assert "bloquée" in result.stderr


@pytest.mark.parametrize(
    "command",
    ["uv run pytest -q", "rm sortie/brouillon.md", "git push", "cat .env.example", "ls -la"],
)
def test_garde_bash_lets_ordinary_commands_run(command):
    result = run_hook("garde_bash.py", bash(command))

    assert result.returncode == 0


def edit(path: Path) -> dict:
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(path)},
    }


def test_lint_fixes_and_formats_a_python_file(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("import os\nx=1\n", encoding="utf-8")

    result = run_hook("lint_apres_edition.py", edit(source), project=tmp_path)

    assert result.returncode == 0
    assert source.read_text(encoding="utf-8") == "x = 1\n"


def test_lint_sends_what_it_cannot_fix_back_to_claude(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("print(undefined_name)\n", encoding="utf-8")

    result = run_hook("lint_apres_edition.py", edit(source), project=tmp_path)

    assert result.returncode == 2
    assert "F821" in result.stderr


def test_lint_ignores_other_files(tmp_path):
    notes = tmp_path / "notes.md"
    notes.write_text("import os\n", encoding="utf-8")

    assert run_hook("lint_apres_edition.py", edit(notes), project=tmp_path).returncode == 0


def test_hooks_are_registered_on_the_right_events():
    pre = SETTINGS["hooks"]["PreToolUse"][0]
    post = SETTINGS["hooks"]["PostToolUse"][0]

    assert pre["matcher"] == "Bash" and "garde_bash.py" in pre["hooks"][0]["command"]
    assert "Write" in post["matcher"] and "lint_apres_edition.py" in post["hooks"][0]["command"]


def test_lint_leaves_files_outside_the_project_alone(tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("import os\nx=1\n", encoding="utf-8")
    project = tmp_path / "projet"
    project.mkdir()

    assert run_hook("lint_apres_edition.py", edit(outside), project=project).returncode == 0
    assert outside.read_text(encoding="utf-8") == "import os\nx=1\n"
