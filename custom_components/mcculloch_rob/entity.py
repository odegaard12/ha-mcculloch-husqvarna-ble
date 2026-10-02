"""Entidad base."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RobCoordinator


class RobEntity(CoordinatorEntity[RobCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: RobCoordinator, key: str, name: str | None) -> None:
        super().__init__(coordinator)
        data = coordinator.data or {}
        self._attr_unique_id = f"{format_mac(coordinator.address)}_{key}"
        self._attr_name = name
        # la tarjeta de Lovelace encuentra cada entidad del robot por esta clave
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, format_mac(coordinator.address))},
            connections={(CONNECTION_BLUETOOTH, format_mac(coordinator.address))},
            name="Robot cortacésped",
            manufacturer="McCulloch",
            model=coordinator.model,
            serial_number=str(data["GetSerialNumber"]) if "GetSerialNumber" in data else None,
            sw_version=data.get("GetSoftwarePackageVersion"),
            hw_version=str(data["GetHardwareRevision"]) if "GetHardwareRevision" in data else None,
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.mower.is_connected()
