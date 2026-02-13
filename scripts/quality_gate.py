from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

if __package__ in {None, ""}:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.common import dump_json, load_system_config

BANNED_PHRASES = [
    "必ず治る",
    "絶対に治る",
    "100%儲かる",
    "元本保証",
    "確実に勝てる",
    "副作用はありません",
    "絶対に稼げる",
]


@dataclass
class GateResult:
    passed: bool
    issues: list[str]


def _char_count(text: str) -> int:
    no_front_matter = re.sub(r"^---[\s\S]*?---\n", "", text, count=1)
    no_markup = re.sub(r"<[^>]+>", "", no_front_matter)
    no_space = re.sub(r"\s+", "", no_markup)
    return len(no_space)


def _duplicate_ratio(text: str) -> float:
    sentences = [s.strip() for s in re.split(r"[。\n]", text) if s.strip()]
    if not sentences:
        return 0.0
    seen: dict[str, int] = {}
    duplicates = 0
    for sentence in sentences:
        seen[sentence] = seen.get(sentence, 0) + 1
    for count in seen.values():
        if count > 1:
            duplicates += count - 1
    return duplicates / len(sentences)


def _find_external_anchors(text: str) -> list[tuple[str, str]]:
    anchors: list[tuple[str, str]] = []
    for match in re.finditer(r"<a\s+([^>]*href=\"https?://[^\"]+\"[^>]*)>", text):
        attrs = match.group(1)
        href_match = re.search(r'href=\"([^\"]+)\"', attrs)
        href = href_match.group(1) if href_match else ""
        anchors.append((href, attrs))
    return anchors


def run_quality_gate(
    text: str,
    min_chars: int,
    disclosure_text: str,
    max_duplicate_ratio: float = 0.35,
) -> GateResult:
    issues: list[str] = []

    char_count = _char_count(text)
    if char_count < min_chars:
        issues.append(f"本文文字数が不足: {char_count} < {min_chars}")

    ratio = _duplicate_ratio(text)
    if ratio > max_duplicate_ratio:
        issues.append(f"重複率が高すぎます: {ratio:.2%} > {max_duplicate_ratio:.2%}")

    for phrase in BANNED_PHRASES:
        if phrase in text:
            issues.append(f"禁止表現を検出: {phrase}")

    if disclosure_text not in text:
        issues.append("広告表記文が本文に存在しません")

    md_link_matches = re.findall(r"\[[^\]]+\]\(https?://[^\)]+\)", text)
    if md_link_matches:
        issues.append("Markdown形式の外部リンクを検出。CTAはHTML <a> で rel を指定してください")

    anchors = _find_external_anchors(text)
    if not anchors:
        issues.append("外部リンクCTAが存在しません")
    for href, attrs in anchors:
        rel_match = re.search(r'rel=\"([^\"]+)\"', attrs)
        rel_values = set((rel_match.group(1).lower().split() if rel_match else []))
        if "sponsored" not in rel_values or "nofollow" not in rel_values:
            issues.append(f"外部リンク({href})に rel=\"sponsored nofollow\" が未設定")

    return GateResult(passed=not issues, issues=issues)


def cli() -> int:
    parser = argparse.ArgumentParser(description="Quality gate for generated post")
    parser.add_argument("--file", required=True)
    parser.add_argument("--config", default="config/system.yaml")
    args = parser.parse_args()

    config = load_system_config(args.config)
    with open(args.file, "r", encoding="utf-8") as fh:
        text = fh.read()

    result = run_quality_gate(
        text=text,
        min_chars=int(config["content"]["min_chars"]),
        disclosure_text=str(config["affiliate"]["disclosure_text"]),
    )
    print(dump_json({"passed": result.passed, "issues": result.issues}))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(cli())
