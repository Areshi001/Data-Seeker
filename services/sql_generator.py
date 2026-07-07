from __future__ import annotations

import json
import os

import requests
from openai import OpenAI

from services.config import DEFAULT_OPENROUTER_BASE_URL, DEFAULT_SQL_MODEL
from services.sql_guard import clean_sql_response


def get_openrouter_client(api_key_env: str = "OPENROUTER_API_KEY", fallback_envs: list[str] | None = None) -> OpenAI:
    fallback_envs = fallback_envs or []
    api_key = None

    for env_name in [api_key_env, *fallback_envs]:
        candidate = os.getenv(env_name)
        if candidate:
            api_key = candidate
            break

    if not api_key:
        all_envs = ", ".join([api_key_env, *fallback_envs])
        raise ValueError(f"Missing OpenRouter credentials. Set one of: {all_envs}.")

    return OpenAI(base_url=DEFAULT_OPENROUTER_BASE_URL, api_key=api_key)


def get_tavily_context(user_prompt: str) -> str:
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    use_tavily = os.getenv("USE_TAVILY_FOR_SQL_CONTEXT", "false").lower() == "true"

    if not tavily_api_key or not use_tavily:
        return ""

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": tavily_api_key,
                "query": user_prompt,
                "search_depth": "basic",
                "max_results": 3,
                "include_answer": True,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        answer = payload.get("answer", "").strip()
        results = payload.get("results", [])
        snippets = [item.get("content", "").strip() for item in results[:3] if item.get("content")]
        combined_context = "\n".join(part for part in [answer, *snippets] if part)
        return combined_context[:1500]
    except Exception:
        return ""


def build_follow_up_context(conversation_context: list[dict] | None) -> str:
    if not conversation_context:
        return ""

    trimmed_context = []
    for item in conversation_context[-3:]:
        trimmed_context.append(
            {
                "question": item.get("question", ""),
                "sql_query": item.get("sql_query", ""),
                "columns": item.get("columns", []),
                "row_count": item.get("row_count", 0),
            }
        )
    return json.dumps(trimmed_context, indent=2)


def text_to_sql(schema_text: str, prompt: str, conversation_context: list[dict] | None = None) -> tuple[str, str]:
    system_prompt = """
    You are an expert analytics engineer who writes SQLite-compatible SQL.
    Given a database schema and a user question, generate one valid SELECT statement only.
    Rules:
    - Use only the tables and columns present in the schema.
    - Respect foreign keys when joins are needed.
    - Ignore SQLite internal tables unless the user explicitly asks for metadata.
    - Return only SQL, with no markdown or explanation.
    - Prefer clear aliases and business-friendly aggregations.
    - If the user asks for top, rank, highest, lowest, best, or worst, include ORDER BY and LIMIT when appropriate.
    - If the user asks for trends or over time, group by the relevant date or period field when available.
    """

    web_context = get_tavily_context(prompt)
    follow_up_context = build_follow_up_context(conversation_context)

    prompt_parts = [
        f"Schema:\n{schema_text}",
        f"Question:\n{prompt}",
    ]
    if follow_up_context:
        prompt_parts.append(f"Recent conversation context:\n{follow_up_context}")
    if web_context:
        prompt_parts.append(f"Optional web context:\n{web_context}")
    prompt_parts.append("SQL Query:")

    client = get_openrouter_client()
    response = client.chat.completions.create(
        model=DEFAULT_SQL_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n\n".join(prompt_parts)},
        ],
    )

    raw_response = response.choices[0].message.content or ""
    return clean_sql_response(raw_response), follow_up_context
