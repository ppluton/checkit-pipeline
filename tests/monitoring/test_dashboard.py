from src.monitoring.dashboard import save_dashboard

KPIS = {
    "stats": {
        "total": 163,
        "by_label": {"real": 66, "fake": 35, "null": 62},
        "has_image": {"true": 58, "false": 105},
    },
    "rejection": {
        "fakeddit": {"raw": 5, "valid": 5, "rejected": 0, "rate": 0.0},
        "snopes": {"raw": 20, "valid": 13, "rejected": 7, "rate": 0.35},
    },
    "split_sizes": {"train": 114, "validation": 24, "test": 25},
    "leakage": 0,
    "image_coverage_rate": 0.36,
}


def test_save_dashboard_writes_non_empty_png(tmp_path):
    out = tmp_path / "dashboard.png"
    save_dashboard(KPIS, out)
    assert out.exists()
    assert out.stat().st_size > 0
