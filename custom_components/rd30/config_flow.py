"""Config flow (host/port + identity check) and options flow (input names)."""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_DEVICE_CLASS,
    CONF_INPUT,
    CONF_INPUTS,
    CONF_NAME,
    CONF_RESET,
    DEFAULT_PORT,
    DEVICE_CLASS_NONE,
    DOMAIN,
    INPUT_DEVICE_CLASSES,
    NUM_INPUTS,
    input_options,
)
from .hub import async_probe

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
        ),
    }
)


class RD30ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for host/port and verify the device identity (1 -> 30)."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RD30OptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            await self.async_set_unique_id(f"rd30_{host}_{port}")
            self._abort_if_unique_id_configured()
            try:
                ok = await async_probe(host, port)
            except (OSError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                if ok:
                    return self.async_create_entry(
                        title=f"RD30 ({host})",
                        data={CONF_HOST: host, CONF_PORT: port},
                    )
                errors["base"] = "no_identify"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class RD30OptionsFlow(OptionsFlow):
    """Name the wired inputs and give them a device class.

    Two steps: pick an input, then set its name and device class.  Naming an
    input also enables its entity if the integration had created it disabled
    (unwired inputs start disabled).  Resetting an input removes its settings;
    the entity keeps whatever enabled state it has.
    """

    def __init__(self) -> None:
        self._number: int | None = None

    def _current(self) -> dict:
        return dict(self.config_entry.options.get(CONF_INPUTS) or {})

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._number = int(user_input[CONF_INPUT])
            return await self.async_step_input()

        inputs = self._current()
        choices = [
            SelectOptionDict(
                value=str(n),
                label=f"{n}: {inputs[str(n)][CONF_NAME]}"
                if inputs.get(str(n), {}).get(CONF_NAME)
                else f"{n}: –",
            )
            for n in range(1, NUM_INPUTS + 1)
        ]
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INPUT): SelectSelector(
                        SelectSelectorConfig(
                            options=choices, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_input(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._number is not None
        number = self._number
        inputs = self._current()
        settings = input_options(self.config_entry.options, number)

        if user_input is not None:
            name = (user_input.get(CONF_NAME) or "").strip()
            device_class = user_input.get(CONF_DEVICE_CLASS) or DEVICE_CLASS_NONE
            if user_input.get(CONF_RESET) or not name:
                inputs.pop(str(number), None)
            else:
                inputs[str(number)] = {
                    CONF_NAME: name,
                    CONF_DEVICE_CLASS: device_class,
                }
                self._enable_entity(number)
            return self.async_create_entry(data={CONF_INPUTS: inputs})

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NAME,
                    description={"suggested_value": settings.get(CONF_NAME, "")},
                ): TextSelector(),
                vol.Required(
                    CONF_DEVICE_CLASS,
                    default=settings.get(CONF_DEVICE_CLASS) or DEVICE_CLASS_NONE,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=INPUT_DEVICE_CLASSES,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="device_class",
                    )
                ),
                vol.Optional(CONF_RESET, default=False): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="input",
            data_schema=schema,
            description_placeholders={"number": str(number)},
        )

    @callback
    def _enable_entity(self, number: int) -> None:
        """Enable the input's entity if the integration had disabled it."""
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN,
            DOMAIN,
            f"{self.config_entry.unique_id}_input_{number}",
        )
        if entity_id is None:
            return
        entry = registry.async_get(entity_id)
        if entry and entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
            registry.async_update_entity(entity_id, disabled_by=None)
