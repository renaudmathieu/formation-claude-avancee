"""Command line entry point: `uv run python -m escale <command>`."""

import argparse
import os
import sys

import anthropic
from dotenv import load_dotenv

from escale.assistant import describe, run_task
from escale.chat import run_chat
from escale.llm import cost_line, send, text_of, with_retry


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="escale", description="Assistant de déplacement")
    commands = parser.add_subparsers(dest="command", required=True)
    ask = commands.add_parser("ask", help="Poser une seule question")
    ask.add_argument("question")
    commands.add_parser("chat", help="Discuter tour à tour")
    agent = commands.add_parser("agent", help="Confier une tâche à l'agent")
    agent.add_argument("task")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY manquante : la renseigner dans .env.", file=sys.stderr)
        return 1

    client = anthropic.Anthropic()
    try:
        if args.command == "ask":
            messages = [{"role": "user", "content": args.question}]
            response = with_retry(lambda: send(client, messages))
            print(text_of(response))
            print(f"[stop_reason={response.stop_reason}, {cost_line(response)}]")
        elif args.command == "agent":
            result = run_task(client, args.task)
            print(f"\n{describe(result)}")
            print(f"[{result.iterations} tours, fin : {result.stop_reason}]")
            return 0 if result.is_complete else 1
        else:
            run_chat(client)
    except anthropic.AuthenticationError:
        print("Clé API refusée : vérifiez ANTHROPIC_API_KEY dans .env.", file=sys.stderr)
        return 1
    except anthropic.APIConnectionError as error:
        print(f"API injoignable, vérifiez le réseau ou le proxy : {error}", file=sys.stderr)
        return 1
    except anthropic.APIStatusError as error:
        print(f"Erreur de l'API ({error.status_code}) : {error.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
