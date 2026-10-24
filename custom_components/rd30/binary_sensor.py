"""Binary sensors: one per RD30 input, plus a connectivity diagnostic."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_HOST, CONF_PORT, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RD30ConfigEntry
from .const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    DEVICE_CLASS_NONE,
    DOMAIN,
    NUM_INPUTS,
    input_options,
)
from .hub import RD30Hub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RD30ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the connectivity entity and all 30 input entities."""
    hub = entry.runtime_data
    entities: list[BinarySensorEntity] = [RD30Connection(hub, entry)]
    entities += [RD30Input(hub, entry, n) for n in range(1, NUM_INPUTS + 1)]
    async_add_entities(entities)


def _device_info(entry: RD30ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name="RD30 Digital Interface",
        manufacturer="AK MODUL-BUS",
        model="RD30",
    )


class RD30Connection(BinarySensorEntity):
    """Diagnostic: is the TCP link to the RD30 up?

    Deliberately ALWAYS available.  A diagnostic entity that itself goes
    unavailable on connection loss falls silent exactly when it is needed.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: RD30Hub, entry: RD30ConfigEntry) -> None:
        self._hub = hub
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_connection"
        self._attr_device_info = _device_info(entry)

    async def async_added_to_hass(self) -> None:
        self._hub.add_listener(self._on_update)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.remove_listener(self._on_update)

    @callback
    def _on_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._hub.available

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "host": self._entry.data[CONF_HOST],
            "port": self._entry.data[CONF_PORT],
            "connected_since": self._hub.last_connected,
            "last_disconnected": self._hub.last_disconnected,
            "connect_count": self._hub.connect_count,
            "last_event": self._hub.last_event,
            # No last_sync here on purpose: the resync runs every minute but
            # only notifies the inputs that changed, so the attribute would
            # freeze and fake a stalled sync.  It is in the downloadable
            # diagnostics, which read the hub directly.
            # unknown_bytes only grows when bytes arrive that the protocol
            # does not know — the signature of a wrong baud rate, data
            # packing on the device server, or a second client on the port.
            "unknown_bytes": self._hub.unknown_bytes,
            "last_error": self._hub.last_error,
        }


class RD30Input(BinarySensorEntity):
    """One RD30 input contact.

    Name and device class come from the options flow.  An input without a
    name is called "Input n" (translated) and is created disabled, so the
    unwired ones do not clutter the entity list; naming an input enables it.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hub: RD30Hub, entry: RD30ConfigEntry, number: int) -> None:
        self._hub = hub
        self._number = number
        self._attr_unique_id = f"{entry.unique_id}_input_{number}"
        self._attr_device_info = _device_info(entry)

        settings = input_options(entry.options, number)
        name = (settings.get(CONF_NAME) or "").strip()
        device_class = settings.get(CONF_DEVICE_CLASS) or DEVICE_CLASS_NONE
        if name:
            self._attr_name = name
            self._attr_entity_registry_enabled_default = True
        else:
            self._attr_translation_key = "input"
            self._attr_translation_placeholders = {"number": str(number)}
            self._attr_entity_registry_enabled_default = False
        if device_class != DEVICE_CLASS_NONE:
            self._attr_device_class = BinarySensorDeviceClass(device_class)

    async def async_added_to_hass(self) -> None:
        self._hub.add_listener(self._on_update, self._number)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.remove_listener(self._on_update, self._number)

    @callback
    def _on_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._hub.available and self._hub.states[self._number] is not None

    @property
    def is_on(self) -> bool | None:
        return self._hub.states[self._number]

    @property
    def extra_state_attributes(self) -> dict:
        return {"input": self._number}
