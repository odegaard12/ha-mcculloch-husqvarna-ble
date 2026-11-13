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


def _plano(d, p=""):
    out = {}
    for k, v in d.items():
        out.update(_plano(v, f"{p}{k}.") if isinstance(v, dict) else {f"{p}{k}": v})
    return out


def test_traducciones_mismas_claves_e_ingles_limpio():
    """es.json, en.json y strings.json tienen exactamente las mismas claves, y el inglés de la configuración y de los
    servicios es el de strings.json (llegó a quedar a medias en español: «Emparejar», «Comando», «Parámetros»...)."""
    leer = lambda f: _plano(json.loads((CC / f).read_text(encoding="utf-8")))  # noqa: E731
    es, en, st = leer("translations/es.json"), leer("translations/en.json"), leer("strings.json")
    assert set(es) == set(en) == set(st), (set(es) ^ set(en), set(en) ^ set(st))
    for k in en:
        if k.startswith(("config.", "services.")):
            assert en[k] == st[k], k


def test_avisos_informativos_no_son_averia():
    """Ajustes restaurados, calibración hecha, cambio de conexión...: el robot los guarda como «error» pero no encienden
    «Avería» (ni la tarjeta en rojo ni un aviso al móvil)."""
    from custom_components.mcculloch_rob.binary_sensor import BINARY, INFORMATIVE

    assert {ErrorCodes(c).name for c in INFORMATIVE} == {
        "SETTINGS_RESTORED", "GUIDE_CALIBRATION_ACCOMPLISHED", "CONNECTION_CHANGED", "CONNECTION_NOT_CHANGED",
        "CONNECTIVITY_SETTINGS_RESTORED"}
    problem = next(b for b in BINARY if b.key == "problem").value_fn
    assert problem({"GetError": 0}) is False and problem({}) is None
    assert all(problem({"GetError": c}) is False for c in INFORMATIVE)
    assert problem({"GetError": ErrorCodes.WHEEL_MOTOR_BLOCKED_LEFT.value}) is True and problem({"GetError": 2}) is True


def test_texto():
    assert texto("wheel_motor_blocked_rear_left") == "Motor de la rueda trasera izquierda bloqueado"
    assert texto("desconocido_999") == "Error desconocido (código 999)"
    assert texto(None) is None
