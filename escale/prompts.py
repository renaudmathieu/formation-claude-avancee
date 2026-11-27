"""Prompts live in `prompts/<name>.v<N>.md`. A change is a new file, never an edit in place.

The version is logged with every API call (see `trace.py`): when the cost or the quality moves,
the log says which prompt was running.
"""

import re
from dataclasses import dataclass
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    text: str

    @property
    def label(self) -> str:
        """The form written in the logs, e.g. `assistant.v1`."""
        return f"{self.name}.v{self.version}"


def load_prompt(name: str, version: int | None = None, folder: Path = PROMPTS_DIR) -> Prompt:
    """Load a prompt. Without a version, the highest one."""
    found = {}
    for path in folder.glob(f"{name}.v*.md"):
        match = re.fullmatch(rf"{re.escape(name)}\.v(\d+)\.md", path.name)
        if match:
            found[int(match.group(1))] = path
    if not found:
        raise ValueError(f"Aucun prompt nommé {name} dans {folder}")
    chosen = version if version is not None else max(found)
    if chosen not in found:
        raise ValueError(
            f"Prompt {name} : version {chosen} inconnue (existantes : {sorted(found)})"
        )
    return Prompt(name, chosen, found[chosen].read_text(encoding="utf-8").strip())
