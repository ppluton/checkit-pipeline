from src.monitoring.streamlit_app import build_frames


def _kpis() -> dict:
    return {
        "stats": {
            "total": 10,
            "by_label": {"fake": 3, "real": 5, "null": 2},
            "by_label_detail": {"false": 3, "true": 5, None: 2},
            "has_image": {"true": 6, "false": 4},
        },
        "rejection": {
            "guardian": {"raw": 5, "valid": 5, "rejected": 0, "rate": 0.0},
            "snopes": {"raw": 5, "valid": 3, "rejected": 2, "rate": 0.4},
        },
        "split_sizes": {"train": 7, "validation": 2, "test": 1},
        "leakage": 0,
        "image_coverage_rate": 0.6,
    }


def test_overall_reject_rate():
    frames = build_frames(_kpis())
    # raw 10, valid 8 -> 20% global rejection
    assert abs(frames["overall_reject"] - 0.2) < 1e-9


def test_volumetry_frame_shape():
    frames = build_frames(_kpis())
    vol = frames["volumetry"]
    assert list(vol.columns) == ["brut", "valides"]
    assert vol.loc["snopes", "valides"] == 3


def test_rejection_table_columns():
    frames = build_frames(_kpis())
    assert "rejetés" in frames["rejection_table"].columns


def test_labels_and_splits_totals():
    frames = build_frames(_kpis())
    assert int(frames["labels"].sum()) == 10
    assert int(frames["splits"].sum()) == 10


def test_label_detail_sorted_desc():
    frames = build_frames(_kpis())
    counts = list(frames["label_detail"]["records"])
    assert counts == sorted(counts, reverse=True)
