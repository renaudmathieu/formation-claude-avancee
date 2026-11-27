"""What makes this agent Escale: its instructions, its tools and how it shows its work."""

from datetime import date
from pathlib import Path

from escale.agent import AgentResult, run_agent
from escale.toolbox import Toolbox
from escale.tools.files import file_tools
from escale.tools.policy import policy_tool
from escale.tools.weather import weather_tool

OUTPUT_DIR = Path("sortie")
REFUSAL_MESSAGE = "Je ne peux pas répondre à cette demande."
TRUNCATED_MESSAGE = "\n[Réponse coupée : limite de tokens atteinte.]"
LIMIT_MESSAGE = "\n[Arrêt : limite de tours atteinte, le travail est peut-être incomplet.]"


def system_prompt(today: date) -> str:
    """Build the system prompt. Claude does not know today's date unless we tell it."""
    return (
        "Tu es Escale, l'assistant de déplacement professionnel d'une entreprise. "
        "Tu réponds en français, de façon concise et concrète. "
        f"Nous sommes le {today.isoformat()}.\n\n"
        "Quand on te demande de préparer un déplacement, travaille en autonomie : rassemble les "
        "informations avec tes outils, puis livre une feuille de route en Markdown avec "
        "write_file. Si une information manque ou qu'un outil échoue, dis-le dans le document "
        "au lieu de l'inventer. Vérifie chaque choix (train, hôtel, repas) dans la politique de "
        "voyage et cite la page des règles que tu appliques."
    )


def build_toolbox() -> Toolbox:
    """Gather the tools the agent can use."""
    return Toolbox([weather_tool(), policy_tool(), *file_tools(OUTPUT_DIR)])


def describe(result: AgentResult) -> str:
    """Turn the way a run ended into what the user reads."""
    if result.stop_reason == "refusal":
        return REFUSAL_MESSAGE
    if result.stop_reason == "max_tokens":
        return result.text + TRUNCATED_MESSAGE
    if result.stop_reason == "iteration_limit":
        return result.text + LIMIT_MESSAGE
    return result.text


def show_progress(event: dict) -> None:
    """Print what the agent is doing, so that the loop can be seen."""
    if event["type"] == "response":
        response = event["response"]
        for block in response.content:
            if block.type == "thinking" and block.thinking:
                print(f"[réflexion] {block.thinking}")
        print(f"[tour {event['iteration']}] stop_reason={response.stop_reason}")
    elif event["type"] == "tool_call":
        print(f"[tool:{event['source']}] {event['name']} {_shorten(str(event['input']))}")
    elif event["type"] == "tool_result" and event["is_error"]:
        print(f"[tool] {event['name']} a échoué")


def _shorten(value: str, limit: int = 200) -> str:
    return value if len(value) <= limit else f"{value[:limit]}..."


def run_task(client, task: str, toolbox: Toolbox | None = None) -> AgentResult:
    """Give the agent one task and let it work until it has finished."""
    return run_agent(
        client,
        [{"role": "user", "content": task}],
        toolbox or build_toolbox(),
        system=system_prompt(date.today()),
        effort="high",
        on_event=show_progress,
    )
