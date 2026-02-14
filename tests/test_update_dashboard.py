from __future__ import annotations

import json
from pathlib import Path

from scripts.update_dashboard import cli as dashboard_cli


def test_update_dashboard_generates_report_and_site(tmp_path: Path, monkeypatch, capsys) -> None:
    root = tmp_path
    (root / "config").mkdir()
    (root / "data").mkdir()
    (root / "content").mkdir()
    (root / ".github" / "workflows").mkdir(parents=True)

    (root / ".github" / "workflows" / "publish.yml").write_text("name: x\n", encoding="utf-8")
    (root / ".github" / "workflows" / "weekly_report.yml").write_text(
        "name: y\n", encoding="utf-8"
    )

    (root / "config" / "system.yaml").write_text(
        """
site:
  base_url: "https://example.com"
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
reporting:
  ad_revenue_csv: "data/ad_revenue.csv"
""".strip(),
        encoding="utf-8",
    )
    (root / "_config.yml").write_text(
        'ga4_measurement_id: "G-TEST1234"\nadsense_publisher_id: "ca-pub-1234567890123456"\n',
        encoding="utf-8",
    )
    (root / "data" / "tools.csv").write_text(
        "tool_id,name,category,official_url,affiliate_url,status,last_posted_at\n"
        "tool-1,Canva,design,https://www.canva.com,https://px.a8.net/svt/ejp?a8mat=TEST,approved,\n",
        encoding="utf-8",
    )
    (root / "data" / "analytics_metrics.csv").write_text(
        "date,pv,clicks\n2026-02-12,100,3\n2026-02-13,120,2\n",
        encoding="utf-8",
    )
    (root / "data" / "ad_revenue.csv").write_text(
        "date,adsense_revenue_usd,source,note\n2026-02-13,0.50,adsense,manual\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(root)
    monkeypatch.setattr(
        "sys.argv",
        [
            "update_dashboard.py",
            "--config",
            str(root / "config" / "system.yaml"),
            "--site-config",
            str(root / "_config.yml"),
            "--tools",
            str(root / "data" / "tools.csv"),
            "--metrics",
            str(root / "data" / "analytics_metrics.csv"),
            "--ad-revenue",
            str(root / "data" / "ad_revenue.csv"),
            "--output-report",
            str(root / "reports" / "monetization-dashboard.md"),
            "--output-site",
            str(root / "content" / "dashboard.md"),
            "--no-live-check",
        ],
    )

    rc = dashboard_cli()
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ready_tools_count"] == 1
    assert payload["total_revenue_7d_usd"] >= 0.5

    report = (root / "reports" / "monetization-dashboard.md").read_text(encoding="utf-8")
    site = (root / "content" / "dashboard.md").read_text(encoding="utf-8")
    assert "Monetization Dashboard" in report
    assert "収益ダッシュボード" in site
