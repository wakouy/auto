from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from scripts.publish import generate_unique_slug
from scripts.quality_gate import run_quality_gate


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
