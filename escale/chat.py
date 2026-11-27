"""Turn-by-turn conversation with Claude, in the terminal.

TP 1: this file has holes. Each `hole(...)` call is a part left for you to write.
"""

import anthropic

from escale.llm import send, text_of

SYSTEM_PROMPT = (
    "Tu es Escale, l'assistant de déplacement professionnel d'une entreprise. "
    "Tu réponds en français, de façon concise et concrète."
)
SUPPORTED_IMAGES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
HELP = "Commandes : /image <chemin> [question], /quitter"
REFUSAL_MESSAGE = "Je ne peux pas répondre à cette demande."
TRUNCATED_MESSAGE = "\n[Réponse coupée : limite de tokens atteinte.]"


def hole(description: str):
    """Mark a part of the exercise that is still to be written."""
    raise NotImplementedError(f"TP 1, à compléter : {description}")


def image_block(path: str) -> dict:
    """Build the content block that sends a local image to Claude."""
    # Trou 2: reject a format outside SUPPORTED_IMAGES with a ValueError.
    return hole("trou 2.1 : construire le bloc image en base64")


class Conversation:
    """Keep the history of a conversation, since the API does not remember anything."""

    def __init__(self, client, system: str = SYSTEM_PROMPT):
        self.client = client
        self.system = system
        self.messages: list[dict] = []

    def ask(self, text: str, image_path: str | None = None) -> str:
        """Send one user turn and return the text of Claude's answer."""
        content = []
        # Trou 2: when image_path is set, the image block goes here, before the text.
        content.append({"type": "text", "text": text})

        # Trou 1.1: replace hole(...) with the variable built just above.
        self.messages.append({"role": "user", "content": hole("trou 1.1 : le contenu de ce tour")})

        try:
            # Trou 1.2: the API does not remember anything, so send it everything.
            response = send(
                self.client,
                hole("trou 1.2 : tout l'historique, pas seulement le dernier message"),
                system=self.system,
            )
        except (anthropic.APIError, KeyboardInterrupt):
            # Keep the history usable: the failed turn is not part of the conversation.
            self.messages.pop()
            raise

        if response.stop_reason == "refusal":
            # Keep the history usable: the refused turn is not part of the conversation.
            self.messages.pop()
            return REFUSAL_MESSAGE

        # Trou 1.3: the next call must see this answer, thinking blocks included.
        self.messages.append(
            {
                "role": "assistant",
                "content": hole("trou 1.3 : tous les blocs de response, pas seulement le texte"),
            }
        )

        answer = text_of(response)
        if response.stop_reason == "max_tokens":
            answer += TRUNCATED_MESSAGE
        return answer


def parse_image_command(line: str) -> tuple[str, str]:
    """Split `/image <path> [question]` into a path and a question."""
    # Trou 2: without a question, use "Que vois-tu sur cette image ?".
    return hole("trou 2.2 : extraire le chemin et la question")


def run_chat(client) -> None:
    """Run the conversation loop until the user leaves."""
    conversation = Conversation(client)
    print(f"Escale est prêt. {HELP}")
    while True:
        try:
            line = input("\nvous> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line == "/quitter":
            return
        try:
            # Trou 2: a line starting with /image goes through parse_image_command.
            answer = conversation.ask(line)
        except (OSError, ValueError) as error:
            print(f"Erreur : {error}")
            continue
        except anthropic.APIError as error:
            print(f"Erreur de l'API, le tour est annulé : {error.message}")
            continue
        except KeyboardInterrupt:
            print("\n[Tour interrompu.]")
            continue
        print(f"\nescale> {answer}")
