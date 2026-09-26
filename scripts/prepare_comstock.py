#!/usr/bin/env python3
"""Inspect/download the actual ComStock source files used by Temple Twin."""

from pathlib import Path
import urllib.request

ROOT = (
    "https://oedi-data-lake.s3.amazonaws.com/"
    "nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/"
    "2021/comstock_amy2018_release_1/timeseries_aggregates/"
    "by_county/state=PA"
)
GISJOIN = "g4201010"
BUILDING_TYPES = ("largeoffice", "secondaryschool", "mediumoffice")


def main() -> None:
    out = Path("data/comstock_raw")
    out.mkdir(parents=True, exist_ok=True)
    for building_type in BUILDING_TYPES:
        url = f"{ROOT}/{GISJOIN}-{building_type}.csv"
        target = out / f"{GISJOIN}-{building_type}.csv"
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, target)
        print(f"  -> {target}")


if __name__ == "__main__":
    main()
