# IVAR room (TalTech) — real layout, rebuilt from the LiDAR scan of 12.10.2026
# and the photos in Models/IVAR_Lab/renders/RoomPict.
# Coordinates: metres, Z up. Origin = floor corner where the entrance wall (X=0)
# meets the long wall with the dark sideboard (Y=0). Window wall at X=5.81,
# partition wall with the opening and the TV niche at Y=2.75.
import bpy, bmesh, math, os, traceback
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "Models", "IVAR_Lab")
SCAN = os.path.join(ROOT, "Scans", "IVAR_scan_2026-10-12.fbx")
LOG = []
def log(*a): LOG.append(" ".join(str(x) for x in a))

L, W, H = 5.81, 2.75, 2.91          # room interior length, width, ceiling height
SCAN_ANGLE = math.radians(36.6)      # scan -> room alignment (found from wall directions)
SCAN_OFFSET = (1.31, 2.0, 1.61)

def srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)

MATS = {}
def mat(name, color, rough=0.6, metal=0.0, emit=0.0, alpha=1.0):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name)
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*srgb(color), 1)
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["Metallic"].default_value = metal
    if emit:
        bs.inputs["Emission Color"].default_value = (*srgb(color), 1)
        bs.inputs["Emission Strength"].default_value = emit
    if alpha < 1:
        bs.inputs["Alpha"].default_value = alpha
        if hasattr(m, "surface_render_method"): m.surface_render_method = "BLENDED"
    m.diffuse_color = (*srgb(color), alpha)
    MATS[name] = m
    return m

COLLS = {}
def coll(name):
    if name not in COLLS:
        c = bpy.data.collections.new(name); ROOTC.children.link(c); COLLS[name] = c
    return COLLS[name]

def box(name, c, m, x0, x1, y0, y1, z0, z1):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 + (v.co.x + 0.5) * (x1 - x0)
        v.co.y = y0 + (v.co.y + 0.5) * (y1 - y0)
        v.co.z = z0 + (v.co.z + 0.5) * (z1 - z0)
    bm.to_mesh(me); bm.free(); me.materials.append(m)
    ob = bpy.data.objects.new(name, me); coll(c).objects.link(ob)
    return ob

def cyl(name, c, m, x, y, z0, z1, r, seg=24, axis="Z"):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=z1 - z0)
    bm.to_mesh(me); bm.free(); me.materials.append(m)
    for p in me.polygons: p.use_smooth = len(p.vertices) == 4
    ob = bpy.data.objects.new(name, me); coll(c).objects.link(ob)
    ob.location = (x, y, (z0 + z1) / 2)
    return ob

def join(objs, name):
    """Join several objects into one (keeps the first object's collection)."""
    ctx = {"active_object": objs[0], "selected_editable_objects": objs, "selected_objects": objs}
    with bpy.context.temp_override(**ctx):
        bpy.ops.object.join()
    objs[0].name = name; objs[0].data.name = name
    return objs[0]

def props(ob, name_uk, desc, zone):
    ob["name_uk"] = name_uk; ob["description"] = desc; ob["zone"] = zone
    return ob

def text(name, c, body, size, loc, rot, color):
    cu = bpy.data.curves.new(name, "FONT"); cu.body = body; cu.size = size; cu.align_x = "CENTER"
    ob = bpy.data.objects.new(name, cu); coll(c).objects.link(ob)
    ob.location = loc; ob.rotation_euler = rot; cu.materials.append(mat("txt_" + color, color))
    return ob

