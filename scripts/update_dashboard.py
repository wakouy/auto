from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

import requests

if __package__ in {None, ""}:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.ad_revenue_validate import read_rows as read_ad_revenue_rows
from scripts.ad_revenue_validate import sum_ad_revenue
from scripts.common import dump_json, load_system_config, load_yaml, read_csv_rows, resolve_path
from scripts.monetization_audit import TOOLS_COLUMNS

METRICS_COLUMNS = ["date", "pv", "clicks"]
AFFILIATE_READY_STATUSES = {"approved", "active", "affiliate_ready"}
ADSENSE_PUBLISHER_PATTERN = re.compile(r"^ca-pub-\d{16}$")
GA4_MEASUREMENT_PATTERN = re.compile(r"^G-[A-Z0-9]+$")


@dataclass
class StatusItem:
    name: str
    passed: bool
    detail: str


def _safe_int(value: str) -> int:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def _load_metric_totals(path: Path, start_day: dt.date, end_day: dt.date) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    pv_total = 0
    clicks_total = 0
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        columns = reader.fieldnames or []
        missing = [col for col in METRICS_COLUMNS if col not in columns]
        if missing:
            raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")
        for row in reader:
            try:
                day = dt.date.fromisoformat((row.get("date", "") or "").strip())
            except ValueError:
                continue
            if start_day <= day <= end_day:
                pv_total += _safe_int(row.get("pv", "0"))
                clicks_total += _safe_int(row.get("clicks", "0"))
    return pv_total, clicks_total


def _is_placeholder_url(url: str) -> bool:
    value = (url or "").strip().lower()
    if not value:
        return True
    return any(
        token in value
        for token in ["example.com", "replace-me", "your-affiliate-link", "<", ">"]
    )


def _http_ok(url: str, timeout: int = 8) -> tuple[bool, str]:
    try:
        res = requests.get(url, timeout=timeout)
        return (res.status_code < 400, f"HTTP {res.status_code}")
    except Exception as exc:  # pragma: no cover
        return (False, f"error: {type(exc).__name__}")


def _date_window(days: int, now: dt.date) -> tuple[dt.date, dt.date]:
    start = now - dt.timedelta(days=days - 1)
    return start, now


def _format_usd(value: float) -> str:
    return f"${value:.2f}"


