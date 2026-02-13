from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import textwrap
from dataclasses import dataclass

import requests

if __package__ in {None, ""}:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.common import dump_json


@dataclass
class ArticleDraft:
    title: str
    body: str
    summary: str
    used_model: bool


def _compact_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def optimize_title_for_ctr(
    *,
    title: str,
    keyword: str,
    intent: str,
    tool_name: str,
    max_chars: int = 48,
) -> str:
    year = dt.datetime.now().year
    keyword_clean = _compact_spaces(keyword)
    intent_clean = _compact_spaces(intent)
    current = _compact_spaces(title)

    if "比較" in keyword_clean or "比較" in intent_clean:
        hook = "比較ポイント5つ"
    elif "料金" in keyword_clean or "費用" in keyword_clean or "料金" in intent_clean:
        hook = "料金と失敗しない選び方"
    elif "初心者" in keyword_clean or "初" in intent_clean:
        hook = "初心者向け導入手順"
    elif "活用" in keyword_clean or "事例" in keyword_clean:
        hook = "活用事例3選"
    else:
        hook = "失敗しない導入チェックリスト"

    candidate = f"【{year}年版】{keyword_clean} {hook}｜{tool_name}"
    if len(candidate) <= max_chars:
        return candidate

    candidate = f"【{year}年版】{keyword_clean} {hook}"
    if len(candidate) <= max_chars:
        return candidate

    if current and keyword_clean in current and len(current) <= max_chars:
        return current

    if len(keyword_clean) > max_chars - 9:
        keyword_clean = keyword_clean[: max_chars - 10] + "…"
    return f"【{year}年版】{keyword_clean}"


def _build_prompt(
    keyword: str,
    intent: str,
    tool_name: str,
    cta_url: str,
    disclosure_text: str,
    min_chars: int,
) -> str:
    return textwrap.dedent(
        f"""
        あなたは日本語SEOライターです。次の条件で記事を作成してください。
        - キーワード: {keyword}
        - 検索意図: {intent}
        - 紹介ツール名: {tool_name}
        - 最低文字数: {min_chars}文字
        - 断定的な医療・投資助言は禁止
        - 過剰な誇張表現は禁止
        - 記事冒頭に次の広告表記文を自然に入れる: {disclosure_text}
        - CTAはHTMLリンクで1つ以上含め、必ず rel=\"sponsored nofollow\" を設定する
        - CTA URLは {cta_url}

        出力形式:
        1行目: タイトル
        2行目以降: 本文
        """
    ).strip()


def _call_huggingface(model: str, token: str, prompt: str, timeout: int = 60) -> str:
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 1500,
            "temperature": 0.7,
            "return_full_text": False,
        },
    }
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(data["error"])

    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            generated = first.get("generated_text") or first.get("summary_text") or ""
            if generated:
                return generated.strip()
    if isinstance(data, dict) and data.get("generated_text"):
        return str(data["generated_text"]).strip()

    raise RuntimeError("Unexpected Hugging Face response format")


def _ensure_cta_block(tool_name: str, cta_url: str) -> str:
    return (
        f'<p><a href="{cta_url}" rel="sponsored nofollow" '
        f'target="_blank">{tool_name}の公式ページを見る</a></p>'
    )


def _cta_count(text: str) -> int:
    return len(re.findall(r'<a\s+[^>]*rel=\"[^\"]*sponsored[^\"]*nofollow[^\"]*\"[^>]*>', text))


def _ensure_min_cta_blocks(body: str, tool_name: str, cta_url: str, min_count: int = 2) -> str:
    cta = _ensure_cta_block(tool_name, cta_url)
    paragraphs = [part.strip() for part in body.split("\n\n") if part.strip()]
    if not paragraphs:
        paragraphs = [body.strip()]

    while _cta_count("\n\n".join(paragraphs)) < min_count:
        insert_pos = min(2, len(paragraphs))
        paragraphs.insert(insert_pos, cta)
    return "\n\n".join(paragraphs)


def _visible_char_count(text: str) -> int:
    no_markup = re.sub(r"<[^>]+>", "", text)
    no_space = re.sub(r"\s+", "", no_markup)
    return len(no_space)


