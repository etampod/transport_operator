"""Ask one question from the command line."""

from __future__ import annotations

import argparse
import json

from podoba_helpdesk.service import ChatService


def main() -> None:
    parser = argparse.ArgumentParser(description="Podoba Transit customer-service assistant")
    parser.add_argument("query", help="Passenger question")
    parser.add_argument("--json", action="store_true", help="Print the full result as JSON")
    args = parser.parse_args()
    result = ChatService().ask(args.query)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["answer"])
        if result["citations"]:
            print("\nSources: " + "; ".join(result["citations"]))


if __name__ == "__main__":
    main()
