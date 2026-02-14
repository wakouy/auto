from __future__ import annotations

import argparse
import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

import requests

if __package__ in {None, ""}:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.ad_revenue_validate import read_rows as read_ad_revenue_rows
from scripts.common import dump_json, load_system_config, load_yaml, read_csv_rows, resolve_path
from scripts.monetization_audit import TOOLS_COLUMNS

ADSENSE_PUBLISHER_PATTERN = re.compile(r"^ca-pub-\d{16}$")


@dataclass
class CheckItem:
    name: str
    passed: bool
    detail: str


def _is_placeholder_url(url: str) -> bool:
    value = (url or "").strip().lower()
    if not value:
        return True
    return any(
        token in value
        for token in [
            "example.com",
            "replace-me",
            "your-affiliate-link",
            "<",
            ">",
        ]
    )


def _http_ok(url: str, timeout: int = 10) -> tuple[bool, str]:
    try:
        res = requests.get(url, timeout=timeout)
        return (res.status_code < 400, f"HTTP {res.status_code}")
    except Exception as exc:  # pragma: no cover
        return (False, f"error: {type(exc).__name__}")


def build_checks(
    *,
    config: dict[str, object],
    site_config: dict[str, object],
    tools: list[dict[str, str]],
    live_check: bool,
) -> list[CheckItem]:
    base_url = str(config["site"]["base_url"]).rstrip("/")
    measurement_id = str(site_config.get("ga4_measurement_id", "")).strip()
    adsense_publisher_id = str(site_config.get("adsense_publisher_id", "")).strip()
    layout_text = resolve_path("_layouts/default.html").read_text(encoding="utf-8")
    ad_revenue_path = resolve_path(
        str(config.get("reporting", {}).get("ad_revenue_csv", "data/ad_revenue.csv"))
    )

    ad_revenue_valid = False
    ad_revenue_detail = str(ad_revenue_path)
    if ad_revenue_path.exists():
        try:
            read_ad_revenue_rows(ad_revenue_path)
            ad_revenue_valid = True
            ad_revenue_detail = f"{ad_revenue_path} (valid)"
        except ValueError as exc:
            ad_revenue_detail = f"{ad_revenue_path} ({exc})"

    checks: list[CheckItem] = [
        CheckItem(
            name="site.base_url が https で設定済み",
            passed=base_url.startswith("https://"),
            detail=base_url,
        ),
        CheckItem(
            name="GA4 Measurement ID が設定済み",
            passed=measurement_id.startswith("G-"),
            detail=measurement_id or "未設定",
        ),
        CheckItem(
            name="AdSense Publisher ID 形式が妥当",
            passed=bool(ADSENSE_PUBLISHER_PATTERN.match(adsense_publisher_id)),
            detail=adsense_publisher_id or "未設定",
        ),
        CheckItem(
            name="robots.txt がリポジトリに存在",
            passed=resolve_path("robots.txt").exists(),
            detail=str(resolve_path("robots.txt")),
        ),
        CheckItem(
            name="sitemap.xml がリポジトリに存在",
            passed=resolve_path("sitemap.xml").exists(),
            detail=str(resolve_path("sitemap.xml")),
        ),
        CheckItem(
            name="広告表記ページが存在",
            passed=resolve_path("content/legal/disclosure.md").exists(),
            detail=str(resolve_path("content/legal/disclosure.md")),
        ),
        CheckItem(
            name="プライバシーポリシーが存在",
            passed=resolve_path("content/legal/privacy.md").exists(),
            detail=str(resolve_path("content/legal/privacy.md")),
        ),
        CheckItem(
            name="利用規約ページが存在",
            passed=resolve_path("content/legal/terms.md").exists(),
            detail=str(resolve_path("content/legal/terms.md")),
        ),
        CheckItem(
            name="Cookie同意バナー(同意前GA停止)が実装済み",
            passed=(
                "cookie-consent-banner" in layout_text
                and "data-cookie-action=\"accept\"" in layout_text
                and "if (hasConsent())" in layout_text
            ),
            detail="_layouts/default.html",
        ),
        CheckItem(
            name="同意後のみAdSense読込が実装済み",
            passed=(
                "function loadAdsense()" in layout_text
                and "loadAdsense();" in layout_text
                and "if (hasConsent())" in layout_text
            ),
            detail="_layouts/default.html",
        ),
        CheckItem(
            name="data/ad_revenue.csv が存在し形式が妥当",
            passed=ad_revenue_valid,
            detail=ad_revenue_detail,
        ),
    ]

    ready_tools = [
        row
        for row in tools
        if row.get("status", "").strip().lower() in {"approved", "active", "affiliate_ready"}
        and not _is_placeholder_url(row.get("affiliate_url", ""))
    ]
    checks.append(
        CheckItem(
            name="収益化リンク(approved/active)が1件以上",
            passed=len(ready_tools) > 0,
            detail=f"{len(ready_tools)}件",
        )
    )

    if live_check:
        root_ok, root_detail = _http_ok(base_url)
        sitemap_ok, sitemap_detail = _http_ok(f"{base_url}/sitemap.xml")
        robots_ok, robots_detail = _http_ok(f"{base_url}/robots.txt")
        checks.extend(
            [
                CheckItem(
                    name="公開サイトが到達可能",
                    passed=root_ok,
                    detail=root_detail,
                ),
                CheckItem(
                    name="公開 sitemap.xml が到達可能",
                    passed=sitemap_ok,
                    detail=sitemap_detail,
                ),
                CheckItem(
                    name="公開 robots.txt が到達可能",
                    passed=robots_ok,
                    detail=robots_detail,
                ),
            ]
        )

    return checks


