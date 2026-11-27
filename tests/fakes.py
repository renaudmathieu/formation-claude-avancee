"""A scripted stand-in for the Anthropic client, so tests never call the API."""

import copy
from types import SimpleNamespace


def text(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=value)


def thinking(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="thinking", thinking=value, signature="sig")


def tool_use(name: str, tool_input: dict, block_id: str = "toolu_1") -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def response(*content, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        content=list(content),
        stop_reason=stop_reason,
        model="claude-test",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


class FakeClient:
    """Return the scripted responses in order and record every request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **request):
        self.requests.append(copy.deepcopy(request))
        next_response = self.responses.pop(0)
        if isinstance(next_response, BaseException):
            raise next_response
        return next_response
