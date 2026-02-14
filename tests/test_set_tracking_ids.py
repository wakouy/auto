from __future__ import annotations

from pathlib import Path

import pytest

from scripts.set_tracking_ids import cli as set_ids_cli


def test_set_tracking_ids_updates_values(tmp_path: Path, monkeypatch, capsys) -> None:
    config_path = tmp_path / "_config.yml"
    config_path.write_text(
        'title: "Auto Revenue Lab"\nga4_measurement_id: ""\nadsense_publisher_id: ""\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "set_tracking_ids.py",
            "--config",
            str(config_path),
            "--ga4",
            "G-TEST1234",
            "--adsense",
            "ca-pub-1234567890123456",
        ],
    )

    rc = set_ids_cli()
    assert rc == 0
    out = capsys.readouterr().out
    assert "G-TEST1234" in out
    assert "ca-pub-1234567890123456" in out
    content = config_path.read_text(encoding="utf-8")
    assert 'ga4_measurement_id: G-TEST1234' in content
    assert 'adsense_publisher_id: ca-pub-1234567890123456' in content


def test_set_tracking_ids_rejects_invalid_ids(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "_config.yml"
    config_path.write_text(
        'title: "Auto Revenue Lab"\nga4_measurement_id: ""\nadsense_publisher_id: ""\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "set_tracking_ids.py",
            "--config",
            str(config_path),
            "--ga4",
            "BAD",
        ],
    )

    with pytest.raises(ValueError):
        set_ids_cli()
