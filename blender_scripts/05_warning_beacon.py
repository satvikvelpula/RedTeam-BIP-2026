"""
Warning Beacon Light - wall-mounted industrial rotating beacon (low-poly game asset for Unity XR)

Run in Blender: Scripting -> Open -> Run Script, or
  blender --background --python 05_warning_beacon.py

Output: D:\\TelTech\\Models\\Warning_Beacon\\Warning_Beacon.blend / .fbx / _preview.png

Hierarchy (real size, metres; front = Blender -Y; origin = wall, bottom of the bracket):
  Warning_Beacon (empty)
   |- Bracket        - grey metal L-bracket on the wall
   |- Beacon (empty) - centre axis of the beacon
       |- Base       - grey metal base, Ø 100 mm
       |- Dome       - red transparent dome, Ø 88 mm (Unity: transparent red material, emission when ON)
       |- Bulb_Core  - light source inside (emission ON/OFF)
       |- Reflector  - mirror reflector, origin on the axis: rotate around local Z (Unity: Y) for the rotating effect
       |- Light_Anchor - put a red Point/Spot Light here in Unity
"""
import bpy, bmesh, os, math
from mathutils import Vector

MM = 0.001
OUT = r"D:\TelTech\Models\Warning_Beacon"
os.makedirs(OUT, exist_ok=True)
NAME = "Warning_Beacon"
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

def material(name, rgb, rough, metal=0.0, alpha=1.0, transmission=0.0, emission=None):
    m = bpy.data.materials.new(name)
    if OLD:
        m.use_nodes = True
    m.diffuse_color = (*rgb, alpha)
    m.metallic = metal
    m.roughness = rough
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        set_input(bsdf, ["Base Color"], (*rgb, 1.0))
        set_input(bsdf, ["Roughness"], rough)
        set_input(bsdf, ["Metallic"], metal)
        if transmission:
            set_input(bsdf, ["Transmission Weight", "Transmission"], transmission)
            set_input(bsdf, ["IOR"], 1.49)
        if emission:
            set_input(bsdf, ["Emission Color", "Emission"], (*emission, 1.0))
            set_input(bsdf, ["Emission Strength"], 0.0)    # OFF in the exported asset
    return m

RED = (1.0, 0.04, 0.02)
MAT_METAL   = material("Beacon_Grey_Metal", (0.30, 0.31, 0.33), 0.45, 0.85)
MAT_BRACKET = material("Beacon_Bracket", (0.20, 0.21, 0.22), 0.5, 0.8)
MAT_DOME    = material("Beacon_Red_Dome", RED, 0.12, alpha=0.6, transmission=1.0, emission=RED)
MAT_CORE    = material("Beacon_Bulb_Core", (1.0, 0.85, 0.8), 0.3, emission=(1.0, 0.1, 0.05))
MAT_MIRROR  = material("Beacon_Reflector", (0.9, 0.9, 0.92), 0.08, 1.0)

# ---------- helpers ----------
def make_object(name, bm, mat, parent, location=(0, 0, 0), smooth_angle=35):
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

def lathe(profile, steps=48, angle=2 * math.pi, closed=True, start_angle=0.0):
    bm = bmesh.new()
    verts = [bm.verts.new((r * math.cos(start_angle), r * math.sin(start_angle), z)) for r, z in profile]
    n = len(verts) if closed else len(verts) - 1
    edges = [bm.edges.new((verts[i], verts[(i + 1) % len(verts)])) for i in range(n)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1),
                   angle=angle, steps=steps, use_duplicate=False)
    return bm

def add_box(bm, center, size, bevel):
    tmp = bmesh.new()
    bmesh.ops.create_cube(tmp, size=1.0)
    bmesh.ops.scale(tmp, vec=size, verts=tmp.verts)
    bmesh.ops.translate(tmp, vec=center, verts=tmp.verts)
    bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=bevel, segments=3,
                    profile=0.5, affect='EDGES', clamp_overlap=True)
    me = bpy.data.meshes.new("tmp")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)

# ---------- build ----------
root = bpy.data.objects.new(NAME, None)
root.empty_display_size = 0.05
scene.collection.objects.link(root)

# L-bracket: wall plate 80 x 110 mm + shelf 80 x 100 mm, 5 mm steel, + gusset
bm = bmesh.new()
add_box(bm, (0, -2.5 * MM, 55 * MM), (80 * MM, 5 * MM, 110 * MM), 1.2 * MM)       # on the wall
add_box(bm, (0, -50 * MM, 2.5 * MM), (80 * MM, 100 * MM, 5 * MM), 1.2 * MM)       # shelf
add_box(bm, (0, -20 * MM, 20 * MM), (5 * MM, 30 * MM, 30 * MM), 1.0 * MM)         # gusset
bracket = make_object("Bracket", bm, MAT_BRACKET, root)

