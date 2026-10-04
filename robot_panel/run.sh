#!/bin/sh
# Como complemento, las opciones vienen en /data/options.json; en Docker suelto, por variables de entorno.
if [ -f /data/options.json ]; then
  ROBOT_PREFIX=$(/usr/bin/python3 -c "import json; print(json.load(open('/data/options.json')).get('robot_prefix', 'robot_cortacesped'))")
  # más robots en la misma app, p. ej. landroid:Landroid:landroid (prefijo:nombre:tipo)
  ROBOTS=$(/usr/bin/python3 -c "import json; print(json.load(open('/data/options.json')).get('robots') or '')")
  export ROBOT_PREFIX ROBOTS
fi
# claves (sesión y avisos push) y suscripciones en /data: lo único que sobrevive a actualizar el complemento
if [ -d /data ]; then
  [ -s /data/.app_secret ] || /usr/bin/python3 -c "import secrets; open('/data/.app_secret', 'w').write(secrets.token_hex(32))"
  [ -s /data/vapid_private.pem ] || /usr/bin/python3 -c "from py_vapid import Vapid01; v = Vapid01(); v.generate_keys(); v.save_key('/data/vapid_private.pem')"
  [ -e /data/push_subs.json ] || echo '[]' > /data/push_subs.json
  [ -e /data/push_state.json ] || echo '{}' > /data/push_state.json
  [ -e /data/robots_cfg.json ] || echo '{}' > /data/robots_cfg.json   # nombre y contraseña de cada robot
  for f in .app_secret vapid_private.pem push_subs.json push_state.json robots_cfg.json; do ln -sf /data/$f /app/$f; done
fi
exec /usr/bin/python3 /app/server.py
