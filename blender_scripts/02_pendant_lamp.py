"""
Pendant Lamp - modern ceiling pendant with a glass globe bulb (low-poly game asset for Unity XR)

Run in Blender: Scripting -> Open -> Run Script, or
  blender --background --python 02_pendant_lamp.py

Output: D:\\TelTech\\Models\\Pendant_Lamp.blend / .fbx / _preview.png

Hierarchy (real size, metres; origin = ceiling mount point, lamp hangs down -Z, total drop ~0.8 m):
  Pendant_Lamp (empty)
   |- Canopy        - ceiling cup, Ø 120 mm
   |- Cable         - black cord
   |- Shade         - matte metal dome, Ø 300 mm
   |- Socket        - bulb holder
   |- Bulb          - G95 glass globe: switch its material emission on/off in Unity
   |- Light_Anchor  - empty in the bulb centre: put a Unity Point/Spot Light here
"""
import bpy, bmesh, os, math
from mathutils import Vector

OUT = r"D:\TelTech\Models\Pendant_Lamp"
os.makedirs(OUT, exist_ok=True)
NAME = "Pendant_Lamp"
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

def material(name, rgb, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    if OLD:
        m.use_nodes = True
    m.diffuse_color = (*rgb, 1.0)
    m.metallic = metal
    m.roughness = rough
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        set_input(bsdf, ["Base Color"], (*rgb, 1.0))
        set_input(bsdf, ["Roughness"], rough)
        set_input(bsdf, ["Metallic"], metal)
    return m

MAT_SHADE  = material("Lamp_Metal_Matte", (0.035, 0.037, 0.04), 0.42, 1.0)
MAT_BRASS  = material("Lamp_Brass", (0.80, 0.62, 0.36), 0.3, 1.0)
MAT_CABLE  = material("Lamp_Cable", (0.02, 0.02, 0.02), 0.6)
MAT_BULB   = material("Lamp_Bulb_Glass", (1.0, 0.95, 0.85), 0.08)
BULB_BSDF = MAT_BULB.node_tree.nodes.get("Principled BSDF")
WARM = (1.0, 0.78, 0.48, 1.0)
if BULB_BSDF:
    set_input(BULB_BSDF, ["Emission Color", "Emission"], WARM)
    set_input(BULB_BSDF, ["Emission Strength"], 0.0)   # OFF in the exported asset

# ---------- helpers ----------
def make_object(name, bm, mat, parent, smooth_angle=35):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
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
    es = ob.modifiers.new("EdgeSplit", 'EDGE_SPLIT')
    es.split_angle = math.radians(smooth_angle)
    return ob

def lathe(bm, profile, steps=48):
    """Revolve a closed (r, z) profile around the Z axis."""
    verts = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    edges = [bm.edges.new((verts[i], verts[(i + 1) % len(verts)])) for i in range(len(verts))]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1),
                   angle=2 * math.pi, steps=steps, use_duplicate=False)
    return bm

def cylinder(bm, r, z_top, z_bottom, steps=32):
    return lathe(bm, [(0, z_top), (r, z_top), (r, z_bottom), (0, z_bottom)], steps)

# ---------- build ----------
root = bpy.data.objects.new(NAME, None)
root.empty_display_size = 0.1
scene.collection.objects.link(root)

# Canopy (ceiling cup) with small rounded lower edge
canopy = make_object("Canopy", lathe(bmesh.new(), [
    (0.0, 0.0), (0.060, 0.0), (0.060, -0.018), (0.058, -0.023), (0.054, -0.025), (0.0, -0.025)]),
    MAT_SHADE, root)

# Cable
SHADE_TOP = -0.60
cable = make_object("Cable", cylinder(bmesh.new(), 0.002, -0.025, SHADE_TOP + 0.02, 12),
                    MAT_CABLE, root, smooth_angle=60)

# Shade: dome shell, 2 mm wall, Ø 300 mm, 160 mm tall + brass collar on top
H, R0, R1, T = 0.16, 0.022, 0.15, 0.002
outer = []
N = 18
for i in range(N + 1):
    t = i / N
    outer.append((R0 + (R1 - R0) * t, SHADE_TOP - H * t ** 1.8))
