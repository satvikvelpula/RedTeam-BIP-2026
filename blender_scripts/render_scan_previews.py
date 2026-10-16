# Renders preview images of the raw LiDAR scan (Scans/IVAR_scan_2026-10-12.fbx) before modelling.
import bpy, os, math
from mathutils import Vector
REPO = r"D:\TelTech"
OUT = os.path.join(REPO, "Models", "IVAR_Lab", "renders", "scan")
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(REPO, "Scans", "IVAR_scan_2026-10-12.fbx"))
sc = bpy.context.scene
meshes = [o for o in sc.objects if o.type == "MESH"]
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
ctr, size = (lo + hi) / 2, hi - lo
print("scan bbox size:", tuple(round(v, 2) for v in size), "meshes:", len(meshes))
# info: are there textures?
print("images:", [i.name for i in bpy.data.images], "materials:", [m.name for m in bpy.data.materials])
world = bpy.data.worlds.new("W"); sc.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.87, 0.88, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
try:
    sc.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
sc.view_settings.view_transform = "Standard"
tgt = bpy.data.objects.new("Target", None); sc.collection.objects.link(tgt); tgt.location = ctr
r = max(size.x, size.y)
views = {
    "overview": ctr + Vector((size.x * 0.9, -size.y * 0.9, size.z * 1.6 + r * 0.4)),
    "overview2": ctr + Vector((-size.x * 0.9, size.y * 0.9, size.z * 1.6 + r * 0.4)),
    "top": ctr + Vector((0, 0, r * 1.6 + size.z)),
}
for name, loc in views.items():
    cam = bpy.data.objects.new("Cam_" + name, bpy.data.cameras.new(name)); sc.collection.objects.link(cam)
    cam.location = loc
    c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
    cam.data.lens = 28
    sc.camera = cam
    sc.render.filepath = os.path.join(OUT, "scan_" + name + ".png")
    bpy.ops.render.render(write_still=True)
    print("saved", sc.render.filepath)
