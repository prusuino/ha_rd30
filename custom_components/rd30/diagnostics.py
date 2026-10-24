"""Diagnostics for the RD30 integration.

Everything the download button needs to tell a wiring problem from a
protocol one: link history, the byte counters, the raw input states
(None = never synced) and the configured input names.
"""
from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import RD30ConfigEntry
from .const import CONF_INPUTS, NUM_INPUTS, RESYNC_INTERVAL


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RD30ConfigEntry
) -> dict[str, Any]:
    hub = entry.runtime_data
    return {
        "connection": {
            "host": entry.data[CONF_HOST],
            "port": entry.data[CONF_PORT],
            "available": hub.available,
            "last_connected": hub.last_connected,
            "last_disconnected": hub.last_disconnected,
            "connect_count": hub.connect_count,
            "last_error": hub.last_error,
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
        "options": {CONF_INPUTS: entry.options.get(CONF_INPUTS, {})},
    }