def render_report_markdown(
    *,
    now_jst: dt.datetime,
    base_url: str,
    tools_ready_count: int,
    tools_total_count: int,
    pv_7d: int,
    clicks_7d: int,
    affiliate_7d: float,
    adsense_7d: float,
    total_7d: float,
    pv_28d: int,
    clicks_28d: int,
    affiliate_28d: float,
    adsense_28d: float,
    total_28d: float,
    status_items: list[StatusItem],
) -> str:
    progress = min(999.0, total_7d / 7.0 / 1.0 * 100.0)
    passed = sum(1 for item in status_items if item.passed)
    total = len(status_items)

    lines = [
        "# Monetization Dashboard",
        "",
        f"- 更新日時: {now_jst.strftime('%Y-%m-%d %H:%M JST')}",
        f"- サイト: {base_url}",
        f"- 目標進捗（$1/日基準）: {progress:.1f}%",
        "",
        "## Revenue (7 days)",
        f"- PV: {pv_7d}",
        f"- Clicks: {clicks_7d}",
        f"- Affiliate推定: {_format_usd(affiliate_7d)}",
        f"- AdSense実績: {_format_usd(adsense_7d)}",
        f"- 合算: {_format_usd(total_7d)}",
        "",
        "## Revenue (28 days)",
        f"- PV: {pv_28d}",
        f"- Clicks: {clicks_28d}",
        f"- Affiliate推定: {_format_usd(affiliate_28d)}",
        f"- AdSense実績: {_format_usd(adsense_28d)}",
        f"- 合算: {_format_usd(total_28d)}",
        "",
        "## Setup Status",
        f"- 完了: {passed}/{total}",
        f"- 収益化案件: {tools_ready_count}/{tools_total_count}",
    ]
    for item in status_items:
        mark = "x" if item.passed else " "
        lines.append(f"- [{mark}] {item.name}（{item.detail}）")

    lines.extend(
        [
            "",
            "## Next",
            "- GA4 Measurement ID と AdSense Publisher ID を設定してトラッキングを有効化する。",
            "- Search Console で sitemap 送信後、流入改善を継続する。",
            "- `data/ad_revenue.csv` を週1で更新する。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_site_markdown(
    *,
    now_jst: dt.datetime,
    base_url: str,
    total_7d: float,
    total_28d: float,
    status_items: list[StatusItem],
) -> str:
    passed = sum(1 for item in status_items if item.passed)
    total = len(status_items)
    lines = [
        "---",
        "layout: default",
        'title: "収益ダッシュボード"',
        "permalink: /dashboard/",
        "---",
        "",
        "# 収益ダッシュボード",
        "",
        f"- 更新日時: {now_jst.strftime('%Y-%m-%d %H:%M JST')}",
        f"- 7日合算収益: {_format_usd(total_7d)}",
        f"- 28日合算収益: {_format_usd(total_28d)}",
        f"- セットアップ進捗: {passed}/{total}",
        "",
        "## 現在の状態",
    ]
    for item in status_items:
        label = "完了" if item.passed else "未完了"
        lines.append(f"- {item.name}: {label}（{item.detail}）")
    lines.extend(
        [
            "",
            "## 補足",
            "- このページは自動更新です（Daily Publish / Weekly Report / Daily Metrics Sync）。",
            "- 詳細ログはリポジトリの `reports/monetization-dashboard.md` を確認してください。",
            f"- サイトURL: {base_url}",
        ]
    )
    return "\n".join(lines) + "\n"


def cli() -> int:
    parser = argparse.ArgumentParser(description="Build monetization dashboard markdown")
    parser.add_argument("--config", default="config/system.yaml")
    parser.add_argument("--site-config", default="_config.yml")
    parser.add_argument("--tools", default="data/tools.csv")
    parser.add_argument("--metrics", default="data/analytics_metrics.csv")
    parser.add_argument("--ad-revenue", default="")
    parser.add_argument("--output-report", default="reports/monetization-dashboard.md")
    parser.add_argument("--output-site", default="content/dashboard.md")
    parser.add_argument("--no-live-check", action="store_true")
    args = parser.parse_args()

    config = load_system_config(args.config)
    site_config = load_yaml(args.site_config)
    tools = read_csv_rows(args.tools, TOOLS_COLUMNS)

    base_url = str(config["site"]["base_url"]).rstrip("/")
    ga4_measurement_id = str(site_config.get("ga4_measurement_id", "")).strip()
    adsense_publisher_id = str(site_config.get("adsense_publisher_id", "")).strip()
    default_epc = float(config["affiliate"]["default_epc_usd"])

    metrics_path = resolve_path(args.metrics)
    ad_revenue_default = str(config.get("reporting", {}).get("ad_revenue_csv", "data/ad_revenue.csv"))
    ad_revenue_path = resolve_path(args.ad_revenue or ad_revenue_default)

    now_jst = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    today = now_jst.date()
    start_7d, end_7d = _date_window(7, today)
    start_28d, end_28d = _date_window(28, today)

    pv_7d, clicks_7d = _load_metric_totals(metrics_path, start_7d, end_7d)
    pv_28d, clicks_28d = _load_metric_totals(metrics_path, start_28d, end_28d)
    affiliate_7d = clicks_7d * default_epc
    affiliate_28d = clicks_28d * default_epc

    adsense_7d = 0.0
    adsense_28d = 0.0
    ad_revenue_valid = False
    ad_revenue_detail = str(ad_revenue_path)
    try:
        read_ad_revenue_rows(ad_revenue_path)
        adsense_7d = sum_ad_revenue(ad_revenue_path, start_7d, end_7d)
        adsense_28d = sum_ad_revenue(ad_revenue_path, start_28d, end_28d)
        ad_revenue_valid = True
        ad_revenue_detail = f"{ad_revenue_path} (valid)"
    except ValueError as exc:
        ad_revenue_detail = f"{ad_revenue_path} ({exc})"

    total_7d = affiliate_7d + adsense_7d
    total_28d = affiliate_28d + adsense_28d

    ready_tools = [
        row
        for row in tools
        if row.get("status", "").strip().lower() in AFFILIATE_READY_STATUSES
        and not _is_placeholder_url(row.get("affiliate_url", ""))
    ]

    status_items: list[StatusItem] = [
        StatusItem(
            name="GA4 Measurement ID 設定",
            passed=bool(GA4_MEASUREMENT_PATTERN.match(ga4_measurement_id)),
            detail=ga4_measurement_id or "未設定",
        ),
        StatusItem(
            name="AdSense Publisher ID 設定",
            passed=bool(ADSENSE_PUBLISHER_PATTERN.match(adsense_publisher_id)),
            detail=adsense_publisher_id or "未設定",
        ),
        StatusItem(
            name="収益化リンク準備",
            passed=len(ready_tools) > 0,
            detail=f"{len(ready_tools)}/{len(tools)}",
        ),
        StatusItem(
            name="ad_revenue.csv 妥当性",
            passed=ad_revenue_valid,
            detail=ad_revenue_detail,
        ),
        StatusItem(
            name="Daily Publish workflow",
            passed=resolve_path(".github/workflows/publish.yml").exists(),
            detail=".github/workflows/publish.yml",
        ),
        StatusItem(
            name="Weekly Report workflow",
            passed=resolve_path(".github/workflows/weekly_report.yml").exists(),
            detail=".github/workflows/weekly_report.yml",
        ),
    ]

    if not args.no_live_check:
        root_ok, root_detail = _http_ok(base_url)
        sitemap_ok, sitemap_detail = _http_ok(f"{base_url}/sitemap.xml")
        robots_ok, robots_detail = _http_ok(f"{base_url}/robots.txt")
        status_items.extend(
            [
                StatusItem("公開サイト到達", root_ok, root_detail),
                StatusItem("公開 sitemap.xml", sitemap_ok, sitemap_detail),
                StatusItem("公開 robots.txt", robots_ok, robots_detail),
            ]
        )

    report_markdown = render_report_markdown(
        now_jst=now_jst,
        base_url=base_url,
        tools_ready_count=len(ready_tools),
        tools_total_count=len(tools),
        pv_7d=pv_7d,
        clicks_7d=clicks_7d,
        affiliate_7d=affiliate_7d,
        adsense_7d=adsense_7d,
        total_7d=total_7d,
        pv_28d=pv_28d,
        clicks_28d=clicks_28d,
        affiliate_28d=affiliate_28d,
        adsense_28d=adsense_28d,
        total_28d=total_28d,
        status_items=status_items,
    )
    site_markdown = render_site_markdown(
        now_jst=now_jst,
        base_url=base_url,
        total_7d=total_7d,
        total_28d=total_28d,
        status_items=status_items,
    )

    output_report = resolve_path(args.output_report)
    output_site = resolve_path(args.output_site)
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_site.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(report_markdown, encoding="utf-8")
    output_site.write_text(site_markdown, encoding="utf-8")

    print(
        dump_json(
            {
                "output_report": str(output_report),
                "output_site": str(output_site),
                "total_revenue_7d_usd": round(total_7d, 4),
                "total_revenue_28d_usd": round(total_28d, 4),
                "ready_tools_count": len(ready_tools),
                "tools_total_count": len(tools),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
