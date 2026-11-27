import pytest

from escale import chat
from tests.fakes import FakeClient, response, text, thinking

pytestmark = pytest.mark.skip(reason="TP 1 : retirer cette ligne pour commencer")

def test_second_turn_sends_the_whole_history():
    client = FakeClient(response(text("Bonjour Camille")), response(text("Camille")))
    conversation = chat.Conversation(client)

    conversation.ask("Je m'appelle Camille")
    assert conversation.ask("Comment je m'appelle ?") == "Camille"

    roles = [message["role"] for message in client.requests[1]["messages"]]
    assert roles == ["user", "assistant", "user"]


def test_thinking_blocks_stay_in_the_history():
    client = FakeClient(response(thinking("hmm"), text("Oui")))
    conversation = chat.Conversation(client)

    assert conversation.ask("Ça va ?") == "Oui"

    assert [block.type for block in conversation.messages[1]["content"]] == ["thinking", "text"]


def test_image_is_sent_before_the_question():
    client = FakeClient(response(text("Un billet")))

    chat.Conversation(client).ask("Quoi ?", image_path="exemples/billet-fictif.png")

    image, question = client.requests[0]["messages"][0]["content"]
    assert image["source"]["media_type"] == "image/png"
    assert image["source"]["data"]
    assert question == {"type": "text", "text": "Quoi ?"}


def test_unsupported_image_format_is_rejected():
    with pytest.raises(ValueError):
        chat.image_block("README.md")


def test_refused_turn_leaves_the_history_clean():
    client = FakeClient(response(stop_reason="refusal"))
    conversation = chat.Conversation(client)

    assert conversation.ask("...") == chat.REFUSAL_MESSAGE
    assert conversation.messages == []


def test_truncated_answer_is_flagged():
    client = FakeClient(response(text("Début"), stop_reason="max_tokens"))

    assert chat.TRUNCATED_MESSAGE in chat.Conversation(client).ask("Longue réponse")


def test_image_command_has_a_default_question():
    assert chat.parse_image_command("/image a.png")[0] == "a.png"
    assert chat.parse_image_command("/image a.png Quel train ?") == ("a.png", "Quel train ?")


def test_interrupted_turn_leaves_the_history_clean():
    client = FakeClient(response(text("Bonjour")), KeyboardInterrupt())
    chat_session = chat.Conversation(client)
    chat_session.ask("Bonjour")

    with pytest.raises(KeyboardInterrupt):
        chat_session.ask("Et ensuite ?")

    assert [message["role"] for message in chat_session.messages] == ["user", "assistant"]
