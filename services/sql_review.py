from __future__ import annotations

import re

from services.types import SQLReviewResult


def infer_question_intent(question: str) -> dict:
    lowered = question.lower()
    return {
        "wants_ranking": any(token in lowered for token in ["top", "highest", "lowest", "best", "worst", "rank"]),
        "wants_trend": any(token in lowered for token in ["trend", "over time", "by month", "by year", "daily", "monthly", "weekly"]),
        "wants_average": any(token in lowered for token in ["average", "avg", "mean"]),
        "wants_total": any(token in lowered for token in ["sum", "total", "revenue", "sales"]),
        "wants_count": any(token in lowered for token in ["count", "how many", "number of"]),
        "wants_comparison": any(token in lowered for token in ["compare", "by", "versus", "vs"]),
        "mentions_schema": any(token in lowered for token in ["schema", "tables", "database structure", "relationship", "columns"]),
    }


def review_generated_sql(question: str, sql_query: str, schema_text: str) -> SQLReviewResult:
    lowered_sql = sql_query.lower()
    intent = infer_question_intent(question)
    issues: list[str] = []
    strengths: list[str] = []

    if "select" in lowered_sql:
        strengths.append("Uses a read-only SELECT statement.")

    if any(table_name.lower() in lowered_sql for table_name in re.findall(r'"([^"]+)": \{', schema_text)):
        strengths.append("References at least one table from the extracted schema.")

    if intent["wants_ranking"]:
        if "order by" not in lowered_sql:
            issues.append("The question sounds like a ranking request, but the SQL has no ORDER BY clause.")
        else:
            strengths.append("Includes ORDER BY for a ranking-style question.")
        if "limit" not in lowered_sql:
            issues.append("A top-ranking question may need LIMIT for a cleaner result.")

    if intent["wants_trend"] and "group by" not in lowered_sql:
        issues.append("The question suggests a trend or time grouping, but the SQL has no GROUP BY clause.")
    elif intent["wants_trend"]:
        strengths.append("Includes GROUP BY for a trend-oriented question.")

    if intent["wants_average"] and "avg(" not in lowered_sql:
        issues.append("The question suggests an average, but the SQL does not use AVG().")
    if intent["wants_total"] and not any(token in lowered_sql for token in ["sum(", "count(", "avg(", "group by"]):
        issues.append("The question sounds metric-driven, but the SQL may not be aggregating results.")
    if intent["wants_count"] and "count(" not in lowered_sql:
        issues.append("The question sounds like a count request, but the SQL does not use COUNT().")

    if not issues:
        strengths.append("The SQL structure broadly matches the intent of the question.")

    return SQLReviewResult(
        approved=len(issues) == 0,
        issues=issues,
        strengths=strengths,
        inferred_intent=intent,
    )
