"""Avisos push de la web app instalada (Web Push con claves VAPID), sin pasar por la app de Home Assistant.

- Cada móvil se suscribe desde Ajustes de la app; las suscripciones se guardan en push_subs.json
  y se copian a la otra Pi (PEER_URL) para que la conmutación no las pierda.
- La Pi que tiene la IP virtual (VIP) vigila al robot cada minuto y avisa. Sin VIP configurada
  (Docker suelto, complemento de HA) avisa siempre.
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
from datetime import datetime
from pathlib import Path

from aiohttp import ClientError, ClientSession, ClientTimeout, web

LOG = logging.getLogger("push")
CHECK_EVERY = 60  # s


def _load(f: Path, default):
    try:
        return json.loads(f.read_text())
    except (OSError, ValueError):
        return default


def _save(f: Path, data) -> None:
    f.write_text(json.dumps(data))
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
            and all(isinstance(s["keys"].get(k), str) and len(s["keys"][k]) < 200 for k in ("p256dh", "auth")))


def setup_push(app: web.Application, here: Path, ha: str, token: str, prefix: str, secret: bytes) -> None:
    pem = here / "vapid_private.pem"
    subs_file, state_file = here / "push_subs.json", here / "push_state.json"
    key = public_key(pem)
    peer = os.environ.get("PEER_URL", "").rstrip("/")
    vip = os.environ.get("VIP", "").strip()
    claim = os.environ.get("VAPID_SUB", "mailto:avisos@example.com")
    subs: list[dict] = [s for s in _load(subs_file, []) if _valid_sub(s)]

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

        try:
            webpush(subscription_info=sub, data=json.dumps(data), vapid_private_key=str(pem),
                    vapid_claims={"sub": claim}, ttl=12 * 3600)
            return True
        except WebPushException as e:
            code = e.response.status_code if e.response is not None else 0
            LOG.warning("Aviso no entregado (%s): %s", code, str(e)[:120])
            return code not in (404, 410)

    async def send(data: dict, only: str | None = None) -> int:
        loop = asyncio.get_running_loop()
        targets = [s for s in subs if only is None or s["endpoint"] == only]
        alive = await asyncio.gather(*(loop.run_in_executor(None, _send, s, data) for s in targets))
        dead = [s for s, ok in zip(targets, alive) if not ok]
        if dead:
            for s in dead:
                subs.remove(s)
            _save(subs_file, subs)
            await replicate()
        return len(targets) - len(dead)

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
        sub = {"endpoint": sub["endpoint"], "keys": {k: sub["keys"][k] for k in ("p256dh", "auth")}}
        subs[:] = [s for s in subs if s["endpoint"] != sub["endpoint"]] + [sub]
        del subs[:-20]  # como mucho 20 móviles
        _save(subs_file, subs)
        await replicate()
        return web.json_response({"ok": True})

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
        n = await send({"title": "Mi robot", "body": "✅ Los avisos llegan a este móvil.", "tag": "prueba", "url": "./"}, only=ep)
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
    E = {k: f"{d}.{prefix}_{k}" for d, k in (("binary_sensor", "averia"), ("binary_sensor", "volcado"),
                                            ("binary_sensor", "levantado"), ("sensor", "actividad"),
                                            ("sensor", "error"), ("sensor", "ultima_conexion"))}
    cur: dict[str, str | None] = {}
    timers: dict[str, asyncio.Task] = {}
    COOLDOWN, DAY_MAX = 6 * 3600, 6  # cada aviso como mucho cada 6 h, y no más de 6 al día en total

    def seen_dt() -> datetime | None:
        try:
            return datetime.fromisoformat(cur.get(E["ultima_conexion"]) or "")
        except ValueError:
            return None

    def rules() -> dict:
        """id -> (activo, espera en s, texto)."""
        on = lambda k: cur.get(E[k]) == "on"  # noqa: E731
        err = (cur.get(E["error"]) or "").replace("_", " ")
        seen = seen_dt()
        lejos = (datetime.now().astimezone() - seen).total_seconds() if seen else 0
        cuando = seen.astimezone().strftime("%d/%m %H:%M") if seen else ""
        return {
            "averia": (on("averia"), 60, f"⚠️ Avería: {err}. Revisa el robot y confírmalo en su teclado."),
            "volcado": (on("volcado"), 30, "⚠️ El robot está volcado. Dale la vuelta y confirma en el robot."),
            "levantado": (on("levantado"), 120, "El robot lleva un rato levantado. Déjalo en el césped para que siga."),
            "parado": (cur.get(E["actividad"]) == "stopped_in_garden", 600,
                       "El robot se ha parado en el jardín y espera que alguien lo atienda."),
            # activos desde el principio; la espera es lo que falta para cumplir el plazo
            "sin_conexion_1": (seen is not None, 86400 - lejos,
                               f"📡 Lleva más de 1 día sin conexión (último contacto {cuando}). ¿Lejos del receptor o sin batería?"),
            "sin_conexion_3": (seen is not None, 3 * 86400 - lejos, f"📡 Lleva más de 3 días sin conexión (último contacto {cuando})."),
        }

    async def notify(cid: str, text: str) -> None:
        mem = _load(state_file, {})
        now = time.time()
        last, day = mem.setdefault("last", {}), [t for t in mem.get("day", []) if now - t < 86400]
        if not subs or now - last.get(cid, 0) < COOLDOWN or len(day) >= DAY_MAX:
            return
        if not await asyncio.get_running_loop().run_in_executor(None, holds_vip):
            return  # avisa la otra Pi (la que tiene la IP virtual)
        if await send({"title": "Mi robot", "body": text, "tag": cid, "url": "./"}):
            last[cid] = now
            mem["day"] = day + [now]
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

    def evaluate(prev_seen: datetime | None) -> None:
        seen = seen_dt()
        if seen and prev_seen and seen > prev_seen:
            # ha vuelto a hablar con el robot: fuera los temporizadores de «sin conexión»;
            # si llegamos a avisar de que estaba desconectado, se avisa también de que vuelve
            disarm("sin_conexion_1")
            disarm("sin_conexion_3")
            last = _load(state_file, {}).get("last", {}).get("sin_conexion_1", 0)
            if last > prev_seen.timestamp():
                asyncio.create_task(notify("vuelve", "✅ El robot vuelve a estar conectado."))
        for cid, (active, wait, _text) in rules().items():
            if active:
                arm(cid, wait)
            else:
                disarm(cid)

    ws_url = ha.replace("http", "ws", 1) + ("/websocket" if ha.endswith("/core") else "/api/websocket")

    async def watch(app):
        backoff = 30
        while True:
            try:
                async with ClientSession() as s, s.ws_connect(ws_url, heartbeat=55) as w:
                    await w.receive_json()
                    await w.send_json({"type": "auth", "access_token": token})
                    if (await w.receive_json()).get("type") != "auth_ok":
                        raise RuntimeError("HA rechazó el token")
                    await w.send_json({"id": 1, "type": "subscribe_entities", "entity_ids": sorted(E.values())})
                    backoff = 30
                    async for msg in w:
                        ev = (msg.json() or {}).get("event") if msg.type.name == "TEXT" else None
                        if not ev:
                            continue
                        prev = seen_dt()
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
