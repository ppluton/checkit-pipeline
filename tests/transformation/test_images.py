from src.transformation.images import _extension_for, _is_valid_image, acquire_images


def _rec(rec_id="rec1", image_url="https://cdn/x.jpg", has_image=True):
    return {
        "id": rec_id,
        "source": "guardian",
        "image_url": image_url,
        "metadata": {"has_image": has_image},
    }


class TestExtensionFor:
    def test_jpeg_content_type(self):
        assert _extension_for("image/jpeg", "https://cdn/x") == ".jpg"

    def test_png_content_type(self):
        assert _extension_for("image/png", "https://cdn/x") == ".png"

    def test_webp_content_type(self):
        assert _extension_for("image/webp", "https://cdn/x") == ".webp"

    def test_falls_back_to_url_extension(self):
        assert _extension_for("application/octet-stream", "https://cdn/photo.png") == ".png"

    def test_defaults_to_jpg(self):
        assert _extension_for("application/octet-stream", "https://cdn/photo") == ".jpg"


class TestIsValidImage:
    def test_image_content_type_with_bytes_is_valid(self):
        assert _is_valid_image("image/jpeg", b"\xff\xd8\xff") is True

    def test_non_image_content_type_is_invalid(self):
        assert _is_valid_image("text/html", b"<html>") is False

    def test_empty_body_is_invalid(self):
        assert _is_valid_image("image/png", b"") is False


class TestAcquireImages:
    def _ok_fetch(self, _url):
        return (b"\xff\xd8\xff", "image/jpeg")

    def test_downloads_and_writes_file(self, tmp_path):
        records = [_rec(rec_id="abc")]
        stats = acquire_images(records, tmp_path, fetch=self._ok_fetch)
        assert stats["downloaded"] == 1
        assert (tmp_path / "abc.jpg").read_bytes() == b"\xff\xd8\xff"
        assert records[0]["metadata"]["has_image"] is True

    def test_failed_fetch_flips_has_image_to_false(self, tmp_path):
        records = [_rec(rec_id="abc")]
        stats = acquire_images(records, tmp_path, fetch=lambda _u: None)
        assert stats["failed"] == 1
        assert records[0]["metadata"]["has_image"] is False
        assert not (tmp_path / "abc.jpg").exists()

    def test_invalid_content_type_flips_has_image_to_false(self, tmp_path):
        records = [_rec(rec_id="abc")]
        stats = acquire_images(records, tmp_path, fetch=lambda _u: (b"<html>", "text/html"))
        assert stats["failed"] == 1
        assert records[0]["metadata"]["has_image"] is False

    def test_record_without_image_url_is_skipped(self, tmp_path):
        calls = []

        def spy(url):
            calls.append(url)
            return (b"x", "image/png")

        records = [_rec(rec_id="abc", image_url=None, has_image=False)]
        stats = acquire_images(records, tmp_path, fetch=spy)
        assert stats["skipped"] == 1
        assert calls == []

    def test_extension_follows_content_type(self, tmp_path):
        records = [_rec(rec_id="abc")]
        acquire_images(records, tmp_path, fetch=lambda _u: (b"x", "image/png"))
        assert (tmp_path / "abc.png").exists()
