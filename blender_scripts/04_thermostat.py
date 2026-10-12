"""
Smart Thermostat - wall-mounted room thermostat / temperature sensor (low-poly game asset for Unity XR)

Run in Blender: Scripting -> Open -> Run Script, or
  blender --background --python 04_thermostat.py

Output: D:\\TelTech\\Models\\Thermostat\\Thermostat.blend / .fbx / _preview.png

Hierarchy (real size, metres, 90 x 90 mm; front = Blender -Y; origin = back centre, on the wall):
  Thermostat (empty)
   |- Body           - matte silver housing
   |- Front_Plate    - matte black front
   |- Screen         - flat dark glass display (swap material / emission for warnings in Unity)
   |- Screen_Anchor  - empty on the screen surface: put a World Space Canvas (temperature text) here
   |- Button_Minus   - touch button "-"
   |- Button_Plus    - touch button "+"
   |- Status_LED     - small LED (e.g. red when the temperature limit is exceeded)
"""
import bpy, bmesh, os, math
from mathutils import Matrix, Vector

MM = 0.001
OUT = r"D:\TelTech\Models\Thermostat"
os.makedirs(OUT, exist_ok=True)
NAME = "Thermostat"
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

def material(name, rgb, rough, metal=0.0, emission=None, strength=0.0):
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
        if emission:
            set_input(bsdf, ["Emission Color", "Emission"], (*emission, 1.0))
            set_input(bsdf, ["Emission Strength"], strength)
    return m

MAT_SILVER = material("Thermo_Silver_Matte", (0.62, 0.63, 0.65), 0.38, 1.0)
MAT_BLACK  = material("Thermo_Black_Matte", (0.018, 0.018, 0.02), 0.55)
MAT_SCREEN = material("Thermo_Screen_Glass", (0.006, 0.008, 0.012), 0.04)
MAT_BTN    = material("Thermo_Button", (0.05, 0.05, 0.055), 0.35)
MAT_ICON   = material("Thermo_Icon", (0.75, 0.76, 0.78), 0.4)
MAT_LED    = material("Thermo_LED", (0.1, 0.8, 0.3), 0.3, emission=(0.1, 0.8, 0.3), strength=2.0)

# ---------- helpers ----------
def finish(name, bm, mat, parent, location=(0, 0, 0), smooth_angle=30):
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

def rbox(bm, sx, sy, sz, center, bevel, segs=5):
    tmp = bmesh.new()
    bmesh.ops.create_cube(tmp, size=1.0)
    bmesh.ops.scale(tmp, vec=(sx, sy, sz), verts=tmp.verts)
    bmesh.ops.translate(tmp, vec=center, verts=tmp.verts)
    if bevel > 0:
        bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=bevel, segments=segs,
                        profile=0.5, affect='EDGES', clamp_overlap=True)
    me = bpy.data.meshes.new("tmp")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    return bm

def disc(bm, r, depth, center, segs=32):
    tmp = bmesh.new()
    bmesh.ops.create_cone(tmp, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=depth)
    bmesh.ops.rotate(tmp, verts=tmp.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
    bmesh.ops.translate(tmp, vec=center, verts=tmp.verts)
    me = bpy.data.meshes.new("tmp")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    return bm

# ---------- build ----------
root = bpy.data.objects.new(NAME, None)
root.empty_display_size = 0.04
scene.collection.objects.link(root)

# Body: 90 x 90 x 14 mm, rounded corners, on the wall (y = 0 -> -14 mm)
body = finish("Body", rbox(bmesh.new(), 90 * MM, 14 * MM, 90 * MM, (0, -7 * MM, 0), 4 * MM, 6), MAT_SILVER, root)

# Front plate: 80 x 80 x 2 mm black, sticks out 1 mm
FRONT = -15 * MM
plate = finish("Front_Plate", rbox(bmesh.new(), 80 * MM, 2 * MM, 80 * MM, (0, FRONT + 1 * MM, 0), 1.2 * MM, 4),
               MAT_BLACK, root)

# Screen: 60 x 36 mm dark glass, upper part
SCR_Z = 9 * MM
screen = finish("Screen", rbox(bmesh.new(), 60 * MM, 0.6 * MM, 36 * MM, (0, FRONT - 0.3 * MM, SCR_Z), 0.25 * MM, 2),
                MAT_SCREEN, root)

anchor = bpy.data.objects.new("Screen_Anchor", None)
anchor.empty_display_type = 'PLAIN_AXES'
anchor.empty_display_size = 0.01
anchor.location = (0, FRONT - 0.7 * MM, SCR_Z)
anchor.parent = root
scene.collection.objects.link(anchor)

# Touch buttons "-" and "+" (each its own object, origin in its centre -> easy to press/animate)
BTN_Z = -24 * MM
for name, x, plus in (("Button_Minus", -15 * MM, False), ("Button_Plus", 15 * MM, True)):
    bm = disc(bmesh.new(), 6 * MM, 1.2 * MM, (0, 0, 0), 40)
    btn = finish(name, bm, MAT_BTN, root, location=(x, FRONT - 0.6 * MM, BTN_Z), smooth_angle=40)
    # icon (thin raised bars) as a child, so it moves with the button
    ib = rbox(bmesh.new(), 5 * MM, 0.3 * MM, 0.9 * MM, (0, -0.75 * MM, 0), 0.0)
    if plus:
        rbox(ib, 0.9 * MM, 0.36 * MM, 5 * MM, (0, -0.78 * MM, 0), 0.0)
    finish(name + "_Icon", ib, MAT_ICON, btn)

# Status LED between the buttons
led = finish("Status_LED", disc(bmesh.new(), 1.2 * MM, 0.6 * MM, (0, 0, 0), 20), MAT_LED, root,
             location=(0, FRONT - 0.3 * MM, BTN_Z), smooth_angle=60)

# ---------- save + FBX ----------
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME + ".blend"), copy=True)
bpy.ops.export_scene.fbx(
    filepath=os.path.join(OUT, NAME + ".fbx"),
    use_selection=False, object_types={'EMPTY', 'MESH'}, use_mesh_modifiers=True,
    apply_scale_options='FBX_SCALE_ALL', bake_space_transform=True,
    axis_forward='-Z', axis_up='Y', add_leaf_bones=False, path_mode='AUTO')

# ---------- preview render ----------
cam_data = bpy.data.cameras.new("PreviewCam")
cam_data.lens = 85
cam = bpy.data.objects.new("PreviewCam", cam_data)
scene.collection.objects.link(cam)
cam.location = (0.12, -0.32, 0.10)
target = Vector((0, -0.008, 0))
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

def area_light(name, loc, power, size):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = power
    ld.size = size
    lo = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

area_light("Key", (-0.25, -0.35, 0.35), 3, 0.3)
area_light("Fill", (0.35, -0.3, 0.0), 1, 0.4)
area_light("Rim", (0.0, 0.1, 0.4), 1, 0.3)

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
if OLD:
    world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 0.7

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

print("Thermostat done ->", OUT)
