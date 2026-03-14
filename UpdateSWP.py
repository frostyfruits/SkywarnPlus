#!/usr/bin/python3

"""
UpdateSWP.py by Mason Nelson
Modified for the FrostyFruits fork of SkywarnPlus
===============================================================================
Script to update SkywarnPlus to the latest version. This script downloads the
latest version of SkywarnPlus from GitHub, merges the existing config.yaml
with the new config.yaml, and creates a backup of the existing SkywarnPlus
directory before updating.

Please note that this script might not work correctly if you have made
significant changes to the SkywarnPlus code or directory structure.
If you have made significant changes, it is recommended that you manually
update SkywarnPlus.

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

import argparse
import datetime
import os
import shutil
import stat
import subprocess
import sys
import zipfile

import requests
from ruamel.yaml import YAML


REPO_ZIP_URL = "https://github.com/frostyfruits/SkywarnPlus/archive/refs/heads/main.zip"
TMP_ZIP = "/tmp/SkywarnPlus-main.zip"
TMP_EXTRACT_DIR = "/tmp/SkywarnPlus-main"


parser = argparse.ArgumentParser(description="Update SkywarnPlus")
parser.add_argument(
    "-f",
    "--force",
    help="Force update without confirmation prompt",
    action="store_true",
)
args = parser.parse_args()


def log(message):
    print("[UPDATE]:", message)


def load_yaml_file(filename):
    yaml = YAML()
    with open(filename, "r", encoding="utf-8") as f:
        return yaml.load(f)


def save_yaml_file(filename, data):
    yaml = YAML()
    yaml.preserve_quotes = True
    with open(filename, "w", encoding="utf-8") as f:
        yaml.dump(data, f)


def merge_yaml_files(old_file, new_file):
    old_yaml_data = load_yaml_file(old_file) or {}
    new_yaml_data = load_yaml_file(new_file) or {}

    for key in new_yaml_data:
        if key in old_yaml_data:
            if isinstance(new_yaml_data[key], dict) and isinstance(old_yaml_data[key], dict):
                new_yaml_data[key].update(old_yaml_data[key])
            else:
                new_yaml_data[key] = old_yaml_data[key]

    save_yaml_file(new_file, new_yaml_data)


def remove_duplicate_comments(filename):
    last_comment_block = []
    new_lines = []

    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_comment_block = []
    for line in lines:
        stripped_line = line.strip()

        if stripped_line.startswith("#") or not stripped_line:
            current_comment_block.append(line)
        else:
            if current_comment_block:
                if current_comment_block != last_comment_block:
                    new_lines.extend(current_comment_block)
                last_comment_block = list(current_comment_block)
                current_comment_block = []
            new_lines.append(line)

    if current_comment_block and current_comment_block != last_comment_block:
        new_lines.extend(current_comment_block)

    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def display_update_warning():
    warning_message = """
    ============================================================
    WARNING: Please read the following information carefully before updating.

    This utility is designed to update SkywarnPlus to the latest version by fetching it
    directly from GitHub. Before updating:

    - A backup of the existing SkywarnPlus directory will be created to ensure safety.

    - The updater will attempt to merge your existing config.yaml with the new version's
      config.yaml. ALWAYS double-check your config.yaml after updating. This script is not
      perfect and may not merge your configuration correctly.

    - If you've made significant changes to the SkywarnPlus code, directory structure, or
      configuration, this updater might not work correctly. In such cases, manual updating
      is recommended.

    Remember, this script's primary goal is to help with the updating process. However,
    given the complexities of merging and updating, always verify the results yourself to
    ensure your system continues to operate as expected.

    Proceed with caution.
    ============================================================
    """
    print(warning_message)


def set_exec_bits(root_dir):
    log("Setting executable permissions on Python files and installer...")
    for dirpath, dirs, files in os.walk(root_dir):
        for filename in files:
            full_path = os.path.join(dirpath, filename)
            if filename.endswith(".py") or filename == "swp-install":
                current_mode = os.stat(full_path).st_mode
                os.chmod(
                    full_path,
                    current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
                )


def rebuild_venv_if_present(root_dir):
    venv_dir = os.path.join(root_dir, ".venv")
    venv_python = os.path.join(venv_dir, "bin", "python")
    venv_pip = os.path.join(venv_dir, "bin", "pip")

    if not os.path.isdir(venv_dir):
        log("No .venv found, skipping virtual environment rebuild.")
        return

    log("Rebuilding local virtual environment...")
    shutil.rmtree(venv_dir, ignore_errors=True)

    subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
    subprocess.run([venv_pip, "install", "--upgrade", "pip", "wheel", "setuptools"], check=True)
    subprocess.run(
        [venv_pip, "install", "requests", "python-dateutil", "ruamel.yaml", "pydub"],
        check=True,
    )

    if os.path.isfile(venv_python):
        log("Virtual environment rebuilt successfully.")


def restore_asl3_ownership(root_dir):
    try:
        shutil.chown(root_dir, user="asterisk", group="asterisk")
    except Exception:
        return

    for walk_root, dirs, files in os.walk(root_dir):
        for name in dirs + files:
            path = os.path.join(walk_root, name)
            try:
                shutil.chown(path, user="asterisk", group="asterisk")
            except Exception:
                pass


def safe_remove(path):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.isfile(path):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


if os.geteuid() != 0:
    sys.exit("ERROR: This script must be run as root.")

if not os.path.isfile("SkywarnPlus.py"):
    print("ERROR: Cannot find SkywarnPlus.py. Make sure this script is in the SkywarnPlus directory.")
    sys.exit(1)

if not args.force:
    display_update_warning()

    confirmation = input("\nDo you want to continue with the update? (yes/no) ")
    if confirmation.lower() != "yes":
        log("Update cancelled by user.")
        sys.exit(0)

root_dir = os.getcwd()
log("Current directory is {}".format(root_dir))

zip_name = root_dir + "_backup_" + datetime.datetime.now().strftime("%Y%m%d_%H%M")
log("Creating backup at {}.zip...".format(zip_name))
shutil.make_archive(zip_name, "zip", root_dir)

safe_remove(TMP_ZIP)
safe_remove(TMP_EXTRACT_DIR)

log("Downloading SkywarnPlus from {}...".format(REPO_ZIP_URL))
response = requests.get(REPO_ZIP_URL, timeout=60)
response.raise_for_status()

with open(TMP_ZIP, "wb") as out_file:
    out_file.write(response.content)

log("Extracting update archive...")
with zipfile.ZipFile(TMP_ZIP, "r") as zip_ref:
    zip_ref.extractall("/tmp")

if not os.path.isdir(TMP_EXTRACT_DIR):
    sys.exit("ERROR: Extracted update directory not found at {}".format(TMP_EXTRACT_DIR))

new_config_path = os.path.join(TMP_EXTRACT_DIR, "config.yaml")
old_config_path = os.path.join(root_dir, "config.yaml")

if os.path.isfile(old_config_path) and os.path.isfile(new_config_path):
    log("Merging old config with new config...")
    merge_yaml_files(old_config_path, new_config_path)
    remove_duplicate_comments(new_config_path)
else:
    log("config.yaml not found in one of the expected locations, skipping merge.")

log("Copying updated files into {}...".format(root_dir))
for walk_root, dirs, files in os.walk(TMP_EXTRACT_DIR):
    for file_name in files:
        src_path = os.path.join(walk_root, file_name)
        rel_path = os.path.relpath(src_path, TMP_EXTRACT_DIR)
        dst_path = os.path.join(root_dir, rel_path)

        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copy2(src_path, dst_path)

set_exec_bits(root_dir)
rebuild_venv_if_present(root_dir)
restore_asl3_ownership(root_dir)

log("Deleting temporary files and folders...")
safe_remove(TMP_EXTRACT_DIR)
safe_remove(TMP_ZIP)

log("Update complete!")