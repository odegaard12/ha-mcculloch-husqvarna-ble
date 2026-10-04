"""Modelo 3D del Worx Landroid L (WR155E y hermanos) hecho por código en Blender, y sus renders.

Mismo sistema que rob_model.py (McCulloch): misma cámara, 24 vistas de la vuelta y la base aparte, para que
encaje en la app y en la tarjeta sin tocar nada más. La forma sale de fotos de producto (vistas de arriba,
de lado y de frente): chasis negro con la batería PowerShare detrás, capó naranja en U por delante, ruedas
traseras grandes de tacos con llanta gris de tres radios, ruedas locas delante, mando naranja de la altura
de corte, pantalla con STOP rojo y pestañas rojas del cargador lateral. Medidas ~60 x 45 x 26 cm.

Uso:
  blender -b -P tools/blender/landroid_model.py -- <carpeta_salida> [still|turn|base|all] [marca]
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = Path(argv[0] if argv else "landroid_out").resolve()
MODE = argv[1] if len(argv) > 1 else "still"
BRAND = len(argv) > 2 and argv[2] == "marca"  # rótulos de la marca: solo para uso propio
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene


def mat(name, color, rough, metal=0.0, coat=0.0, emit=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if "Coat Weight" in p.inputs:
        p.inputs["Coat Weight"].default_value = coat
    if emit is not None:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = 2.0
    return m


def srgb(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


M_ORANGE = mat("naranja", srgb("#f38a12"), 0.42, coat=0.25)
M_BLACK = mat("chasis", srgb("#1d1f21"), 0.5, coat=0.1)
M_DECK = mat("cubierta", srgb("#26292c"), 0.62)
M_SKIRT = mat("faldon", srgb("#141516"), 0.8)
M_TIRE = mat("rueda", srgb("#18191a"), 0.85)
M_RIM = mat("llanta", srgb("#c4c7c9"), 0.45)
M_RIM_D = mat("llanta_fondo", srgb("#8d9194"), 0.6)
M_RED = mat("rojo", srgb("#e0262b"), 0.3, coat=0.5)
M_LCD = mat("pantalla", srgb("#0b2a12"), 0.15, emit=srgb("#2bd04a"))
M_GLASS = mat("cristal", srgb("#0a0b0c"), 0.12, coat=0.8)
M_WHITE = mat("rotulo", srgb("#f4f4f2"), 0.4)
M_GREY_TXT = mat("rotulo_gris", srgb("#7c8084"), 0.55)


def sgnpow(v, e):
    return math.copysign(abs(v) ** e, v)


def superellipsoid(name, a, b, c, n1, n2, seg_u=40, seg_v=96, shape=None):
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


def apply_all(ob):
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def boolean(target, cutter, op="DIFFERENCE"):
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation = op
    m.object = cutter
    m.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def cylinder(name, r, depth, loc, rot=(0, 0, 0), verts=64, material=None, smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts)
    ob = bpy.context.object
    ob.name = name
    if material:
        ob.data.materials.append(material)
    if smooth:
        for f in ob.data.polygons:
            f.use_smooth = True
    return ob


def box(name, size, loc, rot=(0, 0, 0), material=None, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.scale = size
    bpy.ops.object.transform_apply(scale=True)
    ob.name = name
    if material:
        ob.data.materials.append(material)
    if bevel:
        bv = ob.modifiers.new("bev", "BEVEL")
        bv.width, bv.segments = bevel, 3
    return ob


def rbox(name, a, b, c, loc, material, n=0.25):
    """Caja de cantos redondeados (superelipsoide) centrada en loc."""
    ob = superellipsoid(name, a, b, c, n, n, seg_u=16, seg_v=48)
    ob.location = loc
    apply_all(ob)
    ob.data.materials.append(material)
    return ob


def joined(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


# ---------- medidas (metros). Delante = -X, detrás (ruedas grandes) = +X ----------
WHEEL_R, WHEEL_W, WHEEL_X = 0.115, 0.058, 0.185
WHEEL_Y = 0.188                     # centro de la rueda: sobresale del chasis, como en la foto de arriba
SHELL_A, SHELL_B, SHELL_X = 0.19, 0.212, -0.115   # capó naranja: de -0.305 a +0.075
SHELL_Z0, SHELL_Z1 = 0.052, 0.168   # canto inferior y superior del capó
DECK_TOP = 0.172                    # cubierta negra (un pelo por encima del capó)

# chasis negro: de punta a punta, entre las ruedas
chassis = superellipsoid("chasis", 0.29, 0.158, 0.075, 0.28, 0.42,
                         shape=lambda x, y, z: (x, y, z * (0.86 if x < 0 else 1.0)))
chassis.location = (0.0, 0, DECK_TOP - 0.075)
apply_all(chassis)
chassis.data.materials.append(M_BLACK)
for side in (1, -1):  # huecos de las ruedas traseras
    boolean(chassis, cylinder("hueco", WHEEL_R + 0.008, 0.07, (WHEEL_X, side * WHEEL_Y, WHEEL_R), rot=(math.pi / 2, 0, 0)))


def shell_shape(x, y, z):
    # en U vista desde arriba: delante redondo, detrás recto y algo más estrecho
    f = max(0.0, min(1.0, x / SHELL_A))
    return x, y * (1 - 0.05 * f), z


shell = superellipsoid("capo", SHELL_A, SHELL_B, (SHELL_Z1 - SHELL_Z0) / 2, 0.42, 0.62, shape=shell_shape)
shell.location = (SHELL_X, 0, (SHELL_Z0 + SHELL_Z1) / 2)
apply_all(shell)
shell.data.materials.append(M_ORANGE)
# la U: se vacía el centro (donde va la cubierta negra) y la parte de atrás queda en dos brazos
hollow = superellipsoid("vaciado", 0.17, 0.158, 0.2, 0.08, 0.5, seg_u=10)
hollow.location = (0.02, 0, SHELL_Z1 + 0.16)
boolean(shell, hollow)
under = box("bajos", (0.7, 0.36, 0.2), (0.0, 0, SHELL_Z0 - 0.07))  # nada por debajo del canto
boolean(shell, under)

# faldón negro con aletas verticales bajo el capó (delante y costados delanteros)
skirt = superellipsoid("faldon", SHELL_A - 0.014, SHELL_B - 0.014, 0.022, 0.15, 0.62, shape=shell_shape)
skirt.location = (SHELL_X, 0, SHELL_Z0 - 0.01)
apply_all(skirt)
skirt.data.materials.append(M_SKIRT)
boolean(skirt, box("corte_faldon", (0.3, 0.6, 0.2), (0.15 + 0.06, 0, 0.05)))  # solo hasta delante de las ruedas
slots = []
for k in range(46):  # ranuras: cajas finas que muerden el canto del faldón, repartidas por la curva
    t = -math.pi * 0.62 + math.pi * 1.24 * k / 45
    px = SHELL_X - math.cos(t) * (SHELL_A - 0.014)
    py = math.sin(t) * (SHELL_B - 0.014)
    slots.append(box("ranura", (0.024, 0.005, 0.034), (px, py, SHELL_Z0 - 0.016), rot=(0, 0, math.pi - t)))  # largo hacia fuera
boolean(skirt, joined(slots, "ranuras"))

# panel negro del costado («CUT TO EDGE»): piel del capó en la zona baja de los costados
for side in (1, -1):
    pane = shell.copy()
    pane.data = shell.data.copy()
    scn.collection.objects.link(pane)
    pane.scale = (1.006, 1.012, 1.0)
    apply_all(pane)
    pane.data.materials.clear()
    pane.data.materials.append(M_BLACK)
    zone = box("zona_panel", (0.2, 0.08, 0.05), (-0.085, side * 0.2, SHELL_Z0 + 0.022))
    boolean(pane, zone, "INTERSECT")

# cubierta superior (dentro de la U) y bloque trasero más alto con la batería PowerShare
deck = rbox("cubierta", 0.165, 0.152, 0.008, (0.0, 0, DECK_TOP - 0.004), M_DECK, n=0.22)
rear = rbox("trasera", 0.115, 0.158, 0.03, (0.175, 0, DECK_TOP + 0.004), M_BLACK, n=0.3)
battery = rbox("bateria", 0.082, 0.072, 0.016, (0.185, 0, DECK_TOP + 0.034), M_BLACK, n=0.18)
grip = rbox("asa", 0.022, 0.05, 0.006, (0.245, 0, DECK_TOP + 0.05), M_SKIRT, n=0.2)
for k in range(5):  # nervios de la batería
    box("nervio", (0.07, 0.004, 0.004), (0.155, -0.04 + k * 0.02, DECK_TOP + 0.05), material=M_SKIRT)

# mando naranja de la altura de corte, con su asa
knob_x, knob_y = -0.035, 0.055
cylinder("aro_mando", 0.05, 0.008, (knob_x, knob_y, DECK_TOP + 0.002), material=M_BLACK, verts=96)
cylinder("mando", 0.042, 0.022, (knob_x, knob_y, DECK_TOP + 0.012), material=M_ORANGE, verts=96)
box("asa_mando", (0.07, 0.014, 0.012), (knob_x, knob_y, DECK_TOP + 0.027), material=M_ORANGE, bevel=0.004)

# consola: pantalla verde, teclas y STOP rojo
con_x, con_y = -0.05, -0.062
rbox("consola", 0.05, 0.042, 0.007, (con_x, con_y, DECK_TOP + 0.004), M_GLASS, n=0.2)
box("lcd", (0.028, 0.05, 0.002), (con_x - 0.02, con_y, DECK_TOP + 0.011), material=M_LCD)
for i in range(2):
    for j in range(3):
        box("tecla", (0.01, 0.01, 0.002), (con_x + 0.008 + i * 0.016, con_y - 0.018 + j * 0.018, DECK_TOP + 0.011), material=M_GREY_TXT)
rbox("stop", 0.015, 0.032, 0.007, (con_x + 0.068, con_y, DECK_TOP + 0.01), M_RED, n=0.3)

# cargador lateral: pestañas rojas en el costado izquierdo de la cubierta
for dx in (-0.025, 0.025):
    rbox("pestana", 0.016, 0.006, 0.011, (-0.035 + dx, -0.166, DECK_TOP - 0.014), M_RED, n=0.3)
rbox("soporte_pestanas", 0.045, 0.008, 0.016, (-0.035, -0.158, DECK_TOP - 0.014), M_BLACK, n=0.3)


def lug_ring(cx, cy, cz, r, w, n, h, wd, material):
    """Tacos de la rueda: bloques a lo ancho, alternando un pelo de lado (como el dibujo real)."""
    parts = []
    for k in range(n):
        ang = 2 * math.pi * k / n
        off = (0.004 if k % 2 else -0.004)
        parts.append(box("taco", (wd, w * 0.92, h), (cx + math.cos(ang) * (r + h / 2 - 0.001), cy + off,
                                                     cz + math.sin(ang) * (r + h / 2 - 0.001)),
                         rot=(0, -ang + math.pi / 2, 0)))
    ob = joined(parts, "tacos")
    ob.data.materials.append(material)
    return ob


def wheel(side):
    y = side * WHEEL_Y
    parts = []
    core = WHEEL_R - 0.013
    tire = cylinder("neumatico", core, WHEEL_W, (WHEEL_X, y, WHEEL_R), rot=(math.pi / 2, 0, 0), verts=96, material=M_TIRE)
    bev = tire.modifiers.new("bev", "BEVEL")
    bev.width, bev.segments = 0.01, 4
    parts.append(tire)
    parts.append(lug_ring(WHEEL_X, y, WHEEL_R, core, WHEEL_W, 40, 0.014, 0.011, M_TIRE))
    face = y + side * WHEEL_W / 2
    # llanta gris: fondo algo más oscuro, aro, tres radios anchos y tapa central (lo claro sobresale)
    parts.append(cylinder("llanta_fondo", 0.079, 0.004, (WHEEL_X, face, WHEEL_R), rot=(math.pi / 2, 0, 0), verts=96, material=M_RIM_D))
    ring = cylinder("llanta_aro", 0.081, 0.006, (WHEEL_X, face + side * 0.002, WHEEL_R), rot=(math.pi / 2, 0, 0), verts=96, material=M_RIM)
    boolean(ring, cylinder("hueco_aro", 0.067, 0.02, (WHEEL_X, face, WHEEL_R), rot=(math.pi / 2, 0, 0), verts=96))
    parts.append(ring)
    for k in range(3):
        a = 2 * math.pi * k / 3 + math.pi / 2
        parts.append(box("radio", (0.05, 0.006, 0.02), (WHEEL_X + math.cos(a) * 0.05, face + side * 0.002, WHEEL_R + math.sin(a) * 0.05),
                         rot=(0, -a, 0), material=M_RIM, bevel=0.004))
    parts.append(cylinder("tapa", 0.042, 0.008, (WHEEL_X, face + side * 0.003, WHEEL_R), rot=(math.pi / 2, 0, 0), verts=96, material=M_RIM))
    parts.append(cylinder("tapa_centro", 0.03, 0.009, (WHEEL_X, face + side * 0.0035, WHEEL_R), rot=(math.pi / 2, 0, 0), verts=96, material=M_RIM_D))
    axle = bpy.data.objects.new(f"eje_{'izq' if side > 0 else 'der'}", None)
    axle.location = (WHEEL_X, y, WHEEL_R)
    scn.collection.objects.link(axle)
    bpy.context.view_layer.update()
    for p in parts:
        mw = p.matrix_world.copy()
        p.parent = axle
        p.matrix_world = mw
    return axle


axles = [wheel(1), wheel(-1)]
for side in (1, -1):  # ruedas locas delanteras, asomando bajo el faldón
    cylinder("rueda_loca", 0.034, 0.03, (-0.215, side * 0.105, 0.034), rot=(math.pi / 2, 0, 0), material=M_TIRE)
    cylinder("buje_loca", 0.018, 0.032, (-0.215, side * 0.105, 0.034), rot=(math.pi / 2, 0, 0), material=M_RIM_D)


def label(text, loc, rot, size, material, depth=0.0008):
    bpy.ops.object.text_add(location=loc, rotation=rot)
    ob = bpy.context.object
    ob.data.body = text
    ob.data.size = size
    ob.data.extrude = depth
    ob.data.align_x = "CENTER"
    ob.data.align_y = "CENTER"
    try:
        ob.data.body_format[0].use_bold = True
    except (IndexError, AttributeError):
        pass
    ob.data.materials.append(material)
    return ob


if BRAND:
    top = SHELL_Z1 + 0.0008
    label("LANDROID", (-0.255, 0, top), (0, 0, -math.pi / 2), 0.034, M_WHITE)
    label("WORX", (-0.06, 0.168, top), (0, 0, math.pi), 0.022, M_WHITE)
    for side in (1, -1):
        label("CUT TO EDGE", (-0.085, side * 0.214, SHELL_Z0 + 0.022), (math.pi / 2, 0, 0 if side < 0 else math.pi), 0.018, M_GREY_TXT, depth=0.001)
    label("POWERSHARE", (0.185, 0, DECK_TOP + 0.051), (0, 0, -math.pi / 2), 0.012, M_ORANGE)


def build_base():
    """Base de carga del Landroid: placa con rampa y capucha delantera negra donde entra el morro."""
    objs = []
    plate = superellipsoid("base_placa", 0.34, 0.26, 0.011, 0.3, 0.5, seg_u=12)
    plate.location = (-0.04, 0, 0.011)
    plate.data.materials.append(M_SKIRT)
    objs.append(plate)
    hood = superellipsoid("base_capucha", 0.075, 0.2, 0.095, 0.45, 0.5)
    hood.location = (-0.36, 0, 0.1)
    hood.data.materials.append(M_BLACK)
    objs.append(hood)
    trim = superellipsoid("base_franja", 0.077, 0.202, 0.008, 0.3, 0.5, seg_u=10)
    trim.location = (-0.36, 0, 0.15)
    trim.data.materials.append(M_ORANGE)
    objs.append(trim)
    led = cylinder("base_led", 0.008, 0.01, (-0.284, 0, 0.165), rot=(0, math.pi / 2, 0), material=mat("led", srgb("#2fd06a"), 0.2))
    objs.append(led)
    return objs


BASE_OBJS = build_base() if MODE in ("base", "all") else []
for _o in BASE_OBJS:
    _o.hide_render = True

root = bpy.data.objects.new("robot", None)
scn.collection.objects.link(root)
bpy.context.view_layer.update()
for ob in list(scn.objects):
    if ob is not root and ob.parent is None and ob not in BASE_OBJS:
        mw = ob.matrix_world.copy()
        ob.parent = root
        ob.matrix_world = mw

# ---------- luz, cámara y render: idénticos al McCulloch para que encajen igual en la web ----------
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


area("principal", (1.0, -1.2, 1.4), 42, 1.2)
area("relleno", (-1.4, -0.6, 0.7), 14, 1.5, (0.85, 0.9, 1.0))
area("contra", (-0.6, 1.4, 1.0), 40, 1.0)
area("cenital", (0, 0, 2.0), 12, 2.0)

bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
bpy.context.object.is_shadow_catcher = True

cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 70
cam = bpy.data.objects.new("cam", cam_d)
scn.collection.objects.link(cam)
scn.camera = cam


def aim(loc, target=(0.0, 0.0, 0.10)):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


scn.render.engine = "CYCLES"
scn.cycles.samples = 40
scn.cycles.use_denoising = True
try:
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


aim((-1.05, -1.25, 0.72))  # tres cuartos desde delante-izquierda, como la foto de producto
if MODE in ("still", "all"):
    shot(OUT / "still_34.png")
if MODE in ("turn", "all"):
    scn.render.resolution_x, scn.render.resolution_y = 640, 450
    scn.cycles.samples = 48
    aim((0.15, -1.9, 0.55))
    for k in range(24):
        root.rotation_euler = (0, 0, 2 * math.pi * k / 24)
        shot(OUT / f"turn_{k:02d}.png")
    root.rotation_euler = (0, 0, 0)
if MODE in ("base", "all"):
    scn.render.resolution_x, scn.render.resolution_y = 640, 450
    scn.cycles.samples = 48
    aim((0.15, -1.9, 0.55))
    for ob in root.children_recursive:
        ob.hide_render = True
    for ob in BASE_OBJS:
        ob.hide_render = False
    shot(OUT / "base_side.png")
    for ob in root.children_recursive:
        ob.hide_render = False
    for ob in BASE_OBJS:
        ob.hide_render = True

bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "landroid.blend"))
bpy.ops.export_scene.gltf(filepath=str(OUT / "landroid.glb"), export_format="GLB", use_selection=False)
print("RENDER_OK", OUT)
