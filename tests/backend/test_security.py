import pandas as pd

from packages.security.csv_injection_guard import check_csv_injection, sanitize_csv_injection
from packages.security.file_validator import validate_file
from packages.security.malware_scanner import scan_file
from packages.security.pii_detector import detect_pii


class TestFileValidator:
    def test_valid_csv(self):
        content = b"a,b,c\n" + b"1,2,3\n" * 20
        result = validate_file(content, "test.csv")
        assert result["valid"]
        assert result["column_count"] == 3

    def test_blocked_extension(self):
        result = validate_file(b"data", "virus.exe")
        assert not result["valid"]
        assert "not allowed" in result["error"]

    def test_non_csv_extension(self):
        result = validate_file(b"data", "image.png")
        assert not result["valid"]

    def test_empty_file(self):
        result = validate_file(b"", "test.csv")
        assert not result["valid"]
        assert "empty" in result["error"]

    def test_too_few_rows(self):
        content = b"a,b\n1,2\n3,4\n"
        result = validate_file(content, "test.csv")
        assert not result["valid"]
        assert "few rows" in result["error"]


class TestMalwareScanner:
    def test_clean_csv(self):
        result = scan_file(b"a,b,c\n1,2,3\n", "test.csv")
        assert result["safe"]

    def test_executable_magic_bytes(self):
        result = scan_file(b"MZ" + b"\x00" * 100, "data.csv")
        assert not result["safe"]

    def test_zip_rejected(self):
        result = scan_file(b"PK" + b"\x00" * 100, "data.csv")
        assert not result["safe"]

    def test_script_tag_detected(self):
        result = scan_file(b"a,b\n<script>alert(1)</script>,2\n", "test.csv")
        assert not result["safe"]

    def test_legitimate_text_not_flagged(self):
        content = b"description,price\nThe cmd.exe process runs daily,50\n"
        result = scan_file(content, "test.csv")
        assert result["safe"]


class TestCSVInjectionGuard:
    def test_clean_data(self):
        df = pd.DataFrame({"name": ["Alice", "Bob"], "val": [1, 2]})
        result = check_csv_injection(df)
        assert result["safe"]

    def test_formula_injection(self):
        df = pd.DataFrame({"name": ["=CMD()", "Bob"], "val": [1, 2]})
        result = check_csv_injection(df)
        assert not result["safe"]
        assert "name" in result["columns"]

    def test_negative_numbers_not_flagged(self):
        df = pd.DataFrame({"val": ["-5.5", "-100", "10"]})
        result = check_csv_injection(df)
        assert result["safe"]

    def test_sanitize(self):
        df = pd.DataFrame({"cmd": ["=HYPERLINK()", "safe"]})
        cleaned = sanitize_csv_injection(df)
        assert cleaned["cmd"].iloc[0].startswith("'")


class TestPIIDetector:
    def test_email_detection(self):
        df = pd.DataFrame({
            "user_col": ["alice@example.com", "bob@test.org"] * 10 + ["no-email"] * 5,
        })
        result = detect_pii(df)
        assert result["has_pii"]

    def test_clean_data(self):
        df = pd.DataFrame({"product": ["Widget", "Gadget"], "price": [10, 20]})
        result = detect_pii(df)
        assert not result["has_pii"]

    def test_column_name_match(self):
        df = pd.DataFrame({"email_address": ["x", "y"], "count": [1, 2]})
        result = detect_pii(df)
        assert result["has_pii"]
        assert result["pii_columns"][0]["type"] == "column_name_match"

    def test_ssn_pattern(self):
        df = pd.DataFrame({
            "id_col": ["123-45-6789", "987-65-4321"] * 10 + ["not-ssn"] * 5,
        })
        result = detect_pii(df)
        assert result["has_pii"]
        assert any(p["type"] == "ssn" for p in result["pii_columns"])
