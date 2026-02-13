from __future__ import annotations

import argparse
import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.common import dump_json, load_system_config, read_csv_rows, resolve_path

TOOLS_COLUMNS = [
    "tool_id",
    "name",
    "category",
    "official_url",
    "affiliate_url",
    "status",
    "last_posted_at",
]
METRICS_COLUMNS = ["date", "pv", "clicks"]
AFFILIATE_READY_STATUSES = {"approved", "active", "affiliate_ready"}


def _is_placeholder_url(url: str) -> bool:
    value = (url or "").strip().lower()
    if not value:
        return True
    return any(
        token in value
        for token in [
            "example.com",
            "replace-me",
            "your-affiliate-link",
            "<",
            ">",
        ]
    )


@dataclass
class MetricsSummary:
    pv: int
    clicks: int


def _safe_int(value: str) -> int:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def _load_recent_metrics(path: Path, days: int) -> MetricsSummary:
    if not path.exists():
        return MetricsSummary(pv=0, clicks=0)

    today = dt.date.today()
    start_day = today - dt.timedelta(days=days - 1)
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
                day = dt.date.fromisoformat(row.get("date", ""))
            except ValueError:
                continue
            if start_day <= day <= today:
                pv_total += _safe_int(row.get("pv", "0"))
                clicks_total += _safe_int(row.get("clicks", "0"))
    return MetricsSummary(pv=pv_total, clicks=clicks_total)


def cli() -> int:
    parser = argparse.ArgumentParser(description="Audit monetization readiness")
    parser.add_argument("--config", default="config/system.yaml")
    parser.add_argument("--tools", default="data/tools.csv")
    parser.add_argument("--metrics", default="data/analytics_metrics.csv")
    parser.add_argument("--window-days", type=int, default=28)
    parser.add_argument("--target-daily-usd", type=float, default=1.0)
    args = parser.parse_args()

    config = load_system_config(args.config)
    tools = read_csv_rows(args.tools, TOOLS_COLUMNS)
    metrics = _load_recent_metrics(resolve_path(args.metrics), days=args.window_days)

    affiliate_ready = [
        row
        for row in tools
        if row.get("status", "").strip().lower() in AFFILIATE_READY_STATUSES
        and not _is_placeholder_url(row.get("affiliate_url", ""))
    ]
    pending_or_placeholder = [
        row
        for row in tools
        if row not in affiliate_ready
    ]

    ctr = (metrics.clicks / metrics.pv) if metrics.pv > 0 else 0.0
    default_epc = float(config["affiliate"]["default_epc_usd"])
    recent_estimated_revenue = metrics.clicks * default_epc
    target_daily_usd = max(0.01, args.target_daily_usd)
    needed_clicks_daily = target_daily_usd / default_epc
    needed_pv_daily = (needed_clicks_daily / ctr) if ctr > 0 else None

    result = {
        "window_days": args.window_days,
        "ready_tools_count": len(affiliate_ready),
        "ready_tools": [row.get("name", "") for row in affiliate_ready],
        "pending_tools_count": len(pending_or_placeholder),
        "pending_tools": [
            {
                "name": row.get("name", ""),
                "status": row.get("status", ""),
                "affiliate_url": row.get("affiliate_url", ""),
            }
            for row in pending_or_placeholder
        ],
        "recent_pv": metrics.pv,
        "recent_clicks": metrics.clicks,
        "recent_ctr": round(ctr * 100, 2),
        "default_epc_usd": default_epc,
        "recent_estimated_revenue_usd": round(recent_estimated_revenue, 4),
        "target_daily_usd": target_daily_usd,
        "needed_clicks_daily": round(needed_clicks_daily, 2),
        "needed_pv_daily_at_current_ctr": (
            round(needed_pv_daily, 2) if needed_pv_daily is not None else None
        ),
        "actions": [
            "tools.csv の affiliate_url を実リンクに更新",
            "承認済み案件の status を approved か active に更新",
            "Daily Publish を毎日実行し、記事数を増やす",
        ],
    }
    print(dump_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
