# Changelog

## 1.0.0 — 2026-10-24

First public release.

- **Options flow for the inputs:** name any of the 30 inputs and give it a device class (door, moisture, running, …) under *Configure*. Named inputs are enabled automatically; unnamed ones stay disabled and are called *Input n*. Previously the names of the wired inputs were compiled into the code.
- Entity names and the connectivity entity's attributes are now English (`connected_since`, `last_disconnected`, `connect_count`, `last_event`, `unknown_bytes`, `last_error`); the entity names are translated (English, German, French, Italian). Existing entity ids are kept — Home Assistant keeps the registry ids once created.
- Each input entity carries its input number as the attribute `input`.
- Diagnostics download includes the configured input names.
- Config flow uses selectors; the port field is validated (1–65535).
- Repository prepared for HACS as a custom repository (`hacs.json`, validation workflow, MIT license, security policy).

Earlier versions (0.1 – 0.5) were private and are summarised here for reference:

- 0.5.x — resync race fixed, backoff reset after a healthy connection, state writes only for inputs that changed.
- 0.4.0 — inputs 26 and 27 wired.
- 0.3.x — identity anchor (command 1 → 30) to realign the byte stream before every query sequence.
- 0.2.x — connectivity diagnostic entity with link history and unknown-byte counter, downloadable diagnostics.
- 0.1.0 — first working version: 30 inputs as binary sensors, event-driven, periodic resync, reconnect with backoff.
