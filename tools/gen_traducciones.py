"""Genera, desde custom_components/mcculloch_rob/errores.py, los textos de estados y averías:

- strings.json y translations/{es,en}.json: entity.sensor.<clave>.state (HA los muestra traducidos)
- www/errores_es.json (tarjeta) y ha_app/robot/errores_es.json (panel web)

Uso: python tools/gen_traducciones.py
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "mcculloch_rob"
spec = importlib.util.spec_from_file_location("errores", CC / "errores.py")
err = importlib.util.module_from_spec(spec)
spec.loader.exec_module(err)

STATE_ES = {"off": "Apagado", "wait_for_safetypin": "Esperando PIN", "stopped": "Parado", "fatal_error": "Error grave",
            "pending_start": "Arrancando", "paused": "En pausa", "in_operation": "Trabajando", "restricted": "En espera",
            "error": "Error"}
ACTIVITY_ES = {"none": "Sin actividad", "charging": "Cargando", "going_out": "Saliendo de la base", "mowing": "Cortando el césped",
               "going_home": "Volviendo a la base", "parked": "Aparcado en la base", "stopped_in_garden": "Parado en el jardín"}
MODE_ES = {"auto": "Automático", "manual": "Manual", "home": "Aparcado siempre", "demo": "Demo", "poi": "Punto de interés"}


def human(code: str) -> str:
    return code.replace("_", " ").capitalize()


def states(lang: str) -> dict:
    tr = (lambda d: d) if lang == "es" else (lambda d: {k: human(k) for k in d})
    errs = tr(err.ERRORES_ES)
    if lang != "es":
        errs["ninguno"] = "No messages"
    return {
        "state": {"state": tr(STATE_ES)},
        "activity": {"state": tr(ACTIVITY_ES)},
        "mode": {"state": tr(MODE_ES)},
        "error": {"state": errs},
        "last_message": {"state": errs},
    }


for path, lang in ((CC / "strings.json", "es"), (CC / "translations" / "es.json", "es"), (CC / "translations" / "en.json", "en")):
    data = json.loads(path.read_text(encoding="utf-8"))
    sensors = data.setdefault("entity", {}).setdefault("sensor", {})
    for key, block in states(lang).items():
        sensors.setdefault(key, {}).update(block)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("ok", path.relative_to(ROOT))

table = {"mcculloch": err.ERRORES_ES, "landroid": err.LANDROID_ES}
for dst in (CC / "www" / "errores_es.json", ROOT / "ha_app" / "robot" / "errores_es.json"):
    dst.write_text(json.dumps(table, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    print("ok", dst.relative_to(ROOT))