# beacon axis
AX = Vector((0, -55 * MM, 5 * MM))       # standing on the shelf
beacon = bpy.data.objects.new("Beacon", None)
beacon.empty_display_size = 0.03
beacon.location = AX
beacon.parent = root
scene.collection.objects.link(beacon)

# Base Ø 100 mm, 32 mm high, chamfered top + small ring
base = make_object("Base", lathe([
    (0, 0), (50 * MM, 0), (50 * MM, 26 * MM), (48 * MM, 30 * MM), (46 * MM, 31 * MM),
    (46 * MM, 34 * MM), (0, 34 * MM)], 64), MAT_METAL, beacon)

# Dome: Ø 88 mm cylinder with fresnel ribs + rounded top, total ~115 mm
prof = [(0, 33 * MM), (44 * MM, 33 * MM)]
Z0, Z1 = 33 * MM, 120 * MM
ribs = 70
for i in range(1, ribs + 1):
    z = Z0 + (Z1 - Z0) * i / ribs
    r = 44 * MM + 0.7 * MM * abs(math.sin(i * math.pi / 5))
    prof.append((r, z))
CAP = 28 * MM
for i in range(1, 13):
    a = (math.pi / 2) * i / 12
    prof.append((44 * MM * math.cos(a), Z1 + CAP * math.sin(a)))
prof[-1] = (0.0, Z1 + CAP)
dome = make_object("Dome", lathe(prof, 64), MAT_DOME, beacon, smooth_angle=50)

# Bulb core
core = make_object("Bulb_Core", lathe([
    (0, 34 * MM), (11 * MM, 34 * MM), (11 * MM, 95 * MM), (8 * MM, 101 * MM), (0, 103 * MM)], 32),
    MAT_CORE, beacon)

# Rotating reflector: curved mirror shell (160 deg) + a hub, origin on the axis
bm = lathe([(24 * MM, 45 * MM), (25.5 * MM, 45 * MM), (25.5 * MM, 100 * MM), (24 * MM, 100 * MM)],
           steps=16, angle=math.radians(160), start_angle=math.radians(10))
hub = lathe([(0, 40 * MM), (14 * MM, 40 * MM), (14 * MM, 44 * MM), (0, 44 * MM)], 24)
me = bpy.data.meshes.new("tmp"); hub.to_mesh(me); hub.free(); bm.from_mesh(me); bpy.data.meshes.remove(me)
reflector = make_object("Reflector", bm, MAT_MIRROR, beacon)

anchor = bpy.data.objects.new("Light_Anchor", None)
anchor.empty_display_type = 'SPHERE'
anchor.empty_display_size = 0.01
anchor.location = (0, 0, 75 * MM)
anchor.parent = beacon
scene.collection.objects.link(anchor)

# ---------- save + FBX ----------
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME + ".blend"), copy=True)
bpy.ops.export_scene.fbx(
    filepath=os.path.join(OUT, NAME + ".fbx"),
    use_selection=False, object_types={'EMPTY', 'MESH'}, use_mesh_modifiers=True,
    apply_scale_options='FBX_SCALE_ALL', bake_space_transform=True,
    axis_forward='-Z', axis_up='Y', add_leaf_bones=False, path_mode='AUTO')

# ---------- preview render: beacon ON ----------
def emission(mat, s):
    b = mat.node_tree.nodes.get("Principled BSDF")
    if b:
        set_input(b, ["Emission Strength"], s)

emission(MAT_CORE, 40.0)
emission(MAT_DOME, 0.6)

cam_data = bpy.data.cameras.new("PreviewCam")
cam_data.lens = 70
cam = bpy.data.objects.new("PreviewCam", cam_data)
scene.collection.objects.link(cam)
cam.location = (0.30, -0.62, 0.26)
target = Vector((0, -0.045, 0.072))
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

def area_light(name, loc, power, size):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = power
    ld.size = size
    lo = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (target - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

area_light("Key", (-0.4, -0.55, 0.55), 8, 0.4)
area_light("Fill", (0.55, -0.45, 0.1), 3, 0.5)
area_light("Rim", (0.1, 0.15, 0.6), 3, 0.4)

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
if OLD:
    world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 0.7

scene.render.engine = 'CYCLES'
scene.cycles.samples = 160
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

emission(MAT_CORE, 0.0)
emission(MAT_DOME, 0.0)
for n in ("PreviewCam", "Key", "Fill", "Rim"):
    ob = bpy.data.objects.get(n)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)

try:
    for ob in scene.objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = root
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.view3d.view_selected()
except Exception:
    pass

print("Warning beacon done ->", OUT)
