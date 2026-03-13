#!/usr/bin/python3

"""
ASL3_Supermon_Workaround.py by Mason Nelson
Modified for the FrostyFruits fork of SkywarnPlus
===============================================================================
This script is a workaround for the Supermon compatibility issue with ASL 3.
With Asterisk 20 no longer running as the root user, SkywarnPlus may be unable
to write to the legacy AUTOSKY directories. This script can be run by cron as
root to mirror alert data into those directories for Supermon compatibility.

This file is part of SkywarnPlus.
SkywarnPlus is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. SkywarnPlus is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License
along with SkywarnPlus. If not, see <https://www.gnu.org/licenses/>.
"""

import json
import logging
import os
from collections import OrderedDict


BASE_DIR = os.path.dirname(os.path.realpath(__file__))
COUNTY_CODES_PATH = os.path.join(BASE_DIR, "CountyCodes.md")
DATA_FILE = "/tmp/SkywarnPlus/data.json"
OUTPUT_DIRS = ["/tmp/AUTOSKY", "/var/www/html/AUTOSKY"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def load_state():
    if not os.path.isfile(DATA_FILE):
        logging.warning("Data file not found: %s", DATA_FILE)
        return {"last_alerts": OrderedDict()}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        logging.error("Failed to load state from %s: %s", DATA_FILE, exc)
        return {"last_alerts": OrderedDict()}

    raw_last_alerts = state.get("last_alerts", {})

    if isinstance(raw_last_alerts, list):
        try:
            state["last_alerts"] = OrderedDict((item[0], item[1]) for item in raw_last_alerts)
        except (TypeError, IndexError) as exc:
            logging.error("Invalid last_alerts list format: %s", exc)
            state["last_alerts"] = OrderedDict()
    elif isinstance(raw_last_alerts, dict):
        state["last_alerts"] = OrderedDict(raw_last_alerts)
    else:
        logging.warning("Unsupported last_alerts type: %s", type(raw_last_alerts).__name__)
        state["last_alerts"] = OrderedDict()

    return state


def load_county_names(md_file):
    county_data = {}

    if not os.path.isfile(md_file):
        logging.warning("CountyCodes.md not found: %s", md_file)
        return county_data

    try:
        with open(md_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as exc:
        logging.error("Failed to read %s: %s", md_file, exc)
        return county_data

    in_table = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("| County |"):
            in_table = True
            continue

        if not in_table:
            continue

        if not stripped:
            continue

        if stripped.startswith("##"):
            break

        if not stripped.startswith("|"):
            continue

        parts = [part.strip() for part in line.split("|")[1:-1]]
        if len(parts) < 2:
            continue

        name = parts[0]
        code = parts[1]

        if name and code and code.lower() != "code":
            county_data[code] = name

    return county_data


def replace_with_county_name(county_code, county_data):
    return county_data.get(county_code, county_code)


def generate_title_string(alerts, county_data):
    alert_titles_with_counties = []

    for alert_name, entries in alerts.items():
        if not isinstance(entries, list):
            logging.warning("Skipping malformed alert entry for %s", alert_name)
            continue

        counties = sorted(
            set(
                replace_with_county_name(entry.get("county_code", ""), county_data)
                for entry in entries
                if isinstance(entry, dict) and entry.get("county_code")
            )
        )

        if counties:
            alert_titles_with_counties.append(f"{alert_name} [{', '.join(counties)}]")
        else:
            alert_titles_with_counties.append(str(alert_name))

    logging.info("Prepared %d alert line(s) for Supermon", len(alert_titles_with_counties))
    return alert_titles_with_counties


def write_text_file(file_path, content):
    temp_path = file_path + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as file:
        file.write(content)

    os.replace(temp_path, file_path)


def supermon_back_compat(alerts, county_data):
    if os.getuid() != 0:
        logging.error("This script must run as root")
        return

    alert_titles_with_counties = generate_title_string(alerts, county_data)
    output_text = "<br>".join(alert_titles_with_counties)

    for path in OUTPUT_DIRS:
        try:
            os.makedirs(path, exist_ok=True)

            if not os.access(path, os.W_OK):
                logging.error("No write permission for %s", path)
                continue

            file_path = os.path.join(path, "warnings.txt")
            write_text_file(file_path, output_text)
            logging.info("Updated %s", file_path)

        except OSError as exc:
            logging.error("An error occurred while writing to %s: %s", path, exc)


def main():
    if not os.path.isfile(DATA_FILE):
        logging.warning("Data file does not exist, exiting.")
        return

    state = load_state()
    last_alerts = state.get("last_alerts", OrderedDict())
    county_data = load_county_names(COUNTY_CODES_PATH)
    supermon_back_compat(last_alerts, county_data)


if __name__ == "__main__":
    main()