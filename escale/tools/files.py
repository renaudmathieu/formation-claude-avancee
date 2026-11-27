"""File tools. They can only reach one folder, whatever the model asks for."""

from pathlib import Path

from escale.toolbox import Tool, ToolError

MAX_FILE_CHARS = 200_000


def resolve_inside(root: Path, relative_path: str) -> Path:
    """Return the path inside `root`, or refuse it. This is a barrier, not a guideline."""
    root = root.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ToolError(f"Chemin refusé, en dehors de {root.name}/ : {relative_path}")
    return path


def file_tools(root: Path) -> list[Tool]:
    """Build the file tools, limited to the `root` folder."""

    def read_file(tool_input: dict) -> str:
        path = resolve_inside(root, tool_input["path"])
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise ToolError(f"Lecture impossible : {tool_input['path']} ({error})") from error
        if len(content) > MAX_FILE_CHARS:
            raise ToolError(f"Fichier trop long pour être lu en entier : {tool_input['path']}")
        return content

    def write_file(tool_input: dict) -> str:
        path = resolve_inside(root, tool_input["path"])
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(tool_input["content"], encoding="utf-8")
        except OSError as error:
            raise ToolError(f"Écriture impossible : {tool_input['path']} ({error})") from error
        return f"Fichier écrit : {root.name}/{tool_input['path']}"

    return [
        Tool(
            definition={
                "name": "read_file",
                "description": f"Lit un fichier texte du dossier {root.name}/.",
                "strict": True,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": f"Chemin relatif au dossier {root.name}/.",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            handler=read_file,
        ),
        Tool(
            definition={
                "name": "write_file",
                "description": (
                    f"Crée ou remplace un fichier texte dans le dossier {root.name}/. "
                    "Utilise cet outil pour livrer un document à l'utilisateur."
                ),
                "strict": True,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": f"Chemin relatif au dossier {root.name}/.",
                        },
                        "content": {"type": "string", "description": "Contenu complet du fichier."},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
            handler=write_file,
        ),
    ]
