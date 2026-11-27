import anthropic
import pytest

from escale import config, llm
from tests.fakes import FakeClient, api_error, response, text, thinking


def test_ask_returns_the_text_blocks_without_thinking():
    client = FakeClient(response(thinking("hmm"), text("Bonjour "), text("Camille")))

    assert llm.ask(client, "Salut") == "Bonjour Camille"
    assert client.requests[0]["messages"] == [{"role": "user", "content": "Salut"}]


def test_stream_yields_fragments_and_returns_the_final_message():
    final = response(text("Bon"), text("jour"), output_tokens=42)
    client = FakeClient(final)
    fragments = llm.stream(client, [{"role": "user", "content": "Salut"}])

    collected = []
    with pytest.raises(StopIteration) as stop:
        while True:
            collected.append(next(fragments))

    assert collected == ["Bon", "jour"]
    assert stop.value.value.usage.output_tokens == 42


def test_with_retry_replays_transient_errors():
    errors = [
        api_error(anthropic.RateLimitError, 429),
        api_error(anthropic.OverloadedError, 529),
        api_error(anthropic.InternalServerError, 500),
        api_error(anthropic.APIConnectionError),
    ]
    calls = []

    def flaky():
        calls.append(1)
        if errors:
            raise errors.pop(0)
        return "ok"

    waits = []
    assert llm.with_retry(flaky, sleep=waits.append) == "ok"
    assert len(calls) == 5
    # Exponential backoff: each wait is at least twice the previous base (1, 2, 4, 8).
    assert [int(wait) for wait in waits] == [1, 2, 4, 8]


def test_with_retry_gives_up_after_the_last_attempt():
    calls = []

    def always_limited():
        calls.append(1)
        raise api_error(anthropic.RateLimitError, 429)

    with pytest.raises(anthropic.RateLimitError):
        llm.with_retry(always_limited, attempts=3, sleep=lambda wait: None)

    assert len(calls) == 3


@pytest.mark.parametrize(
    ("error_class", "status"),
    [
        (anthropic.BadRequestError, 400),
        (anthropic.AuthenticationError, 401),
        (anthropic.PermissionDeniedError, 403),
        (anthropic.NotFoundError, 404),
    ],
)
def test_with_retry_never_replays_a_client_error(error_class, status):
    calls = []

    def broken():
        calls.append(1)
        raise api_error(error_class, status)

    with pytest.raises(error_class):
        llm.with_retry(broken, sleep=lambda wait: None)

    assert len(calls) == 1


def test_read_ticket_puts_the_image_before_the_question():
    answer = '{"date": "2026-11-17", "stations": "Paris Centre > Lyon Presqu\'île", '
    answer += '"departure_time": "07:42"}'
    client = FakeClient(response(text(answer)))

    ticket = llm.read_ticket(client, "exemples/billet-fictif.png")

    image, question = client.requests[0]["messages"][0]["content"]
    assert image["type"] == "image"
    assert image["source"]["media_type"] == "image/png"
    assert question["type"] == "text"
    assert ticket == {
        "date": "2026-11-17",
        "stations": "Paris Centre > Lyon Presqu'île",
        "departure_time": "07:42",
    }


def test_read_ticket_rejects_an_incomplete_answer():
    client = FakeClient(response(text('{"date": "2026-11-17"}')))

    with pytest.raises(ValueError, match="manquants"):
        llm.read_ticket(client, "exemples/billet-fictif.png")


def test_file_block_uses_a_document_block_for_a_pdf(tmp_path):
    pdf = tmp_path / "billet.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    assert llm.file_block(str(pdf))["type"] == "document"


def test_cost_line_uses_the_config_prices():
    reply = response(text("ok"), input_tokens=1_000_000, output_tokens=0)
    reply.model = config.MODEL_DEFAULT

    assert "2.00000 $" in llm.cost_line(reply)
