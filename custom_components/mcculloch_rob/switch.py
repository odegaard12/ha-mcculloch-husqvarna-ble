"""Interruptores para los ajustes que el robot deja leer y escribir."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RobConfigEntry
from .automower_ble.protocol import ResponseResult
from .entity import RobEntity


@dataclass(frozen=True, kw_only=True)
class RobSwitchDescription(SwitchEntityDescription):
    get: str
    set: str
    value_fn: Callable[[Any], Any] = lambda v: v


SWITCHES: tuple[RobSwitchDescription, ...] = (
    RobSwitchDescription(key="eco", name="Modo ECO", get="GetEcoModeEnabled", set="SetEcoModeEnabled"),
    RobSwitchDescription(key="frost", name="Sensor de heladas", get="GetFrostSensorEnabled",
                         set="SetFrostSensorEnabled"),
    RobSwitchDescription(key="frost_legacy", name="Sensor de heladas (antiguo)",
                         get="GetFrostSensorEnabledLegacy", set="SetFrostSensorEnabledLegacy"),
    RobSwitchDescription(key="sensor_control", name="SensorControl (ritmo según crecimiento)",
                         get="GetSensorControlEnabled", set="SetSensorControlEnabled"),
    RobSwitchDescription(key="garage", name="Modo garaje", get="GetGarageEnabled", set="SetGarageEnabled"),
    RobSwitchDescription(key="radar", name="Radar anticolisión", get="GetAntiCollisionRadar",
                         set="SetAntiCollisionRadarEnabled",
                         value_fn=lambda v: v.get("enabled") if isinstance(v, dict) and v.get("available") else None),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: RobConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        RobSwitch(coordinator, d)
        for d in SWITCHES
        if d.get in coordinator.supported
        and d.value_fn(coordinator.probe_report.get(d.get, {}).get("value")) is not None
    )


class RobSwitch(RobEntity, SwitchEntity):
    entity_description: RobSwitchDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, description: RobSwitchDescription) -> None:
        super().__init__(coordinator, description.key, description.name)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        value = self.entity_description.value_fn((self.coordinator.data or {}).get(self.entity_description.get))
        return None if value is None else bool(value)

    async def _set(self, enabled: bool) -> None:
        await self.coordinator.ensure_connected()
        result, _ = await self.coordinator.read(self.entity_description.set, enabled=enabled)
        if result is not ResponseResult.OK:
            raise HomeAssistantError(f"El robot rechazó el cambio: {result.name}")
        result, value = await self.coordinator.read(self.entity_description.get)
        if result is ResponseResult.OK:
            self.coordinator.data[self.entity_description.get] = value
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
