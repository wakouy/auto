from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from scripts.common import load_system_config
from scripts.publish import (
    KEYWORD_COLUMNS,
    TOOLS_COLUMNS,
    build_post_markdown,
    generate_unique_slug,
    resolve_cta_url,
    select_tool,
)
from scripts.generate_article import generate_article
from scripts.quality_gate import run_quality_gate
from scripts.select_topic import select_topic


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_pipeline_select_generate_gate_publish(tmp_path: Path) -> None:
    root = tmp_path
    (root / "config").mkdir()
    (root / "data").mkdir()
    posts_dir = root / "content" / "posts"
    posts_dir.mkdir(parents=True)

    (root / "config" / "system.yaml").write_text(
        """
site:
  base_url: "https://example.github.io/auto"
  title: "Auto Revenue Lab"
content:
  language: "ja"
  min_chars: 1400
  posts_per_run: 1
generation:
  provider: "huggingface_free"
  model: "Qwen/Qwen2.5-7B-Instruct"
affiliate:
  disclosure_text: "本記事には広告・アフィリエイトリンクが含まれます"
  default_epc_usd: 0.01
schedule:
  publish_cron_utc: "0 0 * * *"
  weekly_report_cron_utc: "0 1 * * 1"
""".strip(),
        encoding="utf-8",
    )

    _write_csv(
        root / "data" / "keywords.csv",
        KEYWORD_COLUMNS,
        [
            {
                "keyword": "AI議事録 自動化",
                "intent": "導入判断をしたい",
                "priority": "10",
                "status": "new",
                "last_used_at": "",
            }
        ],
    )
    _write_csv(
        root / "data" / "tools.csv",
        TOOLS_COLUMNS,
        [
            {
                "tool_id": "tool-1",
                "name": "Canva",
                "category": "design",
                "official_url": "https://www.canva.com",
                "affiliate_url": "https://example.com/a8/canva",
                "status": "approved",
                "last_posted_at": "",
            }
        ],
    )

    config = load_system_config(root / "config" / "system.yaml")
    topic = select_topic(
        [
            {
                "keyword": "AI議事録 自動化",
                "intent": "導入判断をしたい",
                "priority": "10",
                "status": "new",
                "last_used_at": "",
            }
        ]
    )
    assert topic is not None

    tool = select_tool(
        [
            {
                "tool_id": "tool-1",
                "name": "Canva",
                "category": "design",
                "official_url": "https://www.canva.com",
                "affiliate_url": "https://example.com/a8/canva",
                "status": "approved",
                "last_posted_at": "",
            }
        ]
    )
    cta_url = resolve_cta_url(tool)

    draft = generate_article(
        keyword=topic["keyword"],
        intent=topic["intent"],
        tool_name=tool["name"],
        cta_url=cta_url,
        disclosure_text=config["affiliate"]["disclosure_text"],
        min_chars=int(config["content"]["min_chars"]),
        model=config["generation"]["model"],
        provider=config["generation"]["provider"],
        force_template=True,
    )

    slug = generate_unique_slug("ai-tool", posts_dir, date_prefix="2026-02-13")
    markdown = build_post_markdown(
        title=draft.title,
        now=dt.datetime(2026, 2, 13, 9, 0, 0),
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
        disclosure_text=config["affiliate"]["disclosure_text"],
    )
    assert gate.passed

    output = posts_dir / "2026-02-13-ai-tool.md"
    output.write_text(markdown, encoding="utf-8")
    assert output.exists()
