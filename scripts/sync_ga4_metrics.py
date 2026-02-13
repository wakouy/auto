from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.common import load_system_config, resolve_path

METRICS_COLUMNS = ["date", "pv", "clicks"]


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        missing = [col for col in METRICS_COLUMNS if col not in fields]
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
        return [dict(row) for row in reader]


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=METRICS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _upsert_row(rows: list[dict[str, str]], date_key: str, pv: int, clicks: int) -> list[dict[str, str]]:
    updated = False
    new_rows: list[dict[str, str]] = []
    for row in rows:
        copied = dict(row)
        if row.get("date") == date_key:
            copied["pv"] = str(max(0, pv))
            copied["clicks"] = str(max(0, clicks))
            updated = True
        new_rows.append(copied)
    if not updated:
        new_rows.append({"date": date_key, "pv": str(max(0, pv)), "clicks": str(max(0, clicks))})

    def _sort_key(row: dict[str, str]) -> str:
        return row.get("date", "")

    return sorted(new_rows, key=_sort_key)


def _fetch_ga4_day(property_id: str, day: dt.date) -> tuple[int, int] | None:
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Filter,
            FilterExpression,
            Metric,
            RunReportRequest,
        )
    except Exception:
        return None

    if not property_id:
        return None

    client = BetaAnalyticsDataClient()

    pv_req = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=day.isoformat(), end_date=day.isoformat())],
        metrics=[Metric(name="screenPageViews")],
    )
    pv_resp = client.run_report(pv_req)
    pv_total = int(pv_resp.rows[0].metric_values[0].value) if pv_resp.rows else 0

    click_req = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=day.isoformat(), end_date=day.isoformat())],
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="eventName",
                string_filter=Filter.StringFilter(
                    value="affiliate_click", match_type=Filter.StringFilter.MatchType.EXACT
                ),
            )
        ),
    )
    click_resp = client.run_report(click_req)
    clicks_total = int(click_resp.rows[0].metric_values[0].value) if click_resp.rows else 0

    return pv_total, clicks_total


def cli() -> int:
    parser = argparse.ArgumentParser(description="Sync yesterday GA4 metrics into CSV")
    parser.add_argument("--config", default="config/system.yaml")
    parser.add_argument("--metrics", default="data/analytics_metrics.csv")
    parser.add_argument("--date", default="", help="YYYY-MM-DD (default: yesterday JST)")
    args = parser.parse_args()

    config = load_system_config(args.config)
    property_id = (
        os.getenv("GA4_PROPERTY_ID", "").strip()
        or str(config.get("analytics", {}).get("ga4_property_id", "")).strip()
    )

    if args.date:
        target_day = dt.date.fromisoformat(args.date)
    else:
        jst = dt.timezone(dt.timedelta(hours=9))
        target_day = dt.datetime.now(jst).date() - dt.timedelta(days=1)

    ga4 = _fetch_ga4_day(property_id=property_id, day=target_day)
    if ga4 is None:
        print(
            json.dumps(
                {
                    "skipped": True,
                    "reason": "ga4_unavailable_or_unconfigured",
                    "date": target_day.isoformat(),
                },
                ensure_ascii=False,
            )
        )
        return 0

    pv, clicks = ga4
    metrics_path = resolve_path(args.metrics)
    rows = _load_rows(metrics_path)
    merged = _upsert_row(rows, target_day.isoformat(), pv, clicks)
    _write_rows(metrics_path, merged)

    print(
        json.dumps(
            {
                "skipped": False,
                "date": target_day.isoformat(),
                "pv": pv,
                "clicks": clicks,
                "file": str(metrics_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
