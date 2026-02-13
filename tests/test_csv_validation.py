from __future__ import annotations

from pathlib import Path

import pytest

from scripts.common import read_csv_rows
from scripts.publish import TOOLS_COLUMNS


def test_tools_csv_missing_column_raises(tmp_path: Path) -> None:
    csv_path = tmp_path / "tools.csv"
    csv_path.write_text(
        "tool_id,name,category,official_url,affiliate_url,status\n"
        "tool-1,Demo,cat,https://example.com,https://example.com/a,approved\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        read_csv_rows(csv_path, TOOLS_COLUMNS)
