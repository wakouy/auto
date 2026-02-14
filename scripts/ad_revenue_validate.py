from __future__ import annotations

import argparse
import csv
import datetime as dt
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.common import dump_json, resolve_path

AD_REVENUE_COLUMNS = ["date", "adsense_revenue_usd", "source", "note"]


def _parse_day(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat((value or "").strip())
    except ValueError as exc:
        raise ValueError(f"invalid date: {value}") from exc


def _parse_non_negative_float(value: str) -> float:
    try:
        num = float((value or "").strip())
    except ValueError as exc:
        raise ValueError(f"invalid float: {value}") from exc
    if num < 0:
        raise ValueError(f"negative revenue is not allowed: {value}")
    return num


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise ValueError(f"{path} does not exist")
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        missing = [col for col in AD_REVENUE_COLUMNS if col not in headers]
        if missing:
            raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")
        rows = [dict(row) for row in reader]
    for idx, row in enumerate(rows, start=2):
        _parse_day(row.get("date", ""))
        _parse_non_negative_float(row.get("adsense_revenue_usd", "0"))
        for col in ("source", "note"):
            row[col] = (row.get(col, "") or "").strip()
    return rows


def sum_ad_revenue(path: Path, start_day: dt.date, end_day: dt.date) -> float:
    rows = read_rows(path)
    total = 0.0
    for row in rows:
        day = _parse_day(row.get("date", ""))
        if start_day <= day <= end_day:
            total += _parse_non_negative_float(row.get("adsense_revenue_usd", "0"))
    return total


def cli() -> int:
    parser = argparse.ArgumentParser(description="Validate manual AdSense revenue CSV")
    parser.add_argument("--file", default="data/ad_revenue.csv")
    args = parser.parse_args()

    path = resolve_path(args.file)
    rows = read_rows(path)
    total = sum(_parse_non_negative_float(row.get("adsense_revenue_usd", "0")) for row in rows)
    print(
        dump_json(
            {
                "file": str(path),
                "rows": len(rows),
                "total_adsense_revenue_usd": round(total, 4),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
