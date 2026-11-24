import argparse
import json
from dataclasses import asdict
from pathlib import Path

from finance_review.annual_report import (
    answer_question,
    evaluate_search,
    load_reports,
)


DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "demo"


def _print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def build_parser():
    parser = argparse.ArgumentParser(
        description="Synthetic annual-report analyst demo"
    )
    commands = parser.add_subparsers(dest="command")
    commands.required = True

    ask = commands.add_parser(
        "ask", help="Route a question to deterministic metrics or passage retrieval"
    )
    ask.add_argument("question")
    ask.add_argument("--top-k", type=int, default=3)

    evaluate = commands.add_parser(
        "evaluate-search", help="Evaluate qualitative retrieval on synthetic cases"
    )
    evaluate.add_argument("--top-k", type=int, default=3)

    commands.add_parser("sources", help="List official HKMA source discovery links")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "ask":
            reports = load_reports(DATA_DIR / "synthetic_annual_reports.json")
            result = answer_question(args.question, reports, args.top_k)
            _print_json(asdict(result))
        elif args.command == "evaluate-search":
            reports = load_reports(DATA_DIR / "synthetic_annual_reports.json")
            cases_path = DATA_DIR / "search_evaluation_cases.json"
            with cases_path.open("r", encoding="utf-8") as file:
                cases = json.load(file)["cases"]
            _print_json(evaluate_search(cases, reports, args.top_k))
        else:
            with (DATA_DIR / "source_catalog.json").open("r", encoding="utf-8") as file:
                _print_json(json.load(file))
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
