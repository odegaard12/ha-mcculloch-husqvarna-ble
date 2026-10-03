"""Modelo 3D del McCulloch ROB S600/S800 hecho por código en Blender, y sus renders.

No hay modelo descargable del robot: la forma sale de la foto de referencia y de las medidas de la ficha
(54 x 39 x 21 cm, ruedas traseras de ~19 cm). Sin logotipos ni textos de la marca.

Uso:
  blender -b -P tools/blender/rob_model.py -- <carpeta_salida> [still|turn|all]
Genera:
  rob.blend, rob.glb            el modelo
  still_34.png                  vista tres cuartos como la foto (fondo transparente)
  turn_XX.png                   vuelta completa en 24 pasos (para el giro en la web)
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = Path(argv[0] if argv else "rob_out").resolve()
MODE = argv[1] if len(argv) > 1 else "still"
OUT.mkdir(parents=True, exist_ok=True)

# ---------- escena limpia ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene


def mat(name, color, rough, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if "Coat Weight" in p.inputs:
        p.inputs["Coat Weight"].default_value = coat
    return m


def srgb(h):
    """#rrggbb -> lineal (Blender trabaja en lineal)."""
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


M_BODY = mat("carcasa", srgb("#2a2c2e"), 0.62)          # gris casi negro, mate
M_LID = mat("tapa", srgb("#0d0e0f"), 0.24, coat=0.7)    # negro brillante (más pulido quema el reflejo)
M_YEL = mat("amarillo", srgb("#ffb400"), 0.32, coat=0.6)
M_TIRE = mat("rueda", srgb("#1a1b1c"), 0.85)
M_RIM = mat("llanta", srgb("#232527"), 0.45)
M_RED = mat("boton", srgb("#d8371c"), 0.3, coat=0.5)
M_DARK = mat("bajos", srgb("#121314"), 0.9)


def sgnpow(v, e):
    return math.copysign(abs(v) ** e, v)


def superellipsoid(name, a, b, c, n1, n2, seg_u=48, seg_v=96, shape=None):
    """Superelipsoide (caja redondeada lisa). shape(x, y, z) -> (x, y, z) deforma cada vértice."""
    bm = bmesh.new()
    rows = []
    for i in range(seg_u + 1):
        u = -math.pi / 2 + math.pi * i / seg_u
        row = []
        for j in range(seg_v):
            v = -math.pi + 2 * math.pi * j / seg_v
            x = a * sgnpow(math.cos(u), n1) * sgnpow(math.cos(v), n2)
            y = b * sgnpow(math.cos(u), n1) * sgnpow(math.sin(v), n2)
            z = c * sgnpow(math.sin(u), n1)
            if shape:
                x, y, z = shape(x, y, z)
            row.append(bm.verts.new((x, y, z)))
        rows.append(row)
    for i in range(seg_u):
        for j in range(seg_v):
            a1, a2 = rows[i][j], rows[i][(j + 1) % seg_v]
            b1, b2 = rows[i + 1][j], rows[i + 1][(j + 1) % seg_v]
            try:
                bm.faces.new((a1, a2, b2, b1))
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    scn.collection.objects.link(ob)
    for f in me.polygons:
        f.use_smooth = True
    return ob


def boolean(target, cutter, op="DIFFERENCE"):
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation = op
    m.object = cutter
    m.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def cylinder(name, r, depth, loc, rot=(0, 0, 0), verts=64):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts)
    ob = bpy.context.object
    ob.name = name
    return ob


