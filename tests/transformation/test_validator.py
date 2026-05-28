from datetime import UTC, datetime

import pandas as pd

from src.transformation.schema import Article
from src.transformation.validator import validate

COLLECTED_AT = datetime(2026, 5, 15, tzinfo=UTC)


def _row(**over):
    base = {
        "source": "snopes",
        "title": "A title",
        "content": "Some content.",
        "image_url": "https://media.snopes.com/x.png",
        "label": "real",
        "label_detail": "True",
        "language": "en",
        "domain": "snopes.com",
        "collected_at": COLLECTED_AT,
        "metadata": {
            "source_credibility": "high",
            "has_image": True,
            "label_method": "human_expert",
        },
    }
    base.update(over)
    return base


def _validate(*rows):
    return validate(pd.DataFrame(rows))


class TestValidate:
    def test_valid_row_returns_article(self):
        out = _validate(_row())
        assert len(out) == 1
        assert isinstance(out[0], Article)
        assert out[0].label == "real"

    def test_generates_uuid_id(self):
        out = _validate(_row())
        assert out[0].id is not None

    def test_empty_title_is_rejected(self):
        assert _validate(_row(title="")) == []

    def test_whitespace_only_content_is_rejected(self):
        assert _validate(_row(content="   ")) == []

    def test_invalid_image_url_is_rejected(self):
        assert _validate(_row(image_url="not-a-url")) == []

    def test_none_image_url_is_accepted(self):
        out = _validate(
            _row(
                image_url=None,
                metadata={
                    "source_credibility": "high",
                    "has_image": False,
                    "label_method": "human_expert",
                },
            )
        )
        assert len(out) == 1

    def test_invalid_credibility_is_rejected(self):
        out = _validate(
            _row(
                metadata={
                    "source_credibility": "bogus",
                    "has_image": True,
                    "label_method": "human_expert",
                }
            )
        )
        assert out == []

    def test_null_label_is_accepted(self):
        out = _validate(_row(label=None, label_detail="Mixture"))
        assert len(out) == 1
        assert out[0].label is None

    def test_nan_label_is_coerced_to_none(self):
        out = _validate(_row(label=float("nan")))
        assert len(out) == 1
        assert out[0].label is None

    def test_keeps_valid_drops_invalid(self):
        out = _validate(_row(), _row(title=""), _row(content="valid too"))
        assert len(out) == 2
