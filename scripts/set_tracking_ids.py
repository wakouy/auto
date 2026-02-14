from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

if __package__ in {None, ""}:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.common import dump_json, resolve_path

GA4_MEASUREMENT_PATTERN = re.compile(r"^G-[A-Z0-9]+$")
ADSENSE_PUBLISHER_PATTERN = re.compile(r"^ca-pub-\d{16}$")


def cli() -> int:
    parser = argparse.ArgumentParser(description="Set GA4/AdSense IDs in _config.yml")
    parser.add_argument("--config", default="_config.yml")
    parser.add_argument("--ga4", default="")
    parser.add_argument("--adsense", default="")
    args = parser.parse_args()

    path = resolve_path(args.config)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if args.ga4:
        if not GA4_MEASUREMENT_PATTERN.match(args.ga4.strip()):
            raise ValueError("Invalid GA4 measurement id format. expected: G-XXXX")
        data["ga4_measurement_id"] = args.ga4.strip()

    if args.adsense:
        if not ADSENSE_PUBLISHER_PATTERN.match(args.adsense.strip()):
            raise ValueError(
                "Invalid AdSense publisher id format. expected: ca-pub-xxxxxxxxxxxxxxxx"
            )
        data["adsense_publisher_id"] = args.adsense.strip()

    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(
        dump_json(
            {
                "config": str(path),
                "ga4_measurement_id": data.get("ga4_measurement_id", ""),
                "adsense_publisher_id": data.get("adsense_publisher_id", ""),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
