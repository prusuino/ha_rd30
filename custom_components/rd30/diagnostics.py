"""Diagnostics for the RD30 integration.

Everything the download button needs to tell a wiring problem from a
protocol one: link history, the byte counters, the raw input states
(None = never synced) and the configured device classes.

The host, the port and the names given to the inputs are redacted: an
input name can tell what a building's alarm system watches. An error text
is kept, with any address in it masked.
"""
from __future__ import annotations

import re
from typing import Any

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import RD30ConfigEntry
from .const import CONF_INPUTS, CONF_NAME, NUM_INPUTS, RESYNC_INTERVAL

REDACTED = "**REDACTED**"
_IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def _masked_error(error: str | None, host: str) -> str | None:
    """The error text without the address: socket errors repeat it."""
    if not error:
        return error
    return _IPV4.sub(REDACTED, error.replace(host, REDACTED))


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RD30ConfigEntry
) -> dict[str, Any]:
    hub = entry.runtime_data
    return {
        "connection": {
            "host": REDACTED,
            "port": REDACTED,
            "available": hub.available,
            "last_connected": hub.last_connected,
            "last_disconnected": hub.last_disconnected,
            "connect_count": hub.connect_count,
            "last_error": _masked_error(hub.last_error, entry.data[CONF_HOST]),
        },
        "protocol": {
            "last_event": hub.last_event,
            "last_sync": hub.last_sync,
            "resync_interval": RESYNC_INTERVAL,
            "unknown_bytes": hub.unknown_bytes,
        },
        "inputs": {
            str(number): hub.states[number]
            for number in range(1, NUM_INPUTS + 1)
        },
        "options": {
            CONF_INPUTS: {
                number: {**settings, CONF_NAME: REDACTED}
                for number, settings in entry.options.get(CONF_INPUTS, {}).items()
            }
        },
    }
