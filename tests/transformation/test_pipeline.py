from datetime import UTC, datetime

import pandas as pd

from src.transformation.pipeline import transform_source

COLLECTED_AT = datetime(2026, 5, 15, tzinfo=UTC)


def test_fakeddit_dedup_then_normalize_then_validate():
    df = pd.DataFrame(
        [
            {
                "id": "a",
                "clean_title": "Water on Mars",
                "image_url": "https://i.redd.it/a.jpg",
                "domain": "nasa.gov",
                "2_way_label": "0",
                "6_way_label": "0",
            },
            {
                "id": "a",
                "clean_title": "dup",
                "image_url": "https://i.redd.it/a.jpg",
                "domain": "nasa.gov",
                "2_way_label": "0",
                "6_way_label": "0",
            },
            {
                "id": "b",
                "clean_title": "Fake claim",
                "image_url": "https://i.redd.it/b.jpg",
                "domain": "x.com",
                "2_way_label": "1",
                "6_way_label": "5",
            },
        ]
    )
    articles = transform_source(df, "fakeddit", COLLECTED_AT)
    assert len(articles) == 2
    assert {a.label for a in articles} == {"real", "fake"}


def test_snopes_drops_verdictless_rows_through_full_chain():
    df = pd.DataFrame(
        [
            {
                "url": "https://snopes.com/a",
                "title": "T",
                "claim": "C",
                "verdict": "True",
                "image_url": "https://media.snopes.com/a.png",
                "description": "d",
            },
            {
                "url": "https://snopes.com/b",
                "title": "T2",
                "claim": "C2",
                "verdict": None,
                "image_url": "https://media.snopes.com/b.png",
                "description": "d2",
            },
        ]
    )
    articles = transform_source(df, "snopes", COLLECTED_AT)
    assert len(articles) == 1
    assert articles[0].label == "real"
