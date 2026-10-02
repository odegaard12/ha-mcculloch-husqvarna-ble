"""Constantes de McCulloch ROB (BLE)."""

from datetime import timedelta
import logging

DOMAIN = "mcculloch_rob"
LOGGER = logging.getLogger(__package__)

SERVICE_UUID = "98bd0001-0b0e-421a-84e5-ddbf75dc6de4"

FAST_INTERVAL = timedelta(seconds=60)
SLOW_SECONDS = 600  # estadisticas, ajustes, mensajes y programacion

# Se leen en cada ciclo (si el robot los soporta). El resto, cada SLOW_SECONDS.
FAST_COMMANDS = {
    "GetBatteryLevel",
    "IsCharging",
    "GetRemainingChargingTime",
    "GetBatteryVoltage",
    "GetBatteryCurrent",
    "GetBatteryTemperature",
    "GetMode",
    "GetState",
    "GetActivity",
    "GetError",
    "GetRestrictionReason",
    "GetNextStartTime",
    "GetOverride",
    "GetSignalQuality",
    "GetComboardSensorData",
    "GetOrientationPitch",
    "GetOrientationRoll",
    "GetSpotCuttingState",
}

# Comandos con parametro que se prueban en el sondeo (nombre, parametro, valores).
PARAM_PROBES = (
    ("GetStartingPoint", "startingPointId", range(0, 5)),
    ("GetLoopSignals", "signalType", range(0, 4)),
    ("GetLoopSignalStrength", "signalType", range(0, 4)),
)

MAX_MESSAGES = 10
