#!/usr/local/bin/SkywarnPlus/venv/bin/python

"""
CountyIDGen.py by Mason Nelson
Modified for the FrostyFruits fork of SkywarnPlus
===============================================================================
This script is a utility for generating WAV audio files corresponding to each
county code defined in the SkywarnPlus config.yaml. The audio files are generated
using the Voice RSS Text-to-Speech API and the settings defined in the config.yaml.

This script will generate the files, save them in the correct location, and automatically
modify the SkywarnPlus config.yaml to utilize them.

This file is part of SkywarnPlus.
SkywarnPlus is free software: you can redistribute it and/or modify it under the terms of
the GNU General Public License as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version. SkywarnPlus is distributed in the hope
that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with SkywarnPlus. If not, see <https://www.gnu.org/licenses/>.
"""

import io
import logging
import os
import re
import sys
import zipfile
from datetime import datetime

import requests
from pydub import AudioSegment
from pydub.silence import split_on_silence
from ruamel.yaml import YAML


yaml = YAML()

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
COUNTY_CODES_PATH = os.path.join(BASE_DIR, "CountyCodes.md")

with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
    config = yaml.load(config_file)

LOG_CONFIG = config.get("Logging", {})
ENABLE_DEBUG = LOG_CONFIG.get("Debug", False)
LOG_FILE = LOG_CONFIG.get("LogPath", os.path.join("/tmp/SkywarnPlus", "SkywarnPlus.log"))

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG if ENABLE_DEBUG else logging.INFO)
LOGGER.handlers.clear()

LOG_FORMATTER = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

C_HANDLER = logging.StreamHandler()
C_HANDLER.setFormatter(LOG_FORMATTER)
LOGGER.addHandler(C_HANDLER)

log_directory = os.path.dirname(LOG_FILE)
if log_directory and not os.path.exists(log_directory):
    os.makedirs(log_directory, exist_ok=True)

F_HANDLER = logging.FileHandler(LOG_FILE)
F_HANDLER.setFormatter(LOG_FORMATTER)
LOGGER.addHandler(F_HANDLER)

API_KEY = config.get("SkyDescribe", {}).get("APIKey", "")
LANGUAGE = config.get("SkyDescribe", {}).get("Language", "en-us")
SPEED = str(config.get("SkyDescribe", {}).get("Speed", 0))
VOICE = config.get("SkyDescribe", {}).get("Voice", "John")
SOUNDS_PATH = config.get("Alerting", {}).get(
    "SoundsPath", os.path.join(BASE_DIR, "SOUNDS")
)


def sanitize_text_for_tts(text):
    """
    Sanitize the text for TTS processing.
    Remove characters that aren't alphanumeric or whitespace.
    """
    if not text:
        return ""
    sanitized_text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    sanitized_text = re.sub(r"\s+", " ", sanitized_text).strip()
    return sanitized_text


def generate_wav(api_key, language, speed, voice, text, output_file):
    """
    Convert the given text to audio using the Voice RSS Text-to-Speech API and trim silence.
    """
    base_url = "https://api.voicerss.org/"
    params = {
        "key": api_key,
        "hl": language,
        "src": text,
        "c": "WAV",
        "f": "8khz_16bit_mono",
        "r": str(speed),
        "v": voice,
    }

    response = requests.get(base_url, params=params, timeout=60)
    response.raise_for_status()

    response_text = response.text if isinstance(response.text, str) else ""
    if response_text.startswith("ERROR:"):
        LOGGER.error("VoiceRSS: %s", response_text)
        sys.exit(1)

    sound = AudioSegment.from_wav(io.BytesIO(response.content))

    target_dbfs = -6.0
    gain_difference = target_dbfs - sound.max_dBFS
    sound = sound.apply_gain(gain_difference)

    chunks = split_on_silence(sound, min_silence_len=200, silence_thresh=-40)

    if chunks:
        combined_sound = AudioSegment.empty()
        for chunk in chunks:
            combined_sound += chunk
        combined_sound.export(output_file, format="wav")
    else:
        sound.export(output_file, format="wav")


def backup_existing_files(path, backup_name):
    """
    Backup existing county WAV files in the specified path to a zip file.
    """
    if not os.path.isdir(path):
        return

    files_to_backup = [f for f in os.listdir(path) if f.endswith(".wav")]
    if not files_to_backup:
        return

    with zipfile.ZipFile(backup_name, "w") as zipf:
        for file_name in files_to_backup:
            zipf.write(os.path.join(path, file_name), file_name)


