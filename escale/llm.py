"""The single place where Escale calls the Claude Messages API."""

import base64
import json
import mimetypes
import random
import re
import time
from pathlib import Path

import anthropic

from escale.config import (
    CLASSIFICATION_MAX_TOKENS,
    MAX_TOKENS,
    cost_usd,
    default_model,
    model_for,
)

# Beta needed by `fallbacks="default"`: a declined request is retried on another model.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Files Claude can read, and the kind of content block each one needs.
FILE_KINDS = {
    "image/png": "image",
    "image/jpeg": "image",
    "image/gif": "image",
    "image/webp": "image",
    "application/pdf": "document",
}

# Errors worth a second try: the same request may succeed a moment later.
#   429 rate limit, 529 overloaded, 500/503 server side, network failure or timeout.
# Everything else (400, 401, 403, 404...) is a fault in the request or the key: retrying
# the same request can only fail the same way, so those errors are raised at once.
RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.OverloadedError,
    anthropic.InternalServerError,
    anthropic.ServiceUnavailableError,
    anthropic.APIConnectionError,
)


def cached_text(text: str) -> list[dict]:
    """A system prompt as one block marked for the prompt cache.

    A cache hit costs 0.1x the input price, a cache write 1.25x. The prompt must be identical
    from one call to the next: put what changes (the date, the user) in a later block.
    """
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def build_request(
    messages,
    *,
    system=None,
    tools=None,
    tool_choice=None,
    effort="low",
    model=None,
    schema=None,
    max_tokens=None,
    thinking=True,
) -> dict:
    """Build the parameters shared by `send` and `stream`."""
    request = {
        "model": model or default_model(),
        "max_tokens": max_tokens or MAX_TOKENS,
        "messages": messages,
        "output_config": {"effort": effort},
        "fallbacks": "default",
        "betas": [FALLBACK_BETA],
    }
    if thinking:
        request["thinking"] = {"type": "adaptive", "display": "summarized"}
    if schema:
        # Structured outputs: the answer is guaranteed to follow this JSON schema.
        request["output_config"]["format"] = {"type": "json_schema", "schema": schema}
    if system:
        request["system"] = system
    if tools:
        request["tools"] = tools
    if tool_choice:
        request["tool_choice"] = tool_choice
    return request


def send(
    client,
    messages,
    *,
    system=None,
    tools=None,
    tool_choice=None,
    effort="low",
    model=None,
    schema=None,
    max_tokens=None,
    thinking=True,
):
    """Send the conversation to Claude and return the response.

    The API is stateless: `messages` must hold the whole conversation.
    `model` overrides the default model (used to compare models).
    """
    request = build_request(
        messages,
        system=system,
        tools=tools,
        tool_choice=tool_choice,
        effort=effort,
        model=model,
        schema=schema,
        max_tokens=max_tokens,
        thinking=thinking,
    )
    return client.beta.messages.create(**request)


def text_of(response) -> str:
    """Return the text blocks of a response, without the thinking blocks."""
    return "".join(block.text for block in response.content if block.type == "text")


def with_retry(call, *, attempts=5, sleep=None):
    """Run `call()` again after a transient error, waiting longer each time."""
    sleep = sleep or time.sleep
    for attempt in range(attempts):
        try:
            return call()
        except RETRYABLE:
            if attempt == attempts - 1:
                raise
            # Exponential backoff (1 s, 2 s, 4 s...) plus a random jitter, so that many
            # clients do not all retry at the same second.
            sleep(2**attempt + random.uniform(0, 1))


def ask(client, question: str, *, system=None) -> str:
    """Ask one question and return the text of the answer."""
    messages = [{"role": "user", "content": question}]
    response = with_retry(lambda: send(client, messages, system=system))
    return text_of(response)


def stream(client, messages, *, system=None):
    """Yield the answer text fragment by fragment.

    When the generator ends, its return value is the final message, which holds `usage`:
    `final = yield from stream(...)` inside another generator, or read `StopIteration.value`.
    """
    request = build_request(messages, system=system)
    with client.beta.messages.stream(**request) as events:
        yield from events.text_stream
        # Only valid once the stream is consumed: this is the only way to get a full usage.
        return events.get_final_message()


def file_block(path: str) -> dict:
    """Build the content block that sends a local image or PDF to Claude."""
    media_type, _ = mimetypes.guess_type(path)
    kind = FILE_KINDS.get(media_type)
    if kind is None:
        raise ValueError(f"Format de fichier non pris en charge : {path}")
    data = base64.standard_b64encode(Path(path).read_bytes()).decode("ascii")
    return {"type": kind, "source": {"type": "base64", "media_type": media_type, "data": data}}


TICKET_QUESTION = (
    "Lis ce billet de train. Réponds uniquement par un objet JSON avec trois clés : "
    '"date" (AAAA-MM-JJ), "stations" (gare de départ et gare d\'arrivée, telles qu\'écrites) '
    'et "departure_time" (HH:MM). Rien avant, rien après.'
)


def read_ticket(client, path: str) -> dict:
    """Read a ticket (image or PDF) and return its date, stations and departure time."""
    # The file comes before the question: Claude reads the content in order.
    content = [file_block(path), {"type": "text", "text": TICKET_QUESTION}]
    response = with_retry(lambda: send(client, [{"role": "user", "content": content}]))
    # The model may wrap the JSON in a code fence: keep what is between the braces.
    match = re.search(r"\{.*\}", text_of(response), re.DOTALL)
    if match is None:
        raise ValueError("Aucun objet JSON dans la réponse.")
    ticket = json.loads(match.group(0))
    missing = {"date", "stations", "departure_time"} - ticket.keys()
    if missing:
        raise ValueError(f"Champs manquants : {', '.join(sorted(missing))}")
    return ticket


def is_refund_request(client, message: str) -> bool:
    """Classify a message. A yes/no question does not need a big model: it is routed to the fast one."""
    question = (
        "Ce message est-il une demande de remboursement ? Réponds uniquement par oui ou non.\n\n"
        f"Message : {message}"
    )
    messages = [{"role": "user", "content": question}]
    response = with_retry(
        lambda: send(
            client,
            messages,
            model=model_for("classification"),
            max_tokens=CLASSIFICATION_MAX_TOKENS,
            thinking=False,
        )
    )
    return text_of(response).strip().lower().startswith("oui")


def cost_line(response) -> str:
    """Return a one-line summary of the tokens and the cost of a response."""
    usage = response.usage
    line = f"{usage.input_tokens} tokens en entrée, {usage.output_tokens} en sortie"
    try:
        return f"{line}, coût {cost_usd(response.model, usage):.5f} $"
    except ValueError:
        return f"{line}, coût inconnu pour {response.model}"
