"""McCulloch ROB por Bluetooth, sin nube: todos los datos que expone el protocolo."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID, CONF_PIN, Platform
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryAuthFailed, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .automower_ble.mower import Mower
from .automower_ble.protocol import TaskInformation
from .const import DOMAIN
from .coordinator import RobCoordinator

type RobConfigEntry = ConfigEntry[RobCoordinator]

PLATFORMS = [
    Platform.LAWN_MOWER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))["version"]

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MAX_TASKS = 15

SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("tasks"): vol.All(
            cv.ensure_list,
            vol.Length(max=MAX_TASKS),
            [
                vol.Schema(
                    {
                        vol.Required("start"): cv.string,
                        vol.Required("end"): cv.string,
                        vol.Required("days"): vol.All(cv.ensure_list, [vol.In(DAYS)], vol.Length(min=1)),
                    }
                )
            ],
        ),
        vol.Optional("config_entry_id"): cv.string,
    }
)


def _minutes(hhmm: str) -> int:
    """'08:30' -> 510. Admite '24:00' como fin de dia."""
    try:
        h, m = (int(x) for x in hhmm.strip().split(":"))
    except ValueError as err:
        raise ServiceValidationError(f"Hora no valida: {hhmm!r} (usa HH:MM)") from err
    if not (0 <= h <= 24 and 0 <= m < 60) or (h == 24 and m):
        raise ServiceValidationError(f"Hora fuera de rango: {hhmm!r}")
    return h * 60 + m


def _to_task(item: dict[str, Any]) -> TaskInformation:
    start, end = _minutes(item["start"]), _minutes(item["end"])
    if start >= 24 * 60:
        raise ServiceValidationError("El inicio tiene que ser antes de las 24:00")
    if end <= start:
        raise ServiceValidationError(f"El fin ({item['end']}) tiene que ser despues del inicio ({item['start']})")
    days = set(item["days"])
    return TaskInformation(start, end - start, *(d in days for d in DAYS))


SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required("command"): cv.string,
        vol.Optional("params", default={}): dict,
        vol.Optional("config_entry_id"): cv.string,
    }
)


def _coordinator(hass: HomeAssistant, entry_id: str | None) -> RobCoordinator:
    entries = [
        e
        for e in hass.config_entries.async_loaded_entries(DOMAIN)
        if entry_id in (None, e.entry_id)
    ]
    if not entries:
        raise ServiceValidationError("No hay ningun robot cargado")
    return entries[0].runtime_data


CARD_URL = f"/{DOMAIN}_static"
CARD_JS = f"{CARD_URL}/mcculloch-rob-card.js?v={VERSION}"
_LOGGER = logging.getLogger(__name__)


async def _register_card(hass: HomeAssistant) -> None:
    """Sirve la tarjeta de Lovelace desde la integración y la carga en el frontend."""
    if not hass.http:  # en tests sin servidor http
        return
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / "www"), True)]
    )
    add_extra_js_url(hass, CARD_JS)


async def _register_resource(hass: HomeAssistant) -> None:
    """Además, como recurso de Lovelace: la app del móvil guarda la página en caché y no ve el script extra."""
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None or not hasattr(resources, "async_create_item"):
        return  # modo YAML: el recurso lo añade el usuario
    try:
        if not getattr(resources, "loaded", True):
            await resources.async_load()
            resources.loaded = True
        base = CARD_JS.split("?")[0]
        for item in resources.async_items():
            if item["url"].split("?")[0] == base:
                if item["url"] != CARD_JS:
                    await resources.async_update_item(item["id"], {"res_type": "module", "url": CARD_JS})
                return
        await resources.async_create_item({"res_type": "module", "url": CARD_JS})
    except Exception:  # noqa: BLE001 - la tarjeta sigue cargando por add_extra_js_url
        _LOGGER.warning("No se pudo registrar el recurso de la tarjeta; añádelo a mano: %s", CARD_JS, exc_info=True)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    await _register_card(hass)
    if hass.http:
        if hass.state is CoreState.running:
            await _register_resource(hass)
        else:
            # función async: una lambda normal la ejecuta HA en otro hilo y ahí no se pueden crear tareas
            async def _on_started(_event: Event) -> None:
                await _register_resource(hass)

            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)

    async def send_command(call: ServiceCall) -> ServiceResponse:
        """Envia cualquier comando del protocolo y devuelve la respuesta cruda."""
        coordinator = _coordinator(hass, call.data.get("config_entry_id"))
        protocol = await coordinator.mower.get_protocol()
        name = call.data["command"]
        if name not in protocol:
            raise ServiceValidationError(f"Comando desconocido: {name}")
        async with coordinator.op_lock:
            await coordinator.ensure_connected()
            result, value = await coordinator.read(name, **call.data["params"])
        await coordinator.async_request_refresh()
        return {"command": name, "result": result.name, "value": value}

    async def probe(call: ServiceCall) -> ServiceResponse:
        """Vuelve a probar todas las lecturas conocidas."""
        coordinator = _coordinator(hass, call.data.get("config_entry_id"))
        async with coordinator.op_lock:
            report = await coordinator.async_probe()
        await coordinator.async_request_refresh()
        return {"supported": sorted(coordinator.supported), "report": report}

    async def set_schedule(call: ServiceCall) -> ServiceResponse:
        """Sustituye la programacion semanal completa (lista vacia = sin programacion)."""
        coordinator = _coordinator(hass, call.data.get("config_entry_id"))
        tasks = [_to_task(t) for t in call.data["tasks"]]
        written = await coordinator.async_set_schedule(tasks)
        return {"tasks": written}

    async def mow_for(call: ServiceCall) -> None:
        """Corta ahora durante las horas indicadas, saltandose la programacion."""
        coordinator = _coordinator(hass, call.data.get("config_entry_id"))
        async with coordinator.op_lock:
            await coordinator.ensure_connected()
            result = await coordinator.mower.mower_override(float(call.data["hours"]))
        if getattr(result, "name", "OK") != "OK":
            raise ServiceValidationError(f"El robot respondio {result.name}")
        await coordinator.async_request_refresh()

    async def park_for(call: ServiceCall) -> None:
        """Aparca en la base durante las horas indicadas; luego vuelve a la programacion."""
        coordinator = _coordinator(hass, call.data.get("config_entry_id"))
        async with coordinator.op_lock:
            await coordinator.ensure_connected()
            result, _ = await coordinator.read("SetOverridePark", duration=int(float(call.data["hours"]) * 3600))
        if result.name != "OK":
            raise ServiceValidationError(f"El robot respondio {result.name}")
        await coordinator.async_request_refresh()

    hours_schema = lambda hi: vol.Schema({vol.Required("hours"): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=hi)),
                                          vol.Optional("config_entry_id"): cv.string})
    hass.services.async_register(DOMAIN, "mow_for", mow_for, hours_schema(24))
    hass.services.async_register(DOMAIN, "park_for", park_for, hours_schema(168))
    hass.services.async_register(
        DOMAIN, "set_schedule", set_schedule, SET_SCHEDULE_SCHEMA, SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "send_command", send_command, SEND_COMMAND_SCHEMA, SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN,
        "probe",
        probe,
        vol.Schema({vol.Optional("config_entry_id"): cv.string}),
        SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RobConfigEntry) -> bool:
    address: str = entry.data[CONF_ADDRESS]
    channel_id: int = entry.data[CONF_CLIENT_ID]
    pin: str | None = entry.data.get(CONF_PIN) or None
    mower = Mower(channel_id, address, int(pin) if pin is not None else None)

    coordinator = RobCoordinator(hass, entry, mower, address, channel_id)
    await coordinator.async_load()
    if coordinator.supported:
        # Ya lo conocemos (sondeo guardado): las entidades se crean aunque el robot esté lejos,
        # como «no disponibles», y el coordinador sigue reintentando. Así no desaparece de HA.
        await coordinator.async_refresh()
        if isinstance(coordinator.last_exception, ConfigEntryAuthFailed):
            await coordinator.async_shutdown()
            raise coordinator.last_exception
    else:
        # Primera vez: sin sondeo no sabemos qué entidades crear; si no está al alcance, se reintenta.
        try:
            await coordinator.async_config_entry_first_refresh()
        except Exception:
            await coordinator.async_shutdown()  # que no quede un enlace BLE colgado ocupando el robot
            raise
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RobConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: RobConfigEntry) -> None:
    from homeassistant.helpers.storage import Store

    await Store[dict[str, Any]](hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
