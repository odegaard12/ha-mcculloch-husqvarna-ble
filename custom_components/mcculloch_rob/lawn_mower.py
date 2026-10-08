"""Entidad principal de cortacésped."""

from __future__ import annotations

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RobConfigEntry
from .automower_ble.protocol import MowerActivity, MowerState
from .entity import LiveEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RobConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([RobMower(entry.runtime_data)])


class RobMower(LiveEntity, LawnMowerEntity):
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )
    _attr_icon = "mdi:robot-mower"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "mower", None)

    @property
    def activity(self) -> LawnMowerActivity | None:
        data = self.coordinator.data or {}
        state, activity = data.get("GetState"), data.get("GetActivity")
        if state is None or activity is None:
            return None
        if state == MowerState.PAUSED:
            return LawnMowerActivity.PAUSED
        # HA 2026.9 no tiene IDLE: parado en el jardín se muestra como pausa.
        if state in (MowerState.STOPPED, MowerState.OFF, MowerState.WAIT_FOR_SAFETYPIN):
            return LawnMowerActivity.PAUSED
        if state in (MowerState.RESTRICTED, MowerState.IN_OPERATION, MowerState.PENDING_START):
            if activity in (MowerActivity.CHARGING, MowerActivity.PARKED, MowerActivity.NONE):
                return LawnMowerActivity.DOCKED
            if activity in (MowerActivity.GOING_OUT, MowerActivity.MOWING):
                return LawnMowerActivity.MOWING
            if activity == MowerActivity.GOING_HOME:
                return LawnMowerActivity.RETURNING
            # parado en el jardín esperando a que alguien actúe: no es avería
            if activity == MowerActivity.STOPPED_IN_GARDEN:
                return LawnMowerActivity.PAUSED
        return LawnMowerActivity.ERROR

    # coordinator.command: con op_lock (no se cuela en una grabación del horario), comprueba el «no» del robot
    # y convierte los cortes de Bluetooth en un mensaje claro
    async def async_start_mowing(self) -> None:
        mower = self.coordinator.mower
        paused = self.activity is LawnMowerActivity.PAUSED
        await self.coordinator.command(mower.mower_resume if paused else lambda: mower.mower_override(3.0))

    async def async_pause(self) -> None:
        await self.coordinator.command(self.coordinator.mower.mower_pause)

    async def async_dock(self) -> None:
        await self.coordinator.command(self.coordinator.mower.mower_park)
