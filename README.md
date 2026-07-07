# Data Seeker

Turn natural language questions into executable SQL against your database. `Data Seeker` uses one OpenRouter model to generate safe SQL and a second OpenRouter model to rewrite results as a polished senior-analyst answer, then builds a chart-ready result object for the Streamlit UI.

## Features
- Automatic schema extraction from the configured database URL
- Natural language to SQL using OpenRouter-hosted LLMs
- Deterministic SQL generation (`temperature=0`)
- Easily switch models via environment variables
- Second-pass analyst rewrite for clearer, more executive-friendly answers
- Heuristic SQL review to catch weak ranking, trend, and aggregation queries
- Automatic data profiling and dashboard chart selection
- Interactive Streamlit dashboard with filters, exports, and history-aware follow-up context
- Optional Tavily web context enrichment for ambiguous business questions
- Simple Python API (`get_data_from_database(prompt)`) for integration
- Fast environment setup and dependency management via `uv`
- Read-only SQL validation before execution

## Tech Stack
- Python 3.11+
- SQLite by default, with SQLAlchemy-based support for other database URLs
- SQLAlchemy for schema introspection and query execution
- OpenRouter Chat Completions API
- OpenRouter models (default: `deepseek/deepseek-v4-flash`)
- Pandas and Altair for result shaping and chart rendering
- Tavily Search API (optional)
- `uv` for dependency resolution, syncing, and running

## Architecture & Implementation Flow

Data Seeker is coordinated by a central pipeline that routes data between safety checks, databases, and AI models.

```mermaid
flowchart TD
    subgraph UI ["User Interface (frontend.py)"]
        UI_Input[User Input Query]
        UI_Output[Render Analyst Brief, Plotly Chart, Schema Graph]
    end

    subgraph Orchestration ["Pipeline Coordination (services/pipeline.py)"]
        P_Start[analyze_question]
        P_End[Assemble QueryResult]
    end

    subgraph DatabaseLayer ["Database Adaption (services/database.py)"]
        DB_Extract[Extract Schema Map & Graphviz DOT]
        DB_Exec[Execute Clean SQL]
    end

    subgraph SQLGen ["SQL Generation (services/sql_generator.py)"]
        Gen_Tavily[Fetch Web Context]
        Gen_LLM[Call LLM for SQL]
    end

    subgraph Guards ["Security & Reviews"]
        Guard_Validate[Sanitize & Guard SQL\nservices/sql_guard.py]
        Review_Check[Check Intent Heuristics\nservices/sql_review.py]
    end

    subgraph VisLayer ["Visualization & Interpretation"]
        Chart_Profile[Profile Data & Build Chart Spec\nservices/chart_builder.py]
        LLM_Brief[Write Senior Analyst Briefing\nservices/analyst_writer.py]
    end

    UI_Input -->|Submit| P_Start
    
    %% 1. Schema Introspection
    P_Start -->|1. extract_schema_text| DB_Extract
    DB_Extract -->|Return cached schema| P_Start
    
    %% 2. Generate SQL
    P_Start -->|2. text_to_sql| Gen_LLM
    Gen_LLM -->|Optional Tavily search| Gen_Tavily
    Gen_LLM -->|Generate SQL query| P_Start

    %% 3. Validate
    P_Start -->|3. validate_sql_query| Guard_Validate
    Guard_Validate -->|Check syntax & blocklists| P_Start

    %% 4. Review
    P_Start -->|4. review_generated_sql| Review_Check
    Review_Check -->|Verify aggregate intents| P_Start

    %% 5. Execute
    P_Start -->|5. execute_sql| DB_Exec
    DB_Exec -->|Query database| P_Start

    %% 6. Profile & Chart
    P_Start -->|6. build_dataframe & profile| Chart_Profile
    Chart_Profile -->|Recommend visualization| P_Start

    %% 7. Briefing
    P_Start -->|7. generate_analyst_response| LLM_Brief
    LLM_Brief -->|Format markdown brief| P_Start

    %% Return
    P_Start --> P_End
    P_End -->|QueryResult Payload| UI_Output
```


