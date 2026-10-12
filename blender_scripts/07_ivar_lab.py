# Builds the IVAR lab (TalTech) scene in Blender from lab_data.json,
# renders preview images and saves ivar-lab-taltech.blend next to this script.
# Run inside Blender:  exec(open(r"<path>\build_ivar_blend.py").read(), {"__file__": r"<path>\build_ivar_blend.py", "__name__": "__main__"})
import bpy, json, math, os, traceback, time
from mathutils import Matrix, Vector, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "Models", "IVAR_Lab")
LOG = []
def log(*a):
    LOG.append(" ".join(str(x) for x in a))

ZONES = {
    "ivar": "Зона IVAR (VR/AR)",
    "fms": "Лінія Festo FMS",
    "cells": "Роботизовані комірки",
    "study": "Навчальна зона",
    "infra": "Вхід і інфраструктура",
    "list": "З переліку (умовно)",
}
GROUP_COLL = {"Room_Shell": "Приміщення", "Windows": "Приміщення", "Safety_Tape": "Приміщення", "Misc": "Приміщення", "Ceiling": "Стеля"}
CULL = {"wall_white", "wall_greige", "wall_bluegrey", "ceiling_tex", "led_panel"}
# three.js (Y up) -> Blender (Z up)
A4 = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(srgb_to_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))


def m4(a):  # column-major 16 -> Matrix
    return Matrix(((a[0], a[4], a[8], a[12]), (a[1], a[5], a[9], a[13]), (a[2], a[6], a[10], a[14]), (0, 0, 0, 1)))


# ---------------- geometry generators (three.js local space, same conventions) ----------------
def g_box(w, h, d, *_):
    V, F, UV, S = [], [], [], []
    hw, hh, hd = w / 2, h / 2, d / 2
    faces = [((hw, 0, 0), (0, hh, 0), (0, 0, hd)), ((-hw, 0, 0), (0, 0, hd), (0, hh, 0)),
             ((0, hh, 0), (0, 0, hd), (hw, 0, 0)), ((0, -hh, 0), (hw, 0, 0), (0, 0, hd)),
             ((0, 0, hd), (hw, 0, 0), (0, hh, 0)), ((0, 0, -hd), (0, hh, 0), (hw, 0, 0))]
    for n, u, v in faces:
        b = len(V)
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            V.append((n[0] + su * u[0] + sv * v[0], n[1] + su * u[1] + sv * v[1], n[2] + su * u[2] + sv * v[2]))
            UV.append(((su + 1) / 2, (sv + 1) / 2))
        F.append((b, b + 1, b + 2, b + 3)); S.append(False)
    return V, F, UV, S


def g_plane(w=1, h=1, *_):
    V = [(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)]
    return V, [(0, 1, 2, 3)], [(0, 0), (1, 0), (1, 1), (0, 1)], [False]


def g_cyl(rt=1, rb=1, h=1, seg=32, *_):
    seg = int(seg); V, F, UV, S = [], [], [], []
    hh = h / 2
    ang = [2 * math.pi * i / seg for i in range(seg + 1)]
    for i, t in enumerate(ang):
        V.append((rt * math.sin(t), hh, rt * math.cos(t))); UV.append((i / seg, 1))
    for i, t in enumerate(ang):
        V.append((rb * math.sin(t), -hh, rb * math.cos(t))); UV.append((i / seg, 0))
    n = seg + 1
    for i in range(seg):
        F.append((i, n + i, n + i + 1, i + 1)); S.append(True)
    for r, y, top in ((rt, hh, True), (rb, -hh, False)):
        if r <= 0:
            continue
        b = len(V)
        for i in range(seg):
            t = ang[i]
            V.append((r * math.sin(t), y, r * math.cos(t))); UV.append((0.5 + 0.5 * math.sin(t), 0.5 + 0.5 * math.cos(t)))
        idx = list(range(b, b + seg))
        F.append(tuple(idx if top else idx[::-1])); S.append(False)
    return V, F, UV, S


