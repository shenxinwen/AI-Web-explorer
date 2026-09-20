"""Fetch and validate screenshots for the C3 external formal manifest."""

from __future__ import annotations

import argparse
import json
import struct
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable


def build_download_url(source_id: str) -> str:
    return (
        "https://drive.usercontent.google.com/download?"
        f"id={source_id}&export=download&confirm=t"
    )


def inspect_image(data: bytes) -> dict[str, Any]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return {"format": "png", "width": width, "height": height}
    if data.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            if marker in range(0xC0, 0xC4):
                height, width = struct.unpack(">HH", data[offset + 5:offset + 9])
                return {"format": "jpg", "width": width, "height": height}
            if offset + 4 > len(data):
                break
            segment_length = struct.unpack(">H", data[offset + 2:offset + 4])[0]
            if segment_length < 2:
                break
            offset += 2 + segment_length
    raise ValueError("response is not a supported image")


def _download(source_id: str) -> bytes:
    request = urllib.request.Request(
        build_download_url(source_id),
        headers={"User-Agent": "VERA-C3-screenshot-audit/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def fetch_screenshots(
    manifest_path: Path,
    destination: Path,
    downloader: Callable[[str], bytes] = _download,
    workers: int = 8,
) -> dict[str, Any]:
    samples = json.loads(manifest_path.read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=True)
    screenshot_dir = destination / "screenshots"
    screenshot_dir.mkdir(exist_ok=True)
    prior_by_sample = {}
    prior_audit = destination / "screenshot_audit.json"
    if prior_audit.is_file():
        prior_by_sample = {
            record["sample_id"]: record
            for record in json.loads(prior_audit.read_text(encoding="utf-8"))
        }

    def fetch(index: int, sample: dict[str, Any]) -> tuple[int, dict[str, Any], bytes | None]:
        record = {
            "sample_id": sample["sample_id"],
            "source_screenshot_id": sample["source_screenshot_id"],
        }
        try:
            data = downloader(sample["source_screenshot_id"])
            image = inspect_image(data)
            record.update({"status": "valid", "bytes": len(data), **image})
            return index, record, data
        except Exception as exc:  # Each source failure must remain an auditable record.
            record.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
            return index, record, None

    results: list[tuple[dict[str, Any], bytes | None] | None] = [None] * len(samples)
    pending = []
    for index, sample in enumerate(samples):
        prior = prior_by_sample.get(sample["sample_id"])
        prior_path = destination / prior.get("local_path", "") if prior else None
        if (
            prior
            and prior.get("status") == "valid"
            and prior.get("source_screenshot_id") == sample["source_screenshot_id"]
            and prior_path is not None
            and prior_path.is_file()
        ):
            results[index] = (prior, None)
        else:
            pending.append((index, sample))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch, index, sample): index
            for index, sample in pending
        }
        for future in as_completed(futures):
            index, record, data = future.result()
            results[index] = (record, data)

    records = []
    for result in results:
        assert result is not None
        record, data = result
        if data is not None:
            filename = f'{record["sample_id"]}.{record["format"]}'
            (screenshot_dir / filename).write_bytes(data)
            record["local_path"] = f"screenshots/{filename}"
        records.append(record)
    (destination / "screenshot_audit.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = {
        "requested": len(records),
        "valid": sum(record["status"] == "valid" for record in records),
        "failed": sum(record["status"] == "failed" for record in records),
        "formats": {
            image_format: sum(record.get("format") == image_format for record in records)
            for image_format in sorted({record.get("format") for record in records if record.get("format")})
        },
    }
    (destination / "screenshot_audit_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    report = fetch_screenshots(args.manifest, args.destination, workers=args.workers)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
