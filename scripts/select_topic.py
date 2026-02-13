from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.common import dump_json, parse_priority, read_csv_rows, resolve_path, write_csv_rows

REQUIRED_COLUMNS = ["keyword", "intent", "priority", "status", "last_used_at"]


def _sort_key(row: dict[str, str]) -> tuple[int, str, str]:
    priority = parse_priority(row.get("priority", "0"))
    last_used = row.get("last_used_at", "")
    status = row.get("status", "")
    return (-priority, last_used or "0000-00-00", status)


def select_topic(rows: list[dict[str, str]]) -> dict[str, str] | None:
    available = [
        row
        for row in rows
        if (row.get("status", "").strip().lower() not in {"paused", "archived"})
    ]
    if not available:
        return None

    unused = [row for row in available if not row.get("last_used_at")]
    target = sorted(unused or available, key=_sort_key)[0]
    return target


def mark_topic_used(
    rows: list[dict[str, str]], selected_keyword: str, used_at: dt.datetime
) -> list[dict[str, str]]:
    updated: list[dict[str, str]] = []
    for row in rows:
        new_row = dict(row)
        if row.get("keyword") == selected_keyword:
            new_row["last_used_at"] = used_at.date().isoformat()
            if row.get("status", "").lower() in {"new", "ready", ""}:
                new_row["status"] = "used"
        updated.append(new_row)
    return updated


def cli() -> int:
    parser = argparse.ArgumentParser(description="Select one keyword topic from keywords.csv")
    parser.add_argument(
        "--keywords", default="data/keywords.csv", help="Path to keywords CSV"
    )
    parser.add_argument(
        "--mark-used",
        action="store_true",
        help="Mark selected keyword used in CSV with current date",
    )
    args = parser.parse_args()

    rows = read_csv_rows(args.keywords, REQUIRED_COLUMNS)
    selected = select_topic(rows)
    if selected is None:
        print(dump_json({"selected": None, "reason": "no_available_keywords"}))
        return 0

    if args.mark_used:
        now = dt.datetime.now(dt.timezone.utc)
        updated = mark_topic_used(rows, selected["keyword"], now)
        write_csv_rows(resolve_path(args.keywords), updated, REQUIRED_COLUMNS)

    print(dump_json({"selected": selected}))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
