from src.transformation.load import _to_row


def test_to_row_maps_fields_and_flattens_metadata():
    record = {
        "id": "abc",
        "source": "snopes",
        "title": "t",
        "content": "c",
        "image_url": "u",
        "label": None,
        "label_detail": "Mixture",
        "language": "en",
        "domain": "snopes.com",
        "collected_at": "2026-01-01T00:00:00Z",
        "metadata": {
            "source_credibility": "high",
            "has_image": True,
            "label_method": "human_expert",
        },
    }
    row = _to_row(record, "train")
    assert row["id"] == "abc"
    assert row["split"] == "train"
    assert row["label"] is None
    assert row["label_detail"] == "Mixture"
    assert row["source_credibility"] == "high"
    assert row["has_image"] is True
    assert row["label_method"] == "human_expert"


def test_to_row_handles_missing_metadata():
    row = _to_row({"id": "x", "source": "liar"}, "test")
    assert row["split"] == "test"
    assert row["has_image"] is None
    assert row["source_credibility"] is None
    assert row["label_method"] is None


def test_to_row_has_all_table_columns():
    expected = {
        "id",
        "source",
        "split",
        "title",
        "content",
        "image_url",
        "label",
        "label_detail",
        "language",
        "domain",
        "collected_at",
        "source_credibility",
        "has_image",
        "label_method",
    }
    assert set(_to_row({"id": "x", "source": "guardian"}, "train")) == expected