def g_sphere(r=1, ws=32, hs=16, *_):
    ws, hs = int(ws), int(hs); V, F, UV, S = [], [], [], []
    grid = []
    for iy in range(hs + 1):
        v = iy / hs; row = []
        for ix in range(ws + 1):
            u = ix / ws; ph = u * 2 * math.pi; th = v * math.pi
            V.append((-r * math.cos(ph) * math.sin(th), r * math.cos(th), r * math.sin(ph) * math.sin(th)))
            UV.append((u, 1 - v)); row.append(len(V) - 1)
        grid.append(row)
    for iy in range(hs):
        for ix in range(ws):
            a, b = grid[iy][ix + 1], grid[iy][ix]
            c, d = grid[iy + 1][ix], grid[iy + 1][ix + 1]
            if iy != 0:
                F.append((a, b, d)); S.append(True)
            if iy != hs - 1:
                F.append((b, c, d)); S.append(True)
    return V, F, UV, S


def g_torus(R=1, tube=0.4, radial=12, tubular=48, *_):
    radial, tubular = int(radial), int(tubular); V, F, UV, S = [], [], [], []
    for j in range(radial + 1):
        for i in range(tubular + 1):
            u = i / tubular * 2 * math.pi; v = j / radial * 2 * math.pi
            V.append(((R + tube * math.cos(v)) * math.cos(u), (R + tube * math.cos(v)) * math.sin(u), tube * math.sin(v)))
            UV.append((i / tubular, j / radial))
    W = tubular + 1
    for j in range(1, radial + 1):
        for i in range(1, tubular + 1):
            a = W * j + i - 1; b = W * (j - 1) + i - 1; c = W * (j - 1) + i; d = W * j + i
            F.append((a, b, c, d)); S.append(True)
    return V, F, UV, S


def g_tube(pts, radius, radial, *_):
    radial = int(radial); P = [Vector(p) for p in pts]; n = len(P)
    T = []
    for i in range(n):
        d = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]); T.append(d.normalized())
    ax = min(range(3), key=lambda k: abs(T[0][k])); e = Vector((0, 0, 0)); e[ax] = 1
    vec = T[0].cross(e).normalized(); N = [T[0].cross(vec)]; B = [T[0].cross(N[0])]
    for i in range(1, n):
        Ni = N[i - 1].copy(); c = T[i - 1].cross(T[i])
        if c.length > 1e-9:
            ang = math.acos(max(-1, min(1, T[i - 1].dot(T[i]))))
            Ni.rotate(Quaternion(c.normalized(), ang))
        N.append(Ni); B.append(T[i].cross(Ni))
    V, F, UV, S = [], [], [], []
    for i in range(n):
        for j in range(radial + 1):
            v = j / radial * 2 * math.pi; s, c = math.sin(v), -math.cos(v)
            d = (N[i] * c + B[i] * s)
            V.append(tuple(P[i] + d * radius)); UV.append((i / (n - 1), j / radial))
    W = radial + 1
    for j in range(1, n):
        for i in range(1, radial + 1):
            a = W * (j - 1) + i - 1; b = W * j + i - 1; c = W * j + i; d = W * (j - 1) + i
            F.append((a, b, c, d)); S.append(True)
    return V, F, UV, S


GEN = {"box": g_box, "plane": g_plane, "cylinder": g_cyl, "sphere": g_sphere, "torus": g_torus, "tube": g_tube}


