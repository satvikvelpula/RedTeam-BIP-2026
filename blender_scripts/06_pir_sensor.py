"""
Ceiling PIR Motion Sensor (low-poly game asset for Unity XR)

Run in Blender: Scripting -> Open -> Run Script, or
  blender --background --python 06_pir_sensor.py

Output: D:\\TelTech\\Models\\PIR_Sensor\\PIR_Sensor.blend / .fbx / _preview.png

Hierarchy (real size, metres; origin = ceiling mount point, sensor hangs down -Z; Ø 90 mm):
  PIR_Sensor (empty)
   |- Housing         - white plastic base
   |- Lens            - faceted white Fresnel dome
   |- Status_LED      - small LED (blink when motion is detected)
   |- Detection_Zone  - semi-transparent cone, 2.5 m high, Ø 6 m at the floor.
                        Unity: MeshCollider (Convex) + Is Trigger -> OnTriggerEnter = "motion detected".
                        Hidden in the preview render; toggle its MeshRenderer to show/hide the zone.
"""
import bpy, bmesh, os, math
from mathutils import Matrix, Vector

MM = 0.001
OUT = r"D:\TelTech\Models\PIR_Sensor"
os.makedirs(OUT, exist_ok=True)
NAME = "PIR_Sensor"
OLD = bpy.app.version < (5, 0, 0)

# ---------- clean scene ----------
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
    for block in list(coll):
        if block.users == 0:
            coll.remove(block)
scene = bpy.context.scene

# ---------- materials ----------
def set_input(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return

def material(name, rgb, rough, alpha=1.0, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    if OLD:
        m.use_nodes = True
    m.diffuse_color = (*rgb, alpha)
    m.roughness = rough
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        set_input(bsdf, ["Base Color"], (*rgb, 1.0))
        set_input(bsdf, ["Roughness"], rough)
        if alpha < 1.0:
            set_input(bsdf, ["Alpha"], alpha)
        if emission:
            set_input(bsdf, ["Emission Color", "Emission"], (*emission, 1.0))
            set_input(bsdf, ["Emission Strength"], strength)
    return m

MAT_WHITE = material("PIR_White_Plastic", (0.9, 0.9, 0.88), 0.5)
MAT_LENS  = material("PIR_Lens", (0.95, 0.95, 0.94), 0.35)
MAT_LED   = material("PIR_LED", (0.9, 0.1, 0.05), 0.3, emission=(1.0, 0.1, 0.05), strength=0.0)
MAT_ZONE  = material("PIR_Detection_Zone", (0.2, 0.6, 1.0), 0.5, alpha=0.15)

# ---------- helpers ----------
def finish(name, bm, mat, parent, location=(0, 0, 0), smooth_angle=35):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    ob.parent = parent
    ob.location = location
    es = ob.modifiers.new("EdgeSplit", 'EDGE_SPLIT')
    es.split_angle = math.radians(smooth_angle)
    return ob

def lathe(profile, steps=48):
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    edges = [bm.edges.new((verts[i], verts[(i + 1) % len(verts)])) for i in range(len(verts))]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1),
                   angle=2 * math.pi, steps=steps, use_duplicate=False)
    return bm

# ---------- build ----------
root = bpy.data.objects.new(NAME, None)
root.empty_display_size = 0.04
scene.collection.objects.link(root)

# Housing: Ø 90 mm, 18 mm tall, softly rounded lower edge
housing = finish("Housing", lathe([
    (0, 0), (45 * MM, 0), (45 * MM, -10 * MM), (44 * MM, -14 * MM), (41.5 * MM, -17 * MM),
    (38 * MM, -18 * MM), (0, -18 * MM)], 64), MAT_WHITE, root)

# Lens: faceted Fresnel dome, Ø 46 mm, 20 mm high (few segments + low split angle = facets)
LZ = -18 * MM
lens_prof = [(0, LZ + 1 * MM), (23 * MM, LZ + 1 * MM)]
rings = 6
for i in range(1, rings + 1):
    a = (math.pi / 2) * i / rings
    lens_prof.append((23 * MM * math.cos(a), LZ - 20 * MM * math.sin(a)))
lens_prof[-1] = (0.0, lens_prof[-1][1])
lens = finish("Lens", lathe(lens_prof, 16), MAT_LENS, root, smooth_angle=5)

# Lens ring (small step between housing and lens)
finish("Lens_Ring", lathe([(0, LZ + 0.5 * MM), (26 * MM, LZ + 0.5 * MM), (26 * MM, LZ - 1.2 * MM),
                           (0, LZ - 1.2 * MM)], 64), MAT_WHITE, root)

# Status LED on the housing bottom
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=1.4 * MM, radius2=1.4 * MM, depth=0.8 * MM)
led = finish("Status_LED", bm, MAT_LED, root, location=(0, -32 * MM, LZ - 0.2 * MM), smooth_angle=60)

# Detection zone: cone from the lens down to the floor (2.5 m below), Ø 6 m
ZH, ZR = 2.5, 3.0
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=ZR, radius2=0.0, depth=ZH)
bmesh.ops.translate(bm, vec=(0, 0, -ZH / 2), verts=bm.verts)    # apex at origin
zone = finish("Detection_Zone", bm, MAT_ZONE, root, location=(0, 0, LZ - 10 * MM), smooth_angle=60)
zone.display_type = 'WIRE'

# ---------- save + FBX ----------
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME + ".blend"), copy=True)
bpy.ops.export_scene.fbx(
    filepath=os.path.join(OUT, NAME + ".fbx"),
    use_selection=False, object_types={'EMPTY', 'MESH'}, use_mesh_modifiers=True,
    apply_scale_options='FBX_SCALE_ALL', bake_space_transform=True,
    axis_forward='-Z', axis_up='Y', add_leaf_bones=False, path_mode='AUTO')

# ---------- preview render (zone hidden, LED on) ----------
zone.hide_render = True
led_bsdf = MAT_LED.node_tree.nodes.get("Principled BSDF")
if led_bsdf:
    set_input(led_bsdf, ["Emission Strength"], 4.0)

cam_data = bpy.data.cameras.new("PreviewCam")
cam_data.lens = 85
cam = bpy.data.objects.new("PreviewCam", cam_data)
scene.collection.objects.link(cam)
cam.location = (0.13, -0.22, -0.25)
target = Vector((0, 0, -0.018))
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

def area_light(name, loc, power, size):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = power
    ld.size = size
    lo = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (Vector((0, 0, -0.02)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

area_light("Key", (-0.3, -0.3, -0.3), 0.9, 0.3)
area_light("Fill", (0.35, -0.2, -0.1), 0.3, 0.4)
area_light("Rim", (0.0, 0.3, -0.25), 0.6, 0.3)

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
if OLD:
    world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 0.45

scene.render.engine = 'CYCLES'
scene.cycles.samples = 128
try:
    scene.cycles.use_denoising = True
except Exception:
    pass
try:
    scene.view_settings.view_transform = 'Standard'
except Exception:
    pass
scene.render.resolution_x = 1000
scene.render.resolution_y = 1000
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = os.path.join(OUT, NAME + "_preview.png")
bpy.ops.render.render(write_still=True)

zone.hide_render = False
if led_bsdf:
    set_input(led_bsdf, ["Emission Strength"], 0.0)
for n in ("PreviewCam", "Key", "Fill", "Rim"):
    ob = bpy.data.objects.get(n)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)

try:
    for ob in scene.objects:
        ob.select_set(ob.name != "Detection_Zone")
    bpy.context.view_layer.objects.active = root
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.view3d.view_selected()
except Exception:
    pass

print("PIR sensor done ->", OUT)
