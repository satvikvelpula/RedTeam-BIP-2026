"""
Рулонна шторка з приводом Aqara (Roller Shade Driver E1) для вікна лабораторії TalTech.
Робоча модель для Blender 3.6 / 4.x.

ЯК ЗАПУСТИТИ
  1. Blender -> вкладка Scripting -> Open -> цей файл -> Run Script (Alt+P).
  2. Виберіть об'єкт "Shade_Control" -> N-панель -> Item -> Properties ->
     повзунок "open_percent" (0 = закрито, 100 = відкрито, як position у Home Assistant).
  3. Або натисніть Space: на таймлайні вже є демо-анімація відкрити/закрити.

ЩО ПРАЦЮЄ
  * Тканина, нижня планка й товщина рулону керуються одним shape key "Open".
  * Труба з ланцюговим колесом обертається драйвером синхронно з тканиною.
  * Експорт .glb: shape key стає blendshape "Open" (0..100 у Unity).

Повторний запуск перебудовує модель (видаляє лише об'єкти з колекцій
"Roller_Shade" і "Window_Context").
"""
import bpy
import bmesh
import math
from mathutils import Vector, Matrix

# ---------------- розміри, м ----------------
# Виміряно (фото із замірами):
OPEN_W = 1.68          # ширина віконного прорізу по підвіконню
OPEN_H = 2.11          # від підвіконня до верху прорізу
# Оцінено з фото (похибка ~3-5 см):
SHADE_W = 1.82         # ширина тканини (заходить ~7 см за проріз з кожного боку)
TUBE_L = 1.88          # довжина труби
ROLL_Z = 2.24          # висота осі труби над підвіконням
ROLL_Y = -0.075        # відстань осі від стіни (кімната = -Y)
TUBE_R = 0.020
ROLL_R_CLOSED = 0.026  # радіус рулону, коли штора опущена
ROLL_R_OPEN = 0.040    # радіус рулону, коли тканина вся намотана
BOTTOM_STOP = 0.03     # нижня планка в закритому стані над підвіконням
BAR_H, BAR_T = 0.030, 0.012
FABRIC_ROWS = 24
DRIVER_Z = 0.19        # центр приводу Aqara над підвіконням
WALL_T = 0.40
WINDOW_Y = 0.16        # глибина, на якій стоїть рама
FLOOR_Z = -0.85
CEIL_Z = 2.33

BUILD_CONTEXT = True   # стіна, рама, скло, підвіконня
EXPORT_GLB = r"D:\TelTech\Models\Roller_Shade\Roller_Shade.glb"  # "" = не експортувати
SAVE_BLEND = r"D:\TelTech\Models\Roller_Shade\Roller_Shade.blend"  # "" = не зберігати

WHEEL_X = TUBE_L / 2 + 0.0075   # ланцюгове колесо і привід праворуч


# ---------------- допоміжні функції ----------------
def get_coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    else:
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    return c


def make_mat(name, rgb, rough=0.5, metal=0.0, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, alpha)
    m.use_backface_culling = False
    try:
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (*rgb, 1.0)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        b.inputs["Alpha"].default_value = alpha
    except Exception:
        pass
    if alpha < 1.0:
        for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED")):
            try:
                setattr(m, attr, val)
            except Exception:
                pass
    return m


def obj_from_bm(name, bm, material, coll, smooth_axis=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    if smooth_axis is not None:
        ax = Vector(smooth_axis)
        for p in me.polygons:
            p.use_smooth = abs(p.normal.dot(ax)) < 0.5
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def box(name, size, loc, material, coll):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(loc), verts=bm.verts)
    return obj_from_bm(name, bm, material, coll)


def add_cyl(bm, r, length, seg, rot=None, center=(0, 0, 0)):
    res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                                radius1=r, radius2=r, depth=length)
    v = res["verts"]
    if rot is not None:
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=rot, verts=v)
    bmesh.ops.translate(bm, vec=Vector(center), verts=v)


ROT_X_AXIS = Matrix.Rotation(math.pi / 2, 3, "Y")   # циліндр уздовж X
ROT_Y_AXIS = Matrix.Rotation(math.pi / 2, 3, "X")   # циліндр уздовж Y


