import logging
import re

import pandas as pd

logger = logging.getLogger("cortexbi.security.pii_detector")

PII_COLUMN_PATTERNS = [
    r".*email.*", r".*e_mail.*", r".*ssn.*", r".*social.*security.*",
    r".*phone.*", r".*mobile.*", r".*address.*", r".*zip.*code.*",
    r".*credit.*card.*", r".*passport.*", r".*driver.*license.*",
    r".*dob.*", r".*date.*birth.*", r".*first.*name.*", r".*last.*name.*",
    r".*full.*name.*", r".*surname.*",
]

CONTENT_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "ssn": re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
    "phone": re.compile(r"(?:\+1[-.\s]?)?\(?\d{3}\)[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"),
    "credit_card": re.compile(r"(?<!\d)\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)"),
}

PII_MATCH_THRESHOLD = 0.10


def detect_pii(df: pd.DataFrame) -> dict:
    pii_columns: list[dict] = []

    for col in df.columns:
        col_lower = str(col).lower().replace(" ", "_")
        for pattern in PII_COLUMN_PATTERNS:
            if re.match(pattern, col_lower):
                pii_columns.append({
                    "column": col,
                    "type": "column_name_match",
                    "pattern": pattern,
                    "confidence": 0.8,
                })
                break

    for col in df.select_dtypes(include=["object", "string"]).columns:
        if any(p["column"] == col for p in pii_columns):
            continue

        sample = df[col].dropna().head(100)
        if len(sample) == 0:
            continue

        for pii_type, regex in CONTENT_PATTERNS.items():
            matches = sample.astype(str).str.contains(regex, na=False).sum()
            match_ratio = matches / len(sample)
            if match_ratio >= PII_MATCH_THRESHOLD:
                pii_columns.append({
                    "column": col,
                    "type": pii_type,
                    "match_ratio": round(match_ratio, 3),
                    "confidence": min(0.95, match_ratio + 0.3),
                })
                break

    has_pii = len(pii_columns) > 0
    if has_pii:
        logger.warning("PII detected in %d columns", len(pii_columns))

    return {
        "has_pii": has_pii,
        "pii_columns": pii_columns,
        "columns_scanned": len(df.columns),
    }
