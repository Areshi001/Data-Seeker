from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SQLReviewResult:
    approved: bool
    issues: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    inferred_intent: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DataProfile:
    numeric_columns: list[str] = field(default_factory=list)
    categorical_columns: list[str] = field(default_factory=list)
    datetime_columns: list[str] = field(default_factory=list)
    metric_columns: list[str] = field(default_factory=list)
    dimension_columns: list[str] = field(default_factory=list)
    row_count: int = 0
    column_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChartSpec:
    chart_type: str
    title: str
    reason: str
    x: str | None = None
    y: str | None = None
    color: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QueryResult:
    question: str
    sql_query: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    answer_markdown: str
    chart_ideas: list[str]
    sql_review: SQLReviewResult
    data_profile: DataProfile
    visual_spec: ChartSpec | None = None
    schema_summary: list[str] = field(default_factory=list)
    schema_graph: dict[str, Any] = field(default_factory=dict)
    follow_up_context: str = ""
    exports: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.visual_spec:
            payload["visual_spec"] = self.visual_spec.to_dict()
        payload["sql_review"] = self.sql_review.to_dict()
        payload["data_profile"] = self.data_profile.to_dict()
        return payload
