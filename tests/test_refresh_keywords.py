from __future__ import annotations

from pathlib import Path

from scripts.common import read_csv_rows
from scripts.refresh_keywords import cli as refresh_cli
from scripts.select_topic import REQUIRED_COLUMNS


def test_refresh_keywords_adds_rows_when_pool_is_low(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path
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
growth:
  min_keyword_pool: 10
  keyword_add_limit: 20
""".strip(),
        encoding="utf-8",
    )

    (root / "data" / "keywords.csv").write_text(
        "keyword,intent,priority,status,last_used_at\n"
        "既存キーワード,意図,10,new,\n",
        encoding="utf-8",
    )
    (root / "data" / "tools.csv").write_text(
        "tool_id,name,category,official_url,affiliate_url,status,last_posted_at\n"
        "tool-1,Canva,design,https://www.canva.com,https://example.com/a8/canva,approved,\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(root)
    monkeypatch.setattr(
        "sys.argv",
        [
            "refresh_keywords.py",
            "--config",
            str(root / "config" / "system.yaml"),
            "--keywords",
            str(root / "data" / "keywords.csv"),
            "--tools",
            str(root / "data" / "tools.csv"),
        ],
    )

    rc = refresh_cli()
    assert rc == 0

    rows = read_csv_rows(root / "data" / "keywords.csv", REQUIRED_COLUMNS)
    assert len(rows) > 1
