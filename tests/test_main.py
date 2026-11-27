from escale import __main__ as cli


def test_missing_key_gives_a_clear_message(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr("sys.argv", ["escale", "ask", "Bonjour"])

    assert cli.main() == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
