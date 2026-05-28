from src.extraction.guardian import _is_wanted


def _article(type_="article", thumbnail="https://media.guim.co.uk/x.jpg"):
    fields = {}
    if thumbnail is not None:
        fields["thumbnail"] = thumbnail
    return {"type": type_, "fields": fields}


class TestIsWanted:
    def test_article_with_thumbnail_is_kept(self):
        assert _is_wanted(_article(), require_image=True) is True

    def test_article_without_thumbnail_is_dropped_when_image_required(self):
        assert _is_wanted(_article(thumbnail=None), require_image=True) is False

    def test_article_without_thumbnail_is_kept_when_image_not_required(self):
        assert _is_wanted(_article(thumbnail=None), require_image=False) is True

    def test_liveblog_is_dropped(self):
        assert _is_wanted(_article(type_="liveblog"), require_image=True) is False

    def test_crossword_is_dropped(self):
        assert _is_wanted(_article(type_="crossword"), require_image=True) is False

    def test_missing_fields_key_does_not_crash(self):
        assert _is_wanted({"type": "article"}, require_image=True) is False