def render_markdown(
    *,
    base_url: str,
    checks: list[CheckItem],
) -> str:
    now_jst = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")
    passed = sum(1 for item in checks if item.passed)
    total = len(checks)

    lines = [
        "# Search Console 提出チェックリスト",
        "",
        f"- 生成日時: {now_jst}",
        f"- 対象サイト: {base_url}",
        f"- 自動チェック: {passed}/{total} PASS",
        "",
        "## 自動チェック結果",
    ]

    for item in checks:
        mark = "x" if item.passed else " "
        lines.append(f"- [{mark}] {item.name}（{item.detail}）")

    by_name = {item.name: item for item in checks}
    ga4_ok = by_name.get("GA4 Measurement ID が設定済み", CheckItem("", False, "")).passed
    adsense_ok = by_name.get("AdSense Publisher ID 形式が妥当", CheckItem("", False, "")).passed

    lines.extend(
        [
            "",
            "## 手動チェック（Search Consoleで1回だけ実施）",
            "- [ ] Search ConsoleでURLプレフィックス プロパティを追加",
            f"- [ ] 所有権確認を完了（対象: {base_url}）",
            f"- [ ] `sitemap.xml` を送信（{base_url}/sitemap.xml）",
            (
                "- [x] AdSense審査/Publisher ID設定は完了"
                if adsense_ok
                else "- [ ] AdSense審査を通過し、Publisher IDを `_config.yml` に設定"
            ),
            (
                "- [x] GA4 Measurement ID設定は完了"
                if ga4_ok
                else "- [ ] GA4 Measurement ID を `_config.yml` に設定"
            ),
            "- [ ] インデックス未登録ページがあれば原因を確認",
            "- [ ] 主要記事URLをURL検査で送信",
            "",
            "## 運用ルール",
            "- 週1回このチェックを見て、未達項目だけ修正する。",
            "- `公開 sitemap.xml` と `公開 robots.txt` がFAILなら最優先で修正する。",
        ]
    )
    return "\n".join(lines) + "\n"


def cli() -> int:
    parser = argparse.ArgumentParser(description="Generate Search Console checklist report")
    parser.add_argument("--config", default="config/system.yaml")
    parser.add_argument("--site-config", default="_config.yml")
    parser.add_argument("--tools", default="data/tools.csv")
    parser.add_argument("--output", default="reports/search-console-checklist.md")
    parser.add_argument("--no-live-check", action="store_true")
    args = parser.parse_args()

    config = load_system_config(args.config)
    site_config = load_yaml(args.site_config)
    tools = read_csv_rows(args.tools, TOOLS_COLUMNS)

    checks = build_checks(
        config=config,
        site_config=site_config,
        tools=tools,
        live_check=not args.no_live_check,
    )
    base_url = str(config["site"]["base_url"]).rstrip("/")
    markdown = render_markdown(base_url=base_url, checks=checks)

    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    passed = sum(1 for item in checks if item.passed)
    print(
        dump_json(
            {
                "output": str(output_path),
                "passed": passed,
                "total": len(checks),
                "base_url": base_url,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
