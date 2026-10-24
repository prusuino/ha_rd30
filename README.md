<img src="assets/rd30_readme_header_1280x320.png" alt="AK Modul-Bus RD30 — Home Assistant Integration" width="100%">

# RD30 Digital Interface for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/prusuino/ha_rd30/actions/workflows/validate.yml/badge.svg)](https://github.com/prusuino/ha_rd30/actions/workflows/validate.yml)

Reads the 30 digital contact inputs of an **AK MODUL-BUS RD30** module into
Home Assistant as binary sensors.

> [!IMPORTANT]
> **The RD30 alone is not enough.** The module only has an RS-232 serial
> port, and this integration speaks TCP/IP. You need a **serial device
> server** (serial-to-Ethernet converter) such as a **Moxa NPort 5110**
> between the RD30 and your network — see [What you need](#what-you-need).
> Plugging the RD30 into the Home Assistant host with a USB-to-serial
> adapter is **not** supported.

The RD30 pushes a byte on every input change, so this is a true
`local_push` integration: no polling delay, no cloud, no vendor account.

## What you need

```
 AK MODUL-BUS RD30 ──── RS-232 ────► Moxa NPort 5110 ──── Ethernet ────► Home Assistant
 30 contact inputs    crossed cable   (or a comparable      your LAN      this integration
                      9600 8N1        serial device server)               TCP client
```

| Part | Role | Notes |
|---|---|---|
| **RD30 module** | Reads the 30 contacts and reports changes on its serial port | Powered according to its data sheet; inputs 1–24 dry contacts, 25–30 opto-isolated |
| **Serial device server** (required) | Turns the RS-232 port into a TCP socket on your network | Tested with a **Moxa NPort 5110**. Any device server with a raw **TCP Server** mode (no telnet, no RFC 2217) should work, but only the NPort has been verified |
| **Crossed RS-232 cable** | RD30 ↔ device server | Pins 2↔3 crossed, 5 straight through — both ends are wired as DTE |
| **Home Assistant** | Runs this integration | 2025.4 or newer, network access to the device server |

Without the serial device server there is nothing for the integration to
connect to: it opens a TCP connection to the server's IP address and port,
and it has no serial-port mode of its own.

## Features

- 30 inputs as `binary_sensor` entities; **name them and pick a device class
  in the UI** (*Configure* on the integration) — no YAML, no code changes
- Event-driven updates (the module reports changes by itself)
- Full state query on connect, plus a periodic resync every minute — it
  heals a missed byte and doubles as the watchdog for a half-open TCP session
- Automatic reconnect with backoff (5 → 60 s), reset after every healthy
  connection
- Device identity check (`1` → `30`) during setup, so a wrong host or a
  wrong serial device is caught immediately instead of silently doing nothing
- Diagnostic connectivity entity with connect/disconnect timestamps, a
  reconnect counter, the last error text and a counter for bytes the
  protocol does not know
- Downloadable diagnostics with the link history, all raw input states and
  the configured names
- English, German, French and Italian

## Device server settings

Configure the serial device server before you add the integration:

| Setting | Value |
|---|---|
| Operation mode | **TCP Server** (raw socket) |
| TCP port | 4001 (any free port works; enter it in the integration) |
| Serial | **9600 baud, 8 data bits, no parity, 1 stop bit** |
| Flow control | none |
| Data packing (Moxa) | Packing length 0, delimiters disabled, Force transmit 0 |

> [!IMPORTANT]
> On a Moxa NPort, check **Data Packing** before anything else:
> `Packing length 0`, both delimiters **disabled**, `Force transmit 0`.
> With a delimiter enabled, the NPort buffers everything until that byte
> arrives — and the RD30 sends bare single bytes that never include it.
> The symptom is a TCP connection that opens fine and then stays completely
> silent in both directions.

> [!NOTE]
> A serial device server in TCP server mode usually accepts **one** client
> at a time. Close any other tool that is connected to the port before you
> set up the integration, and do not point two Home Assistant instances at
> the same RD30.

## Installation

### HACS (custom repository)

The integration is not in the HACS default store, so add it once as a
custom repository:

1. Click the button — it opens HACS on your instance with this repository
   pre-filled — and confirm **Add**:

   [![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=prusuino&repository=ha_rd30&category=integration)

   Without the button: HACS → three-dot menu → **Custom repositories** →
   `https://github.com/prusuino/ha_rd30`, type **Integration** → **Add**.
2. Open **RD30 Digital Interface** in HACS and click **Download**.
3. Restart Home Assistant.

### Manual

Copy `custom_components/rd30` into your Home Assistant `config/custom_components/`
directory and restart Home Assistant.

## Setup

**Settings → Devices & Services → Add Integration → RD30 Digital Interface.**
Enter the host and TCP port of the serial device server. The integration
sends the identity command and only creates the entry when the module
answers.

### Naming the inputs

All 30 inputs exist from the start, but only the ones you name are enabled —
the unwired rest stays out of your entity list until you need it.

Open the integration, click **Configure**, pick an input, enter a name and
choose a device class (door, window, moisture, running, …). The entity is
enabled and renamed right away. Tick **Reset** to remove the settings again;
the entity then falls back to *Input n*.

## Entities

| Entity | Type | Notes |
|---|---|---|
| *Input 1* … *Input 30* (or your names) | `binary_sensor` | `on` = contact closed. Attribute `input` holds the input number. Unavailable while the link is down or before the first sync. |
| *Connection* | `binary_sensor`, device class `connectivity`, diagnostic | Stays **available even while the connection is down** — a diagnostic entity that goes `unavailable` on connection loss would be silent exactly when it is needed. |

Attributes of the *Connection* entity:

| Attribute | Meaning |
|---|---|
| `host`, `port` | where the integration is connecting to |
| `connected_since` | start of the current connection |
| `last_disconnected` | when the connection last dropped |
| `connect_count` | connect counter — rising means a flapping link |
| `last_event` | last pushed input change |
| `unknown_bytes` | bytes the protocol does not know — rising means wrong baud rate, data packing, or a second client on the port |
| `last_error` | last error text, e.g. `device did not answer identify (30)` |

## Protocol

Serial: **9600 baud, 8N1, no handshake.**

The module reports changes on its own:

| Direction | Byte | Meaning |
|---|---|---|
| RD30 → host | `128 + n` (129…158) | input *n* closed |
| RD30 → host | `64 + n` (65…94) | input *n* opened |

Queries — one byte out, one byte back:

| Command | Reply |
|---|---|
| `1` | `30` (device identification) |
| `32` | bit field, inputs 1–8 |
| `33` | bit field, inputs 9–16 |
| `34` | bit field, inputs 17–24 |
| `35` | bit field, inputs 25–30 |

Inputs 1–24 are dry contacts against GND; inputs 25–30 are opto-isolated
for 5–24 V.

Event bytes and query replies share the same value space, and the protocol
has no framing — so a query sequence always starts with command `1`. Its
reply `30` is a value no event byte can take, which makes it an anchor the
stream can be realigned on: everything arriving before it is a pushed event
and is applied as one.

Without that anchor a single event byte landing in the query window is
consumed as the reply to command `32`, and every following reply shifts by
one group — inputs 25–30 silently inherit the states of 17–24 and keep them
until the next resync.

## Branding

`custom_components/rd30/brand/` ships the icon and logo directly with the
integration. Since Home Assistant 2026.3 local brand images take priority
over the brands CDN, so the integration shows its own icon without any
pull request against `home-assistant/brands`.

Source files (SVG/HTML) and additional sizes live in `assets/`;
`brands/custom_integrations/rd30/` holds a ready-to-submit copy should the
integration ever be published through the brands repository.

## Disclaimer

This is an independent project, not affiliated with or endorsed by
AK MODUL-BUS Computer GmbH or Moxa Inc. Use at your own risk.

---
*If you find this integration useful, you can [buy me a coffee](https://www.buymeacoffee.com/prusuino).*
