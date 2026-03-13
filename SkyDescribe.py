#!/usr/bin/python3

"""
SkyDescribe.py v0.8.0 by Mason Nelson
Modified for the FrostyFruits fork of SkywarnPlus
===============================================================================
Text to speech conversion for weather descriptions.

This script converts the descriptions of weather alerts to audio using the
VoiceRSS Text-to-Speech API. It modifies the description to replace
abbreviations and certain symbols to make the text more suitable for speech,
saves the returned WAV file, and then uses Asterisk to play the audio file
over the configured radio nodes.

The script can be run from the command line with either an index or a title
of an alert as the argument.

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

import contextlib
import json
import logging
import os
import re
import subprocess
import sys
import urllib.parse
import wave
from collections import OrderedDict

import requests
from ruamel.yaml import YAML


yaml = YAML()
yaml.preserve_quotes = True

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")


def fail(message, exit_code=1):
    print(message)
    sys.exit(exit_code)


def load_config():
    if not os.path.isfile(CONFIG_PATH):
        fail("SkyDescribe: Cannot find config.yaml at {}".format(CONFIG_PATH))

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
            config = yaml.load(config_file)
    except Exception as exc:
        fail("SkyDescribe: Failed to load config.yaml: {}".format(exc))

    if not isinstance(config, dict):
        fail("SkyDescribe: config.yaml is invalid or empty.")

    return config


CONFIG = load_config()

TMP_DIR = CONFIG.get("DEV", {}).get("TmpDir", "/tmp/SkywarnPlus")
SKYDESCRIBE_CFG = CONFIG.get("SkyDescribe", {})

API_KEY = SKYDESCRIBE_CFG.get("APIKey", "")
LANGUAGE = SKYDESCRIBE_CFG.get("Language", "en-us")
SPEED = SKYDESCRIBE_CFG.get("Speed", 0)
VOICE = SKYDESCRIBE_CFG.get("Voice", "John")
MAX_WORDS = SKYDESCRIBE_CFG.get("MaxWords", 150)

DATA_FILE = os.path.join(TMP_DIR, "data.json")
LOG_PATH = os.path.join(TMP_DIR, "SkyDescribe.log")

os.makedirs(TMP_DIR, exist_ok=True)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG if CONFIG.get("Logging", {}).get("Debug", False) else logging.INFO)
LOGGER.handlers.clear()

FORMATTER = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(FORMATTER)
LOGGER.addHandler(console_handler)

try:
    file_handler = logging.FileHandler(LOG_PATH)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(FORMATTER)
    LOGGER.addHandler(file_handler)
except OSError as exc:
    LOGGER.warning("SkyDescribe: Could not open log file %s: %s", LOG_PATH, exc)

if not API_KEY:
    LOGGER.error("SkyDescribe: No VoiceRSS API key found in config.yaml")
    sys.exit(1)


def load_state():
    """
    Load the state from the data file if it exists, else return an initial state.
    """
    if not os.path.isfile(DATA_FILE):
        return {
            "ct": None,
            "id": None,
            "alertscript_alerts": [],
            "last_alerts": OrderedDict(),
            "last_sayalert": [],
            "active_alerts": [],
        }

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.error("SkyDescribe: Failed to load state file %s: %s", DATA_FILE, exc)
        return {
            "ct": None,
            "id": None,
            "alertscript_alerts": [],
            "last_alerts": OrderedDict(),
            "last_sayalert": [],
            "active_alerts": [],
        }

    state["alertscript_alerts"] = state.get("alertscript_alerts", [])
    state["last_sayalert"] = state.get("last_sayalert", [])
    state["active_alerts"] = state.get("active_alerts", [])

    raw_last_alerts = state.get("last_alerts", [])
    if isinstance(raw_last_alerts, list):
        try:
            state["last_alerts"] = OrderedDict((x[0], x[1]) for x in raw_last_alerts)
        except (TypeError, IndexError) as exc:
            LOGGER.error("SkyDescribe: Invalid last_alerts list format: %s", exc)
            state["last_alerts"] = OrderedDict()
    elif isinstance(raw_last_alerts, dict):
        state["last_alerts"] = OrderedDict(raw_last_alerts)
    else:
        state["last_alerts"] = OrderedDict()

    return state


def modify_description(description):
    """
    Modify the description to make it more suitable for conversion to audio.
    """
    description = description.replace("\n", " ")
    description = re.sub(r"\s+", " ", description)

    abbreviations = {
        r"\bmph\b": "miles per hour",
        r"\bknots\b": "nautical miles per hour",
        r"\bNm\b": "nautical miles",
        r"\bnm\b": "nautical miles",
        r"\bft\.\b": "feet",
        r"\bin\.\b": "inches",
        r"\bm\b": "meter",
        r"\bkm\b": "kilometer",
        r"\bmi\b": "mile",
        r"\b%\b": "percent",
        r"\bN\b": "north",
        r"\bS\b": "south",
        r"\bE\b": "east",
        r"\bW\b": "west",
        r"\bNE\b": "northeast",
        r"\bNW\b": "northwest",
        r"\bSE\b": "southeast",
        r"\bSW\b": "southwest",
        r"\bF\b": "Fahrenheit",
        r"\bC\b": "Celsius",
        r"\bUV\b": "ultraviolet",
        r"\bgusts up to\b": "gusts of up to",
        r"\bhrs\b": "hours",
        r"\bhr\b": "hour",
        r"\bmin\b": "minute",
        r"\bsec\b": "second",
        r"\bsq\b": "square",
        r"\bw/\b": "with",
        r"\bc/o\b": "care of",
        r"\bblw\b": "below",
        r"\babv\b": "above",
        r"\bavg\b": "average",
        r"\bfr\b": "from",
        r"\btill\b": "until",
        r"\bb/w\b": "between",
        r"\bbtwn\b": "between",
        r"\bN/A\b": "not available",
        r"\b&\b": "and",
        r"\b\+\b": "plus",
        r"\be\.g\.\b": "for example",
        r"\bi\.e\.\b": "that is",
        r"\best\.\b": "estimated",
        r"\bEDT\b": "eastern daylight time",
        r"\bEST\b": "eastern standard time",
        r"\bCST\b": "central standard time",
        r"\bCDT\b": "central daylight time",
        r"\bMST\b": "mountain standard time",
        r"\bMDT\b": "mountain daylight time",
        r"\bPST\b": "pacific standard time",
        r"\bPDT\b": "pacific daylight time",
        r"\bAKST\b": "Alaska standard time",
        r"\bAKDT\b": "Alaska daylight time",
        r"\bHST\b": "Hawaii standard time",
        r"\bHDT\b": "Hawaii daylight time",
    }

    for abbr, full in abbreviations.items():
        description = re.sub(abbr, full, description)

    description = description.replace("*", "")
    description = re.sub(r"\s\s+", " ", description)
    description = re.sub(r"\.\s*\.\s*\.\s*", " ", description)
    description = re.sub(r"(\b\d{1,2})(\d{2}\s*[AP]M)", r"\1:\2", description)
    description = re.sub(r"(\d)\s+([AP]M)", r"\1\2", description)
    description = re.sub(r"(\d)(?=[A-Za-z])", r"\1 ", description)
    description = re.sub(r"\.\s*", ". ", description).strip()

    words = description.split()
    LOGGER.debug("SkyDescribe: Description has %d words.", len(words))
    if len(words) > MAX_WORDS:
        description = " ".join(words[:MAX_WORDS])
        LOGGER.info("SkyDescribe: Description has been limited to %d words.", MAX_WORDS)

    return description


def convert_to_audio(api_key, text):
    """
    Convert the given text to audio using the Voice RSS Text-to-Speech API.
    """
    base_url = "http://api.voicerss.org/"
    params = {
        "key": api_key,
        "hl": str(LANGUAGE),
        "src": text,
        "c": "WAV",
        "f": "8khz_16bit_mono",
        "r": str(SPEED),
        "v": str(VOICE),
    }

    LOGGER.debug(
        "SkyDescribe: Voice RSS API URL: %s",
        base_url + "?" + urllib.parse.urlencode(params),
    )

    try:
        response = requests.get(base_url, params=params, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.error("SkyDescribe: VoiceRSS request failed: %s", exc)
        sys.exit(1)

    response_text = ""
    try:
        response_text = response.text
    except Exception:
        response_text = ""

    if "ERROR" in response_text:
        LOGGER.error("SkyDescribe: %s", response_text)
        sys.exit(1)

    audio_file_path = os.path.join(TMP_DIR, "describe.wav")
    LOGGER.debug("SkyDescribe: Saving audio file to %s", audio_file_path)

    try:
        with open(audio_file_path, "wb") as file:
            file.write(response.content)
    except OSError as exc:
        LOGGER.error("SkyDescribe: Failed to save audio file: %s", exc)
        sys.exit(1)

    return audio_file_path


def get_alert_description(alerts, index_or_title):
    """
    Resolve either an index or an alert title into a description and title.
    """
    if str(index_or_title).isdigit():
        index = int(index_or_title) - 1
        if index < 0 or index >= len(alerts):
            LOGGER.error("SkyDescribe: No alert found at index %d.", index + 1)
            return None, "Sky Describe error, no alert found at index {}.".format(index + 1)

        alert_title, alert_data = alerts[index]
    else:
        alert_title = None
        alert_data = None
        title = str(index_or_title)

        for candidate_title, candidate_data in alerts:
            if candidate_title == title:
                alert_title = candidate_title
                alert_data = candidate_data
                break

        if alert_title is None:
            LOGGER.error("SkyDescribe: No alert with title %s found.", title)
            return None, "Sky Describe error, no alert found with title {}.".format(title)

    if not isinstance(alert_data, list) or not alert_data:
        LOGGER.error("SkyDescribe: Alert data for %s is empty or invalid.", alert_title)
        return None, "Sky Describe error, no description data found for {}.".format(alert_title)

    try:
        unique_instances = len(
            set((data.get("description", ""), data.get("end_time_utc", "")) for data in alert_data if isinstance(data, dict))
        )
    except Exception:
        unique_instances = 1

    first_description = ""
    if isinstance(alert_data[0], dict):
        first_description = alert_data[0].get("description", "")

    if not first_description:
        LOGGER.error("SkyDescribe: No description text found for %s.", alert_title)
        return None, "Sky Describe error, no description found for {}.".format(alert_title)

    if unique_instances == 1:
        return alert_title, first_description

    return (
        alert_title,
        "There are {} unique instances of {}. Describing the first one. {}".format(
            unique_instances,
            alert_title,
            first_description,
        ),
    )


def get_nodes():
    nodes = CONFIG.get("Asterisk", {}).get("Nodes", [])

    if isinstance(nodes, (str, int)):
        return [str(nodes)]

    if isinstance(nodes, list):
        return [str(node) for node in nodes]

    return []


def main(index_or_title):
    state = load_state()
    alerts = list(state["last_alerts"].items())

    LOGGER.debug("SkyDescribe: List of alerts:")
    for i, alert in enumerate(alerts):
        LOGGER.debug("SkyDescribe: %d. %s", i + 1, alert[0])

    alert_title, description = get_alert_description(alerts, index_or_title)

    LOGGER.debug("SkyDescribe: Original description: %s", description)

    if "Sky Describe error" not in description:
        LOGGER.info("SkyDescribe: Generating description for alert: %s", alert_title)
        description = "Detailed alert information for {}. {}".format(alert_title, description)
        description = modify_description(description)

    LOGGER.debug("SkyDescribe: Modified description: %s", description)

    audio_file = convert_to_audio(API_KEY, description)

    try:
        with contextlib.closing(wave.open(audio_file, "r")) as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration = frames / float(rate)
        LOGGER.debug("SkyDescribe: Length of the audio file in seconds: %s", duration)
    except wave.Error as exc:
        LOGGER.warning("SkyDescribe: Could not inspect WAV file: %s", exc)

    audio_stem = audio_file.rsplit(".", 1)[0]
    nodes = get_nodes()

    if not nodes:
        LOGGER.warning("SkyDescribe: No Asterisk nodes configured. Nothing to play.")
        return

    for node in nodes:
        LOGGER.info("SkyDescribe: Broadcasting description on node %s.", node)
        subprocess.run(
            [
                "/usr/sbin/asterisk",
                "-rx",
                "rpt localplay {} {}".format(node, audio_stem),
            ],
            check=False,
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        LOGGER.error("Usage: SkyDescribe.py <alert index or title>")
        sys.exit(1)

    main(sys.argv[1])