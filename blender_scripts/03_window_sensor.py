"""
Window with magnetic contact sensor (low-poly game asset for Unity XR)

Run in Blender: Scripting -> Open -> Run Script, or
  blender --background --python 03_window_sensor.py

Output: D:\\TelTech\\Models\\Window_Sensor\\Window_Sensor.blend / .fbx / _preview.png / _sensor_closeup.png

Hierarchy (real size, metres; 0.9 x 1.3 m, front = room side = Blender -Y; origin = bottom centre of the frame):
  Window_Sensor (empty)
   |- Frame            - fixed thick frame (70 x 70 mm profile)
   |- Hinges
   |- Sensor_Body      - magnetic contact sensor, fixed on the frame
   |- Sash             - THE MOVING PART. Origin = hinge axis (left edge).
   |    |                Open the window: rotate Sash around its local Z (Unity: local Y), 0..-90 deg
   |    |- Glass       - double glazing pane
   |    |- Handle      - origin = handle axis, rotate 90 deg to "unlock"
   |    |- Sensor_Magnet - moves with the sash; distance to Sensor_Body = open/closed
"""
import bpy, bmesh, os, math
from mathutils import Vector

OUT = r"D:\TelTech\Models\Window_Sensor"
os.makedirs(OUT, exist_ok=True)
NAME = "Window_Sensor"
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

def material(name, rgb, rough, metal=0.0, alpha=1.0, transmission=0.0):
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
            set_input(bsdf, ["IOR"], 1.45)
    return m

MAT_FRAME  = material("Window_Frame_Anthracite", (0.075, 0.08, 0.085), 0.5)
MAT_GLASS  = material("Window_Glass", (0.85, 0.93, 0.97), 0.02, alpha=0.25, transmission=1.0)
MAT_METAL  = material("Window_Handle_Alu", (0.75, 0.76, 0.78), 0.3, 1.0)
MAT_HINGE  = material("Window_Hinge", (0.12, 0.12, 0.13), 0.4, 1.0)
MAT_SENSOR = material("Sensor_White", (0.92, 0.92, 0.9), 0.45)
MAT_LED    = material("Sensor_LED", (0.1, 0.9, 0.3), 0.3)