# ---------------- materials ----------------
def make_material(key, p):
    mat = bpy.data.materials.get(key) or bpy.data.materials.new(key)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled"); bs.location = (100, 0)
    nt.links.new(bs.outputs[0], out.inputs["Surface"])
    col = hex_rgb(p["color"])
    if key == "ceiling_tex":
        col = hex_rgb("#f3f3f0")
    if key.startswith("banner_") or key == "motoman_label":
        col = hex_rgb("#fbfbfa")
    bs.inputs["Base Color"].default_value = (*col, 1)
    bs.inputs["Roughness"].default_value = float(p.get("roughness", 0.5))
    bs.inputs["Metallic"].default_value = float(p.get("metalness", 0))
    if p.get("emissiveIntensity", 0) > 0:
        bs.inputs["Emission Color"].default_value = (*hex_rgb(p["emissive"]), 1)
        bs.inputs["Emission Strength"].default_value = float(p["emissiveIntensity"]) * 2.0
    if key in ("tape_red_white", "tape_safety"):
        a, b = (("#d8342c", "#f7f7f7") if key == "tape_red_white" else ("#f2b705", "#1b1d20"))
        uv = nt.nodes.new("ShaderNodeUVMap"); uv.location = (-800, 0)
        sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-600, 0)
        mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 4.0; mul.location = (-420, 0)
        fr = nt.nodes.new("ShaderNodeMath"); fr.operation = "FRACT"; fr.location = (-250, 0)
        ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-150, 200)
        ramp.color_ramp.interpolation = "CONSTANT"
        ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (*hex_rgb(a), 1)
        ramp.color_ramp.elements[1].position = 0.5; ramp.color_ramp.elements[1].color = (*hex_rgb(b), 1)
        nt.links.new(uv.outputs[0], sep.inputs[0]); nt.links.new(sep.outputs[0], mul.inputs[0])
        nt.links.new(mul.outputs[0], fr.inputs[0]); nt.links.new(fr.outputs[0], ramp.inputs[0])
        nt.links.new(ramp.outputs[0], bs.inputs["Base Color"])
    alpha = float(p.get("opacity", 1))
    if alpha < 1:
        bs.inputs["Alpha"].default_value = alpha
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
        elif hasattr(mat, "blend_method"):
            mat.blend_method = "BLEND"
    mat.diffuse_color = (*col, alpha)
    if key in CULL:
        mat.use_backface_culling = True
    return mat


def get_coll(name, parent):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name); parent.children.link(c)
    return c


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for blk in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for d in list(blk):
            if d.users == 0:
                blk.remove(d)


def add_text(name, body, size, mw, color, coll, parent=None):
    cu = bpy.data.curves.new(name, "FONT"); cu.body = body; cu.size = size; cu.align_x = "LEFT"
    ob = bpy.data.objects.new(name, cu); coll.objects.link(ob)
    m = bpy.data.materials.get("text_" + color) or bpy.data.materials.new("text_" + color)
    try:
        m.use_nodes = True
    except Exception:
        pass
    bs = m.node_tree.nodes.get("Principled BSDF")
    if bs:
        bs.inputs["Base Color"].default_value = (*hex_rgb(color), 1); bs.inputs["Roughness"].default_value = 0.6
    m.diffuse_color = (*hex_rgb(color), 1)
    cu.materials.append(m)
    ob.matrix_world = mw
    if parent is not None:
        ob.parent = parent; ob.matrix_parent_inverse = parent.matrix_world.inverted()
    return ob


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def t2b(x, y, z):  # three point -> blender point
    return Vector((x, -z, y))


