"""Pruebas del servidor del panel: lista blanca de órdenes, PIN y sesiones. Ejecutar: python ha_app/test_server.py"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

os.environ.update({"APP_PIN": "4321", "HA_TOKEN": "x", "HA_URL": "http://127.0.0.1:9", "ROBOT_PREFIX": "robot_cortacesped"})
sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402

server.HERE = Path(tempfile.mkdtemp())  # .app_secret de usar y tirar
(server.HERE / "robot").mkdir()


async def main():
    async with TestClient(TestServer(server.make_app())) as c:
        r = await c.post("/api/servicio", json={})
        assert r.status == 401, "sin sesión no se entra"
        # salud: sin PIN, sin datos; 503 porque aquí no hay HA
        r = await c.get("/api/salud")
        assert r.status == 503 and await r.json() == {"ok": True, "ha": False}
        # cabeceras de seguridad en todo
        for path in ("/", "/api/sesion"):
            h = (await c.get(path)).headers
            assert "frame-ancestors 'self'" in h.get("Content-Security-Policy", ""), path
            assert h.get("X-Content-Type-Options") == "nosniff", path
        r = await c.get("/api/historial?d=999")
        assert r.status == 401  # sin sesión ni con parámetros raros
        # versión: sin sesión (la app la mira para recargarse); avisos: con sesión, y la copia entre Pis firmada
        r = await c.get("/api/version")
        assert r.status == 200 and len((await r.json())["v"]) == 12
        assert (await c.get("/api/push/key")).status == 401
        r = await c.post("/api/push/peer", data=b"[]", headers={"X-Peer-Sig": "falsa"})
        assert r.status == 403
        # login
        r = await c.post("/api/login", json={"pin": "0000"})
        assert r.status == 403
        r = await c.post("/api/login", data="no es json")
        assert r.status == 403
        r = await c.post("/api/login", json={"pin": "4321"})
        assert r.status == 200
        s = await (await c.get("/api/sesion")).json()
        assert s == {"pin": True, "pin_len": 4, "ok": True}, s
        # lista blanca
        bad = [
            {"domain": "switch", "service": "turn_on", "entity_id": "switch.robot_cortacesped,switch.garaje"},
            {"domain": "switch", "service": "turn_on", "entity_id": "switch.garaje"},
            {"domain": "switch", "service": "turn_on", "entity_id": ["switch.robot_cortacesped_eco"]},
            {"domain": "switch", "service": "turn_on", "entity_id": "button.robot_cortacesped_cortar_1_hora"},
            {"domain": "light", "service": "turn_on", "entity_id": "light.robot_cortacesped"},
            {"domain": "switch", "service": "turn_on", "entity_id": "switch.robot_cortacesped_eco x"},
        ]
        for b in bad:
            r = await c.post("/api/servicio", json=b)
            assert r.status == 403, (b, r.status)
        r = await c.post("/api/servicio", data="[1,2]")
        assert r.status == 403
        # orden válida: pasa el filtro y falla al llegar a HA (no hay HA en el puerto 9) con 502 en JSON
        r = await c.post("/api/servicio", json={"domain": "switch", "service": "turn_on", "entity_id": "switch.robot_cortacesped_eco"})
        assert r.status == 502 and "error" in await r.json(), r.status
        for path, body in (("/api/durante", {"accion": "cortar", "horas": 1}), ("/api/programacion", {"tasks": []})):
            r = await c.post(path, json=body)
            assert r.status == 502 and "error" in await r.json(), (path, r.status)
        r = await c.get("/api/historial")
        assert r.status == 502
        # con sesión: sin pywebpush no hay clave (503); con él, py_vapid la crea y la suscripción sin https se rechaza
        r = await c.get("/api/push/key")
        assert r.status == 200 and "key" in await r.json()
        bad = {"subscription": {"endpoint": "http://no-https", "keys": {"p256dh": "a", "auth": "b"}}}
        assert (await c.post("/api/push/subscribe", json=bad)).status in (400, 503)
        cookie = c.session.cookie_jar.filter_cookies(c.make_url("/")).get(server.COOKIE).value
    # un PIN nuevo invalida las sesiones viejas
    os.environ["APP_PIN"] = "9999"
    async with TestClient(TestServer(server.make_app())) as c2:
        c2.session.cookie_jar.update_cookies({server.COOKIE: cookie})
        assert not (await (await c2.get("/api/sesion")).json())["ok"]
    # límite global: 20 fallos desde IPs distintas bloquean a todos
    os.environ["APP_PIN"] = "4321"
    async with TestClient(TestServer(server.make_app())) as c3:
        codes = [(await c3.post("/api/login", json={"pin": "0"}, headers={"CF-Connecting-IP": f"10.0.0.{i}"})).status for i in range(21)]
        assert codes[:20] == [403] * 20 and codes[20] == 429, codes
        r = await c3.post("/api/login", json={"pin": "4321"}, headers={"CF-Connecting-IP": "10.9.9.9"})
        assert r.status == 429
    # varios robots: el McCulloch siempre primero; las entradas mal escritas de ROBOTS se ignoran
    os.environ["ROBOTS"] = "landroid:Landroid:landroid, Mal:Nombre:landroid,x:y:otro,robot_cortacesped:Repe:mcculloch"
    async with TestClient(TestServer(server.make_app())) as c4:
        await c4.post("/api/login", json={"pin": "4321"})
        robots = await (await c4.get("/api/robots")).json()
        assert [r["id"] for r in robots] == ["robot_cortacesped", "landroid"], robots
        assert robots[1] == {"id": "landroid", "name": "Landroid", "kind": "landroid"}
        ok = {"domain": "lawn_mower", "service": "dock", "entity_id": "lawn_mower.landroid"}
        assert (await c4.post("/api/servicio", json=ok)).status == 502  # pasa el filtro; no hay HA
        for e in ("lawn_mower.landroidx", "lawn_mower.landroid,lawn_mower.vecino", "switch.mal_eco"):
            r = await c4.post("/api/servicio", json={**ok, "entity_id": e})
            assert r.status == 403, e
        assert (await c4.get("/api/historial?r=landroid&e=actividad")).status == 502
    del os.environ["ROBOTS"]
    print("servidor: todo OK")


asyncio.run(main())
