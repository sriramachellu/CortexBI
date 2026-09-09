import logging

import pandas as pd

logger = logging.getLogger("cortexbi.security.csv_injection")

INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "|")


def check_csv_injection(df: pd.DataFrame) -> dict:
    affected_columns: list[str] = []
    affected_cells = 0

    for col in df.select_dtypes(include=["object", "string"]).columns:
        for value in df[col].dropna():
            str_val = str(value).strip()
            if not str_val or str_val[0] not in INJECTION_PREFIXES:
                continue
            if str_val[0] == "-":
                try:
                    float(str_val)
                    continue
                except ValueError:
                    pass
            if str_val[0] == "+" and len(str_val) > 1 and str_val[1:].replace(" ", "").isdigit():
                continue
            if col not in affected_columns:
                affected_columns.append(col)
            affected_cells += 1

    if affected_columns:
        logger.warning(
            "CSV injection in %d columns, %d cells", len(affected_columns), affected_cells
        )
        return {
            "safe": False,
            "columns": affected_columns,
            "affected_cells": affected_cells,
        }

    logger.info("CSV injection check passed")
    return {"safe": True, "columns": [], "affected_cells": 0}


def sanitize_csv_injection(df: pd.DataFrame) -> pd.DataFrame:
    df_clean = df.copy()
    for col in df_clean.select_dtypes(include=["object", "string"]).columns:
        mask = df_clean[col].astype(str).str.match(r"^[=+\-@\t\r|]")
        df_clean.loc[mask, col] = "'" + df_clean.loc[mask, col].astype(str)
    return df_clean
