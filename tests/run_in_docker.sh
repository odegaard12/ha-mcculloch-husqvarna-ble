#!/bin/sh
# Ejecuta los tests dentro de python:3.14 con Home Assistant (HA no corre en Windows).
set -e
cd /w
python - > /w/req.txt <<'EOF'
import json, os, homeassistant
base = os.path.dirname(homeassistant.__file__) + "/components/"
for comp in ("bluetooth", "usb", "bluetooth_adapters", "diagnostics", "http"):
    for req in json.load(open(base + comp + "/manifest.json")).get("requirements", []):
        print(req)
EOF
uv pip install --system -q -r /w/req.txt > /w/install2.log 2>&1 || true
python -m pytest -q -p no:cacheprovider > /w/pytest.log 2>&1 || true
echo done > /w/finished
