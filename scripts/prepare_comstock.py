#!/usr/bin/env python3
"""Prepare an exported NREL ComStock timeseries file for Temple Twin.

This script intentionally lives outside the runtime model. Give it a CSV export
containing 15-minute timestamps plus electricity end-use columns; it aggregates
to hourly values and emits normalized component shapes.

Example:
python scripts/prepare_comstock.py input.csv output.csv \
  --timestamp timestamp \
  --hvac electricity_hvac_kw \
  --lighting electricity_lighting_kw \
  --process electricity_process_kw \
  --other electricity_other_kw

For parquet, export the selected ComStock rows to CSV first or extend this
utility with pyarrow/pandas. No ComStock credentials are required for OEDI
public data.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path


COMPONENTS = ("hvac", "lighting", "process", "other")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timestamp", default="timestamp")
    for name in COMPONENTS:
        parser.add_argument(f"--{name}", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    component_columns = {name: getattr(args, name) for name in COMPONENTS}
    hourly = defaultdict(lambda: {name: 0.0 for name in COMPONENTS})
    samples = defaultdict(int)

    with args.input.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ts = datetime.fromisoformat(row[args.timestamp].replace("Z", "+00:00"))
            hour = ts.replace(minute=0, second=0, microsecond=0)
            for name, column in component_columns.items():
                hourly[hour][name] += max(float(row[column]), 0.0)
            samples[hour] += 1

    # Input columns are assumed to represent average kW at each 15-minute step;
    # aggregate to hourly mean kW, not a four-times-larger sum.
    rows = []
    for hour in sorted(hourly):
        count = samples[hour]
        values = {name: hourly[hour][name] / count for name in COMPONENTS}
        rows.append((hour, values))

    totals = {
        name: sum(values[name] for _, values in rows)
        for name in COMPONENTS
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "hvac_kw",
                "lighting_kw",
                "process_kw",
                "other_kw",
                "hvac_normalized",
                "lighting_normalized",
                "process_normalized",
                "other_normalized",
            ],
        )
        writer.writeheader()
        for hour, values in rows:
            out = {"timestamp": hour.isoformat()}
            for name in COMPONENTS:
                out[f"{name}_kw"] = values[name]
                out[f"{name}_normalized"] = (
                    values[name] / totals[name] if totals[name] else 0.0
                )
            writer.writerow(out)


if __name__ == "__main__":
    main()
