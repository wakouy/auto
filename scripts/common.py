from __future__ import annotations

import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent


def resolve_path(path_str: str | Path) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else ROOT_DIR / path


def load_yaml(path: str | Path) -> dict[str, Any]:
    with resolve_path(path).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_system_config(path: str | Path) -> dict[str, Any]:
    config = load_yaml(path)
    required_keys = [
        ("site", "base_url"),
        ("site", "title"),
        ("content", "language"),
        ("content", "min_chars"),
        ("content", "posts_per_run"),
        ("generation", "provider"),
        ("generation", "model"),
        ("affiliate", "disclosure_text"),
        ("affiliate", "default_epc_usd"),
        ("schedule", "publish_cron_utc"),
        ("schedule", "weekly_report_cron_utc"),
    ]
    missing: list[str] = []
    for section, key in required_keys:
        if section not in config or key not in config[section]:
            missing.append(f"{section}.{key}")
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")
    return config


def read_csv_rows(path: str | Path, required_columns: list[str]) -> list[dict[str, str]]:
    file_path = resolve_path(path)
    with file_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        columns = reader.fieldnames or []
        missing = [col for col in required_columns if col not in columns]
        if missing:
            raise ValueError(
                f"{file_path} is missing required columns: {', '.join(missing)}"
            )
        return [dict(row) for row in reader]


def write_csv_rows(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    file_path = resolve_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def today_jst() -> dt.datetime:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))


def iso_now() -> str:
    return today_jst().isoformat()


def slugify(text: str) -> str:
    value = text.strip().lower()
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^a-z0-9\-]", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-") or "post"


def parse_priority(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
