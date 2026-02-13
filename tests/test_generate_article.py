from __future__ import annotations

from scripts.generate_article import generate_article, optimize_title_for_ctr


def test_generate_article_fallback_contains_two_ctas() -> None:
    draft = generate_article(
        keyword="AI導入",
        intent="導入手順を確認したい",
        tool_name="ココナラ",
        cta_url="https://px.a8.net/svt/ejp?a8mat=TEST",
        disclosure_text="本記事には広告・アフィリエイトリンクが含まれます",
        min_chars=1400,
        model="Qwen/Qwen2.5-7B-Instruct",
        provider="huggingface_free",
        force_template=True,
    )

    assert draft.body.count('rel="sponsored nofollow"') >= 2


def test_optimize_title_for_ctr_limits_length_and_keeps_keyword() -> None:
    title = optimize_title_for_ctr(
        title="長すぎる仮タイトル",
        keyword="AI導入 チェックリスト",
        intent="失敗しない導入手順を確認したい",
        tool_name="ココナラ",
        max_chars=48,
    )

    assert "AI導入" in title
    assert len(title) <= 48
