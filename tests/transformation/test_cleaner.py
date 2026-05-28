import pandas as pd

from src.transformation.cleaner import clean, sanitize_text


class TestSanitizeText:
    def test_strips_html_tags(self):
        assert sanitize_text("<p>Hello <b>world</b></p>") == "Hello world"

    def test_unescapes_html_entities(self):
        assert sanitize_text("Bread &amp; butter") == "Bread & butter"

    def test_collapses_whitespace(self):
        assert sanitize_text("a\n\n  b\t c") == "a b c"

    def test_normalizes_unicode_to_nfkc(self):
        assert sanitize_text("ﬁle") == "file"

    def test_none_becomes_empty_string(self):
        assert sanitize_text(None) == ""


class TestClean:
    def test_drops_duplicates_on_natural_key(self):
        df = pd.DataFrame(
            [
                {"id": "a", "clean_title": "x"},
                {"id": "a", "clean_title": "x duplicate"},
                {"id": "b", "clean_title": "y"},
            ]
        )
        out = clean(df, "fakeddit")
        assert list(out["id"]) == ["a", "b"]

    def test_dedup_keeps_first_occurrence(self):
        df = pd.DataFrame(
            [
                {"id": "a", "clean_title": "first"},
                {"id": "a", "clean_title": "second"},
            ]
        )
        out = clean(df, "fakeddit")
        assert out.iloc[0]["clean_title"] == "first"

    def test_drops_rows_with_null_natural_key(self):
        df = pd.DataFrame(
            [
                {"url": "https://snopes.com/x", "verdict": "True"},
                {"url": None, "verdict": "False"},
            ]
        )
        out = clean(df, "snopes")
        assert len(out) == 1
        assert out.iloc[0]["url"] == "https://snopes.com/x"

    def test_uses_url_as_natural_key_for_snopes(self):
        df = pd.DataFrame(
            [
                {"url": "https://snopes.com/x", "verdict": "True"},
                {"url": "https://snopes.com/x", "verdict": "False"},
            ]
        )
        out = clean(df, "snopes")
        assert len(out) == 1

    def test_returns_empty_frame_unchanged(self):
        df = pd.DataFrame(columns=["id", "clean_title"])
        out = clean(df, "fakeddit")
        assert len(out) == 0
