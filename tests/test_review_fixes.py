"""Arreglos de la revisión: arranque con el robot lejos, valores desconocidos, PIN nuevo y diagnóstico sin datos personales."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.mcculloch_rob.const import DOMAIN
from custom_components.mcculloch_rob.diagnostics import async_get_config_entry_diagnostics

from .test_integration import ADDRESS, ANSWERS, _setup, auto_enable, fake  # noqa: F401  (fixtures)


async def test_out_of_range_keeps_entities(hass: HomeAssistant, fake) -> None:
    """Conocido de antes y ahora lejos: las entidades existen (no disponibles) en vez de desaparecer."""
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    with patch("custom_components.mcculloch_rob.coordinator.bluetooth.async_ble_device_from_address", return_value=None):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        # el cortacésped (órdenes) no está; los datos muestran lo último que se supo, guardado en disco
        assert hass.states.get("lawn_mower.robot_cortacesped").state == "unavailable"
        assert hass.states.get("sensor.robot_cortacesped_bateria").state == "87"
        assert hass.states.get("sensor.robot_cortacesped_programacion_tareas").state not in ("unknown", "unavailable")


async def test_last_seen_survives_out_of_range(hass: HomeAssistant, fake) -> None:
    """«Última conexión»: se rellena al hablar con el robot y sigue disponible aunque deje de responder."""
    entry = await _setup(hass)
    seen = hass.states.get("sensor.robot_cortacesped_ultima_conexion")
    assert seen is not None and seen.state not in ("unknown", "unavailable")
    with patch("custom_components.mcculloch_rob.coordinator.bluetooth.async_ble_device_from_address", return_value=None):
        entry.runtime_data.mower.connected = False
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("lawn_mower.robot_cortacesped").state == "unavailable"
        assert hass.states.get("sensor.robot_cortacesped_ultima_conexion").state == seen.state


async def test_unknown_state_code_does_not_break(hass: HomeAssistant, fake) -> None:
    old = ANSWERS["GetState"]
    ANSWERS["GetState"] = 99  # código que no está en el enum
    try:
        await _setup(hass)
        assert hass.states.get("sensor.robot_cortacesped_estado").state == "unknown"
        assert hass.states.get("sensor.robot_cortacesped_bateria").state == "87"
    finally:
        ANSWERS["GetState"] = old


async def test_not_available_clears_old_value(hass: HomeAssistant, fake) -> None:
    entry = await _setup(hass)
    assert hass.states.get("sensor.robot_cortacesped_proximo_arranque").state not in ("unknown", "unavailable")
    old = ANSWERS.pop("GetNextStartTime")
    try:
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("sensor.robot_cortacesped_proximo_arranque").state == "unknown"
    finally:
        ANSWERS["GetNextStartTime"] = old


async def test_reauth_updates_pin(hass: HomeAssistant, fake) -> None:
    entry = await _setup(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"pin": "9999"})
    assert result["type"] is FlowResultType.FORM and result["errors"]["base"] == "invalid_auth"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"pin": "1234"})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data["pin"] == "1234"


async def test_diagnostics_hide_identity(hass: HomeAssistant, fake) -> None:
    entry = await _setup(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert ADDRESS not in text and "123456" not in text and "'client_id': 99" not in text
    assert diag["data"]["GetBatteryLevel"] == 87  # lo útil sigue ahí
    assert DOMAIN  # import usado
