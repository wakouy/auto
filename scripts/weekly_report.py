from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.common import load_system_config, resolve_path, today_jst
from scripts.ad_revenue_validate import sum_ad_revenue

METRICS_COLUMNS = ["date", "pv", "clicks"]


def _date_range(end_day: dt.date, days: int = 7) -> tuple[dt.date, dt.date]:
    start_day = end_day - dt.timedelta(days=days - 1)
    return start_day, end_day


def _safe_int(value: str) -> int:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def _load_metrics_csv(path: Path, start_day: dt.date, end_day: dt.date) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    pv_total = 0
    clicks_total = 0
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        missing = [col for col in METRICS_COLUMNS if col not in headers]
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
        for row in reader:
            date_str = row.get("date", "")
            try:
                day = dt.date.fromisoformat(date_str)
            except ValueError:
                continue
            if start_day <= day <= end_day:
                pv_total += _safe_int(row.get("pv", "0"))
                clicks_total += _safe_int(row.get("clicks", "0"))
    return pv_total, clicks_total


def _fetch_ga4_metrics_if_available(
    *,
    start_day: dt.date,
    end_day: dt.date,
    property_id: str,
) -> tuple[int, int] | None:
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

    pageview_req = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[
            DateRange(start_date=start_day.isoformat(), end_date=end_day.isoformat())
        ],
        metrics=[Metric(name="screenPageViews")],
    )
    pageview_resp = client.run_report(pageview_req)
    pv_total = (
        int(pageview_resp.rows[0].metric_values[0].value)
        if pageview_resp.rows
        else 0
    )

    click_req = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[
            DateRange(start_date=start_day.isoformat(), end_date=end_day.isoformat())
        ],
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
    clicks_total = (
        int(click_resp.rows[0].metric_values[0].value) if click_resp.rows else 0
    )
    return pv_total, clicks_total


def build_report_markdown(
    *,
    start_day: dt.date,
    end_day: dt.date,
    pv_total: int,
    clicks_total: int,
    default_epc_usd: float,
    adsense_revenue_usd: float,
    traffic_source: str,
    adsense_source: str,
) -> str:
    ctr = (clicks_total / pv_total * 100.0) if pv_total > 0 else 0.0
    affiliate_revenue = clicks_total * default_epc_usd
    total_revenue = affiliate_revenue + adsense_revenue_usd
    reached_one_dollar = total_revenue >= 1.0
    progress = min(999.0, (total_revenue / 1.0) * 100.0)

    lines = [
        "# Weekly Revenue Report",
        "",
        f"- 期間: {start_day.isoformat()} 〜 {end_day.isoformat()}",
        f"- データソース(トラフィック): {traffic_source}",
        f"- データソース(AdSense): {adsense_source}",
        f"- 目標(合算収益 $1): {'達成' if reached_one_dollar else '未達'}",
        f"- 目標進捗: {progress:.1f}%",
        "",
        "## Metrics",
        f"- PV: {pv_total}",
        f"- Affiliate Clicks: {clicks_total}",
        f"- CTR: {ctr:.2f}%",
        f"- Affiliate推定収益(USD): ${affiliate_revenue:.2f}",
        f"- AdSense収益(USD): ${adsense_revenue_usd:.2f}",
        f"- 合算収益(USD): ${total_revenue:.2f}",
        f"- EPC(固定): ${default_epc_usd:.4f}",
        "",
        "## Notes",
        "- Affiliate推定収益はクリック数 x 固定EPCで算出しています。",
        "- AdSense収益は data/ad_revenue.csv の手入力値を使用しています。",
        "- 実売上はASPおよびAdSense管理画面で確認してください。",
    ]
    return "\n".join(lines) + "\n"


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def cli() -> int:
    parser = argparse.ArgumentParser(description="Generate weekly KPI report")
    parser.add_argument("--config", default="config/system.yaml")
    parser.add_argument("--metrics", default="data/analytics_metrics.csv")
    parser.add_argument("--ad-revenue", default="")
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args()

    config = load_system_config(args.config)
    now = today_jst()
    end_day = now.date() - dt.timedelta(days=1)
    start_day, end_day = _date_range(end_day, days=7)

    property_id = (
        os.getenv("GA4_PROPERTY_ID", "").strip()
        or str(config.get("analytics", {}).get("ga4_property_id", "")).strip()
    )
    ga4_result = _fetch_ga4_metrics_if_available(
        start_day=start_day,
        end_day=end_day,
        property_id=property_id,
    )
    if ga4_result is not None:
        pv_total, clicks_total = ga4_result
        traffic_source = "GA4 Data API"
    else:
        metrics_path = resolve_path(args.metrics)
        pv_total, clicks_total = _load_metrics_csv(metrics_path, start_day, end_day)
        traffic_source = "data/analytics_metrics.csv"

    ad_revenue_default = str(
        config.get("reporting", {}).get("ad_revenue_csv", "data/ad_revenue.csv")
    )
    ad_revenue_arg = args.ad_revenue.strip()
    ad_revenue_path = resolve_path(ad_revenue_arg or ad_revenue_default)
    adsense_revenue = sum_ad_revenue(ad_revenue_path, start_day, end_day)

    report = build_report_markdown(
        start_day=start_day,
        end_day=end_day,
        pv_total=pv_total,
        clicks_total=clicks_total,
        default_epc_usd=float(config["affiliate"]["default_epc_usd"]),
        adsense_revenue_usd=adsense_revenue,
        traffic_source=traffic_source,
        adsense_source=str(ad_revenue_path),
    )

    year, week, _ = end_day.isocalendar()
    report_path = resolve_path(args.reports_dir) / f"weekly-{year}-{week:02d}.md"
    write_report(report_path, report)

    print(
        json.dumps(
            {
                "report": str(report_path),
                "pv": pv_total,
                "clicks": clicks_total,
                "traffic_source": traffic_source,
                "adsense_source": str(ad_revenue_path),
                "affiliate_estimated_revenue_usd": round(
                    clicks_total * float(config["affiliate"]["default_epc_usd"]), 4
                ),
                "adsense_revenue_usd": round(adsense_revenue, 4),
                "total_revenue_usd": round(
                    clicks_total * float(config["affiliate"]["default_epc_usd"])
                    + adsense_revenue,
                    4,
                ),
                "week": f"{year}-W{week:02d}",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
