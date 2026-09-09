import io
import logging

import pandas as pd

from apps.api.config import settings

logger = logging.getLogger("cortexbi.security.file_validator")

BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".sh", ".cmd", ".ps1", ".vbs", ".js",
    ".msi", ".dll", ".com", ".scr", ".pif", ".jar",
}
ALLOWED_EXTENSIONS = {".csv", ".txt"}
ENCODINGS = ["utf-8", "ISO-8859-1", "cp1252"]


def validate_file(content: bytes, filename: str) -> dict:
    max_file_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    max_rows = settings.MAX_UPLOAD_ROWS
    max_columns = settings.MAX_COLUMNS
    min_rows = 10

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in BLOCKED_EXTENSIONS:
        return {"valid": False, "error": f"File type '{ext}' is not allowed"}
    if ext not in ALLOWED_EXTENSIONS:
        return {"valid": False, "error": "Only CSV files are supported"}
    if len(content) == 0:
        return {"valid": False, "error": "File is empty"}
    if len(content) > max_file_size:
        size_mb = len(content) / (1024 * 1024)
        max_mb = max_file_size // (1024 * 1024)
        return {"valid": False, "error": f"File too large ({size_mb:.1f}MB). Max {max_mb}MB"}

    detected_encoding = None
    df = None
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(io.BytesIO(content), encoding=enc, nrows=5)
            detected_encoding = enc
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    if df is None or detected_encoding is None:
        return {"valid": False, "error": "Cannot parse as CSV with any supported encoding"}

    col_count = len(df.columns)
    if col_count > max_columns:
        return {"valid": False, "error": f"Too many columns ({col_count}). Max {max_columns}"}

    total_rows = len(pd.read_csv(io.BytesIO(content), encoding=detected_encoding, usecols=[0]))

    if total_rows > max_rows:
        return {"valid": False, "error": f"Too many rows ({total_rows:,}). Max {max_rows:,}"}
    if total_rows < min_rows:
        return {"valid": False, "error": f"Too few rows ({total_rows}). Min {min_rows}"}

    logger.info(
        "File validation passed: %s (%d bytes, %d rows, encoding=%s)",
        filename, len(content), total_rows, detected_encoding,
    )
    return {
        "valid": True,
        "filename": filename,
        "size_bytes": len(content),
        "row_count": total_rows,
        "column_count": col_count,
        "encoding": detected_encoding,
    }
