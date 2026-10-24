"""RD30 digital interface (AK MODUL-BUS) behind a serial device server."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .hub import RD30Hub

PLATFORMS = [Platform.BINARY_SENSOR]

type RD30ConfigEntry = ConfigEntry[RD30Hub]


async def async_setup_entry(hass: HomeAssistant, entry: RD30ConfigEntry) -> bool:
    """Start the TCP client and set up the platforms."""
    hub = RD30Hub(entry.data[CONF_HOST], entry.data[CONF_PORT])
    await hub.async_start()
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Names and device classes live in the options; a reload applies them.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RD30ConfigEntry) -> bool:
    """Stop the TCP client when the entry is unloaded."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        await entry.runtime_data.async_stop()
    return ok


async def _async_options_updated(hass: HomeAssistant, entry: RD30ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
