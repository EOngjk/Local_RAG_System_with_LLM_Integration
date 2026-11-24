import json
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from finance_review.annual_report import (
    AnnualReport,
    answer_question,
    calculate_metric,
    evaluate_search,
    load_reports,
    route_question,
    search_passages,
)


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"


class AnnualReportAnalystTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports = load_reports(DEMO / "synthetic_annual_reports.json")
        with (DEMO / "search_evaluation_cases.json").open(
            "r", encoding="utf-8"
        ) as file:
            cls.cases = json.load(file)["cases"]

    def test_revenue_growth_is_deterministic_and_cites_both_years(self):
        answer = answer_question(
            "What was revenue growth in 2025?", self.reports
        )

        self.assertEqual(answer.intent, "revenue_growth")
        self.assertEqual(answer.content.value, "5.00")
        self.assertEqual(answer.content.unit, "percent")
        self.assertEqual(
            [item.citation.year for item in answer.content.inputs], [2024, 2025]
        )
        self.assertTrue(answer.human_review_required)

    def test_net_profit_margin_uses_profit_and_revenue(self):
        answer = answer_question(
            "Calculate the net profit margin for 2025.", self.reports
        )

        self.assertEqual(answer.intent, "net_profit_margin")
        self.assertEqual(answer.content.value, "8.00")
        self.assertEqual(
            [item.label for item in answer.content.inputs],
            ["Profit for the year", "Revenue"],
        )

    def test_qualitative_question_returns_page_cited_evidence(self):
        answer = answer_question(
            "What drove revenue growth and fee income in 2024?", self.reports
        )

        self.assertEqual(answer.intent, "text_search")
        self.assertEqual(answer.content[0].passage_id, "2024-revenue-drivers")
        self.assertEqual(answer.content[0].citation.page, 22)
        self.assertEqual(answer.content[0].citation.year, 2024)

    def test_router_only_routes_supported_calculations(self):
        self.assertEqual(route_question("Revenue growth in 2025?")[0], "revenue_growth")
        self.assertEqual(route_question("What is the current market price?")[0], "text_search")

    def test_zero_revenue_is_an_explicit_error(self):
        report = self.reports[-1]
        facts = dict(report.facts)
        facts["revenue"] = replace(facts["revenue"], amount=Decimal("0"))
        zero_revenue_report = replace(report, facts=facts)

        with self.assertRaisesRegex(ValueError, "revenue is zero"):
            calculate_metric(
                "net_profit_margin",
                2025,
                self.reports[:-1] + (zero_revenue_report,),
            )

    def test_missing_comparison_year_is_an_explicit_error(self):
        with self.assertRaisesRegex(ValueError, "requires a report for 2022"):
            calculate_metric("revenue_growth", 2023, self.reports)

    def test_retrieval_evaluation_reports_metrics(self):
        metrics = evaluate_search(self.cases, self.reports, top_k=3)

        self.assertEqual(metrics["cases"], 3)
        self.assertGreater(metrics["recall_at_k"], 0.0)
        self.assertGreater(metrics["mean_reciprocal_rank"], 0.0)

    def test_search_rejects_invalid_top_k(self):
        with self.assertRaisesRegex(ValueError, "top_k"):
            search_passages("revenue drivers", self.reports, top_k=0)

    def test_loader_rejects_duplicate_report_year(self):
        source = json.loads((DEMO / "synthetic_annual_reports.json").read_text(
            encoding="utf-8"
        ))
        source["reports"][1]["year"] = source["reports"][0]["year"]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reports.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate report year"):
                load_reports(path)


if __name__ == "__main__":
    unittest.main()
