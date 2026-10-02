"""Sensores binarios."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RobConfigEntry
from .entity import RobEntity


@dataclass(frozen=True, kw_only=True)
class RobBinaryDescription(BinarySensorEntityDescription):
    command: str
    value_fn: Callable[[dict[str, Any]], Any]


def _field(command: str, field: str) -> Callable[[dict], Any]:
    return lambda d: (d.get(command) or {}).get(field)


BINARY: tuple[RobBinaryDescription, ...] = (
    RobBinaryDescription(key="charging", name="Cargando", command="IsCharging",
                         device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
                         value_fn=lambda d: d.get("IsCharging")),
    RobBinaryDescription(key="problem", name="Avería", command="GetError",
                         device_class=BinarySensorDeviceClass.PROBLEM,
                         value_fn=lambda d: None if d.get("GetError") is None else d["GetError"] != 0),
    RobBinaryDescription(key="in_station", name="En la base", command="GetSignalQuality",
                         device_class=BinarySensorDeviceClass.PLUG,
                         value_fn=_field("GetSignalQuality", "inChargingStation")),
    RobBinaryDescription(key="lifted", name="Levantado", command="GetComboardSensorData",
                         device_class=BinarySensorDeviceClass.SAFETY,
                         value_fn=_field("GetComboardSensorData", "lift")),
    RobBinaryDescription(key="collision", name="Choque", command="GetComboardSensorData",
                         device_class=BinarySensorDeviceClass.SAFETY,
                         value_fn=_field("GetComboardSensorData", "collision")),
    RobBinaryDescription(key="upside_down", name="Volcado", command="GetComboardSensorData",
                         device_class=BinarySensorDeviceClass.SAFETY,
                         value_fn=_field("GetComboardSensorData", "upsideDown")),
    RobBinaryDescription(key="startup_required", name="Requiere secuencia de arranque",
                         command="GetStartupSequenceRequired", entity_category=EntityCategory.DIAGNOSTIC,
                         value_fn=lambda d: d.get("GetStartupSequenceRequired")),
    RobBinaryDescription(key="operator_logged_in", name="PIN aceptado",
                         command="IsOperatorLoggedIn", entity_category=EntityCategory.DIAGNOSTIC,
                         value_fn=lambda d: d.get("IsOperatorLoggedIn")),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: RobConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        RobBinary(coordinator, d) for d in BINARY if d.command in coordinator.supported
    )


class RobBinary(RobEntity, BinarySensorEntity):
    entity_description: RobBinaryDescription

    def __init__(self, coordinator, description: RobBinaryDescription) -> None:
        super().__init__(coordinator, description.key, description.name)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        value = self.entity_description.value_fn(self.coordinator.data or {})
        return None if value is None else bool(value)
