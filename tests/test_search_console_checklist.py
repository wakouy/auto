from __future__ import annotations

from scripts.search_console_checklist import build_checks, render_markdown


def test_build_checks_includes_affiliate_ready_status() -> None:
    config = {
        "site": {"base_url": "https://example.com"},
    }
    site_config = {"ga4_measurement_id": "G-TEST1234"}
    tools = [
        {
            "tool_id": "tool-1",
            "name": "Canva",
            "category": "design",
            "official_url": "https://www.canva.com",
            "affiliate_url": "https://px.a8.net/svt/ejp?a8mat=TEST",
            "status": "approved",
            "last_posted_at": "",
        }
    ]

    checks = build_checks(
        config=config,
        site_config=site_config,
        tools=tools,
        live_check=False,
    )
    assert any(
        item.name == "収益化リンク(approved/active)が1件以上" and item.passed
        for item in checks
    )


def test_render_markdown_has_manual_steps() -> None:
    content = render_markdown(
        base_url="https://example.com",
        checks=[],
    )

    assert "Search Console 提出チェックリスト" in content
    assert "手動チェック" in content
    assert "sitemap.xml" in content
