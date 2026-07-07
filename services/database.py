from __future__ import annotations

import json
import html
import threading
from typing import Any

import networkx as nx
from sqlalchemy import create_engine, inspect, text

from services.config import DEFAULT_DATABASE_URL


# Thread-safe caching mechanism for schema structures
_CACHE_LOCK = threading.Lock()
_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}
MAX_CACHE_SIZE = 50


def clear_schema_cache(database_url: str | None = None) -> None:
    """
    Clears the cached schema mapping and graph data.
    If database_url is provided, evicts that specific url, otherwise clears everything.
    """
    with _CACHE_LOCK:
        if database_url:
            _SCHEMA_CACHE.pop(database_url, None)
        else:
            _SCHEMA_CACHE.clear()


class DatabaseAdapter:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url)

    def extract_schema_map(self) -> dict[str, Any]:
        with _CACHE_LOCK:
            if self.database_url in _SCHEMA_CACHE and "map" in _SCHEMA_CACHE[self.database_url]:
                return _SCHEMA_CACHE[self.database_url]["map"]

        inspector = inspect(self.engine)
        schema: dict[str, Any] = {}

        for table_name in inspector.get_table_names():
            if table_name.startswith("sqlite_"):
                continue

            columns = inspector.get_columns(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            # Identify columns acting as foreign keys
            fk_cols = set()
            for fk in foreign_keys:
                for col_name in fk.get("constrained_columns", []):
                    fk_cols.add(col_name)

            schema[table_name] = {
                "columns": [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col.get("nullable", True),
                        "primary_key": bool(col.get("primary_key", False)),
                        "foreign_key": col["name"] in fk_cols,
                    }
                    for col in columns
                ],
                "foreign_keys": [
                    {
                        "constrained_columns": fk.get("constrained_columns", []),
                        "referred_table": fk.get("referred_table"),
                        "referred_columns": fk.get("referred_columns", []),
                    }
                    for fk in foreign_keys
                ],
            }

        with _CACHE_LOCK:
            # Prevent memory leaks with cache size capping
            if len(_SCHEMA_CACHE) >= MAX_CACHE_SIZE and self.database_url not in _SCHEMA_CACHE:
                oldest_key = next(iter(_SCHEMA_CACHE))
                _SCHEMA_CACHE.pop(oldest_key, None)
            if self.database_url not in _SCHEMA_CACHE:
                _SCHEMA_CACHE[self.database_url] = {}
            _SCHEMA_CACHE[self.database_url]["map"] = schema

        return schema

    def extract_schema_text(self) -> str:
        with _CACHE_LOCK:
            if self.database_url in _SCHEMA_CACHE and "text" in _SCHEMA_CACHE[self.database_url]:
                return _SCHEMA_CACHE[self.database_url]["text"]

        schema_text = json.dumps(self.extract_schema_map(), indent=2)
        with _CACHE_LOCK:
            if self.database_url not in _SCHEMA_CACHE:
                _SCHEMA_CACHE[self.database_url] = {}
            _SCHEMA_CACHE[self.database_url]["text"] = schema_text
        return schema_text

    def schema_summary(self) -> list[str]:
        with _CACHE_LOCK:
            if self.database_url in _SCHEMA_CACHE and "summary" in _SCHEMA_CACHE[self.database_url]:
                return _SCHEMA_CACHE[self.database_url]["summary"]

        schema = self.extract_schema_map()
        summary = []
        for table_name, details in schema.items():
            column_names = [col["name"] for col in details["columns"]]
            fk_targets = [fk["referred_table"] for fk in details["foreign_keys"] if fk.get("referred_table")]
            relation_text = f" -> related to {', '.join(fk_targets)}" if fk_targets else ""
            summary.append(f"{table_name}: {', '.join(column_names)}{relation_text}")

        with _CACHE_LOCK:
            if self.database_url not in _SCHEMA_CACHE:
                _SCHEMA_CACHE[self.database_url] = {}
            _SCHEMA_CACHE[self.database_url]["summary"] = summary
        return summary

    def schema_graph_data(self) -> dict[str, Any]:
        with _CACHE_LOCK:
            if self.database_url in _SCHEMA_CACHE and "graph" in _SCHEMA_CACHE[self.database_url]:
                return _SCHEMA_CACHE[self.database_url]["graph"]

        schema = self.extract_schema_map()
        graph = nx.DiGraph()

        for table_name, details in schema.items():
            graph.add_node(table_name)
            for fk in details["foreign_keys"]:
                referred_table = fk.get("referred_table")
                if referred_table:
                    constrained = fk.get("constrained_columns", [])
                    referred = fk.get("referred_columns", [])
                    label = ""
                    source_col = ""
                    target_col = ""
                    if constrained and referred:
                        label = f"{constrained[0]} -> {referred[0]}"
                        source_col = constrained[0]
                        target_col = referred[0]
                    else:
                        label = "fk"
                    
                    graph.add_edge(
                        table_name,
                        referred_table,
                        label=label,
                        source_col=source_col,
                        target_col=target_col
                    )

        dot_lines = [
            "digraph Schema {",
            '  rankdir="LR";',
            '  graph [bgcolor="transparent", pad="0.5", nodesep="0.4", ranksep="0.7"];',
            '  node [shape="none", fontname="Helvetica", fontsize="11"];',
            '  edge [color="#6366f1", fontname="Helvetica", fontsize="9", labelfontsize="9"];',
        ]

        for node_name in graph.nodes:
            details = schema.get(node_name)
            if not details:
                dot_lines.append(f'  "{node_name}" [label="{node_name}", shape="box"];')
                continue

            rows_html = []
            escaped_node = html.escape(node_name)
            rows_html.append(
                f'<tr><td bgcolor="#4338ca" align="center" cellpadding="6" port="_header"><font color="#ffffff"><b>{escaped_node}</b></font></td></tr>'
            )

            for col in details["columns"]:
                name = col["name"]
                col_type = col["type"]
                pk_fk = ""
                if col.get("primary_key"):
                    pk_fk = ' <font color="#b45309"><b>[PK]</b></font>'
                elif col.get("foreign_key"):
                    pk_fk = ' <font color="#4f46e5"><b>[FK]</b></font>'

                escaped_name = html.escape(name)
                escaped_type = html.escape(col_type)

                rows_html.append(
                    f'<tr><td align="left" bgcolor="#ffffff" cellpadding="4" port="{escaped_name}"><font color="#1e293b">  {escaped_name} </font><font color="#64748b">({escaped_type})</font>{pk_fk}</td></tr>'
                )

            table_label = f'<<table border="0" cellborder="1" cellspacing="0" style="border-collapse: collapse;">{"".join(rows_html)}</table>>'
            dot_lines.append(f'  "{node_name}" [label={table_label}];')

        for source, target, attributes in graph.edges(data=True):
            source_col = attributes.get("source_col", "")
            target_col = attributes.get("target_col", "")
            label = attributes.get("label", "")
            
            # Connect column-to-column if ports are identified
            if source_col and target_col:
                dot_lines.append(f'  "{source}":"{source_col}" -> "{target}":"{target_col}" [label=" {label}"];')
            else:
                dot_lines.append(f'  "{source}" -> "{target}" [label=" {label}"];')

        dot_lines.append("}")

        graph_result = {
            "nodes": list(graph.nodes),
            "edges": [
                {
                    "source": source,
                    "target": target,
                    "label": attributes.get("label", ""),
                    "source_col": attributes.get("source_col", ""),
                    "target_col": attributes.get("target_col", "")
                }
                for source, target, attributes in graph.edges(data=True)
            ],
            "dot": "\n".join(dot_lines),
        }

        with _CACHE_LOCK:
            if self.database_url not in _SCHEMA_CACHE:
                _SCHEMA_CACHE[self.database_url] = {}
            _SCHEMA_CACHE[self.database_url]["graph"] = graph_result
        return graph_result

    def execute_sql(self, sql_query: str) -> tuple[list[str], list[list[Any]]]:
        with self.engine.connect() as connection:
            result = connection.execute(text(sql_query))
            rows = result.fetchall()
            columns = list(result.keys())
        normalized_rows = [list(row) for row in rows]
        return columns, normalized_rows


def get_database_adapter(database_url: str | None = None) -> DatabaseAdapter:
    return DatabaseAdapter(database_url or DEFAULT_DATABASE_URL)
