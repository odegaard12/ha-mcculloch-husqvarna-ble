"""Pruebas de la integración con un robot simulado (sin Bluetooth real)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.mcculloch_rob.automower_ble.protocol import ResponseResult
from custom_components.mcculloch_rob.const import DOMAIN

PROTOCOL = json.loads(
    (Path(__file__).parents[1] / "custom_components/mcculloch_rob/automower_ble/protocol.json").read_text()
)
ADDRESS = "AA:BB:CC:DD:EE:FF"
NEXT_START = 1_790_000_000  # hora local codificada como UTC

# Lo que responde el robot simulado; lo que no esta aqui responde NOT_AVAILABLE.
ANSWERS: dict[str, Any] = {
    "GetBatteryLevel": 87,
    "IsCharging": 1,
    "GetBatteryVoltage": 18650,
    "GetState": 7,  # RESTRICTED
    "GetActivity": 1,  # CHARGING
    "GetMode": 0,
    "GetError": 0,
    "GetNextStartTime": NEXT_START,
    "GetEcoModeEnabled": 0,
    "GetModel": {"deviceType": 22, "deviceVariant": 2},
    "GetSerialNumber": 123456,
    "GetAllStatistics": {
        "totalRunningTime": 36000, "totalCuttingTime": 30000, "totalChargingTime": 7200,
        "totalSearchingTime": 600, "numberOfCollisions": 42, "numberOfChargingCycles": 7,
        "cuttingBladeUsageTime": 3600,
    },
    "GetNumberOfMessages": 2,
    "GetNumberOfTasks": 0,
}


class FakeMower:
    instances: list[FakeMower] = []

    def __init__(self, channel_id, address, pin=None) -> None:
        self.channel_id, self.address, self.pin = channel_id, address, pin
        self.connected = False
        self.sent: list[tuple[str, dict]] = []
        FakeMower.instances.append(self)

    def is_connected(self) -> bool:
        return self.connected

    async def connect(self, device) -> ResponseResult:
        if self.pin is not None and self.pin != 1234:
            return ResponseResult.INVALID_PIN
        self.connected = True
        return ResponseResult.OK

    async def disconnect(self) -> None:
        self.connected = False

    async def get_protocol(self):
        return PROTOCOL

    async def get_model(self):
        return "Rob S600"

    async def get_manufacturer(self):
        return "McCulloch"

    tasks: list = []

    async def get_tasks(self):
        return list(FakeMower.tasks)

    async def set_tasks(self, tasks):
        self.sent.append(("set_tasks", {"n": len(tasks)}))
        FakeMower.tasks = list(tasks)

    async def command_response(self, name, warn_on_error=True, **kwargs):
        self.sent.append((name, kwargs))
        if name == "GetMessage":
            return ResponseResult.OK, {"time": NEXT_START - 86400 * kwargs["messageId"], "code": 13, "severity": 2}
        if name.startswith("Set"):
            if "enabled" in kwargs:
                ANSWERS[name.replace("Set", "Get", 1)] = int(kwargs["enabled"])
            return ResponseResult.OK, None
        if name in ANSWERS:
            return ResponseResult.OK, ANSWERS[name]
        return ResponseResult.NOT_AVAILABLE, None

    async def mower_override(self, hours=3.0):
        self.sent.append(("override", {"hours": hours}))
        return ResponseResult.OK

    async def mower_park(self):
        return ResponseResult.OK

    async def mower_pause(self):
        return None

    async def mower_resume(self):
        return None


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    yield


@pytest.fixture
def fake():
    FakeMower.instances.clear()
    with (
        patch("custom_components.mcculloch_rob.Mower", FakeMower),
        patch("custom_components.mcculloch_rob.config_flow.Mower", FakeMower),
        patch("custom_components.mcculloch_rob.coordinator.bluetooth.async_ble_device_from_address", return_value=object()),
        patch("custom_components.mcculloch_rob.config_flow.bluetooth.async_ble_device_from_address", return_value=object()),
        patch("custom_components.mcculloch_rob.coordinator.close_stale_connections_by_address"),
        patch("custom_components.mcculloch_rob.config_flow.close_stale_connections_by_address"),
        patch("custom_components.mcculloch_rob.config_flow.bluetooth.async_discovered_service_info", return_value=[]),
        patch("homeassistant.loader.Integration.dependencies", new=[]),
    ):
        yield


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ADDRESS, title="McCulloch Rob S600",
        data={"address": ADDRESS, "client_id": 99, "pin": "1234"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities_only_for_supported(hass: HomeAssistant, fake) -> None:
    entry = await _setup(hass)
    ids = {e.unique_id.split("_", 1)[1] for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
    assert {"battery", "battery_voltage", "state", "activity", "next_start", "stat_collisions",
            "stat_totalCuttingTime", "charging", "problem", "eco", "mower", "last_message"} <= ids
    # No responde -> no hay entidad
    assert "battery_temperature" not in ids and "garage" not in ids and "in_station" not in ids


async def test_values(hass: HomeAssistant, fake) -> None:
    await _setup(hass)
    st = hass.states
    assert st.get("sensor.robot_cortacesped_bateria").state == "87"
    assert st.get("sensor.robot_cortacesped_estado").state == "restricted"
    assert st.get("sensor.robot_cortacesped_actividad").state == "charging"
    assert st.get("lawn_mower.robot_cortacesped").state == "docked"
    assert st.get("binary_sensor.robot_cortacesped_cargando").state == "on"
    assert st.get("binary_sensor.robot_cortacesped_averia").state == "off"
    assert float(st.get("sensor.robot_cortacesped_tiempo_total_cortando").state) == pytest.approx(30000 / 3600, 0.01)
    assert st.get("sensor.robot_cortacesped_choques").state == "42"
    assert st.get("sensor.robot_cortacesped_tension_bateria_crudo").state == "18650"
    last = st.get("sensor.robot_cortacesped_ultimo_aviso")
    assert last.state == "trapped" or last.attributes["avisos"][0]["codigo"] == 13
    assert len(last.attributes["avisos"]) == 2
    # Proximo arranque: la hora "UTC" del robot se interpreta como hora local
    from datetime import UTC, datetime
    from homeassistant.util import dt as dt_util
    ts = dt_util.parse_datetime(st.get("sensor.robot_cortacesped_proximo_arranque").state)
    wall = datetime.fromtimestamp(NEXT_START, UTC).replace(tzinfo=None)
    assert dt_util.as_local(ts).replace(tzinfo=None) == wall


async def test_switch_and_service(hass: HomeAssistant, fake) -> None:
    await _setup(hass)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.robot_cortacesped_modo_eco"}, blocking=True)
    assert ("SetEcoModeEnabled", {"enabled": True}) in FakeMower.instances[-1].sent
    assert hass.states.get("switch.robot_cortacesped_modo_eco").state == "on"

    resp = await hass.services.async_call(
        DOMAIN, "send_command", {"command": "GetBatteryLevel"}, blocking=True, return_response=True
    )
    assert resp == {"command": "GetBatteryLevel", "result": "OK", "value": 87}

    await hass.services.async_call("lawn_mower", "start_mowing", {"entity_id": "lawn_mower.robot_cortacesped"}, blocking=True)
    assert ("override", {"hours": 3.0}) in FakeMower.instances[-1].sent


async def test_config_flow_manual(hass: HomeAssistant, fake) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"address": ADDRESS.lower()})
    assert result["step_id"] == "pair"
    bad = await hass.config_entries.flow.async_configure(result["flow_id"], {"pin": "9999"})
    assert bad["errors"] == {"base": "invalid_auth"}
    with patch("custom_components.mcculloch_rob.async_setup_entry", return_value=True):
        ok = await hass.config_entries.flow.async_configure(result["flow_id"], {"pin": "1234"})
    assert ok["type"] == "create_entry"
    assert ok["title"] == "McCulloch Rob S600"
    assert ok["data"]["address"] == ADDRESS and ok["data"]["pin"] == "1234"


async def test_stopped_is_paused(hass: HomeAssistant, fake) -> None:
    ANSWERS["GetState"], ANSWERS["GetActivity"] = 2, 0  # STOPPED, NONE (como el S800 real)
    try:
        await _setup(hass)
        assert hass.states.get("lawn_mower.robot_cortacesped").state == "paused"
    finally:
        ANSWERS["GetState"], ANSWERS["GetActivity"] = 7, 1


async def test_set_schedule(hass: HomeAssistant, fake) -> None:
    from homeassistant.exceptions import ServiceValidationError
    FakeMower.tasks = []
    await _setup(hass)
    resp = await hass.services.async_call(
        DOMAIN, "set_schedule",
        {"tasks": [{"start": "08:00", "end": "20:10", "days": ["monday", "tuesday", "wednesday"]},
                   {"start": "09:30", "end": "24:00", "days": ["saturday"]}]},
        blocking=True, return_response=True,
    )
    t = resp["tasks"]
    assert len(t) == 2
    assert t[0]["start_time_in_minutes"] == 480 and t[0]["duration_in_minutes"] == 730
    assert t[0]["on_monday"] and t[0]["on_wednesday"] and not t[0]["on_thursday"]
    assert t[1]["start_time_in_minutes"] == 570 and t[1]["duration_in_minutes"] == 870 and t[1]["on_saturday"]
    # la tarjeta ve la programacion nueva sin esperar al sondeo lento
    assert hass.states.get("sensor.robot_cortacesped_programacion_tareas").attributes["tareas"] == t

    for bad in ({"start": "20:00", "end": "08:00", "days": ["monday"]},
                {"start": "25:00", "end": "26:00", "days": ["monday"]},
                {"start": "8h", "end": "9:00", "days": ["monday"]}):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(DOMAIN, "set_schedule", {"tasks": [bad]}, blocking=True)
    assert len(FakeMower.tasks) == 2  # lo invalido no llega al robot

    await hass.services.async_call(DOMAIN, "set_schedule", {"tasks": []}, blocking=True)
    assert FakeMower.tasks == []


async def test_mow_for_and_park_for(hass: HomeAssistant, fake) -> None:
    import voluptuous as vol
    await _setup(hass)
    sent = FakeMower.instances[-1].sent
    await hass.services.async_call(DOMAIN, "mow_for", {"hours": 2.5}, blocking=True)
    assert ("override", {"hours": 2.5}) in sent
    await hass.services.async_call(DOMAIN, "park_for", {"hours": 12}, blocking=True)
    assert ("SetOverridePark", {"duration": 43200}) in sent
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "mow_for", {"hours": 30}, blocking=True)
