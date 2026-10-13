import bpy, os
from mathutils import Vector
out = r"D:\TelTech\Models\Roller_Shade\renders"
os.makedirs(out, exist_ok=True)
scn = bpy.context.scene
scn.render.engine = "BLENDER_WORKBENCH"
scn.display.shading.light = "STUDIO"
scn.display.shading.color_type = "MATERIAL"
scn.display.shading.show_shadows = True
scn.display.shading.show_cavity = True
scn.render.resolution_x, scn.render.resolution_y = 1200, 1400
scn.render.film_transparent = False
try:
    scn.world.color = (0.9, 0.9, 0.9)
except Exception:
    pass
cam = bpy.data.objects.get("Preview_Cam")
if cam is None:
    cam = bpy.data.objects.new("Preview_Cam", bpy.data.cameras.new("Preview_Cam"))
    scn.collection.objects.link(cam)
scn.camera = cam
ctrl = bpy.data.objects["Shade_Control"]
if ctrl.animation_data:
    ctrl.animation_data.action = None   # keep demo action off while rendering stills
def aim(loc, target, lens):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
shots = [("front", (0.25, -4.6, 1.15), (0.0, 0.0, 1.15), 32),
         ("detail", (0.45, -0.8, 0.75), (0.95, -0.02, 0.3), 35)]
for name, loc, tgt, lens in shots:
    aim(loc, tgt, lens)
    for p in (0, 50, 100):
        if name == "detail" and p == 50:
            continue
        ctrl["open_percent"] = float(p)
        bpy.context.view_layer.update()
        scn.render.filepath = os.path.join(out, f"{name}_{p:03d}.png")
        bpy.ops.render.render(write_still=True)
        print("rendered", scn.render.filepath)
bpy.ops.wm.revert_mainfile()
print("previews done")
