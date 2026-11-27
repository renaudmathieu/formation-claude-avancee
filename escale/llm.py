"""The single place where Escale calls the Claude Messages API."""

from escale.config import MAX_TOKENS, default_model

# Beta needed by `fallbacks="default"`: a declined request is retried on another model.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def send(client, messages, *, system=None, tools=None, tool_choice=None, effort="low"):
    """Send the conversation to Claude and return the response.

    The API is stateless: `messages` must hold the whole conversation.
    """
    request = {
        "model": default_model(),
        "max_tokens": MAX_TOKENS,
        "messages": messages,
        "thinking": {"type": "adaptive", "display": "summarized"},
        "output_config": {"effort": effort},
        "fallbacks": "default",
        "betas": [FALLBACK_BETA],
    }
    if system:
        request["system"] = system
    if tools:
        request["tools"] = tools
    if tool_choice:
        request["tool_choice"] = tool_choice
    return client.beta.messages.create(**request)


def text_of(response) -> str:
    """Return the text blocks of a response, without the thinking blocks."""
    return "".join(block.text for block in response.content if block.type == "text")