def build():
    t0 = time.time()
    data = json.load(open(os.path.join(HERE, "ivar_lab_data.json"), encoding="utf-8"))
    clear_scene()
    sc = bpy.context.scene
    root = get_coll("IVAR_Lab", sc.collection)
    mats = {k: make_material(k, p) for k, p in data["materials"].items()}
    items = {it["id"]: it for it in data["items"]}

    groups = {}
    for m in data["meshes"]:
        groups.setdefault(m["o"], []).append(m)

    objs = {}
    total_f = 0
    for owner, lst in groups.items():
        V, F, UV, S, MI, matlist = [], [], [], [], [], []
        for m in lst:
            gv, gf, guv, gs = GEN[m["t"]](*m["a"])
            M = A4 @ m4(m["m"])
            base = len(V)
            for v in gv:
                V.append(M @ Vector(v))
            rep = m.get("rep") or [1, 1]
            if m["mat"] not in matlist:
                matlist.append(m["mat"])
            mi = matlist.index(m["mat"])
            for f, sm in zip(gf, gs):
                F.append(tuple(base + i for i in f)); S.append(sm); MI.append(mi)
                UV.append([(guv[i][0] * rep[0], guv[i][1] * rep[1]) for i in f])
        mn = Vector((min(v.x for v in V), min(v.y for v in V), min(v.z for v in V)))
        mx = Vector((max(v.x for v in V), max(v.y for v in V), max(v.z for v in V)))
        org = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
        me = bpy.data.meshes.new(owner)
        me.from_pydata([tuple(v - org) for v in V], [], F)
        uvl = me.uv_layers.new(name="UVMap")
        flat = [c for poly in UV for uv in poly for c in uv]
        uvl.data.foreach_set("uv", flat)
        me.polygons.foreach_set("material_index", MI)
        me.polygons.foreach_set("use_smooth", S)
        for k in matlist:
            me.materials.append(mats[k])
        me.validate(); me.update()
        ob = bpy.data.objects.new(owner, me)
        ob.location = org
        if owner in items:
            it = items[owner]
            coll = get_coll(ZONES[it["zone"]], root)
            ob["name_uk"] = it["name"]; ob["description"] = it["desc"]; ob["quantity"] = it["qty"]
            ob["conditional_placement"] = it["cond"]; ob["zone"] = it["zone"]
        else:
            coll = get_coll(GROUP_COLL.get(owner, "Приміщення"), root)
        coll.objects.link(ob)
        objs[owner] = ob
        total_f += len(F)
    bpy.context.view_layer.update()

    # text: wall sign + Motoman label (canvas text in the web version)
    for t in data["texts"]:
        M = A4 @ m4(t["m"])
        if t["kind"] == "sign":
            W, Hh, cw, ch = 2.3, 0.81, 1024, 360
            par = objs.get("sign"); coll = par.users_collection[0]
            def P(x, y):
                return Matrix.Translation(((x / cw - 0.5) * W, (0.5 - y / ch) * Hh, 0.004))
            lines = [("TALLINNA TEHNIKAÜLIKOOL", 140, 92, 30), ("MEHAANIKA JA TÖÖSTUSTEHNIKA INSTITUUT", 140, 124, 22),
                     ("PAINDTOOTMISSÜSTEEMIDE", 40, 220, 50), ("JA ROBOOTIKA DEMOKESKUS", 40, 284, 50)]
            for k, (txt, x, y, px) in enumerate(lines):
                add_text("sign_text_%d" % k, txt, px / ch * Hh * 0.95, M @ P(x, y), "#26292d", coll, par)
            # logo bars
            Vb, Fb = [], []
            for i in range(6):
                x0 = 40 + i * 13; x1 = x0 + 8; y0, y1 = 60, 122
                b = len(Vb)
                for (x, y) in ((x0, y1), (x1, y1), (x1, y0), (x0, y0)):
                    Vb.append(tuple(M @ Vector(((x / cw - 0.5) * W, (0.5 - y / ch) * Hh, 0.004))))
                Fb.append((b, b + 1, b + 2, b + 3))
            me = bpy.data.meshes.new("sign_logo"); me.from_pydata(Vb, [], Fb); me.update()
            lo = bpy.data.objects.new("sign_logo", me); coll.objects.link(lo)
            me.materials.append(bpy.data.materials.get("text_#26292d"))
            lo.parent = par; lo.matrix_parent_inverse = par.matrix_world.inverted()
        elif t["kind"] == "motoman":
            par = objs.get("motoman-gp8"); coll = par.users_collection[0]
            W, Hh, cw, ch = 0.9, 0.45, 256, 128
            def P(x, y):
                return Matrix.Translation(((x / cw - 0.5) * W, (0.5 - y / ch) * Hh, 0.004))
            add_text("motoman_text", "MOTOMAN", 34 / ch * Hh, M @ P(22, 52), "#1f63c8", coll, par)
            add_text("motoman_sub", "GP8 training stand", 20 / ch * Hh, M @ P(24, 84), "#47515b", coll, par)

    # lights & world
    w = bpy.data.worlds.get("IVAR_World") or bpy.data.worlds.new("IVAR_World")
    try:
        w.use_nodes = True
    except Exception:
        pass
    bg = w.node_tree.nodes.get("Background")
    if bg is None:
        bg = w.node_tree.nodes.new("ShaderNodeBackground")
        wo = w.node_tree.nodes.get("World Output") or w.node_tree.nodes.new("ShaderNodeOutputWorld")
        w.node_tree.links.new(bg.outputs[0], wo.inputs["Surface"])
    if bg:
        bg.inputs[0].default_value = (*hex_rgb("#dde3e8"), 1); bg.inputs[1].default_value = 0.9
    sc.world = w
    lc = get_coll("Світло і камери", root)
    sun_d = bpy.data.lights.new("Sun", "SUN"); sun_d.energy = 3.0; sun_d.angle = math.radians(3)
    sun = bpy.data.objects.new("Sun", sun_d); lc.objects.link(sun)
    sun.location = t2b(3.5, 9, -11); look_at(sun, t2b(1.5, 0, 0.3))
    for i, (x, z) in enumerate(((-2.5, -1.5), (3.0, -1.5), (-0.5, 2.6), (4.5, 2.6))):
        ld = bpy.data.lights.new("Ceiling_Light_%d" % i, "AREA"); ld.energy = 120; ld.size = 1.2
        lo = bpy.data.objects.new("Ceiling_Light_%d" % i, ld); lc.objects.link(lo)
        lo.location = t2b(x, 2.9, z)  # area lights point down (-Z) by default

    def cam(name, loc, tgt, ortho=None, lens=35):
        cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 200
        if ortho:
            cd.type = "ORTHO"; cd.ortho_scale = ortho
        co = bpy.data.objects.new(name, cd); lc.objects.link(co)
        co.location = loc; look_at(co, tgt)
        return co
    c_over = cam("Cam_Overview", t2b(-8.6, 11.2, -10.2), t2b(1.3, 0.4, 0.5), lens=30)
    c_plan = cam("Cam_Plan", t2b(1.5, 30, 0.05), t2b(1.5, 0, 0.05), ortho=16.5)
    c_plan.rotation_euler = (0, 0, 0)
    c_spot = cam("Cam_360_Spot", t2b(0, 1.55, 0), t2b(5, 1.3, 0.0), lens=16)
    c_ivar = cam("Cam_IVAR_Zone", t2b(3.6, 1.7, -0.6), t2b(-0.6, 0.9, 3.2), lens=20)

    # render settings
    r = sc.render
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            r.engine = eng; break
        except Exception:
            pass
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1600, 1000, 100
    r.image_settings.file_format = "PNG"
    try:
        sc.eevee.taa_render_samples = 32
    except Exception:
        pass
    try:
        sc.view_settings.view_transform = "AgX"
    except Exception:
        pass

    ceiling = bpy.data.collections.get("Стеля")
    rdir = os.path.join(OUT, "renders"); os.makedirs(rdir, exist_ok=True)
    shots = [("overview", c_over, True), ("plan", c_plan, True), ("ivar_zone", c_ivar, False), ("from_360_spot", c_spot, False)]
    for name, c, hide_ceiling in shots:
        if ceiling:
            ceiling.hide_render = hide_ceiling
        sc.camera = c
        r.filepath = os.path.join(rdir, name + ".png")
        bpy.ops.render.render(write_still=True)
        log("rendered", name)

    # final state: overview camera, ceiling hidden (toggle the eye on the "Стеля" collection)
    sc.camera = c_over
    if ceiling:
        ceiling.hide_render = True
        def find_lc(lc_, name):
            if lc_.collection.name == name:
                return lc_
            for ch in lc_.children:
                f = find_lc(ch, name)
                if f:
                    return f
        lcx = find_lc(bpy.context.view_layer.layer_collection, "Стеля")
        if lcx:
            lcx.hide_viewport = True
    sc.unit_settings.system = "METRIC"
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "MATERIAL"; sp.clip_end = 500
    path = os.path.join(OUT, "ivar-lab-taltech.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
    n_obj = len([o for o in bpy.data.objects])
    log("objects", n_obj, "mesh_objects", len(objs), "faces", total_f, "materials", len(mats), "seconds", round(time.time() - t0, 1))
    log("saved", path)
    log("blender", bpy.app.version_string, "engine", r.engine)


try:
    build()
    log("OK")
except Exception:
    log("ERROR\n" + traceback.format_exc())
finally:
    with open(os.path.join(OUT, "build_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))
    print("\n".join(LOG))
