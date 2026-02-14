from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from scripts.monetization_audit import cli as audit_cli


def _write_base_files(root: Path, publisher_id: str) -> None:
    (root / "config").mkdir()
    (root / "data").mkdir()

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
    (root / "_config.yml").write_text(
        f'adsense_publisher_id: "{publisher_id}"\n',
        encoding="utf-8",
    )
    (root / "data" / "tools.csv").write_text(
        "tool_id,name,category,official_url,affiliate_url,status,last_posted_at\n"
        "tool-1,Canva,design,https://www.canva.com,https://px.a8.net/svt/ejp?a8mat=TEST,approved,\n",
        encoding="utf-8",
    )
    today = dt.date.today().isoformat()
    (root / "data" / "analytics_metrics.csv").write_text(
        "date,pv,clicks\n"
        f"{today},100,4\n",
        encoding="utf-8",
    )
    (root / "data" / "ad_revenue.csv").write_text(
        "date,adsense_revenue_usd,source,note\n"
        f"{today},0.50,adsense,manual\n",
        encoding="utf-8",
    )


def test_monetization_audit_adsense_unconfigured(tmp_path: Path, monkeypatch, capsys) -> None:
    root = tmp_path
    _write_base_files(root, "")

    monkeypatch.chdir(root)
    monkeypatch.setattr(
        "sys.argv",
        [
            "monetization_audit.py",
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
        ],
    )

    rc = audit_cli()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["adsense_configured"] is False
    assert payload["recent_adsense_revenue_usd"] == 0.5
    assert payload["recent_total_revenue_usd"] == 0.54


def test_monetization_audit_adsense_configured(tmp_path: Path, monkeypatch, capsys) -> None:
    root = tmp_path
    _write_base_files(root, "ca-pub-1234567890123456")

    monkeypatch.chdir(root)
    monkeypatch.setattr(
        "sys.argv",
        [
            "monetization_audit.py",
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
        ],
    )

    rc = audit_cli()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["adsense_configured"] is True
    assert payload["adsense_publisher_id"] == "ca-pub-1234567890123456"
