from __future__ import annotations

import json
import os

from services.config import APP_NAME, DEFAULT_ANALYST_MODEL
from services.sql_generator import get_openrouter_client


def build_fallback_response(user_prompt: str, columns: list[str], rows: list[list], chart_ideas: list[str]) -> str:
    row_count = len(rows)
    if row_count == 0:
        return (
            "## Direct answer\n"
            "No matching records were found for this question.\n\n"
            "## Executive summary\n"
            "The query executed successfully, but the current database does not contain rows that match the request.\n\n"
            "## Key findings\n"
            "- The SQL ran without an execution error.\n"
            "- The current filters or phrasing are likely too narrow.\n\n"
            "## Dashboard recommendations\n"
            "- Start with a broader table view to confirm the available records.\n"
            "- Reduce filters before building a chart.\n\n"
            "## Next questions\n"
            "- Can we widen the date range?\n"
            "- Should we group by customer, category, or month?"
        )

    preview_lines = "\n".join([f"- {dict(zip(columns, row))}" for row in rows[:5]])
    chart_lines = "\n".join([f"- {idea}" for idea in chart_ideas])
    return (
        "## Direct answer\n"
        f"I found `{row_count}` row(s) for `{user_prompt}`.\n\n"
        "## Executive summary\n"
        f"The result set contains `{len(columns)}` field(s): `{', '.join(columns)}`.\n\n"
        "## Key findings\n"
        f"- The query returned `{row_count}` row(s).\n"
        f"- Sample records:\n{preview_lines}\n\n"
        "## Dashboard recommendations\n"
        f"{chart_lines}\n\n"
        "## Next questions\n"
        "- Do you want a ranking, trend view, or customer breakdown next?\n"
        "- Should I narrow this to a specific time period or category?"
    )


def generate_analyst_response(
    user_prompt: str,
    sql_query: str,
    columns: list[str],
    rows: list[list],
    chart_ideas: list[str],
    schema_summary: list[str],
    sql_review: dict,
) -> str:
    try:
        client = get_openrouter_client("OPENROUTER_ANALYST_API_KEY", fallback_envs=["OPENROUTER_API_KEY"])
        system_prompt = """
        You are a senior data analyst preparing a polished dashboard-ready business briefing.
        Rewrite the database result into a clear, sharp, stakeholder-friendly analysis.
        Rules:
        - Never invent facts that are not present in the data.
        - Always respond in Markdown with these exact sections:
          ## Direct answer
          ## Executive summary
          ## Key findings
          ## Dashboard recommendations
          ## Next questions
        - Under Key findings, use concise bullet points.
        - Under Dashboard recommendations, recommend concrete visual displays tied to the actual columns returned.
        - If the question is about schema or structure, explain the data model and relationships clearly.
        - Sound experienced, precise, and useful.
        """

        payload = {
            "question": user_prompt,
            "sql_query": sql_query,
            "columns": columns,
            "row_count": len(rows),
            "preview_rows": [dict(zip(columns, row)) for row in rows[:12]],
            "chart_ideas": chart_ideas,
            "schema_summary": schema_summary,
            "sql_review": sql_review,
        }

        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_ANALYST_MODEL", DEFAULT_ANALYST_MODEL),
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"This answer will be shown inside the {APP_NAME} application. "
                        "Write the result better than a raw SQL tool and make it presentation-ready.\n\n"
                        f"{json.dumps(payload, indent=2, default=str)}"
                    ),
                },
            ],
        )
        analyst_response = response.choices[0].message.content or ""
        return analyst_response.strip()
    except Exception:
        return build_fallback_response(user_prompt, columns, rows, chart_ideas)
