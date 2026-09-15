"""Remap E004 initial annotations from the provisional inventory to frozen v2."""

from __future__ import annotations

import csv
from pathlib import Path


ID_MAP = {
    "practice_shopping": {
        "PS01": "PS01", "PS02": "PS02", "PS03": "PS04", "PS04": "PS08",
        "PS05": "PS10", "PS06": "PS12", "PS07": "PS13", "PS08": "PS14",
        "PS09": "PS15", "PS10": "PS16",
    },
    "saucedemo": {
        "SD01": "SD01", "SD02": "SD02", "SD03": "SD05", "SD04": "SD03",
        "SD05": "SD07", "SD06": "SD12", "SD07": "SD13", "SD08": "SD14",
        "SD09": "SD15", "SD10": "SD16", "SD11": "SD17", "SD12": "SD19",
        "SD13": "SD20",
    },
}


def remap(path: Path) -> None:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0]) if rows else []

    for row in rows:
        site = row["site"]
        row["core_id"] = ID_MAP[site].get(row["core_id"], row["core_id"])
        action = row["canonical_action_id"]
        if site == "practice_shopping" and action == "clear_filters":
            row["core_id"] = "PS03"
        elif site == "practice_shopping" and action == "continue_shopping":
            row["core_id"] = "PS11"
            if row["evidence_label"] == "supported":
                row["core_match_status"] = "matched"
        elif site == "saucedemo" and action == "navigate_home":
            row["core_id"] = "SD21"
            if row["evidence_label"] == "supported":
                row["core_match_status"] = "matched"

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    root = Path("outputs/paper/formal/E004_c2_v2")
    paths = sorted(root.rglob("c2_attempts_ai_initial.csv"))
    for path in paths:
        remap(path)
    print(f"remapped {len(paths)} annotation files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
