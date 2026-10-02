"""Alta del robot: se elige de los detectados por Bluetooth (o MAC a mano) y se empareja."""

from __future__ import annotations

import random
from typing import Any

from bleak import BleakError
from bleak_retry_connector import close_stale_connections_by_address
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID, CONF_PIN

from .automower_ble.mower import Mower
from .automower_ble.protocol import ResponseResult
from .const import DOMAIN, LOGGER, SERVICE_UUID


def _pin_ok(pin: str) -> bool:
    return pin == "" or (pin.isdigit() and int(pin) <= 0xFFFF)


class RobConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._address: str | None = None
        self._name: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._address = discovery_info.address
        self._name = discovery_info.name
        self.context["title_placeholders"] = {"name": self._name or self._address}
        return await self.async_step_pair()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._address = user_input[CONF_ADDRESS].upper().strip()
            await self.async_set_unique_id(self._address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self.async_step_pair()

        found = {
            i.address: f"{i.name or '?'} ({i.address}, {i.rssi} dBm)"
            for i in bluetooth.async_discovered_service_info(self.hass, connectable=True)
            if SERVICE_UUID in i.service_uuids
            and i.address not in self._async_current_ids(include_ignore=False)
        }
        field = vol.In(found) if found else str
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): field}),
            description_placeholders={"count": str(len(found))},
        )

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        assert self._address
        if user_input is not None:
            pin = user_input.get(CONF_PIN, "").strip()
            if not _pin_ok(pin):
                errors["base"] = "invalid_pin"
            else:
                channel_id = random.randint(1, 0xFFFFFFFF)
                errors["base"], title = await self._try_connect(channel_id, pin)
                if errors["base"] == "ok":
                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_ADDRESS: self._address,
                            CONF_CLIENT_ID: channel_id,
                            CONF_PIN: pin,
                        },
                    )

        return self.async_show_form(
            step_id="pair",
            data_schema=vol.Schema({vol.Optional(CONF_PIN, default=""): str}),
            description_placeholders={"address": self._address},
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """El robot rechazó el PIN guardado (lo cambiaron en el menú): se pide otra vez."""
        self._address = entry_data[CONF_ADDRESS]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            pin = user_input.get(CONF_PIN, "").strip()
            if not _pin_ok(pin):
                errors["base"] = "invalid_pin"
            else:
                # mismo canal: así no hace falta volver a poner el robot en modo emparejamiento
                result, _ = await self._try_connect(entry.data[CONF_CLIENT_ID], pin)
                if result == "ok":
                    return self.async_update_reload_and_abort(entry, data_updates={CONF_PIN: pin})
                errors["base"] = result
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PIN, default=""): str}),
            description_placeholders={"address": self._address or ""},
            errors=errors,
        )

    async def _try_connect(self, channel_id: int, pin: str) -> tuple[str, str]:
        assert self._address
        device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if device is None:
            return "not_found", ""
        mower = Mower(channel_id, self._address, int(pin) if pin else None)
        await close_stale_connections_by_address(self._address)
        try:
            result = await mower.connect(device)
            if result is ResponseResult.INVALID_PIN:
                return "invalid_auth", ""
            if result is not ResponseResult.OK:
                LOGGER.warning("Emparejado fallido: %s", result.name)
                return "cannot_connect", ""
            manufacturer = await mower.get_manufacturer() or "McCulloch"
            model = await mower.get_model() or "ROB"
            return "ok", f"{manufacturer} {model}"
        except (BleakError, TimeoutError) as err:
            LOGGER.warning("Emparejado fallido: %s", err)
            return "cannot_connect", ""
        finally:
            if mower.is_connected():
                await mower.disconnect()