def load_county_codes_from_md(md_file_path):
    """
    Load county names from the markdown tables and return a dictionary mapping
    county codes to county names.
    """
    with open(md_file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    county_data = {}
    in_table = False

    for line in lines:
        if line.startswith("| County |"):
            in_table = True
            continue
        if not in_table:
            continue

        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("##"):
            continue
        if not stripped.startswith("|"):
            continue

        parts = [s.strip() for s in line.split("|")[1:-1]]
        if len(parts) != 2:
            continue

        county_name, code = parts
        if county_name == "County" or code == "Code":
            continue

        county_data[code] = county_name

    return county_data


def normalize_county_codes(county_codes_config):
    """
    Normalize Alerting.CountyCodes into a list of county code strings.
    """
    normalized = []

    if isinstance(county_codes_config, list):
        for entry in county_codes_config:
            if isinstance(entry, str):
                normalized.append(entry)
            elif isinstance(entry, dict):
                for county_code in entry.keys():
                    normalized.append(county_code)
    elif isinstance(county_codes_config, dict):
        normalized.extend(list(county_codes_config.keys()))

    return normalized


def process_county_codes(county_data):
    """
    Generate county WAV files and update config mappings.
    """
    county_codes_config = config.get("Alerting", {}).get("CountyCodes", [])
    normalized_county_codes = normalize_county_codes(county_codes_config)

    new_county_codes = []

    for county_code in normalized_county_codes:
        county_name = county_data.get(county_code)

        if not county_name:
            LOGGER.warning(
                "County code %s was not found in CountyCodes.md. Leaving it unchanged.",
                county_code,
            )
            new_county_codes.append(county_code)
            continue

        sanitized_county_name = sanitize_text_for_tts(county_name)
        if not sanitized_county_name:
            LOGGER.warning(
                "County name for %s could not be sanitized into a usable filename. Leaving it unchanged.",
                county_code,
            )
            new_county_codes.append(county_code)
            continue

        expected_wav_file = "{}.wav".format(sanitized_county_name)
        output_file = os.path.join(SOUNDS_PATH, expected_wav_file)

        overwrite = True
        if os.path.exists(output_file):
            user_input = input(
                "The WAV file for {} ({}) already exists. Do you want to overwrite it? [yes/no]: ".format(
                    county_name, expected_wav_file
                )
            ).strip().lower()
            if user_input != "yes":
                LOGGER.info("Skipping generation for %s due to user input.", county_name)
                overwrite = False

        if overwrite:
            LOGGER.info("Generating county WAV for %s -> %s", county_name, expected_wav_file)
            generate_wav(API_KEY, LANGUAGE, SPEED, VOICE, sanitized_county_name, output_file)

        new_county_codes.append({county_code: expected_wav_file})

    config["Alerting"]["CountyCodes"] = new_county_codes


def display_initial_warning():
    warning_message = """
    ============================================================
    WARNING: Please read the following information carefully before proceeding.

    This utility is designed to generate WAV audio files corresponding to each county code
    defined in the SkywarnPlus config.yaml using the Voice RSS Text-to-Speech API. The generated
    audio files will be saved in the appropriate location, and the SkywarnPlus config.yaml will
    be automatically updated to use them.

    However, a few things to keep in mind:
    - The script will only attempt to generate WAV files for county codes that are defined in the config.

    - Pronunciations for some county names might not be accurate. In such cases, you may need to
      manually create the files using VoiceRSS. This might involve intentionally misspelling the county
      name to achieve the desired pronunciation.

    - This script will attempt to backup files before it modifies them, but it is always a good idea to
      manually back up your existing configuration and files before running this script.

    - This script will modify your config.yaml file, so you should ALWAYS double check the changes it makes.

    Proceed with caution.
    ============================================================
    """
    print(warning_message)


def main():
    display_initial_warning()

    user_input = input("Do you want to proceed? [yes/no]: ").strip().lower()
    if user_input != "yes":
        LOGGER.info("Aborting process due to user input.")
        sys.exit(0)

    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        LOGGER.error("SkyDescribe APIKey is not configured in config.yaml.")
        sys.exit(1)

    if not os.path.isdir(SOUNDS_PATH):
        LOGGER.info("Creating sounds directory: %s", SOUNDS_PATH)
        os.makedirs(SOUNDS_PATH, exist_ok=True)

    backup_date = datetime.now().strftime("%Y%m%d")
    backup_name = os.path.join(SOUNDS_PATH, "CountyID_Backup_{}.zip".format(backup_date))
    backup_existing_files(SOUNDS_PATH, backup_name)

    county_data = load_county_codes_from_md(COUNTY_CODES_PATH)
    process_county_codes(county_data)

    with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
        yaml.indent(sequence=4, offset=2)
        yaml.dump(config, config_file)

    LOGGER.info("County WAV files generation completed.")


if __name__ == "__main__":
    main()
