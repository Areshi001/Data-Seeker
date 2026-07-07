from __future__ import annotations


def clean_sql_response(raw_response: str) -> str:
    # Strip markdown code fences
    cleaned_response = raw_response.replace("```sql", "").replace("```", "").strip()

    # Strip closed <think>...</think> blocks (DeepSeek reasoning models)
    if "<think>" in cleaned_response and "</think>" in cleaned_response:
        start = cleaned_response.find("<think>")
        end = cleaned_response.find("</think>") + len("</think>")
        cleaned_response = (cleaned_response[:start] + cleaned_response[end:]).strip()

    # Strip unclosed <think>...</think> — model started reasoning but didn't close it
    elif "<think>" in cleaned_response:
        start = cleaned_response.find("<think>")
        cleaned_response = cleaned_response[:start].strip()

    # If the response still doesn't start with SELECT, the model probably prepended
    # explanatory text (e.g. "Here is the query:\nSELECT ..."). Find the first SELECT.
    if not cleaned_response.lower().lstrip().startswith("select"):
        idx = cleaned_response.lower().find("select")
        if idx != -1:
            cleaned_response = cleaned_response[idx:].strip()

    return cleaned_response



import re

def parse_and_sanitize_sql(sql: str) -> tuple[str, str]:
    """
    Scans SQL query character-by-character.
    Returns:
        clean_sql: SQL with comments removed.
        token_sql: SQL with comments removed and strings replaced by placeholders.
    """
    state = "NORMAL"
    clean_chars = []
    token_chars = []
    i = 0
    n = len(sql)
    
    while i < n:
        c = sql[i]
        next_c = sql[i+1] if i + 1 < n else ""
        
        if state == "NORMAL":
            if c == "-" and next_c == "-":
                state = "LINE_COMMENT"
                i += 2
                continue
            elif c == "/" and next_c == "*":
                state = "BLOCK_COMMENT"
                i += 2
                continue
            elif c == "'":
                state = "STRING_SINGLE"
                clean_chars.append(c)
                token_chars.append(c)
                i += 1
                continue
            elif c == '"':
                state = "STRING_DOUBLE"
                clean_chars.append(c)
                token_chars.append(c)
                i += 1
                continue
            elif c == "`":
                state = "BACKTICK"
                clean_chars.append(c)
                token_chars.append(c)
                i += 1
                continue
            else:
                clean_chars.append(c)
                token_chars.append(c)
                i += 1
                continue
                
        elif state == "LINE_COMMENT":
            if c == "\n":
                state = "NORMAL"
                clean_chars.append("\n")
                token_chars.append("\n")
            i += 1
            continue
            
        elif state == "BLOCK_COMMENT":
            if c == "*" and next_c == "/":
                state = "NORMAL"
                i += 2
            else:
                i += 1
            continue
            
        elif state == "STRING_SINGLE":
            if c == "\\" and next_c == "'":
                clean_chars.append("\\'")
                i += 2
                continue
            elif c == "'" and next_c == "'":
                clean_chars.append("''")
                i += 2
                continue
            elif c == "'":
                state = "NORMAL"
                clean_chars.append(c)
                token_chars.append(c)
                i += 1
                continue
            else:
                clean_chars.append(c)
                i += 1
                continue
                
        elif state == "STRING_DOUBLE":
            if c == "\\" and next_c == '"':
                clean_chars.append('\\"')
                i += 2
                continue
            elif c == '"' and next_c == '"':
                clean_chars.append('""')
                i += 2
                continue
            elif c == '"':
                state = "NORMAL"
                clean_chars.append(c)
                token_chars.append(c)
                i += 1
                continue
            else:
                clean_chars.append(c)
                i += 1
                continue
                
        elif state == "BACKTICK":
            if c == "`" and next_c == "`":
                clean_chars.append("``")
                i += 2
                continue
            elif c == "`":
                state = "NORMAL"
                clean_chars.append(c)
                token_chars.append(c)
                i += 1
                continue
            else:
                clean_chars.append(c)
                i += 1
                continue
                
    if state == "STRING_SINGLE":
        clean_chars.append("'")
        token_chars.append("'")
    elif state == "STRING_DOUBLE":
        clean_chars.append('"')
        token_chars.append('"')
    elif state == "BACKTICK":
        clean_chars.append("`")
        token_chars.append("`")
        
    return "".join(clean_chars), "".join(token_chars)


def validate_sql_query(sql_query: str) -> str:
    clean_sql, token_sql = parse_and_sanitize_sql(sql_query)
    
    normalized = clean_sql.strip().rstrip(";")
    lowered = normalized.lower()

    if not lowered.startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")

    blocked_keywords = [
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "pragma",
        "attach",
        "detach",
        "create",
        "replace",
        "truncate",
        "grant",
        "revoke",
        "exec",
        "execute"
    ]
    
    token_lowered = token_sql.lower()
    for keyword in blocked_keywords:
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, token_lowered):
            raise ValueError(f"Unsafe SQL detected. The keyword '{keyword}' is not allowed.")

    if ";" in normalized:
        raise ValueError("Multiple SQL statements are not allowed.")

    return normalized

