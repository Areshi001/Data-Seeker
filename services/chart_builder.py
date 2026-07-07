from __future__ import annotations

from typing import Any

import pandas as pd

from services.types import ChartSpec, DataProfile


def _safe_datetime(series: pd.Series) -> pd.Series | None:
    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
        return None
    try:
        converted = pd.to_datetime(series.astype(str), errors="coerce", format="mixed")
        valid_ratio = converted.notna().mean() if len(series) else 0
        if valid_ratio >= 0.7:
            return converted
    except Exception:
        return None
    return None


def build_dataframe(columns: list[str], rows: list[list[Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns)


def profile_dataframe(dataframe: pd.DataFrame) -> DataProfile:
    df = dataframe.copy()
    numeric_columns: list[str] = []
    categorical_columns: list[str] = []
    datetime_columns: list[str] = []

    for column in df.columns:
        series = df[column]
        numeric_series = pd.to_numeric(series, errors="coerce")
        if numeric_series.notna().mean() >= 0.9 and numeric_series.notna().sum() > 0:
            df[column] = numeric_series
            numeric_columns.append(column)
            continue

        datetime_series = _safe_datetime(series)
        if datetime_series is not None:
            df[column] = datetime_series
            datetime_columns.append(column)
            continue

        categorical_columns.append(column)

    metric_columns = numeric_columns[:]
    dimension_columns = [*datetime_columns, *categorical_columns]

    return DataProfile(
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        datetime_columns=datetime_columns,
        metric_columns=metric_columns,
        dimension_columns=dimension_columns,
        row_count=len(df),
        column_count=len(df.columns),
    )


def suggest_chart_ideas(profile: DataProfile, columns: list[str], row_count: int) -> list[str]:
    if row_count == 0:
        return ["No chart recommendation because the result set is empty."]

    ideas: list[str] = []
    if profile.datetime_columns and profile.numeric_columns:
        ideas.append(f"Line chart: plot `{profile.numeric_columns[0]}` over `{profile.datetime_columns[0]}` to show trend.")
    if profile.categorical_columns and profile.numeric_columns:
        ideas.append(f"Bar chart: compare `{profile.numeric_columns[0]}` by `{profile.categorical_columns[0]}`.")
    if len(profile.numeric_columns) >= 2:
        ideas.append(f"Scatter plot: compare `{profile.numeric_columns[0]}` against `{profile.numeric_columns[1]}`.")
    if len(columns) == 1 and profile.numeric_columns:
        ideas.append(f"KPI card: emphasize `{columns[0]}` as a headline metric.")
    if not ideas:
        ideas.append("Table view: the result is best understood as a structured table.")
    return ideas[:4]


def _sort_metrics_deterministically(numeric_columns: list[str]) -> list[str]:
    # Prioritize columns with metric-like names (case-insensitive)
    metric_keywords = ["revenue", "sales", "amount", "total", "quantity", "count", "price", "sum", "subtotal"]
    
    def score_column(col: str) -> int:
        col_lower = col.lower()
        for idx, kw in enumerate(metric_keywords):
            if kw in col_lower:
                return idx  # lower score = higher priority
        return len(metric_keywords)  # default low priority
        
    return sorted(numeric_columns, key=score_column)


def _pick_color_dimension(
    profile: DataProfile,
    dataframe: pd.DataFrame | None,
    exclude_col: str | None = None,
    max_cardinality: int = 20,
) -> str | None:
    """
    Picks the best low-cardinality categorical column to use as a Plotly
    color/grouping dimension (e.g. product_name, category).
    Excludes the column already used as the x-axis.
    Returns None if no suitable column is found.
    """
    candidates = [c for c in profile.categorical_columns if c != exclude_col]
    if not candidates:
        return None
    if dataframe is not None:
        # Pick the candidate with fewest unique values that is still > 1
        def cardinality(col: str) -> int:
            if col in dataframe.columns:
                n = dataframe[col].nunique()
                return n if 1 < n <= max_cardinality else 9999
            return 9999
        best = min(candidates, key=cardinality)
        if cardinality(best) == 9999:
            return None
        return best
    # No dataframe available: just pick first candidate
    return candidates[0]


def build_visual_spec(
    profile: DataProfile,
    columns: list[str],
    row_count: int,
    dataframe: pd.DataFrame | None = None,
) -> ChartSpec | None:
    if row_count == 0:
        return None

    # Sort numeric columns deterministically
    sorted_nums = _sort_metrics_deterministically(profile.numeric_columns)

    if len(columns) == 1 and sorted_nums:
        return ChartSpec(
            chart_type="metric",
            title=f"Headline metric: {columns[0]}",
            reason="The result returns a single numeric value, so a KPI card is the clearest display.",
            y=columns[0],
        )

    if profile.datetime_columns and sorted_nums:
        x_col = profile.datetime_columns[0]
        # When there are multiple categorical columns alongside a time axis,
        # use the best low-cardinality one as the color/grouping dimension
        # instead of plotting confusing multi-line per row.
        color_col = _pick_color_dimension(profile, dataframe, exclude_col=x_col)
        if color_col:
            # Group-by colour: use a single primary metric on y
            y_val = sorted_nums[0]
            y_label = sorted_nums[0]
            reason = (
                f"Time trend split by '{color_col}' — each series is one {color_col} value."
            )
        else:
            # No grouping column: multi-metric on y
            y_selection = sorted_nums[:3]
            y_val = y_selection if len(y_selection) > 1 else y_selection[0]
            y_label = ", ".join(y_selection) if isinstance(y_val, list) else y_val
            reason = "A time field and one or more numeric metrics are present, showing trends over time."
        return ChartSpec(
            chart_type="line",
            title=f"{y_label} over {x_col}",
            reason=reason,
            x=x_col,
            y=y_val,
            color=color_col,
        )

    if profile.categorical_columns and sorted_nums:
        x_col = profile.categorical_columns[0]
        color_col = _pick_color_dimension(profile, dataframe, exclude_col=x_col)
        y_selection = sorted_nums[:3]
        y_val = y_selection if len(y_selection) > 1 and not color_col else sorted_nums[0]
        y_label = ", ".join(y_selection) if isinstance(y_val, list) else sorted_nums[0]
        reason = (
            f"Categorical comparison grouped by '{color_col}'." if color_col
            else "A categorical dimension and one or more numeric metrics are present, comparing results."
        )
        return ChartSpec(
            chart_type="bar",
            title=f"{y_label} by {x_col}",
            reason=reason,
            x=x_col,
            y=y_val,
            color=color_col,
        )

    if len(sorted_nums) >= 2:
        return ChartSpec(
            chart_type="scatter",
            title=f"{sorted_nums[0]} vs {sorted_nums[1]}",
            reason="Two numeric measures are present, so a scatter plot can reveal correlation or clustering.",
            x=sorted_nums[0],
            y=sorted_nums[1],
        )

    return ChartSpec(
        chart_type="table",
        title="Structured result table",
        reason="The result shape is mixed or non-numeric, so a table is the safest default view.",
    )
