"""Coordinador: conexion BLE, sondeo de comandos y lectura periodica."""

from __future__ import annotations

import asyncio
from time import monotonic
from typing import TYPE_CHECKING, Any

from bleak import BleakError
from bleak_retry_connector import close_stale_connections_by_address

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .automower_ble.mower import Mower
from .automower_ble.protocol import ResponseResult, TaskInformation
from .const import (
    DOMAIN,
    FAST_COMMANDS,
    FAST_INTERVAL,
    LOGGER,
    MAX_MESSAGES,
    PARAM_PROBES,
    SLOW_SECONDS,
)

if TYPE_CHECKING:
    from . import RobConfigEntry


class RobCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Mantiene la conexion y un diccionario {comando: valor}."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: RobConfigEntry,
        mower: Mower,
        address: str,
        channel_id: int,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=FAST_INTERVAL,
        )
        self.mower = mower
        self.address = address
        self.channel_id = channel_id
        self.model: str | None = None
        self.supported: set[str] = set()
        self.probe_report: dict[str, Any] = {}
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        # None = nunca leído; con 0.0, un equipo recién arrancado (monotonic < 600 s) se saltaba la primera lectura
        self._last_slow: float | None = None
        # Las escrituras de varios pasos (programacion) no se mezclan con el sondeo periodico.
        self.op_lock = asyncio.Lock()

    async def async_load(self) -> None:
        """Carga el resultado del ultimo sondeo para crear entidades aunque falle la conexion."""
        stored = await self._store.async_load() or {}
        self.supported = set(stored.get("supported", []))
        self.probe_report = stored.get("report", {})
        self.model = stored.get("model")

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        if self.mower.is_connected():
            await self.mower.disconnect()

    async def ensure_connected(self) -> None:
        if self.mower.is_connected():
            return
        await close_stale_connections_by_address(self.address)
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            raise UpdateFailed(f"{self.address} no esta al alcance de ningun receptor BLE")
        try:
            result = await self.mower.connect(device)
        except (BleakError, TimeoutError) as err:
            await close_stale_connections_by_address(self.address)
            raise UpdateFailed(f"No conecta: {err or type(err).__name__}") from err
        if result is ResponseResult.INVALID_PIN:
            raise ConfigEntryAuthFailed("PIN incorrecto")
        if result is not ResponseResult.OK:
            raise UpdateFailed(f"No conecta: {result.name}")
        if self.model is None:
            self.model = await self.mower.get_model()

    async def read(self, name: str, **kwargs: Any) -> tuple[ResponseResult, Any]:
        # Si el enlace se cayo entre dos lecturas la libreria deja client=None: no escribir.
        if not self.mower.is_connected():
            return ResponseResult.UNKNOWN_ERROR, None
        try:
            return await self.mower.command_response(name, warn_on_error=False, **kwargs)
        except ValueError as err:  # respuesta con longitud inesperada
            LOGGER.debug("%s: respuesta no interpretable (%s)", name, err)
            return ResponseResult.INVALID_VALUE, None

    async def async_probe(self) -> dict[str, Any]:
        """Prueba todos los comandos de lectura conocidos y guarda cuales responde el robot."""
        await self.ensure_connected()
        protocol = await self.mower.get_protocol()
        report: dict[str, Any] = {}
        for name, spec in protocol.items():
            if not name.startswith(("Get", "Is")) or spec.get("requestType"):
                continue
            result, value = await self.read(name)
            report[name] = {"major": spec["major"], "minor": spec["minor"], "result": result.name, "value": value}
        for name, param, values in PARAM_PROBES:
            for v in values:
                result, value = await self.read(name, **{param: v})
                report[f"{name}[{v}]"] = {"result": result.name, "value": value}
        self.probe_report = report
        # OK con valor None = el robot responde pero sin datos (p.ej. GetBatteryCurrent
        # en el S800): no crear entidad.
        self.supported = {
            n for n, r in report.items()
            if r["result"] == "OK" and r["value"] is not None and "[" not in n
        }
        await self._store.async_save(
            {"supported": sorted(self.supported), "report": report, "model": self.model}
        )
        LOGGER.info(
            "Sondeo: %d de %d lecturas responden", len(self.supported), len(report)
        )
        return report

    async def _read_messages(self) -> list[dict[str, Any]]:
        result, count = await self.read("GetNumberOfMessages")
        if result is not ResponseResult.OK or not count:
            return []
        messages = []
        for msg_id in range(max(0, count - MAX_MESSAGES), count):
            result, msg = await self.read("GetMessage", messageId=msg_id)
            if result is ResponseResult.OK and msg:
                messages.append({"id": msg_id, **msg})
        messages.sort(key=lambda m: m["time"], reverse=True)
        return messages

    async def _read_tasks(self) -> list[dict[str, Any]]:
        return [vars(t) for t in await self.mower.get_tasks()]

    async def async_set_schedule(self, tasks: list[TaskInformation]) -> list[dict[str, Any]]:
        """Sustituye la programacion semanal del robot y devuelve la que queda grabada."""
        async with self.op_lock:
            await self.ensure_connected()
            await self.mower.set_tasks(tasks)
            written = await self._read_tasks()
        if self.data is not None:
            self.data["tasks"] = written
            self.data["GetNumberOfTasks"] = len(written)
            self.async_set_updated_data(self.data)
        return written

    async def _async_update_data(self) -> dict[str, Any]:
        async with self.op_lock:
            return await self._update_locked()

    async def _update_locked(self) -> dict[str, Any]:
        await self.ensure_connected()
        if not self.supported:
            await self.async_probe()

        data = dict(self.data or {})
        slow = self._last_slow is None or monotonic() - self._last_slow > SLOW_SECONDS
        names = [n for n in sorted(self.supported) if slow or n in FAST_COMMANDS]
        failures = 0
        try:
            for name in names:
                result, value = await self.read(name)
                if result is ResponseResult.OK:
                    data[name] = value
                elif result is ResponseResult.UNKNOWN_ERROR:
                    failures += 1
                    if failures >= 3:  # sin respuesta: el canal esta muerto
                        await self.mower.disconnect()
                        raise UpdateFailed("El robot dejo de responder")
            if slow:
                if "GetNumberOfMessages" in self.supported:
                    data["messages"] = await self._read_messages()
                if "GetNumberOfTasks" in self.supported:
                    data["tasks"] = await self._read_tasks()
                self._last_slow = monotonic()
        except (BleakError, TimeoutError, AttributeError) as err:
            await close_stale_connections_by_address(self.address)
            raise UpdateFailed(f"Error BLE: {err or type(err).__name__}") from err
        return data
