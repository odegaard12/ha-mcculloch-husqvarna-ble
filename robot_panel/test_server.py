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
        assert robots[1] == {"id": "landroid", "name": "Landroid", "kind": "landroid", "locked": False, "open": True}
        ok = {"domain": "lawn_mower", "service": "dock", "entity_id": "lawn_mower.landroid"}
        assert (await c4.post("/api/servicio", json=ok)).status == 502  # pasa el filtro; no hay HA
        for e in ("lawn_mower.landroidx", "lawn_mower.landroid,lawn_mower.vecino", "switch.mal_eco"):
            r = await c4.post("/api/servicio", json={**ok, "entity_id": e})
            assert r.status == 403, e
        assert (await c4.get("/api/historial?r=landroid&e=actividad")).status == 502
        # nombre: se guarda y lo ven todos
        assert (await c4.post("/api/robots/nombre", json={"id": "landroid", "name": "  Robot   de abajo "})).status == 200
        assert (await c4.post("/api/robots/nombre", json={"id": "otro", "name": "x"})).status == 400
        # Landroid: su horario no se graba desde aquí (la nube tarda y se pisa), corte puntual de 10 min a 2 h, ajustes con valor válido
        una = [{"start": "09:00", "end": "10:00", "days": ["monday"]}]
        assert (await c4.post("/api/programacion", json={"r": "landroid", "tasks": una})).status == 400
        assert (await c4.post("/api/programacion", json={"r": "nadie", "tasks": []})).status == 400
        assert (await c4.post("/api/durante", json={"r": "landroid", "accion": "cortar", "horas": 5})).status == 400
        assert (await c4.post("/api/durante", json={"r": "landroid", "accion": "cortar", "horas": 1})).status == 502
        num = {"domain": "number", "service": "set_value", "entity_id": "number.landroid_par_motor"}
        assert (await c4.post("/api/servicio", json={**num, "value": "x"})).status == 400
        assert (await c4.post("/api/servicio", json={**num, "value": 5})).status == 502
        assert (await c4.post("/api/servicio", json={**num, "entity_id": "number.otra_cosa", "value": 5})).status == 403
        # contraseña del Landroid: quien la pone sigue dentro en su móvil
        assert (await c4.post("/api/robots/clave", json={"id": "landroid", "nueva": "12"})).status == 400
        assert (await c4.post("/api/robots/clave", json={"id": "landroid", "nueva": "2468"})).status == 200
        assert (await c4.post("/api/servicio", json=ok)).status == 502
    # otro móvil con el PIN de la app pero sin la contraseña del Landroid: ni lo ve ni lo toca
    async with TestClient(TestServer(server.make_app())) as c5:
        await c5.post("/api/login", json={"pin": "4321"})
        robots = {r["id"]: r for r in await (await c5.get("/api/robots")).json()}
        assert robots["landroid"]["name"] == "Robot de abajo" and robots["landroid"]["locked"] and not robots["landroid"]["open"]
        assert robots["robot_cortacesped"]["open"]
        assert (await c5.post("/api/servicio", json=ok)).status == 423
        assert (await c5.get("/api/historial?r=landroid")).status == 423
        assert (await c5.post("/api/robots/nombre", json={"id": "landroid", "name": "Mío"})).status == 423
        assert (await c5.post("/api/robots/clave", json={"id": "landroid", "nueva": ""})).status == 403  # quitarla pide la actual
        assert (await c5.post("/api/robots/abrir", json={"id": "landroid", "pin": "0000"})).status == 403
        assert (await c5.post("/api/robots/abrir", json={"id": "landroid", "pin": "2468"})).status == 200
        assert (await c5.post("/api/servicio", json=ok)).status == 502
        assert (await c5.post("/api/robots/cerrar", json={"id": "landroid"})).status == 200
        assert (await c5.post("/api/servicio", json=ok)).status == 423
        # la copia entre Pis va firmada
        assert (await c5.post("/api/robots/peer", data=b"{}", headers={"X-Peer-Sig": "falsa"})).status == 403
        # quitarla con la actual
        assert (await c5.post("/api/robots/clave", json={"id": "landroid", "actual": "2468", "nueva": ""})).status == 200
        assert (await c5.post("/api/servicio", json=ok)).status == 502
        # copia entre Pis: una vieja (reenviada) no pisa nada y devuelve la buena; una más nueva sí entra
        import hashlib, hmac, json as _json  # noqa: E401
        secret = bytes.fromhex((server.HERE / ".app_secret").read_text().strip())
        sig = lambda b: hmac.new(secret, b"robots-peer:" + b, hashlib.sha256).hexdigest()  # noqa: E731
        old = _json.dumps({"v": 1, "robots": {"landroid": {"name": "Viejo"}}}).encode()
        r = await c5.post("/api/robots/peer", data=old, headers={"X-Peer-Sig": sig(old)})
        back = await r.read()
        assert r.status == 200 and _json.loads(back)["robots"]["landroid"]["name"] == "Robot de abajo"
        assert r.headers["X-Peer-Sig"] == sig(back)  # la respuesta va firmada
        new = _json.dumps({"v": 9e12, "robots": {"landroid": {"name": "Nuevo"}}}).encode()
        assert (await c5.post("/api/robots/peer", data=new, headers={"X-Peer-Sig": sig(new)})).status == 200
        names = {x["id"]: x["name"] for x in await (await c5.get("/api/robots")).json()}
        assert names["landroid"] == "Nuevo", names
        # avisos: solo servicios push de verdad (nada de mandar peticiones a otras direcciones)
        evil = {"subscription": {"endpoint": "https://10.0.0.1/x", "keys": {"p256dh": "a", "auth": "b"}}}
        assert (await c5.post("/api/push/subscribe", json=evil)).status in (400, 503)
    # archivo de nombres/contraseñas cortado (apagón a medias): todo cerrado, no todo abierto, hasta la copia buena
    (server.HERE / "robots_cfg.json").write_text('{"v": 1, "robo')
    async with TestClient(TestServer(server.make_app())) as c6:
        await c6.post("/api/login", json={"pin": "4321"})
        assert (await c6.post("/api/servicio", json=ok)).status == 423
        good = _json.dumps({"v": 9e12 + 1, "robots": {}}).encode()
        assert (await c6.post("/api/robots/peer", data=good, headers={"X-Peer-Sig": sig(good)})).status == 200
        assert (await c6.post("/api/servicio", json=ok)).status == 502
        # suscripciones entre Pis: solo entra una copia más nueva; la misma reenviada o el formato viejo, no
        psig = lambda b: hmac.new(secret, b"push-peer:" + b, hashlib.sha256).hexdigest()  # noqa: E731
        newer = _json.dumps({"v": 9e12, "subs": []}).encode()
        r1 = await c6.post("/api/push/peer", data=newer, headers={"X-Peer-Sig": psig(newer)})
        if r1.status != 404:  # sin pywebpush no hay avisos
            assert r1.status == 200
            assert (await c6.post("/api/push/peer", data=newer, headers={"X-Peer-Sig": psig(newer)})).status == 409
            assert (await c6.post("/api/push/peer", data=b"[]", headers={"X-Peer-Sig": psig(b"[]")})).status == 400
    del os.environ["ROBOTS"]
    print("servidor: todo OK")


asyncio.run(main())
