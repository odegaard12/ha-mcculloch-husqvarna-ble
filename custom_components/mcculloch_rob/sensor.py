"""Sensores: un descriptor por dato del protocolo; solo se crean los que el robot responde."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import RobConfigEntry
from .automower_ble.error_codes import ErrorCodes
from .automower_ble.protocol import ModeOfOperation, MowerActivity, MowerState, OverrideAction
from .entity import RobEntity

LOGGER = logging.getLogger(__name__)
DIAG = EntityCategory.DIAGNOSTIC
TOTAL = SensorStateClass.TOTAL_INCREASING
MEAS = SensorStateClass.MEASUREMENT


def _enum(enum: type, value: int | None, strict: bool = True) -> str | None:
    """strict: para sensores ENUM, que solo admiten sus opciones; un código nuevo sale como desconocido."""
    if value is None:
        return None
    try:
        return enum(value).name.lower()
    except ValueError:
        if strict:
            LOGGER.debug("Valor %s desconocido para %s", value, enum.__name__)
            return None
        return f"desconocido_{value}"


def _local_ts(value: int | None) -> datetime | None:
    """El robot manda hora local como si fuera UTC."""
    if not value:
        return None
    naive = datetime.fromtimestamp(value, UTC).replace(tzinfo=None)
    return naive.replace(tzinfo=dt_util.get_default_time_zone())


def _field(command: str, field: str) -> Callable[[dict], Any]:
    return lambda d: (d.get(command) or {}).get(field)


@dataclass(frozen=True, kw_only=True)
class RobSensorDescription(SensorEntityDescription):
    command: str
    value_fn: Callable[[dict[str, Any]], Any] | None = None
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _d(command: str, key: str, name: str, **kw: Any) -> RobSensorDescription:
    return RobSensorDescription(key=key, name=name, command=command, **kw)


def _stat(field: str, name: str, **kw: Any) -> RobSensorDescription:
    kw.setdefault("device_class", SensorDeviceClass.DURATION)
    kw.setdefault("native_unit_of_measurement", UnitOfTime.SECONDS)
    kw.setdefault("suggested_unit_of_measurement", UnitOfTime.HOURS)
    return _d(
        "GetAllStatistics", f"stat_{field}", name,
        value_fn=_field("GetAllStatistics", field), state_class=TOTAL, **kw,
    )


def _sig(command: str, field: str, name: str) -> RobSensorDescription:
    return _d(
        command, f"{command}_{field}", name, value_fn=_field(command, field),
        state_class=MEAS, entity_category=DIAG, entity_registry_enabled_default=False,
    )


STATES = [s.name.lower() for s in MowerState]
ACTIVITIES = [a.name.lower() for a in MowerActivity]
MODES = [m.name.lower() for m in ModeOfOperation]

SENSORS: tuple[RobSensorDescription, ...] = (
    # Bateria
    _d("GetBatteryLevel", "battery", "Batería", device_class=SensorDeviceClass.BATTERY,
       native_unit_of_measurement=PERCENTAGE, state_class=MEAS),
    # En el S800 devuelve 1037 en reposo y 65532 (0xFFFC) cuando no hay lectura: escala sin confirmar.
    _d("GetBatteryVoltage", "battery_voltage", "Tensión batería (crudo)", state_class=MEAS, entity_category=DIAG,
       value_fn=lambda d: None if d.get("GetBatteryVoltage") in (None, 65532, 65535) else d["GetBatteryVoltage"]),
    _d("GetBatteryCurrent", "battery_current", "Corriente batería",
       device_class=SensorDeviceClass.CURRENT, native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
       state_class=MEAS, entity_category=DIAG),
    # La escala no esta confirmada en el S600: se deja cruda hasta compararla con el termometro.
    _d("GetBatteryTemperature", "battery_temperature", "Temperatura batería (crudo)",
       state_class=MEAS, entity_category=DIAG),
    _d("GetRemainingChargingTime", "charge_remaining", "Carga restante",
       device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.SECONDS,
       suggested_unit_of_measurement=UnitOfTime.MINUTES),
    # Estado
    _d("GetState", "state", "Estado", device_class=SensorDeviceClass.ENUM, options=STATES,
       value_fn=lambda d: _enum(MowerState, d.get("GetState"))),
    _d("GetActivity", "activity", "Actividad", device_class=SensorDeviceClass.ENUM, options=ACTIVITIES,
       value_fn=lambda d: _enum(MowerActivity, d.get("GetActivity"))),
    _d("GetMode", "mode", "Modo", device_class=SensorDeviceClass.ENUM, options=MODES,
       value_fn=lambda d: _enum(ModeOfOperation, d.get("GetMode"))),
    _d("GetError", "error", "Error",
       value_fn=lambda d: "ninguno" if not d.get("GetError") else _enum(ErrorCodes, d.get("GetError"), strict=False),
       attrs_fn=lambda d: {"codigo": d.get("GetError")}),
    _d("GetRestrictionReason", "restriction", "Motivo de restricción", entity_category=DIAG),
    _d("GetNextStartTime", "next_start", "Próximo arranque", device_class=SensorDeviceClass.TIMESTAMP,
       value_fn=lambda d: _local_ts(d.get("GetNextStartTime"))),
    _d("GetOverride", "override", "Orden manual",
       value_fn=lambda d: _enum(OverrideAction, _field("GetOverride", "action")(d), strict=False),
       attrs_fn=lambda d: {
           "inicio": _local_ts(_field("GetOverride", "startTime")(d)),
           "duracion_s": _field("GetOverride", "duration")(d),
       }),
    _d("GetSpotCuttingState", "spot_cutting", "Corte en espiral (estado)", entity_category=DIAG),
    # Estadisticas
    _stat("totalRunningTime", "Tiempo total en marcha"),
    _stat("totalCuttingTime", "Tiempo total cortando"),
    _stat("totalChargingTime", "Tiempo total cargando"),
    _stat("totalSearchingTime", "Tiempo total buscando la base"),
    _stat("cuttingBladeUsageTime", "Uso de las cuchillas"),
    _d("GetAllStatistics", "stat_collisions", "Choques", state_class=TOTAL,
       value_fn=_field("GetAllStatistics", "numberOfCollisions")),
    _d("GetAllStatistics", "stat_charging_cycles", "Ciclos de carga", state_class=TOTAL,
       value_fn=_field("GetAllStatistics", "numberOfChargingCycles")),
    # Ajustes
    _d("GetCuttingHeight", "cutting_height", "Altura de corte", state_class=MEAS),
    _d("GetSensorControlSensitivity", "sensor_control_sensitivity", "Sensibilidad SensorControl",
       entity_category=DIAG),
    _d("GetDrivePastWire", "drive_past_wire", "Pasar el cable (cm)", entity_category=DIAG),
    _d("GetReversingDistance", "reversing_distance", "Marcha atrás al salir (cm)", entity_category=DIAG),
    # Cable perimetral y sensores
    _d("GetSignalQuality", "loop_quality", "Calidad señal del cable", state_class=MEAS,
       value_fn=_field("GetSignalQuality", "signalQuality"), entity_category=DIAG),
    _sig("GetSignalQuality", "a0Signal", "Señal A0"),
    _sig("GetSignalQuality", "fSignal", "Señal F"),
    _sig("GetSignalQuality", "nSignal", "Señal N"),
    _sig("GetSignalQuality", "guide1Signal", "Señal guía 1"),
    _sig("GetSignalQuality", "guide2Signal", "Señal guía 2"),
    _sig("GetSignalQuality", "guide3Signal", "Señal guía 3"),
    _d("GetOrientationPitch", "pitch", "Inclinación (pitch)", state_class=MEAS, entity_category=DIAG),
    _d("GetOrientationRoll", "roll", "Inclinación (roll)", state_class=MEAS, entity_category=DIAG),
    _sig("GetComboardSensorData", "pitch", "Pitch (placa)"),
    _sig("GetComboardSensorData", "roll", "Roll (placa)"),
    _sig("GetComboardSensorData", "zAcceleration", "Aceleración Z"),
    _d("GetComboardSensorData", "mower_temperature", "Temperatura interna (crudo)", state_class=MEAS,
       value_fn=_field("GetComboardSensorData", "mowerTemperature"), entity_category=DIAG),
    # Identidad
    _d("GetUserMowerName", "user_name", "Nombre", entity_category=DIAG),
    _d("GetSerialNumber", "serial", "Número de serie", entity_category=DIAG),
    _d("GetSoftwarePackageVersion", "sw_version", "Versión software", entity_category=DIAG),
    _d("GetSwVersionStringAppl", "sw_appl", "Firmware aplicación", entity_category=DIAG),
    _d("GetSwVersionStringBoot", "sw_boot", "Firmware arranque", entity_category=DIAG),
    _d("GetSwVersionStringSub", "sw_sub", "Firmware sub", entity_category=DIAG),
    _d("GetHwSerialNumber", "hw_serial", "Serie hardware", entity_category=DIAG),
    _d("GetHardwareRevision", "hw_revision", "Revisión hardware", entity_category=DIAG),
    _d("GetProductionTime", "production", "Fecha de fabricación", entity_category=DIAG,
       device_class=SensorDeviceClass.TIMESTAMP, value_fn=lambda d: _local_ts(d.get("GetProductionTime"))),
    _d("GetTime", "clock", "Reloj del robot", entity_category=DIAG, device_class=SensorDeviceClass.TIMESTAMP,
       value_fn=lambda d: _local_ts(d.get("GetTime"))),
    # Historial y programacion
    _d("GetNumberOfMessages", "last_message", "Último aviso",
       value_fn=lambda d: _enum(ErrorCodes, d["messages"][0]["code"], strict=False) if d.get("messages") else "ninguno",
       attrs_fn=lambda d: {
           "total": d.get("GetNumberOfMessages"),
           "avisos": [
               {"fecha": _local_ts(m["time"]), "codigo": m["code"],
                "texto": _enum(ErrorCodes, m["code"], strict=False), "gravedad": m["severity"]}
               for m in d.get("messages", [])
           ],
       }),
    _d("GetNumberOfTasks", "schedule", "Programación (tareas)",
       attrs_fn=lambda d: {"tareas": d.get("tasks", [])}),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: RobConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        RobSensor(coordinator, desc) for desc in SENSORS if desc.command in coordinator.supported
    )


class RobSensor(RobEntity, SensorEntity):
    entity_description: RobSensorDescription

    def __init__(self, coordinator, description: RobSensorDescription) -> None:
        super().__init__(coordinator, description.key, description.name)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(data)
        return data.get(self.entity_description.command)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn:
            return self.entity_description.attrs_fn(self.coordinator.data or {})
        return None
