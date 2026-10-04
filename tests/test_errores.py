"""Todas las averías del robot tienen texto en español: en la integración, en las traducciones de HA y en la tabla
que leen el panel y la tarjeta (si alguien añade un código y no lo traduce, falla aquí y no en el jardín)."""
import json
from pathlib import Path

from custom_components.mcculloch_rob.automower_ble.error_codes import ErrorCodes
from custom_components.mcculloch_rob.errores import ERRORES_ES, texto

CC = Path(__file__).resolve().parent.parent / "custom_components" / "mcculloch_rob"


def test_todos_los_codigos_traducidos():
    falta = [c.name.lower() for c in ErrorCodes if c.name.lower() not in ERRORES_ES]
    assert not falta, falta


def test_traducciones_de_ha_y_tabla_web_al_dia():
    es = json.loads((CC / "translations" / "es.json").read_text(encoding="utf-8"))
    assert es["entity"]["sensor"]["error"]["state"] == ERRORES_ES
    web = json.loads((CC / "www" / "errores_es.json").read_text(encoding="utf-8"))
    assert web["mcculloch"] == ERRORES_ES and "wheel_motor_blocked" in web["landroid"]


def test_texto():
    assert texto("wheel_motor_blocked_rear_left") == "Motor de la rueda trasera izquierda bloqueado"
    assert texto("desconocido_999") == "Error desconocido (código 999)"
    assert texto(None) is None