def _fallback_article(
    keyword: str,
    intent: str,
    tool_name: str,
    cta_url: str,
    disclosure_text: str,
    min_chars: int,
) -> ArticleDraft:
    title = optimize_title_for_ctr(
        title="",
        keyword=keyword,
        intent=intent,
        tool_name=tool_name,
    )
    sections = [
        f"{disclosure_text}。本記事では、{keyword}を検討している方に向けて、{intent}を前提に導入までの流れを具体化します。AIツールは機能比較だけで判断すると失敗しやすいため、業務フロー、教育コスト、既存システムとの接続性、そして継続運用の観点を同時に評価することが重要です。",
        _ensure_cta_block(tool_name, cta_url),
        f"最初に確認すべきは、{tool_name}で何を短縮したいのかを一文で定義することです。たとえば『週次レポート作成の所要時間を半分にする』『問い合わせ一次回答を平日日中に5分以内で返す』のように、対象業務と数値を明確にすると、機能の過不足を定量比較できます。目的が曖昧なまま試すと、便利そうに見える機能へ時間を使い、効果測定が不能になります。",
        f"次に、入力データの品質を点検します。AIツールの成果は、モデル性能だけでなく、与えるコンテキストの正確性に依存します。命名規則が統一されていないファイル、更新履歴のないドキュメント、重複した顧客情報が混在している状態では、回答の一貫性が崩れます。導入前に『最新の正データはどこか』『更新責任者は誰か』を固定し、運用ルールを最小限で整えると、初期効果が出やすくなります。",
        f"費用評価では、月額料金だけでなく運用コストを含めて見積もるべきです。具体的には、管理者の監視時間、プロンプトの保守、チーム教育、障害時の代替フローを合算します。短期的には低価格プランが有利でも、制限で業務が分断されると結果的に高く付きます。反対に、必要最小限の機能で小さく始め、効果が確認できたら段階的に拡張する方式は失敗確率を下げます。",
        f"セキュリティ面では、機密情報の扱いポリシーを事前に定めてください。顧客個人情報、契約金額、未公開情報は入力禁止にし、匿名化や要約化を標準手順に組み込むと、事故リスクを大きく減らせます。また、監査ログの保存期間、アクセス権限、退職者アカウントの無効化を明文化しておくと、運用の再現性が上がります。",
        f"実装段階では、最初の2週間を検証期間として、毎週同じ指標を測定するのが有効です。推奨指標は、作業時間削減率、一次回答までの時間、出力の修正回数、担当者満足度です。数値が改善しない場合は、ツール変更より先に入力形式とプロンプトを見直すと改善余地が見つかりやすいです。",
        f"最後に、{keyword}導入を成功させる鍵は『小さな成功体験を反復する運用設計』です。機能の多さではなく、現場で継続できる運用を優先してください。下記リンクから{tool_name}の現行仕様を確認し、まずは1つの業務に限定して試験導入するのが最短ルートです。",
        _ensure_cta_block(tool_name, cta_url),
    ]
    supplements = [
        f"実行テンプレートとして、初週は『現状工数の計測』『試験導入対象の1業務決定』『入力データ整備』『担当者レビュー』の4点に限定してください。対象を増やしすぎると、どこが改善したのか判定不能になります。週末に振り返るときは、削減時間だけでなく修正時間も記録すると、見かけ上の効率化を排除できます。",
        f"比較時の評価表は、価格、精度、学習負荷、連携性、監査性の5軸で作るのが実務的です。各軸を5点満点で評価し、導入目的に合わせて重みを付けると意思決定が速くなります。{tool_name}を候補にする場合も、他候補と同じ表で比較し、主観ではなく指標で選ぶことが重要です。",
        f"運用開始後は、毎週の定例で『使った機能』『使わなかった機能』『改善要望』を簡潔に収集し、次週の設定変更を1つだけ実施します。変更点を増やしすぎると因果が追えません。小さな改善を継続すると、チーム全体で{keyword}の活用度が安定して上がります。",
    ]
    while _visible_char_count("\n\n".join(sections)) < (min_chars + 80):
        sections.extend(supplements)
    body = _ensure_min_cta_blocks("\n\n".join(sections), tool_name, cta_url, min_count=2)
    summary = f"{keyword}の導入判断で失敗しないための実務チェックポイントを整理。"
    return ArticleDraft(title=title, body=body, summary=summary, used_model=False)


def _parse_model_output(raw_text: str, fallback_title: str) -> tuple[str, str]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return fallback_title, raw_text
    title = lines[0]
    body = "\n\n".join(lines[1:]) if len(lines) > 1 else raw_text
    return title, body


def generate_article(
    keyword: str,
    intent: str,
    tool_name: str,
    cta_url: str,
    disclosure_text: str,
    min_chars: int,
    model: str,
    provider: str,
    force_template: bool = False,
) -> ArticleDraft:
    fallback = _fallback_article(
        keyword,
        intent,
        tool_name,
        cta_url,
        disclosure_text,
        min_chars,
    )

    if force_template:
        return fallback

    if provider != "huggingface_free":
        return fallback

    token = os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
    if not token:
        return fallback

    prompt = _build_prompt(
        keyword=keyword,
        intent=intent,
        tool_name=tool_name,
        cta_url=cta_url,
        disclosure_text=disclosure_text,
        min_chars=min_chars,
    )
    try:
        generated_text = _call_huggingface(model=model, token=token, prompt=prompt)
        raw_title, body = _parse_model_output(generated_text, fallback.title)
        title = optimize_title_for_ctr(
            title=raw_title,
            keyword=keyword,
            intent=intent,
            tool_name=tool_name,
        )
        if disclosure_text not in body:
            body = f"{disclosure_text}\n\n{body}"
        body = _ensure_min_cta_blocks(body, tool_name, cta_url, min_count=2)
        if len(body) < min_chars:
            return fallback
        return ArticleDraft(title=title, body=body, summary=fallback.summary, used_model=True)
    except Exception:
        return fallback


def cli() -> int:
    parser = argparse.ArgumentParser(description="Generate one article draft")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--intent", required=True)
    parser.add_argument("--tool-name", required=True)
    parser.add_argument("--cta-url", required=True)
    parser.add_argument("--disclosure-text", required=True)
    parser.add_argument("--min-chars", type=int, default=1400)
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", default="huggingface_free")
    parser.add_argument("--force-template", action="store_true")
    args = parser.parse_args()

    draft = generate_article(
        keyword=args.keyword,
        intent=args.intent,
        tool_name=args.tool_name,
        cta_url=args.cta_url,
        disclosure_text=args.disclosure_text,
        min_chars=args.min_chars,
        model=args.model,
        provider=args.provider,
        force_template=args.force_template,
    )
    print(
        dump_json(
            {
                "title": draft.title,
                "summary": draft.summary,
                "body": draft.body,
                "used_model": draft.used_model,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
