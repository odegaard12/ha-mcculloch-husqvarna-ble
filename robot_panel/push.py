"""Avisos push de la web app instalada (Web Push con claves VAPID), sin pasar por la app de Home Assistant.

- Cada móvil se suscribe desde Ajustes de la app; las suscripciones se guardan en push_subs.json
  y se copian a la otra Pi (PEER_URL) para que la conmutación no las pierda.
- Cada suscripción lleva los robots que ese móvil puede ver: los de un robot con contraseña solo llegan
  a quien lo tenía desbloqueado al activar los avisos.
- La Pi que tiene la IP virtual (VIP) avisa; sin VIP configurada (Docker suelto, complemento) avisa siempre.
- En iPhone funciona con iOS 16.4+ y la app añadida a la pantalla de inicio.

Variables: PEER_URL, VIP, VAPID_SUB (contacto que exige el estándar: mailto: o https:).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import subprocess
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from aiohttp import ClientError, ClientSession, ClientTimeout, web

LOG = logging.getLogger("push")


def _load(f: Path, default):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(f: Path, data) -> None:
    f.write_text(json.dumps(data), encoding="utf-8")
    f.chmod(0o600)


def public_key(pem: Path) -> str | None:
    """Clave pública VAPID en base64url (la que pide el navegador al suscribirse)."""
    try:
        from cryptography.hazmat.primitives import serialization
        from py_vapid import Vapid01

        raw = Vapid01.from_file(str(pem)).public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    except Exception:  # noqa: BLE001 - sin claves o sin pywebpush: los avisos quedan desactivados
        return None


def _valid_sub(s) -> bool:
    return (isinstance(s, dict) and isinstance(s.get("endpoint"), str) and s["endpoint"].startswith("https://")
            and len(s["endpoint"]) < 1000 and isinstance(s.get("keys"), dict)
            and all(isinstance(s["keys"].get(k), str) and len(s["keys"][k]) < 200 for k in ("p256dh", "auth"))
            and (s.get("robots") is None or (isinstance(s["robots"], list) and all(isinstance(x, str) for x in s["robots"]))))


def setup_push(app: web.Application, here: Path, ha: str, token: str, robots: list[dict], secret: bytes,
               info: Callable[[], dict], visible: Callable[[web.Request], list[str]]) -> dict:
    """robots: [{id, kind}]; info() -> {id: {"name", "locked"}}; visible(req) -> ids que ve esa sesión."""
    pem = here / "vapid_private.pem"
    subs_file, state_file = here / "push_subs.json", here / "push_state.json"
    key = public_key(pem)
    peer = os.environ.get("PEER_URL", "").rstrip("/")
    vip = os.environ.get("VIP", "").strip()
    claim = os.environ.get("VAPID_SUB", "mailto:avisos@example.com")
    subs: list[dict] = [s for s in _load(subs_file, []) if _valid_sub(s)]
    errs = _load(here / "robot" / "errores_es.json", {})

    def err_text(kind: str, code: str | None) -> str:
        if not code:
            return "avería"
        table = errs.get("landroid" if kind == "landroid" else "mcculloch", {})
        return table.get(code) or errs.get("mcculloch", {}).get(code) or code.replace("_", " ")

    def sign(body: bytes) -> str:
        return hmac.new(secret, b"push-peer:" + body, hashlib.sha256).hexdigest()

    async def replicate() -> None:
        """Copia la lista a la otra Pi (sesión propia: el token de HA no sale de aquí)."""
        if not peer:
            return
        body = json.dumps(subs).encode()
        try:
            async with ClientSession(timeout=ClientTimeout(total=5)) as s, \
                    s.post(f"{peer}/api/push/peer", data=body,
                           headers={"X-Peer-Sig": sign(body), "Content-Type": "application/json"}) as r:
                if r.status != 200:
                    LOG.warning("La otra Pi no aceptó las suscripciones: %s", r.status)
        except (ClientError, TimeoutError) as e:
            LOG.warning("No llego a la otra Pi para copiar suscripciones: %s", e)

    def _send(sub: dict, data: dict) -> bool:
        """True si sigue viva; False si el servicio dice que ya no existe (se borra)."""
        from pywebpush import WebPushException, webpush

        target = {"endpoint": sub["endpoint"], "keys": sub["keys"]}
        try:
            webpush(subscription_info=target, data=json.dumps(data), vapid_private_key=str(pem),
                    vapid_claims={"sub": claim}, ttl=12 * 3600)
            return True
        except WebPushException as e:
            code = e.response.status_code if e.response is not None else 0
            LOG.warning("Aviso no entregado (%s): %s", code, str(e)[:120])
            return code not in (404, 410)

    def may_see(sub: dict, rid: str) -> bool:
        # suscripciones de antes de las contraseñas: solo los robots que hoy no tienen contraseña
        if sub.get("robots") is None:
            return not info().get(rid, {}).get("locked")
        return rid in sub["robots"]

    async def send(data: dict, only: str | None = None, robot: str | None = None) -> int:
        loop = asyncio.get_running_loop()
        targets = [s for s in subs if (only is None or s["endpoint"] == only) and (robot is None or may_see(s, robot))]
        alive = await asyncio.gather(*(loop.run_in_executor(None, _send, s, data) for s in targets))
        dead = [s for s, ok in zip(targets, alive) if not ok]
        if dead:
            for s in dead:
                subs.remove(s)
            _save(subs_file, subs)
            await replicate()
        return len(targets) - len(dead)

    async def forget_robot(rid: str) -> None:
        """Al poner contraseña a un robot, nadie sigue recibiendo sus avisos hasta volver a activarlos desbloqueado."""
        changed = False
        for s in subs:
            if s.get("robots") is None or rid in s["robots"]:
                s["robots"] = [x for x in (s.get("robots") or [r["id"] for r in robots]) if x != rid]
                changed = True
        if changed:
            _save(subs_file, subs)
            await replicate()

    # ---------- rutas (todas con sesión salvo /peer, que va firmada) ----------
    async def get_key(_):
        return web.json_response({"key": key, "subs": len(subs)})

    async def subscribe(req):
        try:
            sub = (await req.json()).get("subscription")
        except (ValueError, AttributeError):
            sub = None
        if not key:
            return web.json_response({"error": "avisos no configurados en el servidor"}, status=503)
        if not _valid_sub(sub):
            return web.json_response({"error": "suscripción no válida"}, status=400)
        sub = {"endpoint": sub["endpoint"], "keys": {k: sub["keys"][k] for k in ("p256dh", "auth")}, "robots": visible(req)}
        subs[:] = [s for s in subs if s["endpoint"] != sub["endpoint"]] + [sub]
        del subs[:-20]  # como mucho 20 móviles
        _save(subs_file, subs)
        await replicate()
        return web.json_response({"ok": True, "robots": sub["robots"]})

    async def unsubscribe(req):
        try:
            ep = (await req.json()).get("endpoint")
        except (ValueError, AttributeError):
            ep = None
        subs[:] = [s for s in subs if s["endpoint"] != ep]
        _save(subs_file, subs)
        await replicate()
        return web.json_response({"ok": True})

    async def test(req):
        try:
            ep = (await req.json()).get("endpoint")
        except (ValueError, AttributeError):
            ep = None
        if not any(s["endpoint"] == ep for s in subs):
            return web.json_response({"error": "este móvil no está suscrito"}, status=404)
        n = await send({"title": "Mis robots", "body": "✅ Los avisos llegan a este móvil.", "tag": "prueba", "url": "./"}, only=ep)
        return web.json_response({"ok": n == 1}, status=200 if n == 1 else 502)

    async def from_peer(req):
        body = await req.read()
        if not hmac.compare_digest(req.headers.get("X-Peer-Sig", ""), sign(body)):
            return web.json_response({"error": "firma"}, status=403)
        data = json.loads(body)
        subs[:] = [s for s in data if _valid_sub(s)][-20:]
        _save(subs_file, subs)
        return web.json_response({"ok": True})

    app.router.add_get("/api/push/key", get_key)
    app.router.add_post("/api/push/subscribe", subscribe)
    app.router.add_post("/api/push/unsubscribe", unsubscribe)
    app.router.add_post("/api/push/test", test)
    app.router.add_post("/api/push/peer", from_peer)

    # ---------- vigilante ----------
    def holds_vip() -> bool:
        if not vip:
            return True
        try:
            return vip in subprocess.run(["ip", "-4", "addr"], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return False

    # Sin sondeos: una sola conexión websocket con HA, suscrita solo a las entidades que importan.
    # La Pi no hace nada hasta que una cambia; los «lleva X minutos» y «X días sin conexión» son temporizadores.
    def entities(r: dict) -> dict[str, str]:
        p = r["id"]
        if r["kind"] == "landroid":
            return {"lm": f"lawn_mower.{p}", "error": f"sensor.{p}_error", "seen": f"sensor.{p}_ultima_actualizacion"}
        return {"averia": f"binary_sensor.{p}_averia", "volcado": f"binary_sensor.{p}_volcado",
                "levantado": f"binary_sensor.{p}_levantado", "actividad": f"sensor.{p}_actividad",
                "error": f"sensor.{p}_error", "seen": f"sensor.{p}_ultima_conexion"}

    E = {r["id"]: entities(r) for r in robots}
    KIND = {r["id"]: r["kind"] for r in robots}
    cur: dict[str, str | None] = {}
    timers: dict[str, asyncio.Task] = {}
    COOLDOWN, DAY_MAX = 6 * 3600, 6  # cada aviso como mucho cada 6 h, y no más de 6 al día en total

    def seen_dt(rid: str) -> datetime | None:
        try:
            return datetime.fromisoformat(cur.get(E[rid]["seen"]) or "")
        except ValueError:
            return None

    def rules() -> dict:
        """'robot:aviso' -> (activo, espera en s, texto)."""
        out = {}
        for rid, ent in E.items():
            name = info().get(rid, {}).get("name") or rid
            g = lambda k: cur.get(ent[k])  # noqa: E731
            on = lambda k: g(k) == "on"  # noqa: E731
            seen = seen_dt(rid)
            lejos = (datetime.now().astimezone() - seen).total_seconds() if seen else 0
            cuando = seen.astimezone().strftime("%d/%m %H:%M") if seen else ""
            if KIND[rid] == "landroid":
                online = g("lm") not in (None, "unavailable", "unknown")
                err = g("error")
                bad = online and err not in (None, "no_error", "unknown", "unavailable", "rain_delay")
                rule = {
                    # el error se queda con su último valor sin conexión: solo cuenta con el robot conectado
                    "averia": (bad, 120, f"⚠️ {name}: {err_text('landroid', err)}. Revísalo y pulsa OK en el robot."),
                }
                tip = "¿Sin Wi-Fi o apagado?"
            else:
                rule = {
                    "averia": (on("averia"), 60, f"⚠️ {name}: {err_text('mcculloch', g('error'))}. Revísalo y confírmalo en su teclado."),
                    "volcado": (on("volcado"), 30, f"⚠️ {name} está volcado. Dale la vuelta y confirma en el robot."),
                    "levantado": (on("levantado"), 120, f"{name} lleva un rato levantado. Déjalo en el césped para que siga."),
                    "parado": (g("actividad") == "stopped_in_garden", 600, f"{name} se ha parado en el jardín y espera que alguien lo atienda."),
                }
                tip = "¿Lejos del receptor o sin batería?"
            # activos desde el principio; la espera es lo que falta para cumplir el plazo
            rule["sin_conexion_1"] = (seen is not None, 86400 - lejos, f"📡 {name} lleva más de 1 día sin conexión (último contacto {cuando}). {tip}")
            rule["sin_conexion_3"] = (seen is not None, 3 * 86400 - lejos, f"📡 {name} lleva más de 3 días sin conexión (último contacto {cuando}).")
            out.update({f"{rid}:{cid}": v for cid, v in rule.items()})
        return out

    async def notify(cid: str, text: str) -> None:
        rid = cid.split(":", 1)[0]
        mem = _load(state_file, {})
        now = time.time()
        last, day = mem.setdefault("last", {}), [t for t in mem.get("day", []) if now - t < 86400]
        offline_for = mem.setdefault("offline_for", {})
        seen = seen_dt(rid)
        if "sin_conexion" in cid and seen and offline_for.get(cid) == seen.isoformat():
            return  # ya se avisó de esta misma desconexión
        if not subs or now - last.get(cid, 0) < COOLDOWN or len(day) >= DAY_MAX:
            return
        if not await asyncio.get_running_loop().run_in_executor(None, holds_vip):
            return  # avisa la otra Pi (la que tiene la IP virtual)
        if await send({"title": info().get(rid, {}).get("name") or "Mis robots", "body": text, "tag": cid, "url": "./"}, robot=rid):
            last[cid] = now
            mem["day"] = day + [now]
            if "sin_conexion" in cid and seen:
                offline_for[cid] = seen.isoformat()
            _save(state_file, mem)

    def arm(cid: str, delay: float) -> None:
        if cid in timers:
            return

        async def fire():
            await asyncio.sleep(max(0.0, delay))
            timers.pop(cid, None)
            active, wait, text = rules()[cid]
            if active and wait <= 1:  # sigue igual al cumplirse el plazo
                await notify(cid, text)

        timers[cid] = asyncio.create_task(fire())

    def disarm(cid: str) -> None:
        t = timers.pop(cid, None)
        if t:
            t.cancel()

    def evaluate(prev: dict[str, datetime | None]) -> None:
        for rid in E:
            seen, before = seen_dt(rid), prev.get(rid)
            if seen and before and seen > before:
                # ha vuelto a hablar con el robot: fuera los «sin conexión»; si se llegó a avisar, se avisa de que vuelve
                disarm(f"{rid}:sin_conexion_1")
                disarm(f"{rid}:sin_conexion_3")
                last = _load(state_file, {}).get("last", {}).get(f"{rid}:sin_conexion_1", 0)
                if last > before.timestamp():
                    name = info().get(rid, {}).get("name") or rid
                    asyncio.create_task(notify(f"{rid}:vuelve", f"✅ {name} vuelve a estar conectado."))
        for cid, (active, wait, _text) in rules().items():
            if active:
                arm(cid, wait)
            else:
                disarm(cid)

    ws_url = ha.replace("http", "ws", 1) + ("/websocket" if ha.endswith("/core") else "/api/websocket")

    async def watch(app):
        backoff = 30
        watched = sorted({e for ent in E.values() for e in ent.values()})
        while True:
            try:
                async with ClientSession() as s, s.ws_connect(ws_url, heartbeat=55) as w:
                    await w.receive_json()
                    await w.send_json({"type": "auth", "access_token": token})
                    if (await w.receive_json()).get("type") != "auth_ok":
                        raise RuntimeError("HA rechazó el token")
                    await w.send_json({"id": 1, "type": "subscribe_entities", "entity_ids": watched})
                    backoff = 30
                    async for msg in w:
                        ev = (msg.json() or {}).get("event") if msg.type.name == "TEXT" else None
                        if not ev:
                            continue
                        prev = {rid: seen_dt(rid) for rid in E}
                        for eid, v in (ev.get("a") or {}).items():
                            cur[eid] = v.get("s")
                        for eid, v in (ev.get("c") or {}).items():
                            if "s" in (v.get("+") or {}):
                                cur[eid] = v["+"]["s"]
                        evaluate(prev)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - HA reiniciando, red...: se reintenta con espera creciente
                LOG.warning("Vigilante de avisos sin conexión con HA: %s", e)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 600)

    async def start(app):
        app["push_watch"] = asyncio.create_task(watch(app)) if (key and token) else asyncio.create_task(asyncio.sleep(0))

    async def stop(app):
        app["push_watch"].cancel()

    app.on_startup.append(start)
    app.on_cleanup.append(stop)
    return {"forget_robot": forget_robot}
