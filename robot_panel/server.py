"""Panel «Mi robot» para una Raspberry: sirve la app y habla con Home Assistant por su API REST.

Solo deja leer las entidades del robot y llamar a las órdenes del robot (lista cerrada), así
que el token de HA nunca llega al navegador.

Variables (fichero robot_app.env junto a este script):
  HA_URL        http://homeassistant.local:8123
  HA_TOKEN      token de larga duración de HA (Perfil > Seguridad); lo pone el usuario
  APP_PIN       PIN para abrir la app (vacio = sin bloqueo); lo pone el usuario con set_pin.sh
  PORT          8106
  ROBOT_PREFIX  prefijo de las entidades del robot (por defecto robot_cortacesped)
  ROBOT_NAME    nombre que se ve en la app (por defecto McCulloch)
  ROBOTS        más robots, p. ej. landroid:Landroid:landroid (prefijo:nombre:tipo, separados por comas)

Como complemento de HA (ingress) no hace falta nada: el supervisor da la URL y el token.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aiohttp import ClientError, ClientSession, ClientTimeout, web

HERE = Path(__file__).resolve().parent
LOG = logging.getLogger("panel")


def parse_robots() -> list[dict]:
    """El primero es el McCulloch (ROBOT_PREFIX); ROBOTS=prefijo:Nombre:tipo,... añade más (tipo mcculloch | landroid)."""
    prefix = os.environ.get("ROBOT_PREFIX", "").strip() or "robot_cortacesped"
    out = [{"id": prefix, "name": os.environ.get("ROBOT_NAME", "").strip()[:40] or "McCulloch", "kind": "mcculloch"}]
    for item in os.environ.get("ROBOTS", "").split(","):
        parts = [p.strip() for p in item.split(":")]
        if (len(parts) == 3 and re.fullmatch(r"[a-z0-9_]+", parts[0]) and parts[2] in ("mcculloch", "landroid")
                and parts[0] not in [r["id"] for r in out]):
            out.append({"id": parts[0], "name": parts[1][:40] or parts[0], "kind": parts[2]})
    return out


def entity_re(ids: list[str]) -> re.Pattern:
    # una sola entidad de alguno de los robots, nunca una lista separada por comas (HA la trocearía)
    return re.compile(rf"(lawn_mower|button|switch)\.({'|'.join(map(re.escape, ids))})(_[a-z0-9_]+)?")
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


# El panel no carga nada de fuera: todo «solo de este sitio». frame-ancestors 'self' deja que HA lo
# muestre en su barra lateral (el ingress es el mismo origen) pero no que otra web lo meta en un iframe.
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                               "img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}

COOKIE = "rob_sesion"
SESSION_DAYS = 180
MAX_FAILS, FAIL_WINDOW = 5, 300  # 5 PIN fallidos en 5 min bloquean esa IP 5 min
GLOBAL_MAX_FAILS, GLOBAL_WINDOW = 20, 3600  # y 20 fallos en una hora, vengan de donde vengan, bloquean a todos


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
    robots = parse_robots()
    ids = [r["id"] for r in robots]
    kinds = {r["id"]: r["kind"] for r in robots}
    ENTITY_RE = entity_re(ids)
    PREFIX = ids[0]
    fails: dict[str, list[float]] = {}
    all_fails: list[float] = []
    # la firma incluye el PIN: al cambiarlo, todas las sesiones anteriores dejan de valer
    pin_tag = hashlib.sha256(pin.encode()).hexdigest()[:16]

    def sign(exp: int) -> str:
        return hmac.new(secret, f"{exp}.{pin_tag}".encode(), hashlib.sha256).hexdigest()

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
        # sin sesión: login, estado de la sesión, salud, versión (para recargar la app) y las copias firmadas entre Pis
        if (req.path.startswith("/api/") and not session_ok(req)
                and req.path not in ("/api/login", "/api/sesion", "/api/salud", "/api/version", "/api/push/peer",
                                     "/api/robots/peer")):
            return web.json_response({"error": "pin"}, status=401)
        return await handler(req)

    async def sesion(req):
        return web.json_response({"pin": bool(pin), "pin_len": len(pin), "ok": session_ok(req)})

    def client_ip(req) -> str:
        return req.headers.get("CF-Connecting-IP") or req.remote or "?"

    def too_many(ip: str) -> bool:
        # CF-Connecting-IP se puede falsear si alguien llega directo al puerto: por eso hay
        # además un límite global que no depende de la IP (frena probar los 10 000 PIN).
        now = time.time()
        for k in [k for k, v in fails.items() if not v or now - v[-1] > FAIL_WINDOW]:
            del fails[k]
        all_fails[:] = [t for t in all_fails if now - t < GLOBAL_WINDOW]
        recent = [t for t in fails.get(ip, []) if now - t < FAIL_WINDOW]
        return len(recent) >= MAX_FAILS or len(all_fails) >= GLOBAL_MAX_FAILS

    def failed(ip: str) -> None:
        now = time.time()
        fails[ip] = [t for t in fails.get(ip, []) if now - t < FAIL_WINDOW] + [now]
        all_fails.append(now)

    def secure_cookie(req) -> bool:
        return req.headers.get("X-Forwarded-Proto") == "https" or req.secure

    async def login(req):
        ip = client_ip(req)
        if too_many(ip):
            return web.json_response({"error": "Demasiados intentos. Espera unos minutos."}, status=429)
        try:
            body = await req.json()
        except ValueError:
            body = {}
        if not pin or not hmac.compare_digest(str(body.get("pin", "")).encode(), pin.encode()):
            failed(ip)
            return web.json_response({"error": "PIN incorrecto"}, status=403)
        fails.pop(ip, None)
        exp = int(time.time()) + SESSION_DAYS * 86400
        resp = web.json_response({"ok": True})
        resp.set_cookie(COOKIE, f"{exp}.{sign(exp)}", max_age=SESSION_DAYS * 86400, httponly=True, samesite="Strict",
                        secure=secure_cookie(req))
        return resp

    # ---------- robots: nombre que se ve y contraseña propia (p. ej. para que otro de la casa no lo toque) ----------
    # robots_cfg.json: {"v": marca de tiempo, "robots": {id: {"name": str, "pin": hash pbkdf2}}}. Se copia a la otra
    # Pi: gana siempre la versión más nueva (una copia vieja reenviada no pisa nada), se reintenta si la otra no
    # contesta y al arrancar se sincronizan las dos (la que estaba apagada recoge los cambios).
    cfg_file = HERE / "robots_cfg.json"
    cfg: dict = {}
    cfg_v = [0.0]

    def adopt(data) -> None:
        raw = data.get("robots", data) if isinstance(data, dict) else {}  # formato antiguo: sin "v"
        cfg.clear()
        cfg.update({k: v for k, v in raw.items() if k in ids and isinstance(v, dict)})
        cfg_v[0] = float(data.get("v", 0)) if isinstance(data, dict) and "robots" in data else 0.0

    try:
        adopt(json.loads(cfg_file.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    peer = os.environ.get("PEER_URL", "").rstrip("/")

    def cfg_blob() -> bytes:
        return json.dumps({"v": cfg_v[0], "robots": cfg}, ensure_ascii=False).encode()

    def save_cfg(bump: bool = True) -> None:
        if bump:
            cfg_v[0] = max(time.time(), cfg_v[0] + 0.001)
        cfg_file.write_bytes(cfg_blob())
        cfg_file.chmod(0o600)

    def peer_sig(body: bytes) -> str:
        return hmac.new(secret, b"robots-peer:" + body, hashlib.sha256).hexdigest()

    def sig_ok(got: str, body: bytes) -> bool:
        return hmac.compare_digest(got.encode(errors="replace"), peer_sig(body).encode())

    async def replicate_cfg(tries: int = 10) -> None:
        """Manda la configuración a la otra Pi; si la de allí es más nueva, se queda con la suya."""
        if not peer:
            return
        for n in range(tries):
            body = cfg_blob()
            try:
                async with ClientSession(timeout=ClientTimeout(total=5)) as s, \
                        s.post(f"{peer}/api/robots/peer", data=body, headers={"X-Peer-Sig": peer_sig(body)}) as r:
                    reply = await r.read()
                    if r.status == 200:
                        theirs = json.loads(reply or b"{}")
                        if theirs.get("robots") is not None and sig_ok(r.headers.get("X-Peer-Sig", ""), reply) \
                                and float(theirs.get("v", 0)) > cfg_v[0]:
                            adopt(theirs)
                            save_cfg(bump=False)
                        return
                    LOG.warning("La otra Pi no aceptó la configuración de robots: %s", r.status)
            except (ClientError, TimeoutError, ValueError) as e:
                LOG.warning("No llego a la otra Pi para copiar la configuración de robots (%s/%s): %s", n + 1, tries, e)
            await asyncio.sleep(min(60, 5 * 2 ** n))

    def replicate_soon() -> None:
        asyncio.get_running_loop().create_task(replicate_cfg())

    def rname(rid: str) -> str:
        return (cfg.get(rid) or {}).get("name") or next(r["name"] for r in robots if r["id"] == rid)

    def lock_of(rid: str) -> str | None:
        return (cfg.get(rid) or {}).get("pin")

    def pin_hash(p: str) -> str:
        return hashlib.pbkdf2_hmac("sha256", p.encode(), secret, 120_000).hex()

    def ul_cookie(rid: str) -> str:
        return f"rob_ul_{rid}"

    def ul_sign(rid: str, exp: int) -> str:
        # ligada a la contraseña: si se cambia, los desbloqueos anteriores dejan de valer
        return hmac.new(secret, f"ul.{rid}.{exp}.{lock_of(rid)}".encode(), hashlib.sha256).hexdigest()

    def is_open(req, rid: str) -> bool:
        if not lock_of(rid):
            return True
        try:
            exp, sig = req.cookies.get(ul_cookie(rid), "").split(".")
            return int(exp) > time.time() and hmac.compare_digest(sig, ul_sign(rid, int(exp)))
        except ValueError:
            return False

    def visible(req) -> list[str]:
        return [i for i in ids if is_open(req, i)]

    def robot_of(obj_id: str) -> str | None:
        """Robot al que pertenece un id de objeto (el prefijo más largo que encaje)."""
        for i in sorted(ids, key=len, reverse=True):
            if obj_id == i or obj_id.startswith(i + "_"):
                return i
        return None

    def set_open(resp, req, rid: str) -> None:
        exp = int(time.time()) + SESSION_DAYS * 86400
        resp.set_cookie(ul_cookie(rid), f"{exp}.{ul_sign(rid, exp)}", max_age=SESSION_DAYS * 86400, httponly=True,
                        samesite="Strict", secure=secure_cookie(req))

    def locked_resp():
        return web.json_response({"error": "Este robot tiene contraseña: desbloquéalo primero."}, status=423)

    async def lista(req):
        return web.json_response([{**r, "name": rname(r["id"]), "locked": bool(lock_of(r["id"])), "open": is_open(req, r["id"])}
                                  for r in robots])

    async def nombre(req):
        body = await body_of(req)
        rid, name = body.get("id"), " ".join(str(body.get("name", "")).split())[:30]
        if rid not in ids or not name:
            return web.json_response({"error": "nombre no válido"}, status=400)
        if not is_open(req, rid):
            return locked_resp()
        cfg.setdefault(rid, {})["name"] = name
        save_cfg()
        replicate_soon()
        return web.json_response({"ok": True, "name": name})

    async def clave(req):
        """Poner, cambiar o quitar la contraseña de un robot. Si ya tiene, hace falta la actual."""
        ip = client_ip(req)
        if too_many(ip):
            return web.json_response({"error": "Demasiados intentos. Espera unos minutos."}, status=429)
        body = await body_of(req)
        rid, actual, nueva = body.get("id"), str(body.get("actual", "")), str(body.get("nueva", ""))
        if rid not in ids or (nueva and not re.fullmatch(r"\d{4,8}", nueva)):
            return web.json_response({"error": "La contraseña tiene que ser de 4 a 8 cifras."}, status=400)
        if lock_of(rid) and not hmac.compare_digest(pin_hash(actual), lock_of(rid)):
            failed(ip)
            return web.json_response({"error": "La contraseña actual no es correcta."}, status=403)
        if nueva:
            cfg.setdefault(rid, {})["pin"] = pin_hash(nueva)
        else:
            cfg.setdefault(rid, {}).pop("pin", None)
        save_cfg()
        replicate_soon()
        if nueva:
            await req.app["push"]["forget_robot"](rid)  # sus avisos, solo a quien los vuelva a activar desbloqueado
        resp = web.json_response({"ok": True, "locked": bool(nueva)})
        if nueva:
            set_open(resp, req, rid)  # quien la pone sigue dentro en este móvil
        return resp

    async def abrir(req):
        ip = client_ip(req)
        if too_many(ip):
            return web.json_response({"error": "Demasiados intentos. Espera unos minutos."}, status=429)
        body = await body_of(req)
        rid = body.get("id")
        if rid not in ids:
            return web.json_response({"error": "robot no válido"}, status=400)
        if lock_of(rid) and not hmac.compare_digest(pin_hash(str(body.get("pin", ""))), lock_of(rid)):
            failed(ip)
            return web.json_response({"error": "Contraseña incorrecta"}, status=403)
        resp = web.json_response({"ok": True})
        if lock_of(rid):
            set_open(resp, req, rid)
        return resp

    async def cerrar(req):
        body = await body_of(req)
        resp = web.json_response({"ok": True})
        if body.get("id") in ids:
            resp.del_cookie(ul_cookie(body["id"]))
        return resp

    async def cfg_from_peer(req):
        body = await req.read()
        if not sig_ok(req.headers.get("X-Peer-Sig", ""), body):
            return web.json_response({"error": "firma"}, status=403)
        try:
            data = json.loads(body)
            theirs = float(data.get("v", 0))
        except (ValueError, TypeError, AttributeError):
            return web.json_response({"error": "datos"}, status=400)
        if "robots" in data and theirs > cfg_v[0]:
            adopt(data)
            save_cfg(bump=False)
            return web.json_response({"ok": True})
        # la mía es igual o más nueva: se la devuelvo (firmada) para que la otra Pi se ponga al día
        mine = cfg_blob()
        return web.Response(body=mine, content_type="application/json", headers={"X-Peer-Sig": peer_sig(mine)})

    async def logout(_):
        resp = web.json_response({"ok": True})
        resp.del_cookie(COOKIE)
        return resp
    token = os.environ.get("HA_TOKEN", "") or supervisor
    headers = {"Authorization": f"Bearer {token}"}

    async def on_startup(app):
        app["http"] = ClientSession(timeout=ClientTimeout(total=20), headers=headers)
        replicate_soon()  # al arrancar, ponerse al día con la otra Pi (nombres y contraseñas)

    async def on_cleanup(app):
        await app["http"].close()

    def no_token():
        return web.json_response({"error": "Falta HA_TOKEN en robot_app.env"}, status=503)

    async def index(_):
        # la página lleva dentro su versión: si una copia guardada sin red es vieja, al volver la red se recarga sola
        try:
            html = (HERE / "robot" / "index.html").read_text(encoding="utf-8").replace("__APP_VERSION__", version)
        except OSError:  # (devuelto, no lanzado: así también lleva las cabeceras de seguridad)
            return web.Response(status=404, text="No encontrado")
        return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-cache"})

    async def estado(req):
        if not token:
            return no_token()
        try:
            async with req.app["http"].get(f"{ha}/api/states") as r:
                if r.status != 200:
                    return web.json_response({"error": f"HA respondió {r.status}"}, status=502)
                data = await r.json()
        except (ClientError, TimeoutError) as e:
            return unreachable(e)
        # solo los robots que esta sesión puede ver: uno con contraseña no enseña nada hasta desbloquearlo
        seen = set(visible(req))
        return web.json_response([s for s in data if robot_of(s["entity_id"].split(".", 1)[1]) in seen])

    async def salud(req):
        """Para el despliegue y la vigilancia: ¿sirve y llega a HA? Sin PIN y sin datos del robot."""
        ha_ok = False
        if token:
            try:
                async with req.app["http"].get(f"{ha}/api/", timeout=ClientTimeout(total=5)) as r:
                    ha_ok = r.status == 200
            except (ClientError, TimeoutError):
                pass
        return web.json_response({"ok": True, "ha": ha_ok}, status=200 if ha_ok else 503)

    def unreachable(e: Exception):
        return web.json_response({"error": f"No llego a Home Assistant: {type(e).__name__}"}, status=502)

    async def body_of(req) -> dict:
        try:
            body = await req.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

    async def servicio(req):
        if not token:
            return no_token()
        body = await body_of(req)
        domain, service, entity = body.get("domain"), body.get("service"), body.get("entity_id")
        if ((domain, service) not in ALLOWED or not isinstance(entity, str)
                or not ENTITY_RE.fullmatch(entity) or not entity.startswith(f"{domain}.")):
            return web.json_response({"error": "orden no permitida"}, status=403)
        if not is_open(req, robot_of(entity.split(".", 1)[1])):
            return locked_resp()
        try:
            async with req.app["http"].post(f"{ha}/api/services/{domain}/{service}", json={"entity_id": entity}) as r:
                return web.json_response({"ok": r.status == 200}, status=200 if r.status == 200 else 502)
        except (ClientError, TimeoutError) as e:
            return unreachable(e)

    async def programacion(req):
        """Valida lo basico y pide a HA que grabe la programacion en el robot."""
        if not token:
            return no_token()
        if not is_open(req, PREFIX):
            return locked_resp()
        body = await body_of(req)
        tasks = body.get("tasks")
        if not isinstance(tasks, list) or len(tasks) > 15:
            return web.json_response({"error": "programacion no valida"}, status=400)
        clean = []
        for t in tasks:
            if not isinstance(t, dict):
                return web.json_response({"error": "tarea no valida"}, status=400)
            days = t.get("days", [])
            clean.append({"start": str(t.get("start", "")), "end": str(t.get("end", "")),
                          "days": [str(d) for d in days] if isinstance(days, list) else []})
        url = f"{ha}/api/services/mcculloch_rob/set_schedule?return_response"
        try:
            # grabar 15 turnos por Bluetooth puede pasar de 20 s: este pide más margen
            async with req.app["http"].post(url, json={"tasks": clean}, timeout=ClientTimeout(total=90)) as r:
                data = await r.json(content_type=None) if r.content_length != 0 else {}
                if r.status != 200:
                    msg = data.get("message") if isinstance(data, dict) else None
                    return web.json_response({"error": msg or f"HA respondio {r.status}"}, status=400 if r.status == 400 else 502)
        except (ClientError, TimeoutError) as e:
            return unreachable(e)
        return web.json_response({"ok": True, "tasks": ((data or {}).get("service_response") or {}).get("tasks")})

    async def durante(req):
        """Cortar o aparcar durante N horas (servicios propios de la integracion)."""
        if not token:
            return no_token()
        if not is_open(req, PREFIX):
            return locked_resp()
        body = await body_of(req)
        service = {"cortar": "mow_for", "aparcar": "park_for"}.get(body.get("accion"))
        try:
            hours = float(body.get("horas"))
        except (TypeError, ValueError):
            hours = 0
        if not service or not 0.5 <= hours <= (24 if service == "mow_for" else 168):
            return web.json_response({"error": "orden no valida"}, status=400)
        try:
            async with req.app["http"].post(f"{ha}/api/services/mcculloch_rob/{service}", json={"hours": hours},
                                            timeout=ClientTimeout(total=60)) as r:
                if r.status != 200:
                    data = await r.json(content_type=None) if r.content_length != 0 else {}
                    msg = data.get("message") if isinstance(data, dict) else None
                    return web.json_response({"error": msg or f"HA respondio {r.status}"}, status=502)
        except (ClientError, TimeoutError) as e:
            return unreachable(e)
        return web.json_response({"ok": True})

    async def historial(req):
        if not token:
            return no_token()
        try:  # ?d=7 para la semana; acotado para no pedir a HA meses de historial
            days = min(7, max(1, int(req.query.get("d", "1"))))
        except ValueError:
            days = 1
        start = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        rid = req.query.get("r") if req.query.get("r") in ids else PREFIX
        if not is_open(req, rid):
            return locked_resp()
        if req.query.get("e") != "actividad":
            entity = f"sensor.{rid}_bateria"
        elif kinds[rid] == "landroid":  # Landroid no tiene sensor de actividad: su estado sale del cortacésped
            entity = f"lawn_mower.{rid}"
        else:
            entity = f"sensor.{rid}_actividad"
        url = f"{ha}/api/history/period/{start}"
        params = {"filter_entity_id": entity, "minimal_response": "", "no_attributes": ""}
        try:
            async with req.app["http"].get(url, params=params) as r:
                data = await r.json() if r.status == 200 else []
        except (ClientError, TimeoutError) as e:
            return unreachable(e)
        pts = [{"t": p["last_changed"], "v": p["state"]} for serie in data for p in serie]
        return web.json_response(pts)

    @web.middleware
    async def no_cache(req, handler):
        # Cloudflare guarda los estaticos 4 h por defecto: que revalide siempre.
        resp = await handler(req)
        if not req.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-cache"
        resp.headers.update(SECURITY_HEADERS)
        return resp

    app = web.Application(middlewares=[no_cache, auth])
    app.router.add_get("/api/sesion", sesion)
    app.router.add_post("/api/login", login)
    app.router.add_post("/api/logout", logout)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_get("/", index)
    app.router.add_get("/api/estado", estado)
    app.router.add_get("/api/robots", lista)
    app.router.add_post("/api/robots/nombre", nombre)
    app.router.add_post("/api/robots/clave", clave)
    app.router.add_post("/api/robots/abrir", abrir)
    app.router.add_post("/api/robots/cerrar", cerrar)
    app.router.add_post("/api/robots/peer", cfg_from_peer)
    app.router.add_get("/api/salud", salud)

    # versión de la app = huella de sus archivos: si cambia tras un despliegue, la app abierta se recarga sola
    files = [HERE / "robot" / n for n in ("index.html", "sw.js")]
    version = hashlib.sha256(b"".join(f.read_bytes() for f in files if f.exists())).hexdigest()[:12]
    app.router.add_get("/api/version", lambda _: web.json_response({"v": version}, headers={"Cache-Control": "no-store"}))

    from push import setup_push  # avisos de la web app (Web Push)
    app["push"] = setup_push(app, HERE, ha, token, robots, secret,
                             info=lambda: {r["id"]: {"name": rname(r["id"]), "locked": bool(lock_of(r["id"]))} for r in robots},
                             visible=visible)
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
