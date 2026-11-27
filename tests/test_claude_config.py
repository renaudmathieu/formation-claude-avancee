import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))


def test_claude_md_stays_short_and_states_the_business_rules():
    lines = (ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines()

    assert len(lines) < 60
    assert any("cite sa page" in line for line in lines)
    assert any("manquante" in line for line in lines)
    assert any("confirmation" in line for line in lines)


def test_secrets_and_push_are_denied():
    deny = SETTINGS["permissions"]["deny"]

    assert "Bash(git push *)" in deny
    assert "Read(./.env)" in deny


def test_stop_hook_runs_an_executable_script():
    command = SETTINGS["hooks"]["Stop"][0]["hooks"][0]["command"]
    script = ROOT / ".claude" / "hooks" / "tests-verts.sh"

    assert "tests-verts.sh" in command
    assert os.access(script, os.X_OK)


def test_ajouter_tool_skill_has_a_description():
    skill = (ROOT / ".claude" / "skills" / "ajouter-tool" / "SKILL.md").read_text(encoding="utf-8")

    assert skill.startswith("---\ndescription:")