# ---------- helpers ----------
def box_into(acc, center, size, bevel):
    """Add a bevelled box (world-space centre/size, relative to the object origin) into bmesh acc."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=3,
                        profile=0.5, affect='EDGES', clamp_overlap=True)
    me = bpy.data.meshes.new("tmp")
    bm.to_mesh(me)
    bm.free()
    acc.from_mesh(me)
    bpy.data.meshes.remove(me)

def cyl_into(acc, center, r, h, axis='Z', steps=16):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=steps, radius1=r, radius2=r, depth=h)
    if axis == 'Y':
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                         matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 3, 'X'))
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    me = bpy.data.meshes.new("tmp")
    bm.to_mesh(me)
    bm.free()
    acc.from_mesh(me)
    bpy.data.meshes.remove(me)

def make_object(name, bm, mat, parent, location=(0, 0, 0), smooth_angle=35):
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

# ---------- dimensions ----------
W, H = 0.90, 1.30          # outer frame
F, D = 0.07, 0.07          # frame profile width / depth
YF = -D / 2                # front (room side) face of the frame
GAP = 0.003
SX0, SX1 = -W / 2 + F + GAP, W / 2 - F - GAP     # sash outer x
SZ0, SZ1 = F + GAP, H - F - GAP                  # sash outer z
S, SD = 0.075, 0.06        # sash member width / depth
SY0, SY1 = YF, YF + SD     # sash front flush with frame front

root = bpy.data.objects.new(NAME, None)
root.empty_display_size = 0.2
scene.collection.objects.link(root)

# ---------- frame ----------
bm = bmesh.new()
box_into(bm, (0, 0, F / 2), (W, D, F), 0.004)                      # bottom
box_into(bm, (0, 0, H - F / 2), (W, D, F), 0.004)                  # top
box_into(bm, (-W / 2 + F / 2, 0, H / 2), (F, D, H - 2 * F + 0.002), 0.004)   # left
box_into(bm, (W / 2 - F / 2, 0, H / 2), (F, D, H - 2 * F + 0.002), 0.004)    # right
frame = make_object("Frame", bm, MAT_FRAME, root)

# ---------- hinges (left side, room side) ----------
bm = bmesh.new()
for z in (SZ0 + 0.12, SZ1 - 0.12):
    cyl_into(bm, (SX0 - 0.002, YF - 0.006, z), 0.007, 0.09)
hinges = make_object("Hinges", bm, MAT_HINGE, root)

# ---------- sash (origin on the hinge axis) ----------
PIV = Vector((SX0, YF, 0))              # hinge axis: left front edge of the sash
def L(x, y, z):                          # world -> sash-local
    return (x - PIV.x, y - PIV.y, z - PIV.z)

sy_c = (SY0 + SY1) / 2
sw, sh = SX1 - SX0, SZ1 - SZ0
bm = bmesh.new()
box_into(bm, L(0 + (SX0 + SX1) / 2, sy_c, SZ0 + S / 2), (sw, SD, S), 0.004)
box_into(bm, L((SX0 + SX1) / 2, sy_c, SZ1 - S / 2), (sw, SD, S), 0.004)
box_into(bm, L(SX0 + S / 2, sy_c, (SZ0 + SZ1) / 2), (S, SD, sh - 2 * S + 0.002), 0.004)
box_into(bm, L(SX1 - S / 2, sy_c, (SZ0 + SZ1) / 2), (S, SD, sh - 2 * S + 0.002), 0.004)
# thin glazing beads on the room side
BEAD = 0.015
gx0, gx1, gz0, gz1 = SX0 + S, SX1 - S, SZ0 + S, SZ1 - S
by = SY0 + 0.012
box_into(bm, L((gx0 + gx1) / 2, by, gz0 + BEAD / 2), (gx1 - gx0, 0.02, BEAD), 0.002)
box_into(bm, L((gx0 + gx1) / 2, by, gz1 - BEAD / 2), (gx1 - gx0, 0.02, BEAD), 0.002)
box_into(bm, L(gx0 + BEAD / 2, by, (gz0 + gz1) / 2), (BEAD, 0.02, gz1 - gz0), 0.002)
box_into(bm, L(gx1 - BEAD / 2, by, (gz0 + gz1) / 2), (BEAD, 0.02, gz1 - gz0), 0.002)
sash = make_object("Sash", bm, MAT_FRAME, root, location=tuple(PIV))

# glass pane (24 mm double glazing) - child of the sash
bm = bmesh.new()
box_into(bm, L((gx0 + gx1) / 2, sy_c + 0.008, (gz0 + gz1) / 2), (gx1 - gx0 + 0.02, 0.024, gz1 - gz0 + 0.02), 0.0)
glass = make_object("Glass", bm, MAT_GLASS, sash)

# ---------- handle (child of the sash, origin on its rotation axis) ----------
HX, HZ = SX1 - S / 2, (SZ0 + SZ1) / 2
hpiv = Vector((HX, SY0, HZ))
bm = bmesh.new()
box_into(bm, (0, -0.006, 0.0), (0.028, 0.012, 0.075), 0.004)            # rosette plate
cyl_into(bm, (0, -0.02, 0.012), 0.009, 0.022, axis='Y')                 # neck
box_into(bm, (0, -0.032, 0.012 - 0.055), (0.018, 0.016, 0.125), 0.006)  # lever pointing down = closed
handle = make_object("Handle", bm, MAT_METAL, sash, location=tuple(hpiv - PIV))

# ---------- magnetic contact sensor (top right) ----------
SZ_C = SZ1 - 0.25
# body on the fixed frame (right member), 16 x 12 x 70 mm
bm = bmesh.new()
box_into(bm, (0, 0, 0), (0.016, 0.012, 0.07), 0.003)
body = make_object("Sensor_Body", bm, MAT_SENSOR, root,
                   location=(W / 2 - F + 0.012, YF - 0.006, SZ_C))
bm = bmesh.new()
cyl_into(bm, (0, -0.006, 0.026), 0.0018, 0.0012, axis='Y', steps=12)
make_object("Sensor_LED", bm, MAT_LED, body, smooth_angle=60)
# magnet on the sash, 12 x 10 x 40 mm, ~8 mm gap
bm = bmesh.new()
box_into(bm, (0, 0, 0), (0.012, 0.010, 0.04), 0.0025)
magnet_world = Vector((SX1 - 0.010, YF - 0.005, SZ_C))
magnet = make_object("Sensor_Magnet", bm, MAT_SENSOR, sash, location=tuple(magnet_world - PIV))

# ---------- save + FBX ----------
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME + ".blend"), copy=True)
bpy.ops.export_scene.fbx(
    filepath=os.path.join(OUT, NAME + ".fbx"),
    use_selection=False, object_types={'EMPTY', 'MESH'}, use_mesh_modifiers=True,
    apply_scale_options='FBX_SCALE_ALL', bake_space_transform=True,
    axis_forward='-Z', axis_up='Y', add_leaf_bones=False, path_mode='AUTO')

# ---------- preview renders ----------
def area_light(name, loc, power, size, aim):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = power
    ld.size = size
    lo = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

C = (0, 0, 0.65)
area_light("Key", (-1.2, -2.0, 1.8), 220, 1.2, C)
area_light("Fill", (1.8, -1.5, 0.4), 70, 1.5, C)
area_light("Rim", (0.3, 1.5, 1.8), 80, 1.0, C)

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

cam_data = bpy.data.cameras.new("PreviewCam")
cam = bpy.data.objects.new("PreviewCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def shot(path, loc, target, lens):
    cam_data.lens = lens
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(OUT, path)
    bpy.ops.render.render(write_still=True)

shot(NAME + "_preview.png", (1.15, -3.2, 1.05), (0, 0, 0.65), 50)
shot(NAME + "_sensor_closeup.png", (0.62, -0.38, SZ_C + 0.12), (W / 2 - F, YF, SZ_C), 50)

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

print("Window with sensor done ->", OUT)
