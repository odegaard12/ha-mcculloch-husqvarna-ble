"""Icono de la app «Mi robot»: un cortacésped robot GENÉRICO (diseño propio, sin marca ni colores de McCulloch/Worx).

Perla con cristal oscuro y un aro de luz verde; render con sombra real sobre fondo transparente.
Uso: blender -b -P tools/blender/icono_app.py -- <salida.png> [azul|verde|grafito]
"""
import math
import sys
from pathlib import Path

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = Path(argv[0] if argv else "icono.png").resolve()
ACCENT = {"verde": (0.18, 1.0, 0.45), "azul": (0.25, 0.7, 1.0), "grafito": (0.4, 1.0, 0.3)}[argv[1] if len(argv) > 1 else "verde"]

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene


def mat(name, color, rough, metal=0.0, coat=0.0, emit=None, strength=6.0):
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
        p.inputs["Emission Strength"].default_value = strength
    return m


M_PEARL = mat("perla", (0.92, 0.93, 0.94), 0.28, coat=0.6)
M_GLASS = mat("cristal", (0.012, 0.016, 0.02), 0.06, coat=1.0)
M_DARK = mat("base", (0.02, 0.022, 0.026), 0.55)
M_TIRE = mat("rueda", (0.012, 0.012, 0.014), 0.9)
M_HUB = mat("buje", (0.55, 0.58, 0.6), 0.35, metal=0.8)
M_LED = mat("luz", ACCENT, 0.3, emit=ACCENT, strength=3.5)
M_GROUND = mat("suelo", (1, 1, 1), 1.0)


def obj(ob, m, name):
    ob.name = name
    ob.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    return ob


def ellipsoid(name, m, loc, scale, seg=96):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, location=loc)
    ob = bpy.context.active_object
    ob.scale = scale
    return obj(ob, m, name)


# cuerpo: cúpula baja de perla sobre una base oscura
ellipsoid("faldon", M_DARK, (0, 0, 0.17), (1.02, 0.80, 0.17))
cup = ellipsoid("capo", M_PEARL, (0, 0, 0.24), (1.0, 0.78, 0.42))
# corta la mitad de abajo de la esfera para que no asome
bpy.ops.mesh.primitive_cube_add(size=4, location=(0, 0, -1.8 + 0.22))
cut = bpy.context.active_object
bm = cup.modifiers.new("corte", "BOOLEAN")
bm.object, bm.operation = cut, "DIFFERENCE"
bpy.context.view_layer.objects.active = cup
bpy.ops.object.modifier_apply(modifier="corte")
bpy.data.objects.remove(cut)
# cristal oscuro de arriba y aro de luz
ellipsoid("cristal", M_GLASS, (0.06, 0, 0.55), (0.62, 0.46, 0.13))
bpy.ops.mesh.primitive_torus_add(major_radius=0.64, minor_radius=0.022, location=(0.06, 0, 0.605), major_segments=96, minor_segments=16)
ring = bpy.context.active_object
ring.scale = (1.0, 0.74, 1.0)
obj(ring, M_LED, "aro")
bpy.ops.mesh.primitive_torus_add(major_radius=0.97, minor_radius=0.014, location=(0, 0, 0.3), major_segments=96, minor_segments=12)
trim = bpy.context.active_object
trim.scale = (1.0, 0.785, 1.0)
obj(trim, M_LED, "filete")

# ruedas: dos grandes detrás, dos pequeñas delante
for sy in (-1, 1):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.27, depth=0.17, location=(-0.50, sy * 0.70, 0.27), rotation=(math.pi / 2, 0, 0), vertices=64)
    obj(bpy.context.active_object, M_TIRE, "rueda")
    bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=0.185, location=(-0.50, sy * 0.70, 0.27), rotation=(math.pi / 2, 0, 0), vertices=48)
    obj(bpy.context.active_object, M_HUB, "buje")
    bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=0.16, location=(0.66, sy * 0.52, 0.15), rotation=(math.pi / 2, 0, 0), vertices=48)
    obj(bpy.context.active_object, M_TIRE, "loca")

# suelo que solo recoge la sombra
bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, 0))
ground = bpy.context.active_object
ground.is_shadow_catcher = True
ground.data.materials.append(M_GROUND)

# luz de estudio
bpy.ops.object.light_add(type="AREA", location=(-2.6, -2.2, 3.4))
key = bpy.context.active_object
key.data.energy, key.data.size = 210, 3.2
key.rotation_euler = (math.radians(52), 0, math.radians(-40))
bpy.ops.object.light_add(type="AREA", location=(3.0, 2.4, 2.0))
fill = bpy.context.active_object
fill.data.energy, fill.data.size = 70, 3.0
fill.rotation_euler = (math.radians(65), 0, math.radians(135))
bpy.ops.object.light_add(type="AREA", location=(0, 3.4, 1.4))
rim = bpy.context.active_object
rim.data.energy, rim.data.size = 120, 2.2
rim.rotation_euler = (math.radians(80), 0, math.radians(180))
w = bpy.data.worlds.new("w")
scn.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.5, 0.55, 0.6, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25

# cámara de tres cuartos
bpy.ops.object.empty_add(location=(0, 0, 0.3))
tgt = bpy.context.active_object
bpy.ops.object.camera_add(location=(3.5, -4.0, 2.5))
cam = bpy.context.active_object
cam.data.lens = 62
c = cam.constraints.new("TRACK_TO")
c.target, c.track_axis, c.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
scn.camera = cam

scn.render.engine = "CYCLES"
scn.cycles.device = "CPU"
scn.cycles.samples = 56
scn.cycles.use_denoising = True
scn.render.film_transparent = True
scn.render.resolution_x = scn.render.resolution_y = 1024
scn.render.image_settings.file_format = "PNG"
scn.render.image_settings.color_mode = "RGBA"
scn.view_settings.view_transform = "Standard"
scn.render.filepath = str(OUT)
bpy.ops.render.render(write_still=True)
print("listo", OUT)
