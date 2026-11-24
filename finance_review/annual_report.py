import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
_PRECISION = Decimal("0.01")


@dataclass(frozen=True)
class Citation:
    source_id: str
    title: str
    year: int
    page: int
    locator: str
    source_label: str
    source_url: Optional[str]


@dataclass(frozen=True)
class ReportFact:
    metric: str
    label: str
    amount: Decimal
    unit: str
    page: int
    locator: str


@dataclass(frozen=True)
class NarrativePassage:
    id: str
    section: str
    page: int
    text: str


@dataclass(frozen=True)
class AnnualReport:
    id: str
    issuer: str
    title: str
    year: int
    currency: str
    scale: str
    source_label: str
    source_url: Optional[str]
    facts: Dict[str, ReportFact]
    passages: Tuple[NarrativePassage, ...]


@dataclass(frozen=True)
class PassageMatch:
    passage_id: str
    score: float
    text: str
    citation: Citation


@dataclass(frozen=True)
class MetricInput:
    label: str
    value: str
    unit: str
    citation: Citation


@dataclass(frozen=True)
class MetricAnswer:
    metric: str
    year: int
    value: str
    unit: str
    formula: str
    inputs: Tuple[MetricInput, ...]


@dataclass(frozen=True)
class QuestionAnswer:
    intent: str
    content: object
    human_review_required: bool
    notice: str


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _required_string(record: dict, key: str, context: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} must include a non-empty '{}'".format(context, key))
    return value.strip()


def _optional_url(record: dict, key: str, context: str) -> Optional[str]:
    value = record.get(key)
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError("{} has an invalid '{}'".format(context, key))
    return value.strip() if value is not None else None


def _positive_integer(record: dict, key: str, context: str) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("{} must have a positive integer '{}'".format(context, key))
    return value


def _parse_fact(record: dict, context: str) -> ReportFact:
    value = _required_string(record, "value", context)
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("{} has an invalid decimal value".format(context)) from error
    if not amount.is_finite():
        raise ValueError("{} must have a finite decimal value".format(context))
    return ReportFact(
        metric=_required_string(record, "metric", context),
        label=_required_string(record, "label", context),
        amount=amount,
        unit=_required_string(record, "unit", context),
        page=_positive_integer(record, "page", context),
        locator=_required_string(record, "locator", context),
    )


def load_reports(path: Path) -> Tuple[AnnualReport, ...]:
    data = _read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("reports"), list):
        raise ValueError("Report data must contain a 'reports' list")
    issuer = _required_string(data, "issuer", "Report data")

    reports = []
    seen_ids = set()
    seen_years = set()
    seen_passage_ids = set()
    for index, record in enumerate(data["reports"]):
        context = "Report {}".format(index)
        if not isinstance(record, dict):
            raise ValueError("{} must be an object".format(context))
        report_id = _required_string(record, "id", context)
        if report_id in seen_ids:
            raise ValueError("Duplicate report id: {}".format(report_id))
        seen_ids.add(report_id)
        year = _positive_integer(record, "year", context)
        if year in seen_years:
            raise ValueError("Duplicate report year: {}".format(year))
        seen_years.add(year)
        if not isinstance(record.get("facts"), list) or not record["facts"]:
            raise ValueError("{} must contain financial facts".format(context))
        if not isinstance(record.get("passages"), list):
            raise ValueError("{} must contain a 'passages' list".format(context))

        facts = {}
        for fact_index, item in enumerate(record["facts"]):
            if not isinstance(item, dict):
                raise ValueError("{} fact {} must be an object".format(context, fact_index))
            fact = _parse_fact(item, "{} fact {}".format(context, fact_index))
            if fact.metric in facts:
                raise ValueError(
                    "Duplicate metric '{}' in report {}".format(fact.metric, year)
                )
            facts[fact.metric] = fact

        passages = []
        for passage_index, item in enumerate(record["passages"]):
            passage_context = "{} passage {}".format(context, passage_index)
            if not isinstance(item, dict):
                raise ValueError("{} must be an object".format(passage_context))
            passage_id = _required_string(item, "id", passage_context)
            if passage_id in seen_passage_ids:
                raise ValueError("Duplicate passage id: {}".format(passage_id))
            seen_passage_ids.add(passage_id)
            passages.append(
                NarrativePassage(
                    id=passage_id,
                    section=_required_string(item, "section", passage_context),
                    page=_positive_integer(item, "page", passage_context),
                    text=_required_string(item, "text", passage_context),
                )
            )

        reports.append(
            AnnualReport(
                id=report_id,
                issuer=issuer,
                title=_required_string(record, "title", context),
                year=year,
                currency=_required_string(record, "currency", context),
                scale=_required_string(record, "scale", context),
                source_label=_required_string(record, "source_label", context),
                source_url=_optional_url(record, "source_url", context),
                facts=facts,
                passages=tuple(passages),
            )
        )
    return tuple(sorted(reports, key=lambda report: report.year))