def build():
    global ROOTC
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections): bpy.data.collections.remove(c)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.lights, bpy.data.cameras):
        for d in list(blk):
            if d.users == 0: blk.remove(d)
    sc = bpy.context.scene
    ROOTC = bpy.data.collections.new("IVAR_Room"); sc.collection.children.link(ROOTC)

    wall = mat("wall_white", "#ecebe6", 0.85)
    floor_m = mat("floor_terrazzo", "#a9a7a1", 0.35)
    base_m = mat("baseboard_grey", "#6e6f70", 0.5)
    ceil_m = mat("ceiling_tiles", "#f2f2ef", 0.95)
    grid_m = mat("ceiling_grid", "#d4d5d2", 0.6)
    led = mat("led_panel", "#ffffff", 0.3, emit=3.0)
    pink = mat("door_pink", "#d0207a", 0.45)
    glass = mat("glass", "#cfe3f2", 0.05, alpha=0.2)
    white = mat("white_plastic", "#f4f4f1", 0.45)
    dark = mat("sideboard_anthracite", "#2e2c2b", 0.5)
    handle = mat("aluminium", "#b9bec2", 0.3, 0.8)
    black = mat("black", "#151618", 0.4)
    screen = mat("screen_off", "#0b0d10", 0.2, 0.3)
    desk_top = mat("desk_white", "#e9e9e6", 0.5)
    steel = mat("steel_dark", "#3b3d40", 0.4, 0.6)
    fabric = mat("chair_fabric", "#25272b", 0.9)
    chrome = mat("chrome", "#d8dcdf", 0.15, 1.0)
    osb = mat("osb_board", "#c49558", 0.8)
    wood = mat("wood_dark", "#5c3a24", 0.6)
    radiator = mat("radiator_white", "#f1f1ee", 0.4)
    frame = mat("window_frame", "#fafafa", 0.4)

    # ---------------- room shell ----------------
    S = "Приміщення"
    box("Floor", S, floor_m, 0, L, 0, W, -0.02, 0)
    t = 0.12
    box("Wall_Sideboard", S, wall, 0, L, -t, 0, 0, H)                       # long wall Y=0
    # partition Y=W with opening X 0.79..2.24 (h 2.30) and TV niche X 2.95..4.25
    box("Wall_Partition_a", S, wall, -t, 0.79, W, W + t, 0, H)
    box("Wall_Partition_b", S, wall, 2.24, 2.95, W, W + t, 0, H)
    box("Wall_Partition_c", S, wall, 4.25, L + t, W, W + t, 0, H)
    box("Wall_Partition_lintel", S, wall, 0.79, 2.24, W, W + t, 2.30, H)
    box("Wall_Partition_niche_low", S, wall, 2.95, 4.25, W, W + t, 0, 1.05)
    box("Wall_Partition_niche_high", S, wall, 2.95, 4.25, W, W + t, 1.95, H)
    box("Wall_Partition_niche_back", S, wall, 2.95, 4.25, W + t - 0.02, W + t, 1.05, 1.95)
    # entrance wall X=0 with door opening Y 1.25..2.40 (h 2.25)
    box("Wall_Entrance_a", S, wall, -t, 0, -t, 1.25, 0, H)
    box("Wall_Entrance_b", S, wall, -t, 0, 2.40, W + t, 0, H)
    box("Wall_Entrance_lintel", S, wall, -t, 0, 1.25, 2.40, 2.25, H)
    # window wall X=L, deep reveal (0.40 m) with window Y 0.40..1.80, sill 0.90, top 2.75
    R = 0.40
    box("Wall_Window_a", S, wall, L, L + R + 0.1, -t, 0.40, 0, H)
    box("Wall_Window_b", S, wall, L, L + R + 0.1, 1.80, W + t, 0, H)
    box("Wall_Window_below", S, wall, L, L + R + 0.1, 0.40, 1.80, 0, 0.88)
    box("Wall_Window_above", S, wall, L, L + R + 0.1, 0.40, 1.80, 2.75, H)
    box("Window_sill", S, frame, L, L + R, 0.38, 1.82, 0.88, 0.92)
    # window frame + glass (two lower casements + transom)
    gx = L + R - 0.05
    fr = [box("Window_frame_%d" % i, S, frame, gx - 0.03, gx + 0.03, *yz) for i, yz in enumerate([
        (0.40, 0.46, 0.92, 2.75), (1.74, 1.80, 0.92, 2.75), (1.07, 1.13, 0.92, 2.75),
        (0.40, 1.80, 0.92, 0.98), (0.40, 1.80, 2.69, 2.75), (0.40, 1.80, 2.15, 2.21),
        (0.63, 0.67, 2.21, 2.69), (1.53, 1.57, 2.21, 2.69)])]
    join(fr, "Window_frame")
    box("Window_glass", S, glass, gx - 0.005, gx + 0.005, 0.46, 1.74, 0.98, 2.69)
    # baseboards
    bb = [box("bb%d" % i, S, base_m, *a) for i, a in enumerate([
        (0, L, 0, 0.012, 0, 0.07), (0, 0.79, W - 0.012, W, 0, 0.07), (2.24, L, W - 0.012, W, 0, 0.07),
        (0, 0.012, 0, 1.25, 0, 0.07), (0, 0.012, 2.40, W, 0, 0.07),
        (L - 0.012, L, 0, 0.40, 0, 0.07), (L - 0.012, L, 1.80, W, 0, 0.07)])]
    join(bb, "Baseboards")
    # short floor + back wall beyond the opening (hint of the neighbouring lab)
    box("Neighbour_lab_floor", S, floor_m, 0.3, 2.8, W + t, W + 2.2, -0.02, 0)

    # ---------------- ceiling ----------------
    C = "Стеля"
    box("Ceiling", C, ceil_m, 0, L, 0, W, H, H + 0.02)
    g = []
    x = 0.3
    while x < L:
        g.append(box("cg", C, grid_m, x - 0.012, x + 0.012, 0, W, H - 0.012, H)); x += 0.6
    y = 0.18
    while y < W:
        g.append(box("cg", C, grid_m, 0, L, y - 0.012, y + 0.012, H - 0.012, H)); y += 0.6
    join(g, "Ceiling_grid")
    for i, cx in enumerate((1.0, 2.8, 4.6)):
        box("LED_panel_%d" % (i + 1), C, led, cx - 0.29, cx + 0.29, 1.09, 1.67, H - 0.02, H - 0.012)
    box("Air_diffuser", C, white, 3.42, 3.98, 1.09, 1.67, H - 0.06, H - 0.012)
    props(cyl("KNX_presence_sensor", C, white, 1.9, 0.95, H - 0.05, H - 0.01, 0.09, 32),
          "Датчик присутності на стелі", "Круглий стельовий датчик (присутність/освітленість), видно на фото стелі.", "ceiling")
    cyl("Smoke_detector", C, white, 4.1, 0.6, H - 0.06, H - 0.01, 0.05, 24)

    # ---------------- entrance: door, electrical boxes, cable ducts ----------------
    E = "Вхід"
    fr = [box("df%d" % i, E, pink, *a) for i, a in enumerate([
        (-0.13, 0.01, 1.20, 1.25, 0, 2.30), (-0.13, 0.01, 2.40, 2.45, 0, 2.30), (-0.13, 0.01, 1.20, 2.45, 2.25, 2.30)])]
    join(fr, "Door_frame")
    # door leaf opened outwards (into the corridor)
    leaf = [box("dl0", E, pink, -1.10, -0.14, 2.36, 2.40, 0.01, 2.24)]
    leaf.append(box("dl1", E, glass, -0.95, -0.30, 2.355, 2.405, 0.9, 2.05))
    props(join(leaf, "Door_leaf"), "Двері (рожеві)", "Вхідні двері з коридору, відчинені назовні.", "entrance")
    for i, (y0, y1) in enumerate(((0.30, 0.74), (0.80, 1.24))):
        b = box("Electrical_box_%d" % (i + 1), E, white, 0.0, 0.13, y0, y1, 1.22, 1.98)
        props(b, "Електрощиток %d" % (i + 1), "Білий настінний щиток біля входу (ймовірно, щиток живлення/KNX).", "entrance")
        box("Cable_duct_v%d" % (i + 1), E, white, 0.0, 0.05, (y0 + y1) / 2 - 0.05, (y0 + y1) / 2 + 0.05, 1.98, H)
    box("Cable_duct_long_wall", E, white, 0.0, L, 0.0, 0.05, 1.08, 1.16)

    # ---------------- sideboard + KNX stand ----------------
    K = "Тумба і KNX-стенд"
    x0, x1, d, h = 0.61, 3.01, 0.62, 0.93
    parts = [box("sb_body", K, dark, x0, x1, 0.0, d - 0.02, 0.08, h - 0.03),
             box("sb_top", K, dark, x0 - 0.01, x1 + 0.01, 0.0, d, h - 0.03, h),
             box("sb_plinth", K, steel, x0 + 0.02, x1 - 0.02, 0.02, d - 0.06, 0.0, 0.08)]
    n = 4; w = (x1 - x0) / n
    for i in range(n):
        a = x0 + i * w + 0.004; b = x0 + (i + 1) * w - 0.004
        if i in (1, 2):
            for j, (z0, z1) in enumerate(((0.10, 0.36), (0.37, 0.62), (0.63, 0.88))):
                parts.append(box("dr", K, dark, a, b, d - 0.02, d, z0, z1))
                parts.append(box("hd", K, handle, a + 0.03, b - 0.03, d, d + 0.012, z1 - 0.03, z1 - 0.02))
        else:
            parts.append(box("dr", K, dark, a, b, d - 0.02, d, 0.10, 0.88))
            parts.append(box("hd", K, handle, b - 0.04 if i == 0 else a + 0.03, b - 0.03 if i == 0 else a + 0.04, d, d + 0.012, 0.3, 0.75))
    props(join(parts, "Sideboard"), "Тумба (антрацит)", "Довга темна тумба вздовж стіни, ~2,4 × 0,62 м, висота 0,93 м. На ній стоїть KNX-стенд.", "sideboard")

    # KNX demo stand (OSB board with devices) at the entrance end of the sideboard
    st = []
    st.append(box("knx_base", K, wood, -0.28, 0.28, -0.13, 0.13, 0.0, 0.04))
    st.append(box("knx_rest", K, wood, -0.28, 0.28, 0.06, 0.09, 0.04, 0.12))
    st.append(box("knx_board", K, osb, -0.27, 0.27, -0.03, -0.01, 0.04, 0.72))
    st.append(box("knx_back_leg", K, wood, -0.05, 0.05, -0.01, 0.06, 0.04, 0.5))
    dev = [((-0.17, 0.60), (0.13, 0.13), white, "fan"), ((0.0, 0.62), (0.14, 0.08), white, "relay"),
           ((0.16, 0.58), (0.10, 0.16), white, "lamp1"), ((-0.08, 0.30), (0.10, 0.16), white, "lamp2"),
           ((0.04, 0.48), (0.07, 0.06), white, "thermostat"), ((0.14, 0.46), (0.05, 0.05), white, "switch"),
           ((0.10, 0.24), (0.14, 0.10), black, "touch_panel")]
    for (cx, cz), (sw, sh), m, nm in dev:
        st.append(box("knx_" + nm, K, m, cx - sw / 2, cx + sw / 2, -0.09 if nm.startswith("lamp") else -0.055, -0.03, cz - sh / 2, cz + sh / 2))
    knx = join(st, "KNX_stand")
    knx.location = (0.95, 0.30, h)
    knx.rotation_euler = (0, 0, math.radians(125))
    props(knx, "KNX-стенд (демо)", "Навчальний стенд «розумного будинку» на OSB-панелі: вентилятор, два світильники, реле, термостат, вимикачі, сенсорна панель. Детальні моделі пристроїв — у Models/<Device>.", "sideboard")

    # ---------------- window corner: desk, chairs, monitor, radiator ----------------
    D = "Стіл біля вікна"
    dx0, dx1, dy0, dy1 = 4.71, 5.71, 1.50, 2.75
    dk = [box("desk_top", D, desk_top, dx0, dx1, dy0, dy1 - 0.01, 0.715, 0.74)]
    for lx in (dx0 + 0.03, dx1 - 0.06):
        for ly in (dy0 + 0.03, dy1 - 0.06):
            dk.append(box("leg", D, steel, lx, lx + 0.03, ly, ly + 0.03, 0, 0.715))
    props(join(dk, "Desk"), "Стіл біля вікна", "Білий стіл ~1,0 × 1,25 м у куті біля вікна та перегородки.", "window")
    mon = [box("mon_screen", D, black, 5.48, 5.52, 1.82, 2.42, 0.86, 1.22), box("mon_panel", D, screen, 5.475, 5.48, 1.84, 2.40, 0.88, 1.20),
           box("mon_stand", D, black, 5.50, 5.56, 2.08, 2.16, 0.74, 0.86), box("mon_foot", D, black, 5.45, 5.62, 2.02, 2.22, 0.74, 0.755)]
    props(join(mon, "Monitor"), "Монітор", "Монітор на столі біля вікна.", "window")
    cyl("Webcam", D, white, 5.25, 2.55, 0.74, 0.82, 0.04, 16)
    for i, cy in enumerate((1.78, 2.38)):
        ch = [box("seat", D, fabric, -0.22, 0.22, -0.22, 0.22, 0.44, 0.50), box("back", D, fabric, -0.26, -0.22, -0.21, 0.21, 0.55, 0.88)]
        for sx in (-0.19, 0.19):
            ch.append(box("fl", D, chrome, sx - 0.01, sx + 0.01, -0.2, 0.2, 0.0, 0.02))
            ch.append(box("lg", D, chrome, sx - 0.01, sx + 0.01, -0.01, 0.01, 0.0, 0.44))
            ch.append(box("bl", D, chrome, -0.25, -0.23, sx - 0.01, sx + 0.01, 0.44, 0.75))
        o = join(ch, "Chair_%d" % (i + 1)); o.location = (4.48, cy, 0)
        props(o, "Стілець", "Офісний стілець на полозах.", "window")
    rd = [box("rad_%d" % k, D, radiator, L - 0.16, L - 0.06, 0.55 + k * 0.073, 0.55 + k * 0.073 + 0.055, 0.14, 0.74) for k in range(15)]
    rd.append(box("rad_pipe", D, radiator, L - 0.12, L - 0.09, 0.5, 2.3, 0.70, 0.73))
    props(join(rd, "Radiator"), "Радіатор", "Чавунний радіатор під вікном.", "window")

    # ---------------- TV in the partition niche ----------------
    T = "Перегородка і ТВ"
    tv = [box("tv_body", T, black, 3.05, 4.15, W - 0.02, W + 0.04, 1.15, 1.80), box("tv_panel", T, screen, 3.08, 4.12, W - 0.025, W - 0.02, 1.18, 1.77)]
    props(join(tv, "TV"), "Телевізор у ніші", "Телевізор ~50\" у ніші перегородки між кімнатою та сусідньою лабораторією.", "partition")

    # ---------------- reference: imported LiDAR scan (hidden) ----------------
    if os.path.exists(SCAN):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=SCAN)
        new = [o for o in bpy.data.objects if o not in before]
        rc = coll("Скан LiDAR (референс)")
        for o in new:
            for c in list(o.users_collection): c.objects.unlink(o)
            rc.objects.link(o)
            if o.type == "MESH":
                o.data.transform(o.matrix_world); o.matrix_world = Matrix.Identity(4)
                ext = max(o.dimensions)
                if ext < 1.0:   # imported as centimetres -> scale to metres
                    o.data.transform(Matrix.Scale(100.0, 4))
                o.data.transform(Matrix.Translation(SCAN_OFFSET) @ Matrix.Rotation(-SCAN_ANGLE, 4, "Z"))
                o.name = "LiDAR_scan"
                log("scan dims", tuple(round(v, 2) for v in o.dimensions))
        rc.hide_render = True
    else:
        log("scan not found", SCAN)

    # ---------------- lights, cameras, render ----------------
    LC = coll("Світло і камери")
    wd = bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); sc.world = wd
    bg = wd.node_tree.nodes.get("Background")
    if bg: bg.inputs[0].default_value = (*srgb("#dfe4e8"), 1); bg.inputs[1].default_value = 0.6
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); LC.objects.link(sun)
    sun.data.energy = 2.5; sun.rotation_euler = (math.radians(55), 0, math.radians(100))
    for i, cx in enumerate((1.0, 2.8, 4.6)):
        a = bpy.data.objects.new("Area_%d" % i, bpy.data.lights.new("Area_%d" % i, "AREA")); LC.objects.link(a)
        a.data.energy = 90; a.data.size = 0.6; a.location = (cx, 1.38, H - 0.05)
    def cam(name, loc, tgt, lens=18, ortho=None):
        cd = bpy.data.cameras.new(name); cd.lens = lens
        if ortho: cd.type = "ORTHO"; cd.ortho_scale = ortho
        co = bpy.data.objects.new(name, cd); LC.objects.link(co); co.location = loc
        co.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return co
    c_over = cam("Cam_Overview", (7.5, -3.2, 5.6), (2.6, 1.4, 0.6), 24)
    c_plan = cam("Cam_Plan", (L / 2, W / 2 + 0.5, 12), (L / 2, W / 2 + 0.5, 0), ortho=7.6); c_plan.rotation_euler = (0, 0, 0)
    c_door = cam("Cam_From_Window", (5.3, 0.9, 1.6), (0.0, 1.2, 1.1), 16)
    c_knx = cam("Cam_KNX_Stand", (2.6, 1.6, 1.55), (0.95, 0.3, 1.2), 22)
    r = sc.render
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try: r.engine = eng; break
        except Exception: pass
    r.resolution_x, r.resolution_y = 1600, 1000
    rdir = os.path.join(OUT, "renders"); os.makedirs(rdir, exist_ok=True)
    ceil = COLLS["Стеля"]
    for nm, c, hide in (("v2_overview", c_over, True), ("v2_plan", c_plan, True), ("v2_from_window", c_door, False), ("v2_knx_stand", c_knx, False)):
        ceil.hide_render = hide; sc.camera = c
        cut = nm == "v2_overview"   # cut-away: hide the two walls nearest to the overview camera
        for o in bpy.data.objects:
            if o.name.startswith(("Wall_Sideboard", "Wall_Window", "Window_", "Cable_duct_long")):
                o.hide_render = cut
        r.filepath = os.path.join(rdir, nm + ".png"); bpy.ops.render.render(write_still=True); log("rendered", nm)
    for o in bpy.data.objects: o.hide_render = False
    ceil.hide_render = False
    sc.camera = c_over
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.type = "MATERIAL"
    path = os.path.join(OUT, "ivar-lab-taltech.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
    log("saved", path, "objects", len(bpy.data.objects))

try:
    build(); log("OK")
except Exception:
    log("ERROR\n" + traceback.format_exc())
finally:
    open(os.path.join(OUT, "build_log_v2.txt"), "w", encoding="utf-8").write("\n".join(LOG))
    print("\n".join(LOG))
