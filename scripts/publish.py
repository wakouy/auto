from __future__ import annotations

import argparse
import calendar
import datetime as dt
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.common import (
    dump_json,
    load_system_config,
    read_csv_rows,
    resolve_path,
    slugify,
    today_jst,
    write_csv_rows,
)
from scripts.generate_article import generate_article
from scripts.quality_gate import run_quality_gate
from scripts.select_topic import REQUIRED_COLUMNS as KEYWORD_COLUMNS
from scripts.select_topic import mark_topic_used, select_topic

TOOLS_COLUMNS = [
    "tool_id",
    "name",
    "category",
    "official_url",
    "affiliate_url",
    "status",
    "last_posted_at",
]
COST_COLUMNS = ["month", "total_usd"]
AFFILIATE_READY_STATUSES = {"approved", "active", "affiliate_ready"}


def _is_placeholder_url(url: str) -> bool:
    value = (url or "").strip().lower()
    if not value:
        return True
    placeholders = [
        "example.com",
        "replace-me",
        "your-affiliate-link",
        "<",
        ">",
    ]
    return any(token in value for token in placeholders)


def _parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return dt.date(1970, 1, 1)


def select_tool(rows: list[dict[str, str]]) -> dict[str, str]:
    if not rows:
        raise ValueError("tools.csv has no rows")
    monetizable_rows = [
        row
        for row in rows
        if row.get("status", "").strip().lower() in AFFILIATE_READY_STATUSES
        and not _is_placeholder_url(row.get("affiliate_url", ""))
    ]
    candidate_rows = monetizable_rows or rows
    sorted_rows = sorted(
        candidate_rows, key=lambda r: _parse_date(r.get("last_posted_at", ""))
    )
    return sorted_rows[0]


def resolve_cta_url(tool: dict[str, str]) -> str:
    status = tool.get("status", "").strip().lower()
    affiliate_url = tool.get("affiliate_url", "").strip()
    official_url = tool.get("official_url", "").strip()

    if (
        status in AFFILIATE_READY_STATUSES
        and affiliate_url
        and not _is_placeholder_url(affiliate_url)
    ):
        return affiliate_url
    if official_url:
        return official_url
    if affiliate_url and not _is_placeholder_url(affiliate_url):
        return affiliate_url
    raise ValueError(f"tool '{tool.get('name', 'unknown')}' has no usable URL")


def generate_unique_slug(base_slug: str, posts_dir: Path, date_prefix: str) -> str:
    posts_dir.mkdir(parents=True, exist_ok=True)
    candidate = base_slug
    suffix = 2
    existing_names = {path.stem for path in posts_dir.glob("*.md")}

    while f"{date_prefix}-{candidate}" in existing_names:
        candidate = f"{base_slug}-{suffix}"
        suffix += 1

    return candidate


def _yaml_escape(value: str) -> str:
    return value.replace('"', '\\"')


def build_post_markdown(
    *,
    title: str,
    now: dt.datetime,
    slug: str,
    keyword: str,
    intent: str,
    tool: dict[str, str],
    cta_url: str,
    body: str,
) -> str:
    front_matter = (
        "---\n"
        "layout: post\n"
        f'title: "{_yaml_escape(title)}"\n'
        f"date: {now.isoformat()}\n"
        f"permalink: /posts/{slug}/\n"
        "autogen_post: true\n"
        f'keyword: "{_yaml_escape(keyword)}"\n'
        f'intent: "{_yaml_escape(intent)}"\n'
        f'tool_id: "{_yaml_escape(tool.get("tool_id", ""))}"\n'
        f'tool_name: "{_yaml_escape(tool.get("name", ""))}"\n'
        f'cta_url: "{_yaml_escape(cta_url)}"\n'
        "---\n\n"
    )
    return front_matter + body.strip() + "\n"


def _within_month(day: dt.date, month_str: str) -> bool:
    if not month_str:
        return False
    try:
        year, month = month_str.split("-", 1)
        return day.year == int(year) and day.month == int(month)
    except (ValueError, TypeError):
        return False


def should_skip_for_budget(
    today: dt.date,
    costs_rows: list[dict[str, str]],
    max_monthly_usd: float,
) -> bool:
    current_month_total = 0.0
    for row in costs_rows:
        if _within_month(today, row.get("month", "")):
            try:
                current_month_total += float(row.get("total_usd", "0") or "0")
            except ValueError:
                continue
    if current_month_total <= max_monthly_usd:
        return False
    return today.day % 2 == 1


def _update_tool_last_posted(
    rows: list[dict[str, str]], selected_tool_id: str, posted_at: dt.datetime
) -> list[dict[str, str]]:
    new_rows: list[dict[str, str]] = []
    for row in rows:
        copied = dict(row)
        if row.get("tool_id") == selected_tool_id:
            copied["last_posted_at"] = posted_at.date().isoformat()
        new_rows.append(copied)
    return new_rows


