#!/bin/sh
# Como complemento, las opciones vienen en /data/options.json; en Docker suelto, por variables de entorno.
if [ -f /data/options.json ]; then
  ROBOT_PREFIX=$(/usr/bin/python3 -c "import json; print(json.load(open('/data/options.json')).get('robot_prefix', 'robot_cortacesped'))")
  export ROBOT_PREFIX
fi
exec /usr/bin/python3 /app/server.py
