import pandas as pd
import plotly.express as px
import streamlit as st

from main import analyze_question

st.set_page_config(page_title="Data Seeker", page_icon="📊", layout="wide")


def initialize_state() -> None:
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("database_url", "sqlite:///amazon.db")


def to_dataframe(result: dict) -> pd.DataFrame:
    return pd.DataFrame(result["rows"], columns=result["columns"])


def apply_filters(dataframe: pd.DataFrame, profile: dict) -> pd.DataFrame:
    filtered_df = dataframe.copy()
    with st.sidebar:
        st.subheader("Result filters")
        for column in profile.get("categorical_columns", [])[:3]:
            unique_values = [value for value in filtered_df[column].dropna().unique().tolist() if value != ""]
            if 1 < len(unique_values) <= 20:
                selected_values = st.multiselect(f"Filter {column}", unique_values, default=unique_values)
                if selected_values:
                    filtered_df = filtered_df[filtered_df[column].isin(selected_values)]
    return filtered_df


def render_metric_block(dataframe: pd.DataFrame, visual_spec: dict) -> None:
    metric_value = dataframe.iloc[0][visual_spec["y"]] if not dataframe.empty else None
    st.metric(visual_spec["title"], metric_value)


def render_chart(dataframe: pd.DataFrame, visual_spec: dict | None) -> None:
    if dataframe.empty:
        st.info("No data available for charting.")
        return

    if not visual_spec:
        st.dataframe(dataframe, use_container_width=True)
        return

    chart_type = visual_spec.get("chart_type")
    if chart_type == "metric":
        render_metric_block(dataframe, visual_spec)
        return

    if chart_type == "table":
        st.dataframe(dataframe, use_container_width=True)
        return

    x_col = visual_spec.get("x")
    y_col = visual_spec.get("y")
    color_col = visual_spec.get("color")

    # Check if y_col is a list or single string, ensuring existence in dataframe
    if isinstance(y_col, list):
        y_exists = all(col in dataframe.columns for col in y_col)
    else:
        y_exists = y_col in dataframe.columns

    if x_col and x_col in dataframe.columns and y_col and y_exists:
        chart_df = dataframe.copy()
        figure = None
        if chart_type == "line":
            figure = px.line(
                chart_df,
                x=x_col,
                y=y_col,
                markers=True,
                title=visual_spec.get("title"),
            )
        elif chart_type == "bar":
            figure = px.bar(
                chart_df,
                x=x_col,
                y=y_col,
                color=color_col if color_col and color_col in chart_df.columns else None,
                title=visual_spec.get("title"),
            )
        elif chart_type == "scatter":
            figure = px.scatter(
                chart_df,
                x=x_col,
                y=y_col,
                color=color_col if color_col and color_col in chart_df.columns else None,
                title=visual_spec.get("title"),
            )

        if figure is not None:
            figure.update_layout(
                height=460,
                margin=dict(l=16, r=16, t=56, b=16),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            figure.update_traces(
                hovertemplate=None,
            )
            st.plotly_chart(figure, use_container_width=True)
            return

    st.dataframe(dataframe, use_container_width=True)


def render_history() -> None:
    if not st.session_state["history"]:
        return
    with st.expander("Recent question history", expanded=False):
        for item in reversed(st.session_state["history"][-5:]):
            st.markdown(f"- **{item['question']}**")


initialize_state()

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .ds-hero {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 55%, #312e81 100%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 24px;
        padding: 28px 28px 22px 28px;
        color: #f8fafc;
        box-shadow: 0 20px 60px rgba(15, 23, 42, 0.35);
        margin-bottom: 1rem;
    }
    .ds-kicker {
        letter-spacing: 0.18em;
        text-transform: uppercase;
        font-size: 0.75rem;
        opacity: 0.75;
    }
    .ds-title {
        font-size: 2.4rem;
        font-weight: 700;
        margin: 0.4rem 0 0.6rem 0;
    }
    .ds-copy {
        font-size: 1rem;
        max-width: 820px;
        opacity: 0.92;
    }
    </style>
    <div class="ds-hero">
        <div class="ds-kicker">Data analysis workspace</div>
        <div class="ds-title">Data Seeker</div>
        <div class="ds-copy">Ask a question in plain English. Data Seeker turns it into SQL, reviews the query, runs it against your database, builds a chart-ready result profile, and rewrites the answer like a senior analyst.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Workspace")
    st.session_state["database_url"] = st.text_input("Database URL", value=st.session_state["database_url"])
    if st.button("Refresh Cached Schema", use_container_width=True):
        from services.database import clear_schema_cache
        clear_schema_cache(st.session_state["database_url"])
        st.toast("Schema cache cleared!", icon="🧹")
    st.caption("Works best with SQLite now. Other SQLAlchemy-supported databases can be used if the required driver is installed.")
    st.subheader("Suggested questions")
    st.markdown("- Top products by revenue")
    st.markdown("- Orders by month")
    st.markdown("- Explain the database structure")
    st.markdown("- Customers by city")

query_col, action_col = st.columns([5, 1])
with query_col:
    user_query = st.text_area(
        "Ask a data question",
        placeholder="e.g., Which product categories generated the highest revenue, and how should I visualize it?",
        height=140,
    )
with action_col:
    st.write("")
    st.write("")
    run_analysis = st.button("Analyze", type="primary", use_container_width=True)

render_history()

if run_analysis:
    if user_query.strip() == "":
        st.warning("Please enter a question to analyze.")
    else:
        try:
            recent_context = st.session_state["history"][-3:]
            with st.spinner("Generating SQL, running the query, and preparing the analyst brief..."):
                result = analyze_question(
                    user_query,
                    conversation_context=recent_context,
                    database_url=st.session_state["database_url"],
                )
            st.session_state["last_result"] = result
            st.session_state["history"].append(
                {
                    "question": result["question"],
                    "sql_query": result["sql_query"],
                    "columns": result["columns"],
                    "row_count": result["row_count"],
                }
            )
            st.success("Analysis complete.")
        except Exception as exc:
            st.error(f"Request failed: {exc}")

result = st.session_state.get("last_result")
if result:
    dataframe = to_dataframe(result)
    filtered_df = apply_filters(dataframe, result["data_profile"])

    analyst_tab, dashboard_tab, data_tab, schema_tab, review_tab, export_tab, sql_tab = st.tabs(
        ["Analyst brief", "Dashboard", "Data", "Schema graph", "SQL review", "Exports", "SQL"]
    )

    with analyst_tab:
        stats_col1, stats_col2, stats_col3 = st.columns(3)
        stats_col1.metric("Rows returned", result["row_count"])
        stats_col2.metric("Columns", len(result["columns"]))
        stats_col3.metric("Chart mode", result["visual_spec"]["chart_type"] if result.get("visual_spec") else "table")
        st.markdown(result["answer_markdown"])

    with dashboard_tab:
        st.subheader(result["visual_spec"]["title"] if result.get("visual_spec") else "Recommended view")
        if result.get("visual_spec"):
            st.caption(result["visual_spec"]["reason"])
        render_chart(filtered_df, result.get("visual_spec"))
        st.divider()
        st.subheader("Recommended follow-up visuals")
        for idea in result["chart_ideas"]:
            st.markdown(f"- {idea}")

    with data_tab:
        st.subheader("Filtered result")
        st.dataframe(filtered_df, use_container_width=True)
        if filtered_df.empty:
            st.info("The current filters removed all rows.")

    with schema_tab:
        st.subheader("Database relationship graph")
        schema_graph = result.get("schema_graph", {})
        if schema_graph.get("dot"):
            st.graphviz_chart(schema_graph["dot"], use_container_width=True)
        else:
            st.info("No schema relationship graph is available for this database.")
        if schema_graph.get("edges"):
            st.markdown("**Detected relationships**")
            for edge in schema_graph["edges"]:
                st.markdown(f"- `{edge['source']}` -> `{edge['target']}` via `{edge['label']}`")

    with review_tab:
        review = result["sql_review"]
        if review["approved"]:
            st.success("The SQL review passed the heuristic quality checks.")
        else:
            st.warning("The SQL is safe, but the review found possible quality gaps.")

        review_col1, review_col2 = st.columns(2)
        with review_col1:
            st.markdown("**Strengths**")
            for item in review["strengths"]:
                st.markdown(f"- {item}")
        with review_col2:
            st.markdown("**Potential issues**")
            if review["issues"]:
                for item in review["issues"]:
                    st.markdown(f"- {item}")
            else:
                st.markdown("- No major issues detected.")

        st.markdown("**Detected intent**")
        st.json(review["inferred_intent"])

    with export_tab:
        st.subheader("Download results")
        st.download_button(
            "Download CSV",
            data=result["exports"]["csv"],
            file_name="data_seeker_results.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download Markdown brief",
            data=result["exports"]["markdown"],
            file_name="data_seeker_brief.md",
            mime="text/markdown",
        )
        st.download_button(
            "Download JSON payload",
            data=result["exports"]["json"],
            file_name="data_seeker_result.json",
            mime="application/json",
        )

    with sql_tab:
        st.code(result["sql_query"], language="sql")
        if result["schema_summary"]:
            st.markdown("**Schema summary used for reasoning**")
            for line in result["schema_summary"]:
                st.markdown(f"- {line}")