def _citation(report: AnnualReport, page: int, locator: str) -> Citation:
    return Citation(
        source_id=report.id,
        title=report.title,
        year=report.year,
        page=page,
        locator=locator,
        source_label=report.source_label,
        source_url=report.source_url,
    )


def _fact(report: AnnualReport, metric: str) -> ReportFact:
    fact = report.facts.get(metric)
    if fact is None:
        raise ValueError(
            "Metric '{}' is unavailable in the {} report".format(metric, report.year)
        )
    return fact


def _metric_input(report: AnnualReport, fact: ReportFact) -> MetricInput:
    return MetricInput(
        label=fact.label,
        value=str(fact.amount),
        unit=fact.unit,
        citation=_citation(report, fact.page, fact.locator),
    )


def calculate_metric(
    metric: str, year: int, reports: Sequence[AnnualReport]
) -> MetricAnswer:
    reports_by_year = {report.year: report for report in reports}
    current = reports_by_year.get(year)
    if current is None:
        raise ValueError("No report is available for {}".format(year))

    if metric == "revenue_growth":
        previous = reports_by_year.get(year - 1)
        if previous is None:
            raise ValueError(
                "Revenue growth for {} requires a report for {}".format(year, year - 1)
            )
        if (previous.issuer, previous.currency, previous.scale) != (
            current.issuer,
            current.currency,
            current.scale,
        ):
            raise ValueError("Revenue growth inputs must use the same issuer and units")
        previous_revenue = _fact(previous, "revenue")
        current_revenue = _fact(current, "revenue")
        if previous_revenue.unit != current_revenue.unit:
            raise ValueError("Revenue growth inputs must use the same unit")
        if previous_revenue.amount == 0:
            raise ValueError("Revenue growth is undefined when prior-year revenue is zero")
        value = (
            (current_revenue.amount - previous_revenue.amount)
            / previous_revenue.amount
            * Decimal("100")
        ).quantize(_PRECISION, rounding=ROUND_HALF_UP)
        return MetricAnswer(
            metric=metric,
            year=year,
            value=str(value),
            unit="percent",
            formula="(current-year revenue - prior-year revenue) / prior-year revenue * 100",
            inputs=(
                _metric_input(previous, previous_revenue),
                _metric_input(current, current_revenue),
            ),
        )

    if metric == "net_profit_margin":
        revenue = _fact(current, "revenue")
        net_profit = _fact(current, "net_profit")
        if revenue.amount == 0:
            raise ValueError("Net profit margin is undefined when revenue is zero")
        if revenue.unit != net_profit.unit:
            raise ValueError("Net profit and revenue must use the same unit")
        value = (net_profit.amount / revenue.amount * Decimal("100")).quantize(
            _PRECISION, rounding=ROUND_HALF_UP
        )
        return MetricAnswer(
            metric=metric,
            year=year,
            value=str(value),
            unit="percent",
            formula="net profit / revenue * 100",
            inputs=(
                _metric_input(current, net_profit),
                _metric_input(current, revenue),
            ),
        )

    raise ValueError("Unsupported metric: {}".format(metric))


def _tokens(text: str) -> List[str]:
    return _TOKEN_PATTERN.findall(text.casefold())


