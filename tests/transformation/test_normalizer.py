from datetime import UTC, datetime

import pandas as pd

from src.transformation.normalizer import normalize

COLLECTED_AT = datetime(2026, 5, 15, tzinfo=UTC)


def _normalize(records, source):
    return normalize(pd.DataFrame(records), source, COLLECTED_AT)


class TestFakeddit:
    def _row(self, **over):
        base = {
            "id": "abc",
            "clean_title": "NASA confirms water on Mars",
            "image_url": "https://i.redd.it/abc.jpg",
            "domain": "nasa.gov",
            "2_way_label": "0",
            "6_way_label": "0",
        }
        base.update(over)
        return base

    def test_binary_label_zero_is_real(self):
        out = _normalize([self._row(**{"2_way_label": "0"})], "fakeddit")
        assert out.iloc[0]["label"] == "real"

    def test_binary_label_one_is_fake(self):
        out = _normalize([self._row(**{"2_way_label": "1"})], "fakeddit")
        assert out.iloc[0]["label"] == "fake"

    def test_six_way_label_detail(self):
        out = _normalize([self._row(**{"6_way_label": "1"})], "fakeddit")
        assert out.iloc[0]["label_detail"] == "satire"

    def test_title_and_content_from_clean_title(self):
        out = _normalize([self._row()], "fakeddit")
        assert out.iloc[0]["title"] == "NASA confirms water on Mars"
        assert out.iloc[0]["content"] == "NASA confirms water on Mars"

    def test_metadata_is_community_medium(self):
        meta = _normalize([self._row()], "fakeddit").iloc[0]["metadata"]
        assert meta["source_credibility"] == "medium"
        assert meta["label_method"] == "community"
        assert meta["has_image"] is True

    def test_collected_at_is_set(self):
        out = _normalize([self._row()], "fakeddit")
        assert out.iloc[0]["collected_at"] == COLLECTED_AT


class TestGuardian:
    def _row(self, **fields):
        base = {
            "headline": "Real reporting",
            "body": "<p>Some <b>HTML</b> body</p>",
            "thumbnail": "https://media.guim.co.uk/x.jpg",
            "trailText": "trail",
        }
        base.update(fields)
        return {"id": "world/2026/x", "webTitle": "wt", "fields": base}

    def test_label_is_real_baseline(self):
        out = _normalize([self._row()], "guardian")
        assert out.iloc[0]["label"] == "real"

    def test_metadata_is_human_expert_high(self):
        meta = _normalize([self._row()], "guardian").iloc[0]["metadata"]
        assert meta["source_credibility"] == "high"
        assert meta["label_method"] == "human_expert"

    def test_title_from_headline(self):
        out = _normalize([self._row()], "guardian")
        assert out.iloc[0]["title"] == "Real reporting"

    def test_content_html_is_stripped(self):
        out = _normalize([self._row()], "guardian")
        assert out.iloc[0]["content"] == "Some HTML body"

    def test_domain_is_theguardian(self):
        out = _normalize([self._row()], "guardian")
        assert out.iloc[0]["domain"] == "theguardian.com"


class TestSnopes:
    def _row(self, verdict, **over):
        base = {
            "url": "https://snopes.com/fact-check/x",
            "title": "Was X true?",
            "claim": "X happened on a highway.",
            "verdict": verdict,
            "image_url": "https://media.snopes.com/x.png",
            "description": "desc",
        }
        base.update(over)
        return base

    def test_true_verdict_maps_to_real(self):
        out = _normalize([self._row("True")], "snopes")
        assert out.iloc[0]["label"] == "real"

    def test_false_verdict_maps_to_fake(self):
        out = _normalize([self._row("False")], "snopes")
        assert out.iloc[0]["label"] == "fake"

    def test_ambiguous_verdict_has_null_label_but_keeps_detail(self):
        out = _normalize([self._row("Mixture")], "snopes")
        assert pd.isna(out.iloc[0]["label"])
        assert out.iloc[0]["label_detail"] == "Mixture"

    def test_rows_without_verdict_are_dropped(self):
        out = _normalize([self._row(None), self._row("True")], "snopes")
        assert len(out) == 1
        assert out.iloc[0]["label"] == "real"

    def test_content_from_claim(self):
        out = _normalize([self._row("True")], "snopes")
        assert out.iloc[0]["content"] == "X happened on a highway."

    def test_metadata_human_expert_high(self):
        meta = _normalize([self._row("True")], "snopes").iloc[0]["metadata"]
        assert meta["source_credibility"] == "high"
        assert meta["label_method"] == "human_expert"


class TestLiar:
    def _row(self, label_text, **over):
        base = {
            "id": "123.json",
            "statement": "The deficit tripled last year.",
            "label_text": label_text,
            "speaker": "someone",
        }
        base.update(over)
        return base

    def test_true_maps_to_real(self):
        out = _normalize([self._row("true")], "liar")
        assert out.iloc[0]["label"] == "real"

    def test_false_maps_to_fake(self):
        out = _normalize([self._row("false")], "liar")
        assert out.iloc[0]["label"] == "fake"

    def test_pants_fire_maps_to_fake(self):
        out = _normalize([self._row("pants-fire")], "liar")
        assert out.iloc[0]["label"] == "fake"

    def test_half_true_is_ambiguous_null(self):
        out = _normalize([self._row("half-true")], "liar")
        assert pd.isna(out.iloc[0]["label"])
        assert out.iloc[0]["label_detail"] == "half-true"

    def test_no_image(self):
        out = _normalize([self._row("true")], "liar")
        assert out.iloc[0]["image_url"] is None
        assert out.iloc[0]["metadata"]["has_image"] is False

    def test_content_from_statement(self):
        out = _normalize([self._row("true")], "liar")
        assert out.iloc[0]["content"] == "The deficit tripled last year."
