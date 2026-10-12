"""
KNX Switch - smart wall push button (low-poly game asset for Unity XR)

Run in Blender:
  * Scripting tab -> Open -> this file -> Run Script
  * or from a terminal:  blender --background --python 01_knx_switch.py

Output (folder "Models" next to this script's parent folder, e.g. D:\\TelTech\\Models):
  KNX_Switch.blend, KNX_Switch.fbx, KNX_Switch_preview.png

Hierarchy (real size, metres, 80 x 80 mm plate):
  KNX_Switch (empty, origin = back of the plate, on the wall)
   |- Frame        - square wall plate
   |- Insert       - grey base, visible as a thin gap around the button
   |- Button_Cap   - the moving part: animate local position to "press" (~2 mm into the wall)
       |- LED      - status LED, switch the emission on/off in Unity
The front of the switch faces Blender -Y.
"""
import bpy, bmesh, os, math
from mathutils import Matrix, Vector

MM = 0.001

# ---------- output folder ----------
def out_dir():
    # fixed path: when run from Blender's Text Editor, __file__ is not reliable
    d = r"D:\TelTech\Models\KNX_Switch"
    os.makedirs(d, exist_ok=True)
    return d

OUT = out_dir()
NAME = "KNX_Switch"

# ---------- clean scene (without factory reset, so it also works from the Text Editor) ----------
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
    for block in list(coll):
        if block.users == 0:
            coll.remove(block)

scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0

# ---------- materials ----------
def set_input(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return

def material(name, rgb, rough, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    if bpy.app.version < (5, 0, 0):
        m.use_nodes = True
    m.diffuse_color = (*rgb, 1.0)          # viewport colour + used by some importers
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        set_input(bsdf, ["Base Color"], (*rgb, 1.0))
        set_input(bsdf, ["Roughness"], rough)
        if emission:
            set_input(bsdf, ["Emission Color", "Emission"], (*emission, 1.0))
            set_input(bsdf, ["Emission Strength"], strength)
    return m

MAT_WHITE = material("KNX_White_Matte", (0.88, 0.88, 0.86), 0.55)
MAT_CAP   = material("KNX_Button_White", (0.93, 0.93, 0.91), 0.45)
MAT_GAP   = material("KNX_Gap_Grey", (0.32, 0.32, 0.33), 0.7)
MAT_LED   = material("KNX_LED", (0.15, 0.45, 1.0), 0.2, emission=(0.15, 0.45, 1.0), strength=3.0)

# ---------- mesh helpers ----------
def finish(name, bm, mat, parent=None, location=(0, 0, 0), smooth_angle=30):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    ob.location = location
    if parent:
        ob.parent = parent
    # smooth bevels, sharp large faces; works in every Blender version and survives FBX export
    es = ob.modifiers.new("EdgeSplit", 'EDGE_SPLIT')
    es.split_angle = math.radians(smooth_angle)
    return ob

def rounded_box(name, sx, sy, sz, y_back, bevel, segs, mat, parent=None, location=(0, 0, 0)):
    """Box sx (X) x sz (Z), depth sy along -Y, back face at local y = y_back."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, y_back - sy / 2, 0), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segs,
                    profile=0.5, affect='EDGES', clamp_overlap=True)
    return finish(name, bm, mat, parent, location)

# ---------- build ----------
root = bpy.data.objects.new(NAME, None)
root.empty_display_type = 'PLAIN_AXES'
root.empty_display_size = 0.03
scene.collection.objects.link(root)

# Frame: 80 x 80 mm, 6 mm thick, sits on the wall (y = 0) and comes towards the viewer (-Y)
frame = rounded_box("Frame", 80 * MM, 6 * MM, 80 * MM, 0.0, 2.5 * MM, 6, MAT_WHITE, root)

# Insert: 55 x 55 mm, sticks 1.5 mm out of the frame, visible as a dark ring around the button
insert = rounded_box("Insert", 55 * MM, 3.5 * MM, 55 * MM, -4 * MM, 0.8 * MM, 3, MAT_GAP, root)

# Button cap: 53 x 53 x 4.5 mm. Origin at its back face so a press = move +Y (towards the wall)
cap_back = -7 * MM
cap = rounded_box("Button_Cap", 53 * MM, 4.5 * MM, 53 * MM, 0.0, 1.8 * MM, 6, MAT_CAP,
                  root, location=(0, cap_back, 0))

# Slightly domed front of the cap (0.6 mm in the middle) - reads much nicer than a flat slab
for v in cap.data.vertices:
    if v.co.y < -4.4 * MM:
        r = math.sqrt(v.co.x ** 2 + v.co.z ** 2) / (26.5 * MM)
        v.co.y -= 0.6 * MM * max(0.0, 1.0 - r * r)

# LED: Ø 2.4 mm, top centre of the button, child of the cap so it moves with it
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=1.2 * MM, radius2=1.2 * MM, depth=0.8 * MM)
bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
led = finish("LED", bm, MAT_LED, cap, location=(0, -4.5 * MM - 0.15 * MM, 20 * MM), smooth_angle=60)

# ---------- save .blend and export FBX for Unity ----------
blend_path = os.path.join(OUT, NAME + ".blend")
fbx_path = os.path.join(OUT, NAME + ".fbx")

bpy.ops.wm.save_as_mainfile(filepath=blend_path, copy=True)

bpy.ops.export_scene.fbx(
    filepath=fbx_path,
    use_selection=False,
    object_types={'EMPTY', 'MESH'},
    use_mesh_modifiers=True,
    apply_scale_options='FBX_SCALE_ALL',
    bake_space_transform=True,
    axis_forward='-Z',
    axis_up='Y',
    add_leaf_bones=False,
    path_mode='AUTO',
)

# ---------- preview render (white studio background) ----------
cam_data = bpy.data.cameras.new("PreviewCam")
cam_data.lens = 85
cam = bpy.data.objects.new("PreviewCam", cam_data)
scene.collection.objects.link(cam)
cam.location = (0.11, -0.30, 0.09)
target = Vector((0, -0.006, 0))
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
if bpy.app.version < (5, 0, 0):
    world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 0.7

scene.render.engine = 'CYCLES'
scene.cycles.samples = 96
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

# remove the preview helpers so the open scene only contains the asset
for n in ("PreviewCam", "Key", "Fill", "Rim"):
    ob = bpy.data.objects.get(n)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)

# select the asset and zoom the viewport to it (it is only 8 cm big)
try:
    for ob in scene.objects:
        ob.select_set(ob.name in (NAME, "Frame", "Insert", "Button_Cap", "LED"))
    bpy.context.view_layer.objects.active = root
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.view3d.view_selected()
except Exception:
    pass

print("KNX switch done ->", OUT)