def box(name, size, loc, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.scale = size
    bpy.ops.object.transform_apply(scale=True)
    ob.name = name
    return ob


# ---------- medidas (metros). Delante = -X, detrás (ruedas grandes) = +X ----------
L, W, H = 0.54, 0.39, 0.21
WHEEL_R, WHEEL_W = 0.097, 0.052
WHEEL_X = 0.12
CLEAR = 0.035  # altura de los bajos


def body_shape(x, y, z):
    f = max(0.0, min(1.0, -x / (L / 2)))          # 0 detrás .. 1 delante
    y *= 1 - 0.16 * f                              # más estrecho delante
    if z > 0:
        z *= 1 - 0.30 * f ** 1.4                   # morro más bajo
    else:
        z *= 0.28                                  # bajos casi planos
    return x, y, z


# laterales casi verticales con canto redondeado arriba (n1 bajo) y planta redondeada (n2)
body = superellipsoid("carcasa", L / 2, W / 2, H * 0.62, 0.5, 0.55, shape=body_shape)
body.location = (0, 0, CLEAR + H * 0.62 * 0.28)
bpy.context.view_layer.objects.active = body
body.select_set(True)
bpy.ops.object.transform_apply(location=True)
body.data.materials.append(M_BODY)

# huecos de las ruedas traseras
for side in (1, -1):
    cut = cylinder("hueco", WHEEL_R + 0.010, 0.10, (WHEEL_X, side * (W / 2 + 0.01), WHEEL_R), rot=(math.pi / 2, 0, 0))
    boolean(body, cut)
TOP = CLEAR + H * 0.62 * 0.28 + H * 0.62


def footprint(name, a, b, x):
    """Prisma vertical con planta de óvalo-rectángulo: recorta una zona de la carcasa vista desde arriba."""
    pr = superellipsoid(name, a, b, 0.4, 0.05, 0.6, seg_u=12,
                        shape=lambda px, py, pz: (px, py * (1 - 0.12 * max(0.0, min(1.0, -px / a))), pz))
    # el prisma empieza 4,5 cm por debajo de lo alto: así la piel queda solo arriba, no baja por los costados
    pr.location = (x, 0, TOP + 0.4 - 0.045)
    return pr


def skin(name, grow, material, outer, inner=None):
    """Piel pegada a la carcasa: copia algo mayor de la carcasa ∩ planta (− otra planta). Sigue su curva."""
    sk = body.copy()
    sk.data = body.data.copy()
    sk.name = name
    scn.collection.objects.link(sk)
    sk.scale = (1 + grow, 1 + grow, 1 + grow * 1.6)
    bpy.context.view_layer.objects.active = sk
    bpy.ops.object.select_all(action="DESELECT")
    sk.select_set(True)
    bpy.ops.object.transform_apply(scale=True)
    sk.data.materials.clear()
    sk.data.materials.append(material)
    boolean(sk, outer, "INTERSECT")
    if inner is not None:
        boolean(sk, inner, "DIFFERENCE")
    return sk


# aro amarillo embutido (detrás y a los lados de la tapa) y tapa negra brillante algo más alta
ring = skin("aro", 0.010, M_YEL, footprint("planta_aro", 0.215, 0.168, 0.05), footprint("planta_hueco", 0.172, 0.126, 0.035))
lid = skin("tapa", 0.020, M_LID, footprint("planta_tapa", 0.172, 0.126, 0.035))
# botón rojo de parada, delante de la tapa
btn = cylinder("boton", 0.022, 0.03, (-0.165, 0, TOP - 0.025))
btn.data.materials.append(M_RED)
for f in btn.data.polygons:
    f.use_smooth = True


def wheel(side):
    y = side * (W / 2 - 0.05)  # metida en la carcasa, enrasada con el costado
    parts = []
    tire = cylinder("neumatico", WHEEL_R, WHEEL_W, (WHEEL_X, y, WHEEL_R), rot=(math.pi / 2, 0, 0), verts=96)
    bev = tire.modifiers.new("bev", "BEVEL")
    bev.width, bev.segments = 0.008, 4
    tire.data.materials.append(M_TIRE)
    for f in tire.data.polygons:
        f.use_smooth = True
    parts.append(tire)
    # tacos del neumático
    for k in range(40):
        ang = 2 * math.pi * k / 40
        t = box("taco", (0.007, WHEEL_W * 0.8, 0.004),
                (WHEEL_X + math.cos(ang) * WHEEL_R, y, WHEEL_R + math.sin(ang) * WHEEL_R), rot=(0, -ang + math.pi / 2, 0))
        t.data.materials.append(M_TIRE)
        parts.append(t)
    face = y + side * WHEEL_W / 2
    rim = cylinder("llanta", WHEEL_R * 0.78, 0.006, (WHEEL_X, face, WHEEL_R), rot=(math.pi / 2, 0, 0))
    rim.data.materials.append(M_RIM)
    parts.append(rim)
    # cinco radios amarillos
    for k in range(5):
        ang = 2 * math.pi * k / 5 + 0.3
        r0 = WHEEL_R * 0.45
        sp = box("radio", (0.010, 0.006, WHEEL_R * 0.34),
                 (WHEEL_X + math.cos(ang) * r0, face + side * 0.004, WHEEL_R + math.sin(ang) * r0), rot=(0, -ang + math.pi / 2, 0))
        sp.data.materials.append(M_YEL)
        parts.append(sp)
    hub = cylinder("buje", WHEEL_R * 0.2, 0.012, (WHEEL_X, face + side * 0.004, WHEEL_R), rot=(math.pi / 2, 0, 0))
    hub.data.materials.append(M_LID)
    parts.append(hub)
    # agrupa la rueda bajo un vacío en su eje: así se puede girar para animar
    axle = bpy.data.objects.new(f"eje_{'izq' if side > 0 else 'der'}", None)
    axle.location = (WHEEL_X, y, WHEEL_R)
    scn.collection.objects.link(axle)
    bpy.context.view_layer.update()  # sin esto el vacío aún no tiene su matriz y la rueda se desplaza
    for p in parts:
        mw = p.matrix_world.copy()
        p.parent = axle
        p.matrix_world = mw
    return axle


axles = [wheel(1), wheel(-1)]
caster = cylinder("rueda_delantera", 0.03, 0.025, (-0.19, 0, 0.03), rot=(math.pi / 2, 0, 0))
caster.data.materials.append(M_TIRE)

def build_base():
    """Base de carga genérica (no hay fotos de la real): placa baja y torre delantera donde entra el morro."""
    objs = []
    plate = superellipsoid("base_placa", 0.33, 0.25, 0.012, 0.3, 0.5, seg_u=12)
    plate.location = (-0.03, 0, 0.012)
    plate.data.materials.append(M_DARK)
    objs.append(plate)
    tower = superellipsoid("base_torre", 0.055, 0.17, 0.075, 0.5, 0.5)
    tower.location = (-0.33, 0, 0.085)
    tower.data.materials.append(M_BODY)
    objs.append(tower)
    stripe = superellipsoid("base_franja", 0.057, 0.172, 0.010, 0.3, 0.5, seg_u=10)
    stripe.location = (-0.33, 0, 0.125)
    stripe.data.materials.append(M_YEL)
    objs.append(stripe)
    led = cylinder("base_led", 0.008, 0.01, (-0.275, 0, 0.12), rot=(0, math.pi / 2, 0))
    led.data.materials.append(mat("led", srgb("#2fd06a"), 0.2))
    objs.append(led)
    return objs


BASE_OBJS = build_base() if MODE in ("base", "all") else []

# todo el robot cuelga de un vacío: girarlo es girar el robot
root = bpy.data.objects.new("robot", None)
scn.collection.objects.link(root)
bpy.context.view_layer.update()
for ob in list(scn.objects):
    if ob is not root and ob.parent is None and ob not in BASE_OBJS:
        mw = ob.matrix_world.copy()
        ob.parent = root
        ob.matrix_world = mw

# ---------- luz de estudio y cámara ----------
world = bpy.data.worlds.new("mundo")
scn.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.05, 0.055, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25


def area(name, loc, energy, size, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.size, d.color = energy, size, color
    o = bpy.data.objects.new(name, d)
    o.location = loc
    scn.collection.objects.link(o)
    o.rotation_euler = (Vector((0, 0, 0.1)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


# (con más potencia el negro y el amarillo salen lavados)
area("principal", (1.0, -1.2, 1.4), 45, 1.2)
area("relleno", (-1.4, -0.6, 0.7), 14, 1.5, (0.85, 0.9, 1.0))
area("contra", (-0.6, 1.4, 1.0), 40, 1.0)
area("cenital", (0, 0, 2.0), 12, 2.0)

# suelo que solo recoge sombra (en la web el césped va debajo)
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
floor = bpy.context.object
floor.is_shadow_catcher = True

cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 70
cam = bpy.data.objects.new("cam", cam_d)
scn.collection.objects.link(cam)
scn.camera = cam


def aim(loc, target=(0.0, 0.0, 0.10)):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


# ---------- render ----------
scn.render.engine = "CYCLES"
scn.cycles.samples = 40  # con el eliminador de ruido basta; en CPU cada vista tarda menos de un minuto
scn.cycles.use_denoising = True
try:  # GPU si hay; si no, CPU
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(d.type != "CPU" for d in prefs.devices):
                for d in prefs.devices:
                    d.use = True
                scn.cycles.device = "GPU"
                break
        except TypeError:
            continue
except Exception:  # noqa: BLE001
    pass
scn.render.film_transparent = True
scn.render.resolution_x, scn.render.resolution_y = 960, 675
scn.render.image_settings.file_format = "PNG"
scn.render.image_settings.color_mode = "RGBA"
scn.view_settings.view_transform = "AgX"


def shot(path):
    scn.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


# vista como la foto: desde atrás-derecha, algo elevada (la foto mira el lado de la rueda y la trasera)
aim((1.05, -1.25, 0.62))
if MODE in ("still", "all"):
    shot(OUT / "still_34.png")
if MODE in ("turn", "all"):
    # vista lateral (morro a la izquierda) y vuelta completa en 24 pasos
    scn.render.resolution_x, scn.render.resolution_y = 640, 450
    scn.cycles.samples = 48
    aim((0.15, -1.9, 0.55))
    for k in range(24):
        root.rotation_euler = (0, 0, 2 * math.pi * k / 24)
        shot(OUT / f"turn_{k:02d}.png")
    root.rotation_euler = (0, 0, 0)
if MODE in ("base", "all"):
    # la base sola, desde la misma cámara lateral que la vuelta (en la web el robot se pone encima)
    scn.render.resolution_x, scn.render.resolution_y = 640, 450
    scn.cycles.samples = 48
    aim((0.15, -1.9, 0.55))
    for ob in root.children_recursive:
        ob.hide_render = True
    shot(OUT / "base_side.png")
    for ob in root.children_recursive:
        ob.hide_render = False

bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "rob.blend"))
bpy.ops.export_scene.gltf(filepath=str(OUT / "rob.glb"), export_format="GLB", use_selection=False)
print("RENDER_OK", OUT)
