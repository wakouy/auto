from __future__ import annotations

from pathlib import Path

from scripts.sync_ga4_metrics import _upsert_row


def test_upsert_row_updates_existing() -> None:
    rows = [
        {"date": "2026-02-10", "pv": "10", "clicks": "1"},
        {"date": "2026-02-11", "pv": "12", "clicks": "2"},
    ]

    merged = _upsert_row(rows, "2026-02-11", 30, 7)

    assert any(r["date"] == "2026-02-11" and r["pv"] == "30" and r["clicks"] == "7" for r in merged)


def test_upsert_row_inserts_new() -> None:
    rows = [{"date": "2026-02-10", "pv": "10", "clicks": "1"}]

    merged = _upsert_row(rows, "2026-02-12", 5, 0)

    assert any(r["date"] == "2026-02-12" and r["pv"] == "5" and r["clicks"] == "0" for r in merged)
