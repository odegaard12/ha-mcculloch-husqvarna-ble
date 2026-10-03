"""Pasa los renders de Blender a la web: mismo recorte para todos (así la base y el robot siguen encajando),
tamaño razonable y WebP con transparencia.

Uso: python tools/blender/to_web.py
Lee tools/blender/out/turn_*.png y base_side.png; escribe ha_app/robot/rob3d/ y la copia de la tarjeta.
"""
import shutil
from pathlib import Path

from PIL import Image, ImageChops

HERE = Path(__file__).resolve().parent
SRC = HERE / "out"
DST = HERE.parents[1] / "ha_app" / "robot" / "rob3d"
CARD = HERE.parents[1] / "custom_components" / "mcculloch_rob" / "www" / "rob3d"
WIDTH = 520  # px del recorte final (suficiente para pantallas 2x en el panel)

files = sorted(SRC.glob("turn_*.png")) + ([SRC / "base_side.png"] if (SRC / "base_side.png").exists() else [])
assert len([f for f in files if f.name.startswith("turn_")]) == 24, "faltan vistas de la vuelta"
ims = {f.name: Image.open(f).convert("RGBA") for f in files}

# recuadro común: la unión de lo que no es transparente en todas las imágenes, con un margen
box = None
for im in ims.values():
    # la sombra del suelo es casi transparente pero llega lejos: solo cuenta lo bastante opaco
    b = im.getchannel("A").point(lambda a: 255 if a > 70 else 0).getbbox()
    if b:
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
pad = 12
w0, h0 = next(iter(ims.values())).size
box = (max(0, box[0] - pad), max(0, box[1] - pad), min(w0, box[2] + pad), min(h0, box[3] + pad))

DST.mkdir(parents=True, exist_ok=True)
total = 0
for name, im in ims.items():
    c = im.crop(box)
    c = c.resize((WIDTH, round(c.height * WIDTH / c.width)), Image.LANCZOS)
    # el recorte corta la sombra suave del suelo: se difumina el borde para que no se vea un rectángulo
    fade = Image.new("L", c.size, 255)
    px = fade.load()
    m = 28
    for x in range(c.width):
        for y in range(c.height):
            d = min(x, y, c.width - 1 - x, c.height - 1 - y)
            if d < m:
                px[x, y] = int(255 * d / m)
    c.putalpha(ImageChops.multiply(c.getchannel("A"), fade))
    out = DST / name.replace(".png", ".webp")
    c.save(out, "WEBP", quality=82, method=4)  # method=6 tarda ~17 s por imagen y apenas ahorra
    total += out.stat().st_size
if CARD.parent.exists():
    shutil.rmtree(CARD, ignore_errors=True)
    shutil.copytree(DST, CARD)
print(f"ok: {len(ims)} imágenes, recorte {box}, {total // 1024} KB en total")
