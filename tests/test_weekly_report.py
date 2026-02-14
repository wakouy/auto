from __future__ import annotations

import json
from pathlib import Path

from scripts.weekly_report import cli as weekly_cli


def test_weekly_report_includes_adsense_and_total(tmp_path: Path, monkeypatch, capsys) -> None:
    root = tmp_path
    (root / "config").mkdir()
    (root / "data").mkdir()
    (root / "reports").mkdir()

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
reporting:
  ad_revenue_csv: "data/ad_revenue.csv"
""".strip(),
        encoding="utf-8",
    )

    (root / "data" / "analytics_metrics.csv").write_text(
        "date,pv,clicks\n"
        "2026-02-07,100,3\n"
        "2026-02-08,120,2\n"
        "2026-02-09,130,1\n"
        "2026-02-10,140,2\n"
        "2026-02-11,150,1\n"
        "2026-02-12,160,0\n"
        "2026-02-13,170,1\n",
        encoding="utf-8",
    )

    (root / "data" / "ad_revenue.csv").write_text(
        "date,adsense_revenue_usd,source,note\n"
        "2026-02-09,0.40,adsense,week\n"
        "2026-02-11,0.30,adsense,week\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(root)
    monkeypatch.setattr(
        "sys.argv",
        [
            "weekly_report.py",
            "--config",
            str(root / "config" / "system.yaml"),
            "--metrics",
            str(root / "data" / "analytics_metrics.csv"),
            "--reports-dir",
            str(root / "reports"),
            "--ad-revenue",
            str(root / "data" / "ad_revenue.csv"),
        ],
    )

    rc = weekly_cli()
    assert rc == 0

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["adsense_revenue_usd"] == 0.7
    assert payload["total_revenue_usd"] == 0.8

    report_path = Path(payload["report"])
    content = report_path.read_text(encoding="utf-8")
    assert "Affiliate推定収益(USD): $0.10" in content
    assert "AdSense収益(USD): $0.70" in content
    assert "合算収益(USD): $0.80" in content
