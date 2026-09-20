import json
from pathlib import Path

from scripts.paper.fetch_c3_external_screenshots import (
    build_download_url,
    fetch_screenshots,
    inspect_image,
)


PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
)


def test_build_download_url_uses_source_id():
    assert build_download_url("abc_123") == (
        "https://drive.usercontent.google.com/download?id=abc_123&export=download&confirm=t"
    )


def test_inspect_image_reads_png_dimensions_and_rejects_html():
    assert inspect_image(PNG_1X1) == {"format": "png", "width": 1, "height": 1}
    try:
        inspect_image(b"<html>permission denied</html>")
    except ValueError as exc:
        assert "supported image" in str(exc)
    else:
        raise AssertionError("Expected HTML to be rejected")


def test_fetch_screenshots_records_success_and_failure(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([
        {"sample_id": "EXTF001", "source_screenshot_id": "ok"},
        {"sample_id": "EXTF002", "source_screenshot_id": "bad"},
    ]), encoding="utf-8")

    def downloader(source_id: str) -> bytes:
        if source_id == "ok":
            return PNG_1X1
        raise OSError("network unavailable")

    report = fetch_screenshots(manifest, tmp_path / "out", downloader=downloader)

    assert report["requested"] == 2
    assert report["valid"] == 1
    assert report["failed"] == 1
    assert (tmp_path / "out" / "screenshots" / "EXTF001.png").is_file()
    records = json.loads(
        (tmp_path / "out" / "screenshot_audit.json").read_text(encoding="utf-8")
    )
    assert records[0]["status"] == "valid"
    assert records[0]["width"] == 1
    assert records[1]["status"] == "failed"
    assert "network unavailable" in records[1]["error"]

    retried = []

    def retry_downloader(source_id: str) -> bytes:
        retried.append(source_id)
        return PNG_1X1

    second_report = fetch_screenshots(
        manifest, tmp_path / "out", downloader=retry_downloader
    )

    assert retried == ["bad"]
    assert second_report["valid"] == 2
    assert second_report["failed"] == 0
