"""Safety checks. The AI must never be allowed to change or delete data."""
import re

FORBIDDEN_WORDS = [
    "insert", "update", "delete", "drop", "alter", "create",
    "replace", "truncate", "attach", "detach", "pragma", "vacuum",
]


def clean_sql(text):
    """The AI sometimes wraps SQL in ```sql ... ```. Remove that."""
    text = text.strip()
    text = re.sub(r"^```(?:sql)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def is_safe_sql(sql):
    """Return (True, "") if the query is a single read-only SELECT, else (False, reason)."""
    sql = sql.strip().rstrip(";").strip()

    if not sql:
        return False, "Empty query"
    if ";" in sql:
        return False, "Only one query is allowed"
    if not sql.lower().startswith("select"):
        return False, "Only SELECT queries are allowed"
    for word in FORBIDDEN_WORDS:
        if re.search(rf"\b{word}\b", sql, flags=re.IGNORECASE):
            return False, f"Forbidden word: {word}"
    return True, ""
