# SkywarnPlus

> [!IMPORTANT]
> This is the maintained FrostyFruits fork of SkywarnPlus.
> This fork is focused on keeping SkywarnPlus working on modern systems, including AllStarLink 3, Debian 12, and Debian 13.

![SkywarnPlus Logo](https://raw.githubusercontent.com/frostyfruits/SkywarnPlus/main/Logo_SWP.svg)

![Repo Size](https://img.shields.io/github/repo-size/frostyfruits/SkywarnPlus?label=Repo%20Size&color=f15d24)
![Last Commit](https://img.shields.io/github/last-commit/frostyfruits/SkywarnPlus?label=Last%20Update&color=f15d24)
![Issues](https://img.shields.io/github/issues/frostyfruits/SkywarnPlus?label=Issues&color=f15d24)
![License](https://img.shields.io/github/license/frostyfruits/SkywarnPlus?label=License&color=f15d24)

SkywarnPlus is an advanced weather alerting solution for Asterisk and app_rpt nodes. It brings National Weather Service alerts directly into your radio system so your node can automatically announce active alerts, manage tail messages, switch courtesy tones, change IDs, and provide detailed weather information when it matters most.

This fork keeps the original spirit and major feature set of SkywarnPlus while updating installation and compatibility for current systems.

> [!NOTE]
> This README is intentionally streamlined for this fork. If you want the longer historical documentation and deeper feature walkthroughs, the original SkywarnPlus project remains a useful reference.

## Contents

- [Key Features](#key-features)
- [Supported Platforms](#supported-platforms)
- [Installation](#installation)
  - [Automated Installation](#automated-installation)
  - [Manual Installation](#manual-installation)
- [Configuration](#configuration)
- [TimeType Configuration](#timetype-configuration)
- [Tail Messages](#tail-messages)
- [Courtesy Tones](#courtesy-tones)
- [CW / Voice IDs](#cw--voice-ids)
- [Pushover Integration](#pushover-integration)
- [SkyControl](#skycontrol)
- [AlertScript](#alertscript)
- [SkyDescribe](#skydescribe)
- [County Identifiers](#county-identifiers)
- [Supermon Integration](#supermon-integration)
- [Testing](#testing)
- [Debugging](#debugging)
- [Contributing](#contributing)
- [License](#license)

## Key Features

- Real-time National Weather Service alert monitoring
- Automatic spoken alert announcements
- Automatic all-clear announcements
- Tail message creation and removal
- Dynamic courtesy tone switching based on alert state
- Dynamic CW or voice ID switching based on alert state
- Support for multiple counties
- County-specific identifiers in announcements
- DTMF control through SkyControl
- Detailed alert playback through SkyDescribe
- Pushover notification support
- Alert-triggered command execution through AlertScript
- Supermon and Supermon2 compatibility features

## Supported Platforms

This fork is intended to support the following environments:

- AllStarLink 3
- Debian 12
- Debian 13
- HamVoIP where practical

> [!NOTE]
> Debian 13 support is a major goal of this fork. Installer and dependency handling are being updated to keep SkywarnPlus usable on current Debian-based systems.

## Installation

## Automated Installation

Run the installer as root:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/frostyfruits/SkywarnPlus/main/swp-install)"
```

The installer supports both Debian 12 and Debian 13 and allows you to confirm or override the detected system type during setup.

## Manual Installation

SkywarnPlus is recommended to be installed in:

```text
/usr/local/bin/SkywarnPlus
```

### Debian 12 / Debian 13

Install base dependencies:

```bash
apt update
apt install -y unzip ffmpeg curl git python3 python3-venv python3-requests python3-dateutil python3-ruamel.yaml
```

Download the repository:

```bash
cd /usr/local/bin
git clone https://github.com/frostyfruits/SkywarnPlus.git
cd SkywarnPlus
```

Create a local Python virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip wheel setuptools
.venv/bin/pip install requests python-dateutil ruamel.yaml pydub
```

Make scripts executable:

```bash
chmod +x *.py swp-install
```

If you are using ASL3, allow the asterisk user to access the files:

```bash
chown -R asterisk:asterisk /usr/local/bin/SkywarnPlus
chmod -R u+rw /usr/local/bin/SkywarnPlus
```

Create a cron entry for ASL1/2:

```bash
echo '* * * * * root /usr/local/bin/SkywarnPlus/.venv/bin/python /usr/local/bin/SkywarnPlus/SkywarnPlus.py' > /etc/cron.d/SkywarnPlus
```

Create a cron entry for ASL3:

```bash
echo '* * * * * asterisk /usr/local/bin/SkywarnPlus/.venv/bin/python /usr/local/bin/SkywarnPlus/SkywarnPlus.py' > /etc/cron.d/SkywarnPlus
```

### HamVoIP

HamVoIP may still require a different dependency path because of its older Python environment. If you are using HamVoIP, expect some differences from the Debian 12 and Debian 13 install flow.

## Configuration

Edit `config.yaml` for your county codes, enabled features, node behavior, and audio options.

```bash
cd /usr/local/bin/SkywarnPlus
nano config.yaml
```

County codes can be found in `CountyCodes.md`.

> [!WARNING]
> Use county codes, not zone codes, unless you fully understand the difference. Using zone codes can cause you to miss alerts.

> [!IMPORTANT]
> On first run after installation or reboot, SkywarnPlus will not announce anything until it detects a change in alert state. That is normal behavior.

## TimeType Configuration

SkywarnPlus supports two timing models for alert processing:

- `ONSET` waits until the event is actually imminent.
- `EFFECTIVE` processes alerts as soon as they are issued by the NWS.

The default `ONSET` mode is usually the better choice for practical on-air use because it avoids announcing events too early.

You can inspect active alert data directly from the NWS API with:

```text
https://api.weather.gov/alerts/active?zone=YOUR_COUNTY_CODE_HERE
```

## Tail Messages

SkywarnPlus can automatically create and remove tail messages while weather alerts are active.

Example `rpt.conf` configuration:

```ini
tailmessagetime = 600000
tailsquashedtime = 30000
tailmessagelist = /tmp/SkywarnPlus/wx-tail
```

## Courtesy Tones

SkywarnPlus can automatically switch courtesy tones between normal and weather-alert modes.

Example `config.yaml` section:

```yaml
CourtesyTones:
  Enable: true
  ToneDir: /usr/local/bin/SkywarnPlus/SOUNDS/TONES
  Tones:
    ct1:
      Normal: Boop.ulaw
      WX: Stardust.ulaw
```

Example `rpt.conf` section:

```ini
[telemetry]
ct1 = /usr/local/bin/SkywarnPlus/SOUNDS/TONES/ct1
```

## CW / Voice IDs

SkywarnPlus can automatically change your ID audio based on active alerts.

Example `config.yaml` section:

```yaml
IDChange:
  Enable: false
  IDDir: /usr/local/bin/SkywarnPlus/SOUNDS/ID
  IDs:
    NormalID: NORMALID.ulaw
    WXID: WXID.ulaw
    RptID: RPTID.ulaw
```

Example `rpt.conf` section:

```ini
[NODENUMBER]
idrecording = /usr/local/bin/SkywarnPlus/SOUNDS/ID/RPTID
```

## Pushover Integration

SkywarnPlus can send alerts and debug notifications through Pushover.

1. Create a Pushover account.
2. Get your User Key.
3. Create an application key.
4. Add both values to `config.yaml`.

## SkyControl

`SkyControl.py` allows you to toggle or force certain functions without manually editing `config.yaml`.

Examples:

```bash
/usr/local/bin/SkywarnPlus/SkyControl.py enable false
/usr/local/bin/SkywarnPlus/SkyControl.py enable true
/usr/local/bin/SkywarnPlus/SkyControl.py changect normal
/usr/local/bin/SkywarnPlus/SkyControl.py changeid normal
```

## AlertScript

`AlertScript` lets you execute DTMF commands or shell scripts when specific alerts become active or clear.

Example:

```yaml
AlertScript:
  Enable: false
  Mappings:
    - Type: DTMF
      Nodes:
        - 1999
      Commands:
        - "*123*456*789"
      Triggers:
        - Tornado Warning
```

This makes it possible to trigger custom repeater behavior, notifications, scripts, or linked-node actions automatically.

## SkyDescribe

`SkyDescribe.py` can read back the detailed description of a stored alert.

Examples:

```bash
SkyDescribe.py 1
SkyDescribe.py "Tornado Warning"
```

This can also be used with AlertScript or DTMF commands.

## County Identifiers

SkywarnPlus can include county-specific audio tags in alert announcements.

You can either:

- generate them automatically with `CountyIDGen.py`
- create the audio files manually and reference them in `config.yaml`

## Supermon Integration

SkywarnPlus includes compatibility features for:

- Supermon 6.1 to 7.4
- Supermon 2

On ASL3 systems, helper logic may be needed because Asterisk no longer runs as root.

## Testing

SkywarnPlus can inject test alerts instead of calling the live NWS API.

Example `config.yaml` developer section:

```yaml
INJECT: true
INJECTALERTS:
  - Title: "Tornado Warning"
  - Title: "Tornado Watch"
```

## Debugging

Enable debug logging in `config.yaml`:

```yaml
Logging:
  Debug: true
```

Open an Asterisk console in another terminal while testing:

```bash
asterisk -rvvv
```

## Contributing

Pull requests, fixes, compatibility improvements, and documentation updates are welcome.

If you are using this fork to keep SkywarnPlus alive on newer systems, contributions that improve Debian 12, Debian 13, and ASL3 support are especially helpful.

## License

SkywarnPlus is licensed under the GPL-3.0 license.

Created by Mason Nelson (N5LSN/WRKF394)

Audio library voiced by Rachel Nelson (N5LSN/WRKF394 XYL)

Skywarn and the Skywarn logo are registered trademarks of the National Oceanic and Atmospheric Administration, used with permission.
