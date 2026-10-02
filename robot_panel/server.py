"""Panel «Mi robot» para una Raspberry: sirve la app y habla con Home Assistant por su API REST.

Solo deja leer las entidades del robot y llamar a las órdenes del robot (lista cerrada), así
que el token de HA nunca llega al navegador.

Variables (fichero robot_app.env junto a este script):
  HA_URL        http://homeassistant.local:8123
  HA_TOKEN      token de larga duración de HA (Perfil > Seguridad); lo pone el usuario
  APP_PIN       PIN para abrir la app (vacio = sin bloqueo); lo pone el usuario con set_pin.sh
  PORT          8106
  ROBOT_PREFIX  prefijo de las entidades del robot (por defecto robot_cortacesped)

Como complemento de HA (ingress) no hace falta nada: el supervisor da la URL y el token.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aiohttp import ClientError, ClientSession, ClientTimeout, web

HERE = Path(__file__).resolve().parent
PREFIX = os.environ.get("ROBOT_PREFIX", "robot_cortacesped")
ALLOWED = {
    ("lawn_mower", "start_mowing"), ("lawn_mower", "pause"), ("lawn_mower", "dock"),
    ("button", "press"), ("switch", "turn_on"), ("switch", "turn_off"),
}


def load_env() -> None:
    env = HERE / "robot_app.env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


COOKIE = "rob_sesion"
SESSION_DAYS = 180
MAX_FAILS, FAIL_WINDOW = 5, 300  # 5 PIN fallidos en 5 min bloquean esa IP 5 min


def load_secret() -> bytes:
    """Clave para firmar la cookie de sesion; se crea una vez y se guarda junto al script."""
    f = HERE / ".app_secret"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
        f.chmod(0o600)
    return bytes.fromhex(f.read_text().strip())


def make_app() -> web.Application:
    supervisor = os.environ.get("SUPERVISOR_TOKEN", "")
    ha = os.environ.get("HA_URL", "http://supervisor/core" if supervisor else "http://homeassistant.local:8123").rstrip("/")
    pin = os.environ.get("APP_PIN", "")
    secret = load_secret()
    fails: dict[str, list[float]] = {}

    def sign(exp: int) -> str:
        return hmac.new(secret, str(exp).encode(), hashlib.sha256).hexdigest()

    def session_ok(req) -> bool:
        if not pin:
            return True
        try:
            exp, sig = req.cookies.get(COOKIE, "").split(".")
            return int(exp) > time.time() and hmac.compare_digest(sig, sign(int(exp)))
        except ValueError:
            return False

    @web.middleware
    async def auth(req, handler):
        if req.path.startswith("/api/") and req.path not in ("/api/login", "/api/sesion") and not session_ok(req):
            return web.json_response({"error": "pin"}, status=401)
        return await handler(req)

    async def sesion(req):
        return web.json_response({"pin": bool(pin), "ok": session_ok(req)})

    async def login(req):
        ip = req.headers.get("CF-Connecting-IP") or req.remote or "?"
        now = time.time()
        recent = [t for t in fails.get(ip, []) if now - t < FAIL_WINDOW]
        if len(recent) >= MAX_FAILS:
            return web.json_response({"error": "Demasiados intentos. Espera unos minutos."}, status=429)
        body = await req.json()
        if not pin or not hmac.compare_digest(str(body.get("pin", "")), pin):
            fails[ip] = recent + [now]
            return web.json_response({"error": "PIN incorrecto"}, status=403)
        fails.pop(ip, None)
        exp = int(now) + SESSION_DAYS * 86400
        resp = web.json_response({"ok": True})
        resp.set_cookie(COOKIE, f"{exp}.{sign(exp)}", max_age=SESSION_DAYS * 86400, httponly=True, samesite="Strict",
                        secure=req.headers.get("X-Forwarded-Proto") == "https" or req.secure)
        return resp

    async def logout(_):
        resp = web.json_response({"ok": True})
        resp.del_cookie(COOKIE)
        return resp
    token = os.environ.get("HA_TOKEN", "") or supervisor
    headers = {"Authorization": f"Bearer {token}"}

    async def on_startup(app):
        app["http"] = ClientSession(timeout=ClientTimeout(total=20), headers=headers)

    async def on_cleanup(app):
        await app["http"].close()

    def no_token():
        return web.json_response({"error": "Falta HA_TOKEN en robot_app.env"}, status=503)

    async def index(_):
        return web.FileResponse(HERE / "robot" / "index.html", headers={"Cache-Control": "no-cache"})

    async def estado(req):
        if not token:
            return no_token()
        try:
            async with req.app["http"].get(f"{ha}/api/states") as r:
                if r.status != 200:
                    return web.json_response({"error": f"HA respondió {r.status}"}, status=502)
                data = await r.json()
        except (ClientError, TimeoutError) as e:
            return web.json_response({"error": f"No llego a Home Assistant ({ha}): {type(e).__name__}"}, status=502)
        return web.json_response([s for s in data if PREFIX in s["entity_id"]])

    async def servicio(req):
        if not token:
            return no_token()
        body = await req.json()
        domain, service, entity = body.get("domain"), body.get("service"), body.get("entity_id", "")
        if (domain, service) not in ALLOWED or not entity.startswith(f"{domain}.{PREFIX}"):
            return web.json_response({"error": "orden no permitida"}, status=403)
        async with req.app["http"].post(f"{ha}/api/services/{domain}/{service}", json={"entity_id": entity}) as r:
            return web.json_response({"ok": r.status == 200}, status=200 if r.status == 200 else 502)

    async def programacion(req):
        """Valida lo basico y pide a HA que grabe la programacion en el robot."""
        if not token:
            return no_token()
        body = await req.json()
        tasks = body.get("tasks")
        if not isinstance(tasks, list) or len(tasks) > 15:
            return web.json_response({"error": "programacion no valida"}, status=400)
        clean = []
        for t in tasks:
            if not isinstance(t, dict):
                return web.json_response({"error": "tarea no valida"}, status=400)
            clean.append({"start": str(t.get("start", "")), "end": str(t.get("end", "")),
                          "days": [str(d) for d in t.get("days", [])]})
        url = f"{ha}/api/services/mcculloch_rob/set_schedule?return_response"
        async with req.app["http"].post(url, json={"tasks": clean}) as r:
            data = await r.json(content_type=None) if r.content_length != 0 else {}
            if r.status != 200:
                msg = data.get("message") if isinstance(data, dict) else None
                return web.json_response({"error": msg or f"HA respondio {r.status}"}, status=400 if r.status == 400 else 502)
        return web.json_response({"ok": True, "tasks": (data.get("service_response") or {}).get("tasks")})

    async def durante(req):
        """Cortar o aparcar durante N horas (servicios propios de la integracion)."""
        if not token:
            return no_token()
        body = await req.json()
        service = {"cortar": "mow_for", "aparcar": "park_for"}.get(body.get("accion"))
        try:
            hours = float(body.get("horas"))
        except (TypeError, ValueError):
            hours = 0
        if not service or not 0.5 <= hours <= (24 if service == "mow_for" else 168):
            return web.json_response({"error": "orden no valida"}, status=400)
        async with req.app["http"].post(f"{ha}/api/services/mcculloch_rob/{service}", json={"hours": hours}) as r:
            if r.status != 200:
                data = await r.json(content_type=None)
                return web.json_response({"error": (data or {}).get("message") or f"HA respondio {r.status}"}, status=502)
        return web.json_response({"ok": True})

    async def historial(req):
        if not token:
            return no_token()
        start = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
        entity = f"sensor.{PREFIX}_" + ("actividad" if req.query.get("e") == "actividad" else "bateria")
        url = f"{ha}/api/history/period/{start}"
        params = {"filter_entity_id": entity, "minimal_response": "", "no_attributes": ""}
        async with req.app["http"].get(url, params=params) as r:
            data = await r.json() if r.status == 200 else []
        pts = [{"t": p["last_changed"], "v": p["state"]} for serie in data for p in serie]
        return web.json_response(pts)

    @web.middleware
    async def no_cache(req, handler):
        # Cloudflare guarda los estaticos 4 h por defecto: que revalide siempre.
        resp = await handler(req)
        if not req.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    app = web.Application(middlewares=[no_cache, auth])
    app.router.add_get("/api/sesion", sesion)
    app.router.add_post("/api/login", login)
    app.router.add_post("/api/logout", logout)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_get("/", index)
    app.router.add_get("/api/estado", estado)
    app.router.add_post("/api/servicio", servicio)
    app.router.add_get("/api/historial", historial)
    app.router.add_post("/api/programacion", programacion)
    app.router.add_post("/api/durante", durante)

    async def sw(_):
        return web.FileResponse(HERE / "robot" / "sw.js", headers={"Cache-Control": "no-cache",
                                                                    "Content-Type": "text/javascript"})

    app.router.add_get("/sw.js", sw)
    app.router.add_static("/static/", HERE / "robot", show_index=False)
    return app


if __name__ == "__main__":
    load_env()
    web.run_app(make_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8106")))
