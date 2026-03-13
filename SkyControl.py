#!/usr/bin/python3

"""
SkyControl.py v0.8.0 by Mason Nelson
Modified for the FrostyFruits fork of SkywarnPlus
===============================================================================
A control script for SkywarnPlus.

This script allows you to change the value of specific keys in the
SkywarnPlus config.yaml file. It is designed to enable or disable certain
features of SkywarnPlus from the command line. It is case-insensitive,
accepting both upper and lower case parameters.

Usage: SkyControl.py <key> <value>
Example: SkyControl.py sayalert false
This will set 'SayAlert' to 'False' in the config.yaml file.

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

import os
import shutil
import subprocess
import sys
from pathlib import Path

from pydub import AudioSegment
from ruamel.yaml import YAML

yaml = YAML()
yaml.preserve_quotes = True

SCRIPT_DIR = Path(__file__).parent.absolute()
CONFIG_FILE = SCRIPT_DIR / "config.yaml"


VALID_KEYS = {
    "enable": {
        "key": "Enable",
        "section": "SKYWARNPLUS",
        "true_file": "SWP_137.wav",
        "false_file": "SWP_138.wav",
    },
    "sayalert": {
        "key": "SayAlert",
        "section": "Alerting",
        "true_file": "SWP_139.wav",
        "false_file": "SWP_140.wav",
    },
    "sayallclear": {
        "key": "SayAllClear",
        "section": "Alerting",
        "true_file": "SWP_141.wav",
        "false_file": "SWP_142.wav",
    },
    "tailmessage": {
        "key": "Enable",
        "section": "Tailmessage",
        "true_file": "SWP_143.wav",
        "false_file": "SWP_144.wav",
    },
    "courtesytone": {
        "key": "Enable",
        "section": "CourtesyTones",
        "true_file": "SWP_145.wav",
        "false_file": "SWP_146.wav",
    },
    "idchange": {
        "key": "Enable",
        "section": "IDChange",
        "true_file": "SWP_135.wav",
        "false_file": "SWP_136.wav",
    },
    "alertscript": {
        "key": "Enable",
        "section": "AlertScript",
        "true_file": "SWP_133.wav",
        "false_file": "SWP_134.wav",
    },
    "changect": {
        "key": "",
        "section": "",
        "true_file": "SWP_131.wav",
        "false_file": "SWP_132.wav",
        "available_values": ["wx", "normal"],
    },
    "changeid": {
        "key": "",
        "section": "",
        "true_file": "SWP_129.wav",
        "false_file": "SWP_130.wav",
        "available_values": ["wx", "normal"],
    },
}


def fail(message):
    print(message)
    sys.exit(1)


def load_config():
    if not CONFIG_FILE.is_file():
        fail("Cannot find config.yaml at {}".format(CONFIG_FILE))

    try:
        with open(str(CONFIG_FILE), "r", encoding="utf-8") as f:
            config = yaml.load(f)
    except Exception as exc:
        fail("Failed to load config.yaml: {}".format(exc))

    if not isinstance(config, dict):
        fail("config.yaml is invalid or empty.")

    return config


def save_config(config):
    try:
        with open(str(CONFIG_FILE), "w", encoding="utf-8") as f:
            yaml.dump(config, f)
    except Exception as exc:
        fail("Failed to save config.yaml: {}".format(exc))


def ensure_section_key(config, section, key):
    if section not in config:
        fail("Missing config section: {}".format(section))
    if key not in config[section]:
        fail("Missing config key: {}.{}".format(section, key))


def safe_copy(src_file, dest_file, label):
    if not os.path.isfile(src_file):
        fail("Source file does not exist for {}: {}".format(label, src_file))

    os.makedirs(os.path.dirname(dest_file), exist_ok=True)

    try:
        shutil.copyfile(src_file, dest_file)
    except Exception as exc:
        fail("Failed to copy {} file: {}".format(label, exc))


def change_ct(config, ct_mode):
    ct_mode_lower = ct_mode.lower()
    if ct_mode_lower not in ["normal", "wx"]:
        fail("Invalid CT mode. Please provide either 'wx' or 'normal'.")

    if "CourtesyTones" not in config:
        fail("Missing config section: CourtesyTones")

    mode_key = "Normal" if ct_mode_lower == "normal" else "WX"
    tone_dir = config["CourtesyTones"].get(
        "ToneDir", "/usr/local/bin/SkywarnPlus/SOUNDS/TONES"
    )
    tones_config = config["CourtesyTones"].get("Tones", {})

    if not isinstance(tones_config, dict) or not tones_config:
        fail("No CourtesyTones.Tones entries found in config.yaml")

    changes_made = False

    for ct_key, settings in tones_config.items():
        if not isinstance(settings, dict):
            print("Skipping invalid tone config for {}".format(ct_key))
            continue

        target_tone = settings.get(mode_key)
        if not target_tone:
            print("No tone configured for {} mode in {}".format(ct_mode_lower, ct_key))
            continue

        src_file = os.path.join(tone_dir, target_tone)
        dest_file = os.path.join(tone_dir, "{}.ulaw".format(ct_key))

        if os.path.isfile(src_file):
            shutil.copyfile(src_file, dest_file)
            print("Updated {} to {} mode with tone {}".format(ct_key, ct_mode_lower, target_tone))
            changes_made = True
        else:
            print("Source tone file does not exist: {}".format(src_file))

    if changes_made:
        print("All courtesy tones updated to {} mode.".format(ct_mode_lower))
    else:
        print("No changes made to courtesy tones.")

    return changes_made


def change_id(config, mode):
    if "IDChange" not in config:
        fail("Missing config section: IDChange")
    if "IDs" not in config["IDChange"]:
        fail("Missing config section: IDChange.IDs")

    id_dir = config["IDChange"].get("IDDir", os.path.join(str(SCRIPT_DIR), "ID"))
    ids = config["IDChange"]["IDs"]

    for key_name in ["NormalID", "WXID", "RptID"]:
        if key_name not in ids:
            fail("Missing config key: IDChange.IDs.{}".format(key_name))

    normal_id = ids["NormalID"]
    wx_id = ids["WXID"]
    rpt_id = ids["RptID"]

    if mode == "normal":
        src_file = os.path.join(id_dir, normal_id)
        dest_file = os.path.join(id_dir, rpt_id)
        safe_copy(src_file, dest_file, "normal ID")
        print("ID changed to normal mode.")
        return True

    if mode == "wx":
        src_file = os.path.join(id_dir, wx_id)
        dest_file = os.path.join(id_dir, rpt_id)
        safe_copy(src_file, dest_file, "WX ID")
        print("ID changed to wx mode.")
        return False

    fail("Invalid ID value. Please provide either 'wx' or 'normal'.")


def silent_tailmessage(config):
    tailmessage_path = config.get("Tailmessage", {}).get(
        "TailmessagePath", "/tmp/SkywarnPlus/wx-tail.wav"
    )

    silence = AudioSegment.silent(duration=100)
    converted_silence = silence.set_frame_rate(8000).set_channels(1)

    try:
        os.makedirs(os.path.dirname(tailmessage_path), exist_ok=True)
        converted_silence.export(tailmessage_path, format="wav")
        print("Replaced tailmessage with 100ms of silence.")
    except Exception as exc:
        fail("Failed to replace tailmessage with silence: {}".format(exc))


def get_nodes(config):
    asterisk_section = config.get("Asterisk", {})
    nodes = asterisk_section.get("Nodes", [])

    if isinstance(nodes, (str, int)):
        return [str(nodes)]

    if isinstance(nodes, list):
        return [str(node) for node in nodes]

    return []


def play_audio_for_nodes(config, audio_file):
    nodes = get_nodes(config)
    if not nodes:
        print("No Asterisk nodes configured. Skipping playback.")
        return

    audio_stem = audio_file.rsplit(".", 1)[0]
    audio_path = "{}/SOUNDS/ALERTS/{}".format(SCRIPT_DIR, audio_stem)

    for node in nodes:
        subprocess.run(
            [
                "/usr/sbin/asterisk",
                "-rx",
                "rpt localplay {} {}".format(node, audio_path),
            ],
            check=False,
        )


def main():
    if len(sys.argv) != 3:
        print("Incorrect number of arguments. Please provide the key and the new value.")
        print("Usage: python3 {} <key> <value>".format(sys.argv[0]))
        sys.exit(1)

    key, value = sys.argv[1:3]
    key = key.lower()
    value = value.lower()

    if key not in VALID_KEYS:
        fail("The provided key does not match any configurable item.")

    if key in ["changect", "changeid"]:
        if value not in VALID_KEYS[key]["available_values"]:
            fail(
                "Invalid value for {}. Please provide either {} or {}.".format(
                    key,
                    VALID_KEYS[key]["available_values"][0],
                    VALID_KEYS[key]["available_values"][1],
                )
            )
    else:
        if value not in ["true", "false", "toggle"]:
            fail("Invalid value. Please provide either 'true', 'false', or 'toggle'.")

    config = load_config()
    tailmessage_previously_enabled = config.get("Tailmessage", {}).get("Enable", False)

    if key == "changect":
        result_value = change_ct(config, value)
    elif key == "changeid":
        result_value = change_id(config, value)
    else:
        section = VALID_KEYS[key]["section"]
        config_key = VALID_KEYS[key]["key"]

        ensure_section_key(config, section, config_key)

        if value == "toggle":
            current_value = config[section][config_key]
            if not isinstance(current_value, bool):
                fail("Config value {}.{} is not a boolean.".format(section, config_key))
            result_value = not current_value
        else:
            result_value = value == "true"

        if key in ["enable", "tailmessage"] and result_value is False and tailmessage_previously_enabled:
            silent_tailmessage(config)

        config[section][config_key] = result_value
        save_config(config)

    audio_file = VALID_KEYS[key]["true_file"] if result_value else VALID_KEYS[key]["false_file"]
    play_audio_for_nodes(config, audio_file)


if __name__ == "__main__":
    main()