"""Diagnóstico descargable: sondeo completo y últimos datos (sin el PIN)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PIN
from homeassistant.core import HomeAssistant

from . import RobConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RobConfigEntry
) -> dict[str, Any]:
    c = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), {CONF_PIN}),
        "model": c.model,
        "connected": c.mower.is_connected(),
        "supported": sorted(c.supported),
        "probe_report": c.probe_report,
        "data": c.data,
    }
