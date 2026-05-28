from src.transformation.dataset import assign_splits, compute_stats


def _rec(source="liar", label="fake", content="some statement", **over):
    base = {
        "source": source,
        "label": label,
        "label_detail": "false",
        "language": "en",
        "content": content,
        "metadata": {"has_image": False},
    }
    base.update(over)
    return base


class TestComputeStats:
    def test_total_count(self):
        stats = compute_stats([_rec(), _rec(), _rec()])
        assert stats["total"] == 3

    def test_counts_by_source(self):
        stats = compute_stats([_rec(source="liar"), _rec(source="snopes"), _rec(source="liar")])
        assert stats["by_source"] == {"liar": 2, "snopes": 1}

    def test_null_label_reported_as_null_key(self):
        stats = compute_stats([_rec(label=None), _rec(label="real")])
        assert stats["by_label"]["null"] == 1
        assert stats["by_label"]["real"] == 1

    def test_has_image_split(self):
        stats = compute_stats(
            [
                _rec(metadata={"has_image": True}),
                _rec(metadata={"has_image": False}),
                _rec(metadata={"has_image": False}),
            ]
        )
        assert stats["has_image"] == {"true": 1, "false": 2}

    def test_detects_duplicate_content_groups(self):
        stats = compute_stats([_rec(content="same"), _rec(content="same"), _rec(content="unique")])
        assert stats["duplicate_content_groups"] == 1


class TestAssignSplits:
    def _stratum(self, n, source="liar", label="fake"):
        return [_rec(source=source, label=label, content=f"text-{i}") for i in range(n)]

    def test_every_record_gets_exactly_one_split(self):
        out = assign_splits(self._stratum(20))
        assert all(r["split"] in {"train", "validation", "test"} for r in out)
        assert len(out) == 20

    def test_is_deterministic_with_seed(self):
        records = self._stratum(20)
        a = [r["split"] for r in assign_splits(records, seed=7)]
        b = [r["split"] for r in assign_splits(records, seed=7)]
        assert a == b

    def test_ratios_70_15_15_on_clean_stratum(self):
        out = assign_splits(self._stratum(10))
        counts = {
            s: sum(1 for r in out if r["split"] == s) for s in ("train", "validation", "test")
        }
        assert counts == {"train": 7, "validation": 2, "test": 1}

    def test_singleton_stratum_goes_to_train(self):
        out = assign_splits(self._stratum(1))
        assert out[0]["split"] == "train"

    def test_duplicate_content_stays_in_same_split(self):
        records = self._stratum(18) + [_rec(content="dup"), _rec(content="dup")]
        out = assign_splits(records, seed=1)
        dup_splits = {r["split"] for r in out if r["content"] == "dup"}
        assert len(dup_splits) == 1

    def test_strata_are_independent(self):
        records = self._stratum(10, label="fake") + self._stratum(10, label="real")
        out = assign_splits(records)
        for label in ("fake", "real"):
            counts = {
                s: sum(1 for r in out if r["split"] == s and r["label"] == label)
                for s in ("train", "validation", "test")
            }
            assert counts == {"train": 7, "validation": 2, "test": 1}


class TestRenderDataCard:
    def test_card_contains_total_and_split_counts(self):
        from src.transformation.dataset import render_data_card

        stats = {
            "total": 163,
            "by_source": {"liar": 100, "guardian": 45},
            "by_label": {"real": 66, "fake": 35, "null": 62},
            "by_label_detail": {"false": 30},
            "by_language": {"en": 163},
            "has_image": {"true": 63, "false": 100},
            "content_length": {"min": 10, "max": 5000, "mean": 800.5, "median": 120},
            "duplicate_content_groups": 0,
        }
        breakdown = {
            "train": {"liar": 70, "guardian": 31},
            "validation": {"liar": 15, "guardian": 7},
            "test": {"liar": 15, "guardian": 7},
        }
        card = render_data_card(stats, breakdown)
        assert "163" in card
        assert "train" in card.lower()
        assert "guardian" in card.lower()