def search_passages(
    query: str, reports: Sequence[AnnualReport], top_k: int = 3
) -> Tuple[PassageMatch, ...]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Search query must not be empty")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer")
    query_terms = Counter(_tokens(query))
    if not query_terms:
        return ()

    passages = []
    for report in reports:
        for passage in report.passages:
            terms = _tokens(passage.text)
            if terms:
                passages.append((report, passage, terms, Counter(terms)))
    if not passages:
        return ()

    document_count = len(passages)
    average_length = sum(len(item[2]) for item in passages) / float(document_count)
    document_frequency = Counter()
    for _, _, terms, _ in passages:
        document_frequency.update(set(terms))

    ranked = []
    for report, passage, terms, frequencies in passages:
        length_norm = 1.2 * (1.0 - 0.75 + 0.75 * len(terms) / average_length)
        score = 0.0
        for term, query_frequency in query_terms.items():
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            doc_frequency = document_frequency[term]
            inverse_frequency = math.log(
                1.0
                + (document_count - doc_frequency + 0.5)
                / (doc_frequency + 0.5)
            )
            score += query_frequency * inverse_frequency * (
                frequency * 2.2 / (frequency + length_norm)
            )
        if score > 0.0:
            ranked.append(
                PassageMatch(
                    passage_id=passage.id,
                    score=score,
                    text=passage.text,
                    citation=_citation(report, passage.page, passage.section),
                )
            )
    ranked.sort(key=lambda result: (-result.score, result.citation.year, result.passage_id))
    return tuple(ranked[:top_k])


def route_question(query: str) -> Tuple[str, Optional[int]]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Question must not be empty")
    lowered = query.casefold()
    year_match = _YEAR_PATTERN.search(query)
    year = int(year_match.group(1)) if year_match else None
    qualitative_cue = re.search(
        r"\b(why|what drove|drivers?|explain|describe|discuss|summari[sz]e)\b",
        lowered,
    )
    if qualitative_cue:
        return "text_search", year
    revenue_query = re.search(r"\b(revenue|sales)\b", lowered)
    growth_query = re.search(r"\b(growth|grew|yoy|year[- ]over[- ]year)\b", lowered)
    profit_query = re.search(r"\b(net profit|net income)\b", lowered)
    margin_query = re.search(r"\bmargin\b", lowered)

    if revenue_query and growth_query:
        return "revenue_growth", year
    if profit_query and margin_query:
        return "net_profit_margin", year
    return "text_search", year


def answer_question(
    query: str, reports: Sequence[AnnualReport], top_k: int = 3
) -> QuestionAnswer:
    if not reports:
        raise ValueError("At least one annual report is required")
    intent, year = route_question(query)
    notice = (
        "Synthetic demo data only. Verify reported figures and citations against "
        "the original filing before relying on them."
    )
    if intent in ("revenue_growth", "net_profit_margin"):
        target_year = year if year is not None else max(report.year for report in reports)
        result = calculate_metric(intent, target_year, reports)
        return QuestionAnswer(
            intent=intent,
            content=result,
            human_review_required=True,
            notice=notice,
        )
    return QuestionAnswer(
        intent=intent,
        content=search_passages(query, reports, top_k),
        human_review_required=True,
        notice=notice,
    )


def evaluate_search(
    cases: Sequence[dict], reports: Sequence[AnnualReport], top_k: int = 3
) -> dict:
    if not cases:
        raise ValueError("At least one evaluation case is required")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer")

    recalls = []
    reciprocal_ranks = []
    precisions = []
    for case in cases:
        query = case.get("query")
        relevant_ids = case.get("relevant_passage_ids")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Evaluation cases must include a query")
        if not isinstance(relevant_ids, list) or not relevant_ids:
            raise ValueError("Evaluation cases must list relevant passage ids")
        relevant = set(relevant_ids)
        ranked_ids = [
            item.passage_id for item in search_passages(query, reports, top_k)
        ]
        hits = [
            index
            for index, passage_id in enumerate(ranked_ids, start=1)
            if passage_id in relevant
        ]
        recalls.append(len(set(ranked_ids) & relevant) / float(len(relevant)))
        reciprocal_ranks.append(1.0 / hits[0] if hits else 0.0)
        denominator = min(top_k, len(ranked_ids))
        precisions.append(
            len(set(ranked_ids) & relevant) / float(top_k) if denominator else 0.0
        )
    case_count = float(len(cases))
    return {
        "cases": len(cases),
        "top_k": top_k,
        "recall_at_k": sum(recalls) / case_count,
        "mean_reciprocal_rank": sum(reciprocal_ranks) / case_count,
        "precision_at_k": sum(precisions) / case_count,
    }