inner = []
for i, (r, z) in enumerate(outer):
    a = outer[max(i - 1, 0)]; b = outer[min(i + 1, N)]
    tx, tz = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(tx, tz)
    nx, nz = tz / ln, -tx / ln            # normal pointing inside / down
    inner.append((r - nx * T, z - nz * T))
# make sure the inner normal really points down-inwards
if inner[N // 2][1] > outer[N // 2][1]:
    inner = [(2 * o[0] - i[0], 2 * o[1] - i[1]) for o, i in zip(outer, inner)]
shade_profile = outer + [(R1 - T * 0.6, SHADE_TOP - H)] + list(reversed(inner))
shade_bm = lathe(bmesh.new(), shade_profile, 64)
shade = make_object("Shade", shade_bm, MAT_SHADE, root)

collar = make_object("Collar", lathe(bmesh.new(), [
    (0.0, SHADE_TOP + 0.022), (0.016, SHADE_TOP + 0.022), (0.024, SHADE_TOP + 0.004),
    (0.024, SHADE_TOP - 0.004), (0.0, SHADE_TOP - 0.004)], 32), MAT_BRASS, root)

# Socket (bulb holder) inside the shade
SOCK_BOTTOM = -0.695
socket = make_object("Socket", lathe(bmesh.new(), [
    (0.0, SHADE_TOP - 0.004), (0.017, SHADE_TOP - 0.004), (0.017, SOCK_BOTTOM + 0.004),
    (0.015, SOCK_BOTTOM), (0.0, SOCK_BOTTOM)], 32), MAT_BRASS, root)

# Bulb: G95 globe, Ø 95 mm, hangs slightly below the shade rim
BR = 0.0475
BC = SOCK_BOTTOM - 0.012 - BR          # sphere centre
neck_r = 0.015
a_top = math.asin(neck_r / BR)         # angle from the top where sphere meets the neck
prof = [(0.0, SOCK_BOTTOM), (neck_r, SOCK_BOTTOM)]
steps = 20
for i in range(steps + 1):
    a = a_top + (math.pi - a_top) * i / steps   # 0 = top of sphere, pi = bottom
    prof.append((BR * math.sin(a), BC + BR * math.cos(a)))
prof[-1] = (0.0, BC - BR)
bulb = make_object("Bulb", lathe(bmesh.new(), prof, 48), MAT_BULB, root, smooth_angle=50)

anchor = bpy.data.objects.new("Light_Anchor", None)
anchor.empty_display_type = 'SPHERE'
anchor.empty_display_size = 0.02
anchor.location = (0, 0, BC)
anchor.parent = root
scene.collection.objects.link(anchor)

# ---------- save + FBX ----------
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME + ".blend"), copy=True)
bpy.ops.export_scene.fbx(
    filepath=os.path.join(OUT, NAME + ".fbx"),
    use_selection=False, object_types={'EMPTY', 'MESH'}, use_mesh_modifiers=True,
    apply_scale_options='FBX_SCALE_ALL', bake_space_transform=True,
    axis_forward='-Z', axis_up='Y', add_leaf_bones=False, path_mode='AUTO')

# ---------- preview render: lamp switched ON ----------
if BULB_BSDF:
    set_input(BULB_BSDF, ["Emission Strength"], 6.0)

cam_data = bpy.data.cameras.new("PreviewCam")
cam_data.lens = 60
cam = bpy.data.objects.new("PreviewCam", cam_data)
scene.collection.objects.link(cam)
cam.location = (0.75, -1.75, -0.78)
target = Vector((0, 0, -0.43))
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

def area_light(name, loc, power, size, aim=(0, 0, -0.6)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = power
    ld.size = size
    lo = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

area_light("Key", (-1.0, -1.4, 0.4), 120, 1.0)
area_light("Fill", (1.4, -1.0, -0.8), 40, 1.2)
area_light("Rim", (0.2, 1.2, 0.2), 60, 0.8)

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
if OLD:
    world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 0.75

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

# back to OFF + remove preview helpers
if BULB_BSDF:
    set_input(BULB_BSDF, ["Emission Strength"], 0.0)
for n in ("PreviewCam", "Key", "Fill", "Rim"):
    ob = bpy.data.objects.get(n)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)

# frame the asset in the viewport
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

print("Pendant lamp done ->", OUT)
