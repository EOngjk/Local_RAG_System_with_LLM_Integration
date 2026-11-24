# Financial Filing Analyst

A portfolio prototype for questions over annual reports, with two distinct paths:

- **Numerical questions** (revenue growth, net profit margin) route to deterministic Python `Decimal` calculations over extracted facts. The result includes formula, units, periods, and citations for every input.
- **Qualitative questions** route to BM25 passage retrieval and return page/section citations rather than an unverified generated answer.

The router is deliberately simple and testable. LangGraph or an LLM answer-generation step can be added later if evaluation demonstrates a need; neither should perform financial arithmetic.

## Run the synthetic demo

The demo uses Python's standard library and fictional data only:

```powershell
python -m finance_review.cli sources
python -m finance_review.cli ask "What was revenue growth in 2025?"
python -m finance_review.cli ask "Calculate net profit margin for 2025."
python -m finance_review.cli ask "What drove revenue growth and fee income in 2024?"
python -m finance_review.cli evaluate-search --top-k 3
python -m unittest discover -s tests -v
```

`data/demo/synthetic_annual_reports.json` contains three years of fictional financial facts and narrative excerpts. Its page references are synthetic demonstration metadata, not citations to real filings. The retrieval evaluation set is also synthetic and small; its scores are a baseline, not a production-quality claim.

## Using real reports

The [HKEXnews Title Search](https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=en) is listed only as a source-discovery link. HKEX notes that issuer-submitted materials may not be verified and may be copyrighted. Public availability is not permission to redistribute: check the relevant HKEX and issuer terms before downloading, processing, or packaging filings. Do not commit report PDFs without authorization.

For a real-data extension, select one issuer and a small set of annual reports, record source URL, year, currency, unit, page/table/section, and extraction method for each fact, and manually verify extracted figures against the filing. Do not use Societe Generale internal material, client documents, or confidential data.

This tool is an evidence and calculation aid, not investment advice. It does not make buy/sell recommendations. Verify reported figures and citations against the original filing before relying on them.

The root-level `main.py`, `populate_database.py`, and `query_data.py` are the earlier local RAG prototype; they are separate from this standard-library demo.
