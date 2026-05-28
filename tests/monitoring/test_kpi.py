from src.monitoring.kpi import leakage_count, per_source_rejection, rejection_rate


class TestRejectionRate:
    def test_basic_rate(self):
        assert rejection_rate(20, 13) == 0.35

    def test_no_rejection(self):
        assert rejection_rate(45, 45) == 0.0

    def test_empty_raw_is_zero(self):
        assert rejection_rate(0, 0) == 0.0


class TestPerSourceRejection:
    def test_counts_and_rate_per_source(self):
        raw_counts = {"snopes": 20, "guardian": 45}
        records = [{"source": "snopes"}] * 13 + [{"source": "guardian"}] * 45
        out = per_source_rejection(raw_counts, records)
        assert out["snopes"] == {"raw": 20, "valid": 13, "rejected": 7, "rate": 0.35}
        assert out["guardian"]["rejected"] == 0

    def test_source_absent_from_processed(self):
        out = per_source_rejection({"liar": 100}, [])
        assert out["liar"]["valid"] == 0
        assert out["liar"]["rejected"] == 100


class TestLeakageCount:
    def test_no_overlap(self):
        splits = {
            "train": [{"content": "a"}],
            "validation": [{"content": "b"}],
            "test": [{"content": "c"}],
        }
        assert leakage_count(splits) == 0

    def test_detects_content_in_two_splits(self):
        splits = {
            "train": [{"content": "shared"}],
            "validation": [],
            "test": [{"content": "shared"}, {"content": "unique"}],
        }
        assert leakage_count(splits) == 1

    def test_is_case_and_whitespace_insensitive(self):
        splits = {
            "train": [{"content": "Same Text"}],
            "validation": [],
            "test": [{"content": "  same text  "}],
        }
        assert leakage_count(splits) == 1
