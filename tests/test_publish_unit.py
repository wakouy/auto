from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from scripts.publish import (
    generate_unique_slug,
    reserve_unique_slug,
    resolve_cta_url,
    select_tool,
)
from scripts.quality_gate import run_quality_gate
from scripts.common import slugify


def test_generate_unique_slug_adds_suffix_when_duplicate(tmp_path: Path) -> None:
    posts_dir = tmp_path / "content" / "posts"
    posts_dir.mkdir(parents=True)
    (posts_dir / "2026-02-13-ai-tool.md").write_text("x", encoding="utf-8")

    slug = generate_unique_slug("ai-tool", posts_dir, date_prefix="2026-02-13")

    assert slug == "ai-tool-2"


def test_quality_gate_fails_without_disclosure() -> None:
    text = """---
layout: post
---

本文だけで広告表記がない記事。

<p><a href=\"https://example.com\" rel=\"sponsored nofollow\">リンク</a></p>
"""
    result = run_quality_gate(
        text=text,
        min_chars=10,
        disclosure_text="本記事には広告・アフィリエイトリンクが含まれます",
    )

    assert not result.passed
    assert any("広告表記文" in issue for issue in result.issues)


def test_select_tool_prefers_affiliate_ready_real_link() -> None:
    rows = [
        {
            "tool_id": "tool-001",
            "name": "Pending Tool",
            "category": "x",
            "official_url": "https://official.example/a",
            "affiliate_url": "https://example.com/a8/pending",
            "status": "pending",
            "last_posted_at": "2026-01-01",
        },
        {
            "tool_id": "tool-002",
            "name": "Approved Tool",
            "category": "x",
            "official_url": "https://official.example/b",
            "affiliate_url": "https://a8.net/real-link",
            "status": "approved",
            "last_posted_at": "2026-02-01",
        },
    ]

    selected = select_tool(rows)
    assert selected["tool_id"] == "tool-002"
    assert resolve_cta_url(selected) == "https://a8.net/real-link"


def test_resolve_cta_url_falls_back_when_affiliate_is_placeholder() -> None:
    tool = {
        "tool_id": "tool-009",
        "name": "Demo",
        "category": "x",
        "official_url": "https://official.example/demo",
        "affiliate_url": "https://example.com/a8/demo",
        "status": "approved",
        "last_posted_at": "",
    }
    assert resolve_cta_url(tool) == "https://official.example/demo"


def test_select_tool_respects_excluded_ids() -> None:
    rows = [
        {
            "tool_id": "tool-1",
            "name": "A",
            "category": "x",
            "official_url": "https://official.example/a",
            "affiliate_url": "https://a8.net/a",
            "status": "approved",
            "last_posted_at": "2026-02-10",
        },
        {
            "tool_id": "tool-2",
            "name": "B",
            "category": "x",
            "official_url": "https://official.example/b",
            "affiliate_url": "https://a8.net/b",
            "status": "approved",
            "last_posted_at": "2026-02-10",
        },
    ]
    selected = select_tool(rows, excluded_tool_ids={"tool-1"})
    assert selected["tool_id"] == "tool-2"


def test_reserve_unique_slug_avoids_duplicate_in_same_run(tmp_path: Path) -> None:
    posts_dir = tmp_path / "content" / "posts"
    posts_dir.mkdir(parents=True)
    reserved: set[str] = set()

    first = reserve_unique_slug("ai", posts_dir, "2026-02-14", reserved)
    second = reserve_unique_slug("ai", posts_dir, "2026-02-14", reserved)

    assert first == "ai"
    assert second == "ai-2"


def test_slugify_non_ascii_uses_hash_prefix() -> None:
    slug = slugify("日本語 キーワード")
    assert slug.startswith("kw-")