## Prerequisites
- Create OpenRouter credentials at [OpenRouter](https://openrouter.ai/)
- Optional: create a Tavily API key at [Tavily](https://tavily.com/)
- Ensure `amazon.db` exists in the project root.

## Setup (UV)
No need to manually create a virtual environment—`uv` handles it.

```bash
# Install dependencies from pyproject.toml
uv sync

# Run the Streamlit app
uv run streamlit run frontend.py
```

## Environment Variables

Copy `.env.example` to `.env` and fill in your own values. The app loads `.env` automatically:

```env
DATABASE_URL=sqlite:///amazon.db
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=deepseek/deepseek-v4-flash
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_ANALYST_API_KEY=your_second_openrouter_api_key
OPENROUTER_ANALYST_MODEL=google/gemma-4-31b-it:free

TAVILY_API_KEY=your_tavily_api_key
USE_TAVILY_FOR_SQL_CONTEXT=false
```

Notes:
- `OPENROUTER_API_KEY` is required.
- `DATABASE_URL` defaults to `sqlite:///amazon.db`.
- `TAVILY_API_KEY` is optional.
- `USE_TAVILY_FOR_SQL_CONTEXT=true` enables prompt enrichment from Tavily search results.

To add a new dependency:
```bash
uv add package_name
```

To upgrade dependencies:
```bash
uv lock --upgrade
uv sync
```

## Usage
Python API example:
```python
from main import analyze_question
result = analyze_question("Show revenue by category")
print(result["answer_markdown"])
print(result["visual_spec"])
```

Run the dashboard UI:
```bash
uv run streamlit run frontend.py
```

### Switching Models
Edit your environment instead of the code:
```env
OPENROUTER_MODEL=openai/gpt-4.1-mini
```
or
```env
OPENROUTER_MODEL=deepseek/deepseek-v4-flash
```

### SQL Safety
The app now validates generated SQL before execution:
- Only single `SELECT` statements are allowed
- Multi-statement SQL is blocked
- Keywords like `DROP`, `DELETE`, `UPDATE`, `ALTER`, and `PRAGMA` are blocked

### Dashboard Behavior
The Streamlit app now:
- Renders an automatic chart based on the result shape
- Renders a schema relationship graph with Graphviz
- Preserves recent questions for follow-up context
- Lets you filter categorical columns in the result set
- Exports the result as CSV, Markdown, or JSON
- Shows a heuristic SQL review alongside the generated query

### Visualization Stack
- Data charts: `Plotly`
- Schema relationships: `NetworkX` + `Graphviz`
- Workflow documentation: `Mermaid`
- `Altair` remains available in the environment, but the dashboard now uses `Plotly` for more interactive charts
- `Matplotlib` and `LangGraph` visualization are not enabled by default because the current app does not need them to function well

## Performance Tips
- Use faster OpenRouter models for snappy responses
- Keep `temperature=0` for deterministic output
- Cache schema: avoid recomputing `extract_schema` each call
- Use Tavily enrichment only when needed, since it adds latency

## Troubleshooting
| Issue | Cause | Fix |
|-------|-------|-----|
| Long response time | Model latency or web enrichment enabled | Switch to a faster model or disable Tavily enrichment |
| SQL errors (no such column) | Model hallucinated | Strengthen prompt, show schema clearly |
| Empty results | Query valid but data missing | Inspect `amazon.db` contents |
| OpenRouter authentication error | Invalid or missing key | Check `OPENROUTER_API_KEY` |
| Tavily request failed | Invalid key or network issue | Disable Tavily or check `TAVILY_API_KEY` |

## Limitations
- **Chart Plotting Limitations**: The automatic chart generator might not render or display plots correctly for complex, nested, or heavily grouped query result profiles.
- **SQL Parser Constraints**: The safety validation uses a state-machine scanner that blocklist keywords to prevent writes; highly custom or non-standard queries might trigger false positives.

## Roadmap / Ideas
- Add a lightweight caching layer for repeated schema reads and common questions
- Add true drill-down interactions that regenerate SQL from chart selections
- Add tests (unit test for SQL validation + schema extraction)
- Add bundled drivers for Postgres and DuckDB

## Security Notes
Executing arbitrary LLM-generated SQL can be risky. Restrict to read-only queries and sanitize user inputs if you later interpolate values.

## Contributing
1. Fork & branch
2. Make changes
3. Run `uv sync && uv run python -m py_compile main.py`
4. Submit PR

## License
MIT (adjust in `pyproject.toml` if you choose a different one)

---
Built with local AI + fast Python tooling.
