"""Diagnóstico descargable: sondeo completo y últimos datos, sin nada que identifique al robot o a su dueño.

Se suele pegar en issues públicos, así que se tapan el PIN, la MAC, el canal de emparejamiento,
los números de serie y el nombre que el dueño le puso al robot.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID, CONF_PIN
from homeassistant.core import HomeAssistant

from . import RobConfigEntry

TO_REDACT = {
    CONF_PIN, CONF_ADDRESS, CONF_CLIENT_ID,
    "GetSerialNumber", "GetHwSerialNumber", "GetHusqvarnaId", "GetNodeIprId",
    "GetUserMowerName", "GetUserMowerNameAsAsciiString",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RobConfigEntry
) -> dict[str, Any]:
    c = entry.runtime_data
    return async_redact_data(
        {
            "entry": dict(entry.data),
            "model": c.model,
            "connected": c.mower.is_connected(),
            "supported": sorted(c.supported),
            "probe_report": c.probe_report,
            "data": c.data,
        },
        TO_REDACT,
    )