def cyl_between(name, p1, p2, r, material, coll, seg=6):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bm = bmesh.new()
    rot = d.to_track_quat("Z", "Y").to_matrix()
    add_cyl(bm, r, d.length, seg, rot, (p1 + p2) / 2)
    return obj_from_bm(name, bm, material, coll, smooth_axis=d.normalized())


def add_prop_driver(owner, path, index, ctrl, expr):
    fc = owner.driver_add(path, index) if index is not None else owner.driver_add(path)
    drv = fc.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "p"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = ctrl
    var.targets[0].data_path = '["open_percent"]'
    drv.expression = expr


# ---------------- матеріали ----------------
M_FABRIC = make_mat("Shade_Fabric", (0.72, 0.72, 0.70), rough=0.9)
M_ALU = make_mat("Shade_Aluminium", (0.85, 0.85, 0.85), rough=0.35, metal=0.6)
M_PLASTIC = make_mat("White_Plastic", (0.92, 0.92, 0.90), rough=0.4)
M_GREY = make_mat("Grey_Plastic", (0.55, 0.55, 0.55), rough=0.5)
M_WALL = make_mat("Wall", (0.86, 0.83, 0.77), rough=0.9)
M_FRAME = make_mat("PVC_Frame", (0.95, 0.95, 0.95), rough=0.3)
M_GLASS = make_mat("Glass", (0.70, 0.85, 0.95), rough=0.05, alpha=0.2)

if "Cube" in bpy.data.objects:
    bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True)
shade = get_coll("Roller_Shade")

# ---------------- тканина + планка + рулон (одна сітка, shape key "Open") ----------------
GAP = ROLL_R_OPEN * 0.85                       # планка зупиняється трохи нижче рулону
fab_bot_c = BOTTOM_STOP + BAR_H * 0.5
fab_bot_o = ROLL_Z - GAP - BAR_H * 0.5
y_c = ROLL_Y - ROLL_R_CLOSED
y_o = ROLL_Y - ROLL_R_OPEN
hw = SHADE_W / 2

vc, vo, faces, mat_idx = [], [], [], []

# тканина
for i in range(FABRIC_ROWS):
    t = i / (FABRIC_ROWS - 1)
    zc = ROLL_Z + t * (fab_bot_c - ROLL_Z)
    zo = ROLL_Z + t * (fab_bot_o - ROLL_Z)
    for x in (-hw, hw):
        vc.append((x, y_c, zc))
        vo.append((x, y_o, zo))
for i in range(FABRIC_ROWS - 1):
    a = i * 2
    faces.append((a, a + 1, a + 3, a + 2))
    mat_idx.append(0)

# нижня планка
base = len(vc)
bx = hw + 0.005
dz = (ROLL_Z - GAP - BAR_H) - BOTTOM_STOP
for x in (-bx, bx):
    for y in (-BAR_T / 2, BAR_T / 2):
        for z in (0.0, BAR_H):
            vc.append((x, y_c + y, BOTTOM_STOP + z))
            vo.append((x, y_o + y, BOTTOM_STOP + z + dz))
# індекси: x(0/1)*4 + y(0/1)*2 + z(0/1)
for f in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
    faces.append(tuple(base + k for k in f))
    mat_idx.append(1)

# рулон намотаної тканини
SEG = 32
base = len(vc)
for x in (-hw, hw):
    for s in range(SEG):
        a = 2 * math.pi * s / SEG
        ca, sa = math.cos(a), math.sin(a)
        vc.append((x, ROLL_Y + ROLL_R_CLOSED * ca, ROLL_Z + ROLL_R_CLOSED * sa))
        vo.append((x, ROLL_Y + ROLL_R_OPEN * ca, ROLL_Z + ROLL_R_OPEN * sa))
cl = len(vc); vc.append((-hw, ROLL_Y, ROLL_Z)); vo.append((-hw, ROLL_Y, ROLL_Z))
cr = len(vc); vc.append((hw, ROLL_Y, ROLL_Z)); vo.append((hw, ROLL_Y, ROLL_Z))
roll_side_start = len(faces)
for s in range(SEG):
    n = (s + 1) % SEG
    faces.append((base + s, base + n, base + SEG + n, base + SEG + s)); mat_idx.append(0)