def _generate_one_post(
    *,
    config: dict[str, object],
    now: dt.datetime,
    keywords: list[dict[str, str]],
    tools: list[dict[str, str]],
    posts_dir: Path,
    force_template: bool,
    write: bool,
) -> tuple[dict[str, str] | None, list[dict[str, str]], list[dict[str, str]]]:
    topic = select_topic(keywords)
    if topic is None:
        return None, keywords, tools

    tool = select_tool(tools)
    cta_url = resolve_cta_url(tool)

    draft = generate_article(
        keyword=topic["keyword"],
        intent=topic["intent"],
        tool_name=tool["name"],
        cta_url=cta_url,
        disclosure_text=str(config["affiliate"]["disclosure_text"]),
        min_chars=int(config["content"]["min_chars"]),
        model=str(config["generation"]["model"]),
        provider=str(config["generation"]["provider"]),
        force_template=force_template,
    )

    slug_base = slugify(f"{topic['keyword']}-{tool['name']}")
    date_prefix = now.date().isoformat()
    slug = generate_unique_slug(slug_base, posts_dir, date_prefix=date_prefix)

    markdown = build_post_markdown(
        title=draft.title,
        now=now,
        slug=slug,
        keyword=topic["keyword"],
        intent=topic["intent"],
        tool=tool,
        cta_url=cta_url,
        body=draft.body,
    )

    gate = run_quality_gate(
        text=markdown,
        min_chars=int(config["content"]["min_chars"]),
        disclosure_text=str(config["affiliate"]["disclosure_text"]),
    )
    if not gate.passed:
        raise RuntimeError("Quality gate failed: " + " | ".join(gate.issues))

    output_file = posts_dir / f"{date_prefix}-{slug}.md"
    if write:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(markdown, encoding="utf-8")

    updated_keywords = mark_topic_used(keywords, topic["keyword"], now)
    updated_tools = _update_tool_last_posted(tools, tool["tool_id"], now)
    result = {
        "output": str(output_file),
        "title": draft.title,
        "keyword": topic["keyword"],
        "tool": tool["name"],
        "cta_url": cta_url,
        "used_model": str(draft.used_model).lower(),
    }
    return result, updated_keywords, updated_tools


def cli() -> int:
    parser = argparse.ArgumentParser(description="Generate and publish one post")
    parser.add_argument("--config", default="config/system.yaml")
    parser.add_argument("--keywords", default="data/keywords.csv")
    parser.add_argument("--tools", default="data/tools.csv")
    parser.add_argument("--costs", default="data/costs.csv")
    parser.add_argument("--posts-dir", default="content/posts")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    config = load_system_config(args.config)
    now = today_jst()
    today = now.date()

    keywords = read_csv_rows(args.keywords, KEYWORD_COLUMNS)
    tools = read_csv_rows(args.tools, TOOLS_COLUMNS)

    costs_path = resolve_path(args.costs)
    costs_rows = read_csv_rows(costs_path, COST_COLUMNS) if costs_path.exists() else []

    max_monthly_usd = float(config.get("cost", {}).get("max_monthly_usd", 5.0))
    if should_skip_for_budget(today, costs_rows, max_monthly_usd=max_monthly_usd):
        print(
            dump_json(
                {
                    "skipped": True,
                    "reason": "budget_limit_even_day_only",
                    "today": today.isoformat(),
                    "month": f"{today.year}-{today.month:02d}",
                }
            )
        )
        return 0

    posts_dir = resolve_path(args.posts_dir)
    posts_per_run = max(1, int(config["content"]["posts_per_run"]))
    current_keywords = keywords
    current_tools = tools
    generated: list[dict[str, str]] = []

    for index in range(posts_per_run):
        result, current_keywords, current_tools = _generate_one_post(
            config=config,
            now=now + dt.timedelta(minutes=index),
            keywords=current_keywords,
            tools=current_tools,
            posts_dir=posts_dir,
            force_template=args.mock,
            write=not args.dry_run,
        )
        if result is None:
            break
        generated.append(result)

    if not generated:
        print(dump_json({"skipped": True, "reason": "no_topic_available"}))
        return 0

    if not args.dry_run:
        write_csv_rows(args.keywords, current_keywords, KEYWORD_COLUMNS)
        write_csv_rows(args.tools, current_tools, TOOLS_COLUMNS)

    month_last_day = calendar.monthrange(today.year, today.month)[1]
    print(
        dump_json(
            {
                "skipped": False,
                "count": len(generated),
                "posts": generated,
                "month_end": f"{today.year}-{today.month:02d}-{month_last_day:02d}",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
