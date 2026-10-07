"""Botones: aparcar, reanudar, cortar ya y volver a sondear."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RobConfigEntry
from .automower_ble.protocol import ResponseResult
from .coordinator import RobCoordinator
from .entity import LiveEntity


@dataclass(frozen=True, kw_only=True)
class RobButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[RobCoordinator], Awaitable[Any]]


async def _cmd(c: RobCoordinator, name: str, **kw: Any) -> ResponseResult:
    result, _ = await c.read(name, **kw)
    return result


BUTTONS: tuple[RobButtonDescription, ...] = (
    RobButtonDescription(key="park_next", name="Aparcar hasta el próximo turno", icon="mdi:home-clock",
                         press_fn=lambda c: _cmd(c, "SetOverrideParkUntilNextStart")),
    RobButtonDescription(key="park_forever", name="Aparcar hasta nuevo aviso", icon="mdi:home-lock",
                         press_fn=lambda c: c.mower.mower_park_permanently()),
    RobButtonDescription(key="resume_schedule", name="Volver a la programación", icon="mdi:calendar-sync",
                         press_fn=lambda c: c.mower.mower_resume_schedule()),
    RobButtonDescription(key="mow_1h", name="Cortar 1 hora", icon="mdi:robot-mower",
                         press_fn=lambda c: c.mower.mower_override(1.0)),
    RobButtonDescription(key="mow_3h", name="Cortar 3 horas", icon="mdi:robot-mower",
                         press_fn=lambda c: c.mower.mower_override(3.0)),
    RobButtonDescription(key="sync_clock", name="Poner en hora", icon="mdi:clock-check",
                         entity_category=EntityCategory.CONFIG, press_fn=lambda c: _sync_clock(c)),
    RobButtonDescription(key="probe", name="Sondear comandos", icon="mdi:magnify-scan",
                         entity_category=EntityCategory.DIAGNOSTIC, press_fn=lambda c: c.async_probe()),
)


async def _sync_clock(c: RobCoordinator) -> ResponseResult:
    from homeassistant.util import dt as dt_util

    # El robot guarda la hora local codificada como si fuera UTC.
    local_as_utc = int(dt_util.now().replace(tzinfo=dt_util.UTC).timestamp())
    return await _cmd(c, "SetTime", time=local_as_utc)


async def async_setup_entry(
    hass: HomeAssistant, entry: RobConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(RobButton(entry.runtime_data, d) for d in BUTTONS)


class RobButton(LiveEntity, ButtonEntity):
    entity_description: RobButtonDescription

    def __init__(self, coordinator, description: RobButtonDescription) -> None:
        super().__init__(coordinator, description.key, description.name)
        self.entity_description = description

    @property
    def available(self) -> bool:
        # El sondeo tambien sirve para reconectar.
        return self.entity_description.key == "probe" or super().available

    async def async_press(self) -> None:
        await self.coordinator.command(lambda: self.entity_description.press_fn(self.coordinator))