roll_side_end = len(faces)
for s in range(SEG):
    n = (s + 1) % SEG
    faces.append((cl, base + n, base + s)); mat_idx.append(0)
    faces.append((cr, base + SEG + s, base + SEG + n)); mat_idx.append(0)

me = bpy.data.meshes.new("Shade_Fabric")
me.from_pydata(vc, [], faces)
me.update()
me.materials.append(M_FABRIC)
me.materials.append(M_ALU)
for p, mi in zip(me.polygons, mat_idx):
    p.material_index = mi
for p in me.polygons[roll_side_start:roll_side_end]:
    p.use_smooth = True
fabric = bpy.data.objects.new("Shade_Fabric", me)
shade.objects.link(fabric)

fabric.shape_key_add(name="Basis", from_mix=False)
key_open = fabric.shape_key_add(name="Open", from_mix=False)
for i, co in enumerate(vo):
    key_open.data[i].co = co
key_open.slider_min, key_open.slider_max = 0.0, 1.0

# ---------------- труба з ланцюговим колесом ----------------
bm = bmesh.new()
add_cyl(bm, TUBE_R, TUBE_L, 24, ROT_X_AXIS)
add_cyl(bm, 0.024, 0.012, 8, ROT_X_AXIS, (-(TUBE_L / 2 + 0.006), 0, 0))   # заглушка ліворуч
tube = obj_from_bm("Shade_Tube", bm, M_PLASTIC, shade, smooth_axis=(1, 0, 0))
tube.location = (0, ROLL_Y, ROLL_Z)

bm = bmesh.new()
add_cyl(bm, 0.032, 0.015, 8, ROT_X_AXIS)        # восьмигранне колесо: обертання видно
wheel = obj_from_bm("Shade_ChainWheel", bm, M_GREY, shade)
wheel.parent = tube
wheel.location = (WHEEL_X, 0, 0)

# ---------------- кронштейни ----------------
br_depth = 0.035 - ROLL_Y
for name, x in (("Shade_Bracket_L", -(TUBE_L / 2 + 0.022)), ("Shade_Bracket_R", WHEEL_X + 0.0175)):
    box(name, (0.02, br_depth, 0.09), (x, -br_depth / 2, ROLL_Z + 0.01), M_PLASTIC, shade)

# ---------------- привід Aqara E1 і ланцюг ----------------
DRV_D = 0.030
drv_y = -DRV_D / 2 - 0.001
box("Aqara_Driver_E1", (0.042, DRV_D, 0.19), (WHEEL_X, drv_y, DRIVER_Z), M_PLASTIC, shade)
bm = bmesh.new()
front = drv_y - DRV_D / 2 - 0.0015
add_cyl(bm, 0.008, 0.003, 16, ROT_Y_AXIS, (WHEEL_X, front, DRIVER_Z - 0.03))
add_cyl(bm, 0.008, 0.003, 16, ROT_Y_AXIS, (WHEEL_X, front, DRIVER_Z - 0.065))
obj_from_bm("Aqara_Driver_Buttons", bm, M_GREY, shade)

drv_top = DRIVER_Z + 0.095
cyl_between("Shade_Chain_Front", (WHEEL_X, ROLL_Y - 0.032, ROLL_Z),
            (WHEEL_X, drv_y - 0.007, drv_top), 0.0018, M_GREY, shade)
cyl_between("Shade_Chain_Back", (WHEEL_X, ROLL_Y + 0.032, ROLL_Z),
            (WHEEL_X, drv_y + 0.007, drv_top), 0.0018, M_GREY, shade)

# ---------------- керування ----------------
ctrl = bpy.data.objects.new("Shade_Control", None)
ctrl.empty_display_type = "SPHERE"
ctrl.empty_display_size = 0.04
ctrl.location = (WHEEL_X + 0.08, -0.05, DRIVER_Z)
shade.objects.link(ctrl)
ctrl["open_percent"] = 0.0
try:
    ctrl.id_properties_ui("open_percent").update(
        min=0.0, max=100.0, soft_min=0.0, soft_max=100.0, step=100,
        description="0 = закрито, 100 = відкрито (як current_position у Home Assistant)")
except Exception:
    pass

add_prop_driver(key_open, "value", None, ctrl, "p / 100")
wound = fab_bot_o - fab_bot_c                         # довжина тканини, що намотується
total_angle = wound / ((ROLL_R_CLOSED + ROLL_R_OPEN) / 2)
add_prop_driver(tube, "rotation_euler", 0, ctrl, f"-p / 100 * {total_angle:.4f}")

