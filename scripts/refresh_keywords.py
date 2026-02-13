from __future__ import annotations

import argparse
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.common import load_system_config, read_csv_rows, resolve_path, write_csv_rows
from scripts.select_topic import REQUIRED_COLUMNS

SEED_TEMPLATE = [
    ("{tool} 活用 事例", "導入効果の具体例を知りたい", 9),
    ("{tool} 料金 比較", "費用対効果を見極めたい", 9),
    ("{tool} 導入 手順", "失敗しない導入手順を確認したい", 10),
    ("{tool} 使い方 初心者", "まず何から始めるべきか知りたい", 8),
    ("{tool} 業務効率化", "実務での時短方法を知りたい", 8),
]


def _normalize_keyword(value: str) -> str:
    return "".join((value or "").split()).lower()


def _existing_set(rows: list[dict[str, str]]) -> set[str]:
    return {_normalize_keyword(row.get("keyword", "")) for row in rows if row.get("keyword")}


def _make_row(keyword: str, intent: str, priority: int) -> dict[str, str]:
    return {
        "keyword": keyword,
        "intent": intent,
        "priority": str(priority),
        "status": "new",
        "last_used_at": "",
    }


def cli() -> int:
    parser = argparse.ArgumentParser(description="Refresh keyword pool from current tools")
    parser.add_argument("--config", default="config/system.yaml")
    parser.add_argument("--keywords", default="data/keywords.csv")
    parser.add_argument("--tools", default="data/tools.csv")
    parser.add_argument("--min-pool", type=int, default=80)
    parser.add_argument("--max-add", type=int, default=40)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_system_config(args.config)
    min_pool = max(1, int(config.get("growth", {}).get("min_keyword_pool", args.min_pool)))
    max_add = max(1, int(config.get("growth", {}).get("keyword_add_limit", args.max_add)))

    keywords = read_csv_rows(args.keywords, REQUIRED_COLUMNS)
    tools = read_csv_rows(
        args.tools,
        [
            "tool_id",
            "name",
            "category",
            "official_url",
            "affiliate_url",
            "status",
            "last_posted_at",
        ],
    )

    active_count = len(
        [
            row
            for row in keywords
            if row.get("status", "").strip().lower() not in {"archived", "paused"}
        ]
    )
    needed = max(0, min_pool - active_count)
    if needed == 0:
        print({"added": 0, "reason": "pool_sufficient", "active_count": active_count})
        return 0

    existing = _existing_set(keywords)
    additions: list[dict[str, str]] = []
    for tool in tools:
        tool_name = tool.get("name", "").strip()
        if not tool_name:
            continue
        for pattern, intent, priority in SEED_TEMPLATE:
            keyword = pattern.format(tool=tool_name)
            key = _normalize_keyword(keyword)
            if key in existing:
                continue
            additions.append(_make_row(keyword, intent, priority))
            existing.add(key)
            if len(additions) >= min(needed, max_add):
                break
        if len(additions) >= min(needed, max_add):
            break

    if additions and not args.dry_run:
        merged = keywords + additions
        write_csv_rows(resolve_path(args.keywords), merged, REQUIRED_COLUMNS)

    print(
        {
            "added": len(additions),
            "active_count_before": active_count,
            "active_count_after": active_count + len(additions),
            "target_min_pool": min_pool,
            "sample": [row["keyword"] for row in additions[:5]],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
