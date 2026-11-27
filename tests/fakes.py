"""A scripted stand-in for the Anthropic client, so tests never call the API."""

import copy
from types import SimpleNamespace

import anthropic
import httpx


def text(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=value)


def thinking(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="thinking", thinking=value, signature="sig")


def tool_use(name: str, tool_input: dict, block_id: str = "toolu_1") -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def response(
    *content,
    stop_reason: str = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 5,
    model: str = "claude-sonnet-5-5",
) -> SimpleNamespace:
    return SimpleNamespace(
        content=list(content),
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class FakeClient:
    """Return the scripted responses in order and record every request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[dict] = []
        self.beta = SimpleNamespace(
            messages=SimpleNamespace(create=self._create, stream=self._stream)
        )

    def _create(self, **request):
        self.requests.append(copy.deepcopy(request))
        next_response = self.responses.pop(0)
        if isinstance(next_response, BaseException):
            raise next_response
        return next_response

    def _stream(self, **request):
        return FakeStream(self._create(**request))


class FakeStream:
    """Stand-in for `client.beta.messages.stream(...)`: a context manager over one response."""

    def __init__(self, final_response):
        self.final_response = final_response
        self.text_stream = iter(
            [block.text for block in final_response.content if block.type == "text"]
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get_final_message(self):
        return self.final_response


def api_error(
    error_class, status: int = 500, message: str = "erreur de test"
) -> anthropic.APIError:
    """Build a real SDK exception, as the client would raise it."""
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    if error_class is anthropic.APIConnectionError:
        return error_class(request=request)
    http_response = httpx.Response(status, request=request)
    return error_class(message, response=http_response, body=None)


# Words that mean the same thing share an axis, so that the fake embedder "understands" synonyms.
CONCEPTS = [
    ("voiture", "vehicule", "automobile"),
    ("amende", "amendes", "contravention", "pv"),
    ("avion", "vol"),
    ("hotel", "chambre"),
    ("repas", "dejeuner", "diner"),
]


def concept_embedder(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """A deterministic stand-in for Voyage: one axis per concept, no network."""
    from escale.rag import tokens

    vectors = []
    for text in texts:
        words = tokens(text)
        vectors.append([0.01 + sum(words.count(w) for w in group) for group in CONCEPTS])
    return vectors