# корінь, щоб пересувати всю шторку разом
root = bpy.data.objects.new("Roller_Shade", None)
root.empty_display_type = "PLAIN_AXES"
root.empty_display_size = 0.1
shade.objects.link(root)
for o in shade.objects:
    if o is not root and o.parent is None:
        o.parent = root

# демо-анімація: закрито -> відкрито -> закрито
scn = bpy.context.scene
for frame, val in ((1, 0.0), (100, 100.0), (160, 100.0), (260, 0.0)):
    ctrl["open_percent"] = val
    ctrl.keyframe_insert(data_path='["open_percent"]', frame=frame)
scn.frame_start, scn.frame_end = 1, 280
scn.frame_set(1)

# ---------------- контекст: стіна з прорізом, рама, скло, підвіконня ----------------
if BUILD_CONTEXT:
    ctx = get_coll("Window_Context")
    WX = 1.6
    hz = (CEIL_Z + FLOOR_Z) / 2
    full_h = CEIL_Z - FLOOR_Z
    side_w = WX - OPEN_W / 2
    box("Wall_L", (side_w, WALL_T, full_h), (-(OPEN_W / 2 + side_w / 2), WALL_T / 2, hz), M_WALL, ctx)
    box("Wall_R", (side_w, WALL_T, full_h), (OPEN_W / 2 + side_w / 2, WALL_T / 2, hz), M_WALL, ctx)
    box("Wall_Top", (OPEN_W, WALL_T, CEIL_Z - OPEN_H), (0, WALL_T / 2, (CEIL_Z + OPEN_H) / 2), M_WALL, ctx)
    box("Wall_Bottom", (OPEN_W, WALL_T, -FLOOR_Z), (0, WALL_T / 2, FLOOR_Z / 2), M_WALL, ctx)
    sill_d = WINDOW_Y + 0.05
    box("Window_Sill", (OPEN_W + 0.10, sill_d, 0.03), (0, WINDOW_Y - sill_d / 2, -0.015), M_FRAME, ctx)

    fy = WINDOW_Y + 0.035
    F, TR_Z, MX = 0.065, 1.43, 0.28
    for name, size, loc in (
        ("Frame_L", (F, 0.07, OPEN_H), (-(OPEN_W - F) / 2, fy, OPEN_H / 2)),
        ("Frame_R", (F, 0.07, OPEN_H), ((OPEN_W - F) / 2, fy, OPEN_H / 2)),
        ("Frame_Top", (OPEN_W, 0.07, F), (0, fy, OPEN_H - F / 2)),
        ("Frame_Bottom", (OPEN_W, 0.07, F), (0, fy, F / 2)),
        ("Frame_Transom", (OPEN_W, 0.07, 0.08), (0, fy, TR_Z)),
        ("Frame_Mullion_L", (0.08, 0.07, OPEN_H), (-MX, fy, OPEN_H / 2)),
        ("Frame_Mullion_R", (0.08, 0.07, OPEN_H), (MX, fy, OPEN_H / 2)),
    ):
        box(name, size, loc, M_FRAME, ctx)
    box("Window_Glass", (OPEN_W - 0.1, 0.006, OPEN_H - 0.1), (0, fy, OPEN_H / 2), M_GLASS, ctx)

print(f"Roller shade built. Fabric travel {wound:.3f} m, tube turns {total_angle / (2 * math.pi):.1f} "
      f"({math.degrees(total_angle):.0f} deg) for 0->100 %.")


# ---------------- експорт для Unity ----------------
def export_glb(path):
    """Експорт лише шторки. Blendshape "Open": 0 = закрито, 100 = відкрито (Unity)."""
    prev = ctrl["open_percent"]
    scn.frame_set(1)
    bpy.ops.object.select_all(action="DESELECT")
    for o in shade.objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
                              export_apply=False, export_morph=True, export_animations=False,
                              export_yup=True)
    ctrl["open_percent"] = prev
    print("Exported:", path)


if EXPORT_GLB:
    export_glb(EXPORT_GLB)

if SAVE_BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=SAVE_BLEND)
    print("Saved:", SAVE_BLEND)
