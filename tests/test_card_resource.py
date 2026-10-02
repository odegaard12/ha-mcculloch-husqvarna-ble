"""La tarjeta se registra como recurso de Lovelace y se actualiza cuando cambia la versión."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.mcculloch_rob import CARD_JS, _register_resource


async def _resources(hass: HomeAssistant):
    assert await async_setup_component(hass, "lovelace", {})
    res = hass.data["lovelace"].resources
    if not res.loaded:
        await res.async_load()
        res.loaded = True
    return res


async def test_creates_resource(hass: HomeAssistant) -> None:
    res = await _resources(hass)
    await _register_resource(hass)
    assert [i["url"] for i in res.async_items()] == [CARD_JS]


async def test_updates_old_version(hass: HomeAssistant) -> None:
    res = await _resources(hass)
    old = CARD_JS.split("?")[0] + "?v=0.0.1"
    await res.async_create_item({"res_type": "module", "url": old})
    await _register_resource(hass)
    assert [i["url"] for i in res.async_items()] == [CARD_JS]
