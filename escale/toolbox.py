"""The set of tools an agent can use."""

from collections.abc import Callable
from dataclasses import dataclass


class ToolError(Exception):
    """A tool failed in a way Claude can read and work around."""


@dataclass(frozen=True)
class Tool:
    """A tool: what Claude sees (`definition`) and what actually runs (`handler`)."""

    definition: dict
    handler: Callable[[dict], str]
    source: str = "local"

    @property
    def name(self) -> str:
        return self.definition["name"]


class Toolbox:
    """Find tools by name and turn every failure into a result Claude can read."""

    def __init__(self, tools: list[Tool]):
        self.tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in self.tools:
                # The first one wins: a remote server must not replace a local tool.
                print(f"[tools] {tool.name} ignoré : ce nom existe déjà.")
                continue
            self.tools[tool.name] = tool

    def definitions(self) -> list[dict]:
        """Return the definitions sent to the API, in a stable order."""
        return [tool.definition for tool in self.tools.values()]

    def source_of(self, name: str) -> str:
        """Tell where a tool comes from, for the trace."""
        tool = self.tools.get(name)
        return tool.source if tool else "inconnu"

    def run(self, name: str, tool_input: dict) -> tuple[str, bool]:
        """Run a tool and return `(content, is_error)`. A failing tool never stops the agent."""
        tool = self.tools.get(name)
        if tool is None:
            return f"Outil inconnu : {name}", True
        try:
            return tool.handler(tool_input), False
        except ToolError as error:
            return str(error), True
        except Exception as error:  # noqa: BLE001
            # Whatever happens, Claude must get a result: a tool_use without one breaks the history.
            return f"Erreur interne de l'outil {name} : {error}", True
