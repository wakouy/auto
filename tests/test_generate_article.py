from __future__ import annotations

from scripts.generate_article import generate_article


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
