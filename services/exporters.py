from __future__ import annotations

import json

import pandas as pd

from services.types import QueryResult


def build_export_payloads(result: QueryResult) -> dict[str, str]:
    dataframe = pd.DataFrame(result.rows, columns=result.columns)
    csv_payload = dataframe.to_csv(index=False) if not dataframe.empty else ""
    markdown_payload = "\n\n".join(
        [
            f"# {result.question}",
            result.answer_markdown,
            "## SQL",
            f"```sql\n{result.sql_query}\n```",
        ]
    )
    json_payload = json.dumps(result.to_dict(), indent=2, default=str)

    return {
        "csv": csv_payload,
        "markdown": markdown_payload,
        "json": json_payload,
    }
