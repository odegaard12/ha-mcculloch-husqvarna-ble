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
from .entity import RobEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RobConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([RobMower(entry.runtime_data)])


class RobMower(RobEntity, LawnMowerEntity):
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
        return LawnMowerActivity.ERROR

    async def async_start_mowing(self) -> None:
        await self.coordinator.ensure_connected()
        if self.activity is LawnMowerActivity.PAUSED:
            await self.coordinator.mower.mower_resume()
        else:
            await self.coordinator.mower.mower_override(3.0)
        await self.coordinator.async_request_refresh()

    async def async_pause(self) -> None:
        await self.coordinator.ensure_connected()
        await self.coordinator.mower.mower_pause()
        await self.coordinator.async_request_refresh()

    async def async_dock(self) -> None:
        await self.coordinator.ensure_connected()
        await self.coordinator.mower.mower_park()
        await self.coordinator.async_request_refresh()
