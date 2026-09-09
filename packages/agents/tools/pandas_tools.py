import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("cortexbi.agents.tools.pandas")


def clean_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    before = len(df)
    df_clean = df.drop_duplicates()
    dropped = before - len(df_clean)
    return df_clean, {"duplicates_found": dropped, "rows_after": len(df_clean)}


def detect_missing_values(df: pd.DataFrame) -> dict:
    missing = df.isnull().sum()
    total = len(df)
    return {
        col: {"count": int(missing[col]), "pct": round(missing[col] / total * 100, 2)}
        for col in df.columns
        if missing[col] > 0
    }


def infer_datetime_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    converted = []
    df_out = df.copy()
    for col in df_out.select_dtypes(include=["object", "string"]).columns:
        sample = df_out[col].dropna().head(20)
        if len(sample) == 0:
            continue
        try:
            parsed = pd.to_datetime(sample, format="mixed")
            if parsed.notna().sum() >= len(sample) * 0.8:
                df_out[col] = pd.to_datetime(df_out[col], errors="coerce")
                converted.append(col)
        except (ValueError, TypeError):
            continue
    return df_out, converted


def compute_column_profiles(df: pd.DataFrame) -> list[dict]:
    profiles = []
    for col in df.columns:
        series = df[col]
        total = len(series)
        missing = int(series.isnull().sum())
        unique = int(series.nunique())

        profile = {
            "column_name": col,
            "dtype": str(series.dtype),
            "missing_count": missing,
            "missing_pct": round(missing / total * 100, 2) if total > 0 else 0,
            "unique_count": unique,
            "unique_pct": round(unique / total * 100, 2) if total > 0 else 0,
            "is_id_column": unique == total and total > 1,
            "is_datetime": pd.api.types.is_datetime64_any_dtype(series),
            "has_outliers": False,
        }

        profile["mean"] = None
        profile["std"] = None
        profile["min"] = None
        profile["max"] = None
        profile["q25"] = None
        profile["q50"] = None
        profile["q75"] = None

        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            desc = series.describe()
            profile.update({
                "mean": _safe_float(desc.get("mean")),
                "std": _safe_float(desc.get("std")),
                "min": _safe_float(desc.get("min")),
                "max": _safe_float(desc.get("max")),
                "q25": _safe_float(desc.get("25%")),
                "q50": _safe_float(desc.get("50%")),
                "q75": _safe_float(desc.get("75%")),
            })
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                outlier_count = ((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum()
                profile["has_outliers"] = int(outlier_count) > 0

        top = series.value_counts().head(5)
        profile["top_values"] = [
            {"value": str(v), "count": int(c)} for v, c in top.items()
        ]

        profiles.append(profile)
    return profiles


def compute_correlations(df: pd.DataFrame) -> dict:
    numeric = df.select_dtypes(include=["number"]).select_dtypes(exclude=["bool"])
    if numeric.shape[1] < 2:
        return {"matrix": {}, "strong_pairs": []}

    corr = numeric.corr()
    strong = []
    cols = corr.columns.tolist()
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1:]:
            val = corr.loc[c1, c2]
            if abs(val) >= 0.7:
                strong.append({"col1": c1, "col2": c2, "correlation": round(float(val), 3)})

    return {
        "matrix": {c: {r: round(float(corr.loc[c, r]), 3) for r in cols} for c in cols},
        "strong_pairs": strong,
    }


def detect_outliers_iqr(df: pd.DataFrame) -> dict:
    results = {}
    for col in df.select_dtypes(include=["number"]).select_dtypes(exclude=["bool"]).columns:
        q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outliers = df[(df[col] < lower) | (df[col] > upper)]
        if len(outliers) > 0:
            results[col] = {
                "count": len(outliers),
                "pct": round(len(outliers) / len(df) * 100, 2),
                "lower_bound": round(float(lower), 3),
                "upper_bound": round(float(upper), 3),
            }
    return results


def _safe_float(v) -> float | None:
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), 4)
