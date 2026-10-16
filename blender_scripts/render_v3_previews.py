# Renders preview images of the newer IVAR room version (from git object of commit "Room update").
# Step 1: exec with STEP=1 opens the file; Step 2: exec with STEP=2 renders every camera.
import bpy, os, zlib, tempfile
REPO = r"D:\TelTech"
OUT = os.path.join(REPO, "Models", "IVAR_Lab", "renders", "v3")
TMP = os.path.join(tempfile.gettempdir(), "ivar_room_v3.blend")
if STEP == 1:
    raw = zlib.decompress(open(os.path.join(REPO, ".git", "objects", "32", "98c9d67fd503197554fa0d8e3818bcc10b3c56"), "rb").read())
    open(TMP, "wb").write(raw.split(b"\0", 1)[1])
    bpy.ops.wm.open_mainfile(filepath=TMP)
else:
    os.makedirs(OUT, exist_ok=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1600, 1000, 100
    if sc.render.engine == "CYCLES":
        sc.cycles.samples = 48
        try: sc.cycles.use_denoising = True
        except Exception: pass
    cams = [o for o in sc.objects if o.type == "CAMERA"]
    print("cameras:", [c.name for c in cams], "engine:", sc.render.engine)
    for c in cams:
        sc.camera = c
        sc.render.filepath = os.path.join(OUT, "v3_" + c.name.lower().replace(" ", "_") + ".png")
        bpy.ops.render.render(write_still=True)
        print("saved", sc.render.filepath)
