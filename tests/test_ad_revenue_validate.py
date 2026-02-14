from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from scripts.ad_revenue_validate import read_rows, sum_ad_revenue


def test_read_rows_valid_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "ad_revenue.csv"
    csv_path.write_text(
        "date,adsense_revenue_usd,source,note\n"
        "2026-02-10,0.45,adsense,week1\n"
        "2026-02-11,1.20,adsense,week1\n",
        encoding="utf-8",
    )

    rows = read_rows(csv_path)
    total = sum_ad_revenue(csv_path, dt.date(2026, 2, 10), dt.date(2026, 2, 11))

    assert len(rows) == 2
    assert total == pytest.approx(1.65)


def test_read_rows_missing_column_raises(tmp_path: Path) -> None:
    csv_path = tmp_path / "ad_revenue.csv"
    csv_path.write_text(
        "date,adsense_revenue_usd,source\n"
        "2026-02-10,0.45,adsense\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        read_rows(csv_path)


def test_read_rows_negative_revenue_raises(tmp_path: Path) -> None:
    csv_path = tmp_path / "ad_revenue.csv"
    csv_path.write_text(
        "date,adsense_revenue_usd,source,note\n"
        "2026-02-10,-0.45,adsense,bad\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        read_rows(csv_path)
