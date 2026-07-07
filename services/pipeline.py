from __future__ import annotations

from services.analyst_writer import generate_analyst_response
from services.chart_builder import build_dataframe, build_visual_spec, profile_dataframe, suggest_chart_ideas
from services.database import get_database_adapter
from services.exporters import build_export_payloads
from services.sql_generator import text_to_sql
from services.sql_guard import validate_sql_query
from services.sql_review import review_generated_sql
from services.types import QueryResult


def analyze_question(prompt: str, conversation_context: list[dict] | None = None, database_url: str | None = None) -> dict:
    adapter = get_database_adapter(database_url)
    schema_text = adapter.extract_schema_text()
    schema_summary = adapter.schema_summary()
    schema_graph = adapter.schema_graph_data()

    sql_query, follow_up_context = text_to_sql(schema_text, prompt, conversation_context=conversation_context)
    safe_sql_query = validate_sql_query(sql_query)

    sql_review = review_generated_sql(prompt, safe_sql_query, schema_text)
    columns, rows = adapter.execute_sql(safe_sql_query)

    dataframe = build_dataframe(columns, rows)
    data_profile = profile_dataframe(dataframe)
    chart_ideas = suggest_chart_ideas(data_profile, columns, len(rows))
    visual_spec = build_visual_spec(data_profile, columns, len(rows), dataframe=dataframe)

    answer_markdown = generate_analyst_response(
        user_prompt=prompt,
        sql_query=safe_sql_query,
        columns=columns,
        rows=rows,
        chart_ideas=chart_ideas,
        schema_summary=schema_summary,
        sql_review=sql_review.to_dict(),
    )

    result = QueryResult(
        question=prompt,
        sql_query=safe_sql_query,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        answer_markdown=answer_markdown,
        chart_ideas=chart_ideas,
        sql_review=sql_review,
        data_profile=data_profile,
        visual_spec=visual_spec,
        schema_summary=schema_summary,
        schema_graph=schema_graph,
        follow_up_context=follow_up_context,
    )
    result.exports = build_export_payloads(result)
    return result.to_dict()


def get_data_from_database(prompt: str, database_url: str | None = None) -> list[list]:
    return analyze_question(prompt, database_url=database_url)["rows"]
