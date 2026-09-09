import pandas as pd

from packages.agents.tools.pandas_tools import (
    clean_duplicates,
    compute_column_profiles,
    compute_correlations,
    detect_missing_values,
    detect_outliers_iqr,
    infer_datetime_columns,
)


class TestCleanDuplicates:
    def test_removes_duplicates(self):
        df = pd.DataFrame({"a": [1, 1, 2], "b": [3, 3, 4]})
        cleaned, info = clean_duplicates(df)
        assert info["duplicates_found"] == 1
        assert len(cleaned) == 2

    def test_no_duplicates(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        cleaned, info = clean_duplicates(df)
        assert info["duplicates_found"] == 0


class TestDetectMissingValues:
    def test_finds_missing(self):
        df = pd.DataFrame({"a": [1, None, 3], "b": [4, 5, 6]})
        result = detect_missing_values(df)
        assert "a" in result
        assert result["a"]["count"] == 1
        assert "b" not in result


class TestInferDatetimeColumns:
    def test_converts_dates(self):
        df = pd.DataFrame({"date": ["2024-01-01", "2024-01-02", "2024-01-03"], "val": [1, 2, 3]})
        df_out, converted = infer_datetime_columns(df)
        assert "date" in converted
        assert pd.api.types.is_datetime64_any_dtype(df_out["date"])

    def test_skips_non_dates(self):
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"]})
        df_out, converted = infer_datetime_columns(df)
        assert len(converted) == 0


class TestComputeColumnProfiles:
    def test_profiles_numeric_and_categorical(self):
        df = pd.DataFrame({
            "price": [10.0, 20.0, 30.0, 40.0, 50.0],
            "category": ["A", "B", "A", "C", "B"],
        })
        profiles = compute_column_profiles(df)
        assert len(profiles) == 2

        price_p = next(p for p in profiles if p["column_name"] == "price")
        assert price_p["mean"] is not None
        assert price_p["dtype"].startswith("float")

        cat_p = next(p for p in profiles if p["column_name"] == "category")
        assert cat_p["mean"] is None
        assert len(cat_p["top_values"]) > 0


class TestComputeCorrelations:
    def test_finds_strong_correlation(self):
        df = pd.DataFrame({
            "x": list(range(100)),
            "y": list(range(100)),
            "noise": [i % 7 for i in range(100)],
        })
        result = compute_correlations(df)
        assert len(result["strong_pairs"]) >= 1
        pair = result["strong_pairs"][0]
        assert abs(pair["correlation"]) >= 0.7

    def test_single_numeric_col(self):
        df = pd.DataFrame({"x": [1, 2, 3], "name": ["a", "b", "c"]})
        result = compute_correlations(df)
        assert result["strong_pairs"] == []


class TestDetectOutliersIQR:
    def test_detects_outliers(self):
        df = pd.DataFrame({"val": [1, 2, 3, 4, 5, 100]})
        result = detect_outliers_iqr(df)
        assert "val" in result
        assert result["val"]["count"] >= 1
