"""Turn-by-turn conversation with Claude, in the terminal."""

import anthropic

from escale.llm import cost_line, file_block, send, text_of, with_retry

SYSTEM_PROMPT = (
    "Tu es Escale, l'assistant de déplacement professionnel d'une entreprise. "
    "Tu réponds en français, de façon concise et concrète."
)
HELP = "Commandes : /image <chemin> [question], /quitter"
REFUSAL_MESSAGE = "Je ne peux pas répondre à cette demande."
TRUNCATED_MESSAGE = "\n[Réponse coupée : limite de tokens atteinte.]"


def image_block(path: str) -> dict:
    """Build the content block that sends a local image to Claude."""
    block = file_block(path)
    if block["type"] != "image":
        raise ValueError(f"Ce n'est pas une image : {path}")
    return block


class Conversation:
    """Keep the history of a conversation, since the API does not remember anything."""

    def __init__(self, client, system: str = SYSTEM_PROMPT):
        self.client = client
        self.system = system
        self.messages: list[dict] = []
        self.last_response = None

    def ask(self, text: str, image_path: str | None = None) -> str:
        """Send one user turn and return the text of Claude's answer."""
        content = []
        if image_path:
            content.append(image_block(image_path))
        content.append({"type": "text", "text": text})
        self.messages.append({"role": "user", "content": content})

        try:
            response = with_retry(lambda: send(self.client, self.messages, system=self.system))
        except (anthropic.APIError, KeyboardInterrupt):
            # Keep the history usable: the failed turn is not part of the conversation.
            self.messages.pop()
            raise

        self.last_response = response
        if response.stop_reason == "refusal":
            # Keep the history usable: the refused turn is not part of the conversation.
            self.messages.pop()
            return REFUSAL_MESSAGE
        # Append the whole content, not only the text: thinking blocks must be sent back.
        self.messages.append({"role": "assistant", "content": response.content})
        answer = text_of(response)
        if response.stop_reason == "max_tokens":
            answer += TRUNCATED_MESSAGE
        return answer


def parse_image_command(line: str) -> tuple[str, str]:
    """Split `/image <path> [question]` into a path and a question."""
    parts = line.split(maxsplit=2)
    if len(parts) < 2:
        raise ValueError("Usage : /image <chemin> [question]")
    question = parts[2] if len(parts) == 3 else "Que vois-tu sur cette image ?"
    return parts[1], question


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
            if line.startswith("/image"):
                path, question = parse_image_command(line)
                answer = conversation.ask(question, image_path=path)
            else:
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
        print(f"[{cost_line(conversation.last_response)}]")
