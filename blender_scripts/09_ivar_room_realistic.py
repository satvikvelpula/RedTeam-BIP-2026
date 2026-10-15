# IVAR room (TalTech) — realistic version (v3).
# Same layout as 08_ivar_room_real.py (from the LiDAR scan of 12.10.2026 + photos),
# with procedural PBR materials, bevelled geometry, detailed furniture and Cycles lighting.
# Coordinates: metres, Z up. Origin = floor corner of entrance wall (X=0) and sideboard wall (Y=0).
import bpy, bmesh, math, os, traceback
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "Models", "IVAR_Lab")
SCAN = os.path.join(ROOT, "Scans", "IVAR_scan_2026-10-12.fbx")
RENDER_SAMPLES = 160
LOG = []
def log(*a): LOG.append(" ".join(str(x) for x in a))

L, W, H = 5.81, 2.75, 2.91
T = 0.12                      # wall thickness
SCAN_ANGLE = math.radians(36.6)
SCAN_OFFSET = (1.31, 2.0, 1.61)

# =====================================================================================
# materials
# =====================================================================================
def srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)

def sock(node, ident, out=False):
    socks = node.outputs if out else node.inputs
    for s in socks:
        if s.identifier == ident: return s
    for s in socks:
        if s.name == ident and s.enabled: return s
    raise KeyError(ident)

class MB:
    """Small helper to build a Principled material with node graphs."""
    def __init__(self, name):
        self.m = bpy.data.materials.new(name)
        try: self.m.use_nodes = True
        except Exception: pass
        self.nt = self.m.node_tree; self.N = self.nt.nodes; self.Lk = self.nt.links
        self.bs = self.N.get("Principled BSDF")
        self.x = -400
    def n(self, t, **kw):
        nd = self.N.new(t); nd.location = (self.x, len(self.N) * -40); self.x -= 30
        for k, v in kw.items(): setattr(nd, k, v)
        return nd
    def link(self, a, b): self.Lk.new(a, b)
    def set(self, name, v):
        s = self.bs.inputs.get(name)
        if s is not None: s.default_value = v
    def coord(self, kind="Object", scale=(1, 1, 1)):
        tc = self.n("ShaderNodeTexCoord"); mp = self.n("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = scale
        self.link(tc.outputs[kind], mp.inputs["Vector"]); return mp.outputs["Vector"]
    def ramp(self, inp, stops, interp="LINEAR"):
        r = self.n("ShaderNodeValToRGB"); cr = r.color_ramp; cr.interpolation = interp
        while len(cr.elements) < len(stops): cr.elements.new(0.5)
        for e, (p, c) in zip(cr.elements, stops):
            e.position = p; e.color = (*srgb(c), 1) if isinstance(c, str) else (c, c, c, 1)
        self.link(inp, r.inputs["Fac"]); return r
    def mix(self, fac, a, b):
        mx = self.n("ShaderNodeMix"); mx.data_type = "RGBA"
        self.link(fac, sock(mx, "Factor_Float")) if not isinstance(fac, float) else None
        if isinstance(fac, float): sock(mx, "Factor_Float").default_value = fac
        for ident, v in (("A_Color", a), ("B_Color", b)):
            if isinstance(v, str): sock(mx, ident).default_value = (*srgb(v), 1)
            else: self.link(v, sock(mx, ident))
        return sock(mx, "Result_Color", out=True)
    def bump(self, height, strength=0.1, distance=0.01):
        bp = self.n("ShaderNodeBump"); bp.inputs["Strength"].default_value = strength
        bp.inputs["Distance"].default_value = distance
        self.link(height, bp.inputs["Height"]); self.link(bp.outputs["Normal"], self.bs.inputs["Normal"])
    def noise(self, vec, scale, detail=4.0, rough=0.55):
        nz = self.n("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = scale
        nz.inputs["Detail"].default_value = detail; nz.inputs["Roughness"].default_value = rough
        self.link(vec, nz.inputs["Vector"]); return nz

MATS = {}
def simple(name, color, rough=0.5, metal=0.0, **extra):
    if name in MATS: return MATS[name]
    b = MB(name); b.set("Base Color", (*srgb(color), 1)); b.set("Roughness", rough); b.set("Metallic", metal)
    for k, v in extra.items(): b.set(k, v)
    b.m.diffuse_color = (*srgb(color), 1)
    MATS[name] = b.m; return b.m

def mat_paint(name, color, rough=0.82, scale=180, strength=0.04):
    b = MB(name); v = b.coord()
    nz = b.noise(v, scale, 6, 0.6)
    b.set("Base Color", (*srgb(color), 1)); b.set("Roughness", rough)
    b.bump(nz.outputs["Fac"], strength, 0.002)
    b.m.diffuse_color = (*srgb(color), 1); MATS[name] = b.m; return b.m

def mat_terrazzo():
    b = MB("floor_terrazzo"); v = b.coord()
    warp = b.noise(v, 6, 2, 0.5)
    vv = b.n("ShaderNodeVectorMath", operation="ADD"); b.link(v, vv.inputs[0])
    sc = b.n("ShaderNodeVectorMath", operation="SCALE"); sc.inputs["Scale"].default_value = 0.012
    b.link(warp.outputs["Color"], sc.inputs[0]); b.link(sc.outputs[0], vv.inputs[1]); vw = vv.outputs[0]
    base = b.ramp(b.noise(v, 3, 3).outputs["Fac"], [(0.35, "#a6a29a"), (0.65, "#99958d")]).outputs["Color"]
    col = base
    # three chip layers: large dark, medium mixed, small light/dark speckle
    # angular chips: voronoi cells inset from their edges (distance-to-edge), each cell its own stone colour;
    # only part of the cells become stones so the cement matrix shows between them
    for scale, thr, keep, pal in ((7, 0.10, 0.55, [(0.0, "#6c6964"), (0.3, "#8a867f"), (0.55, "#c8c4bb"), (0.8, "#55524e"), (1.0, "#b3aea4")]),
                                  (17, 0.12, 0.50, [(0.0, "#dedad2"), (0.35, "#74716b"), (0.7, "#a29d93"), (1.0, "#3c3b39")]),
                                  (48, 0.14, 0.45, [(0.0, "#efece6"), (0.5, "#4a4946"), (1.0, "#bdb8ae")])):
        vo = b.n("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = scale
        vo.inputs["Randomness"].default_value = 1.0; b.link(vw, vo.inputs["Vector"])
        ve = b.n("ShaderNodeTexVoronoi"); ve.feature = "DISTANCE_TO_EDGE"; ve.inputs["Scale"].default_value = scale
        ve.inputs["Randomness"].default_value = 1.0; b.link(vw, ve.inputs["Vector"])
        sep = b.n("ShaderNodeSeparateColor"); b.link(vo.outputs["Color"], sep.inputs["Color"])
        chip = b.ramp(sep.outputs[0], pal, "CONSTANT")
        inside = b.n("ShaderNodeMath", operation="GREATER_THAN"); inside.inputs[1].default_value = thr
        b.link(ve.outputs["Distance"], inside.inputs[0])
        sel = b.n("ShaderNodeMath", operation="LESS_THAN"); sel.inputs[1].default_value = keep
        b.link(sep.outputs[1], sel.inputs[0])
        both = b.n("ShaderNodeMath", operation="MULTIPLY"); b.link(inside.outputs[0], both.inputs[0]); b.link(sel.outputs[0], both.inputs[1])
        col = b.mix(both.outputs[0], col, chip.outputs["Color"])
    b.link(col, b.bs.inputs["Base Color"])
    b.set("Roughness", 0.28)
    b.bump(b.noise(v, 90, 3).outputs["Fac"], 0.02, 0.001)
    b.m.diffuse_color = (*srgb("#aeaba4"), 1); MATS[b.m.name] = b.m; return b.m

def mat_osb():
    b = MB("osb_board"); v = b.coord(scale=(1, 1, 1))
    vo = b.n("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 26; vo.inputs["Randomness"].default_value = 1
    mp = b.n("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.0, 1.0, 3.0)
    mp.inputs["Rotation"].default_value = (0, 0.6, 0); b.link(v, mp.inputs["Vector"]); b.link(mp.outputs[0], vo.inputs["Vector"])
    sep = b.n("ShaderNodeSeparateColor"); b.link(vo.outputs["Color"], sep.inputs["Color"])
    flakes = b.ramp(sep.outputs[0], [(0.0, "#a8702f"), (0.2, "#c98d44"), (0.45, "#e0ad62"), (0.7, "#b77c36"), (0.85, "#8c5a24"), (1.0, "#d49c52")], "CONSTANT")
    vo2 = b.n("ShaderNodeTexVoronoi"); vo2.inputs["Scale"].default_value = 55; vo2.inputs["Randomness"].default_value = 1
    mp2 = b.n("ShaderNodeMapping"); mp2.inputs["Scale"].default_value = (1.0, 1.0, 2.2)
    mp2.inputs["Rotation"].default_value = (0, -0.9, 0); b.link(v, mp2.inputs["Vector"]); b.link(mp2.outputs[0], vo2.inputs["Vector"])
    sep2 = b.n("ShaderNodeSeparateColor"); b.link(vo2.outputs["Color"], sep2.inputs["Color"])
    flakes2 = b.ramp(sep2.outputs[0], [(0.0, "#9a6428"), (0.4, "#d6a057"), (0.75, "#bf8640"), (1.0, "#e6bb78")], "CONSTANT")
    pick = b.ramp(sep2.outputs[1], [(0.55, 0.0), (0.56, 1.0)], "CONSTANT")
    col = b.mix(pick.outputs["Color"], flakes.outputs["Color"], flakes2.outputs["Color"])
    edge = b.ramp(vo.outputs["Distance"], [(0.0, 0.35), (0.12, 0.0)])
    col = b.mix(edge.outputs["Color"], col, "#6b4219")
    grain = b.ramp(b.noise(v, 160, 4).outputs["Fac"], [(0.3, "#7a5023"), (0.7, "#e8bd7e")])
    col = b.mix(0.18, col, grain.outputs["Color"])
    b.link(col, b.bs.inputs["Base Color"]); b.set("Roughness", 0.78)
    b.bump(vo.outputs["Distance"], 0.25, 0.002)
    b.m.diffuse_color = (*srgb("#c49558"), 1); MATS[b.m.name] = b.m; return b.m

def mat_wood(name="wood_dark", c1="#2f1c12", c2="#4f3020"):
    b = MB(name); v = b.coord(scale=(1, 1, 1))
    wv = b.n("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.bands_direction = "X"
    wv.inputs["Scale"].default_value = 22; wv.inputs["Distortion"].default_value = 4; wv.inputs["Detail"].default_value = 3
    b.link(v, wv.inputs["Vector"])
    r = b.ramp(wv.outputs["Fac"], [(0.2, c1), (0.8, c2)])
    b.link(r.outputs["Color"], b.bs.inputs["Base Color"]); b.set("Roughness", 0.5)
    b.m.diffuse_color = (*srgb(c2), 1); MATS[name] = b.m; return b.m

def mat_brushed(name="aluminium_brushed", color="#c3c7ca"):
    b = MB(name); v = b.coord(scale=(1, 1, 1))
    mp = b.n("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1, 400, 400); b.link(v, mp.inputs["Vector"])
    nz = b.noise(mp.outputs[0], 2, 2)
    r = b.ramp(nz.outputs["Fac"], [(0.3, 0.22), (0.7, 0.38)])
    b.link(r.outputs["Color"], b.bs.inputs["Roughness"])
    b.set("Base Color", (*srgb(color), 1)); b.set("Metallic", 1.0)
    b.m.diffuse_color = (*srgb(color), 1); MATS[name] = b.m; return b.m

def mat_ceiling_tile():
    b = MB("ceiling_tile"); v = b.coord()
    nz = b.noise(v, 260, 5, 0.7)
    pits = b.n("ShaderNodeTexVoronoi"); pits.inputs["Scale"].default_value = 140; b.link(v, pits.inputs["Vector"])
    b.set("Base Color", (*srgb("#f2f1ee"), 1)); b.set("Roughness", 0.95)
    add = b.n("ShaderNodeMath", operation="MULTIPLY"); b.link(pits.outputs["Distance"], add.inputs[0]); b.link(nz.outputs["Fac"], add.inputs[1])
    b.bump(add.outputs[0], 0.35, 0.002)
    b.m.diffuse_color = (*srgb("#f2f1ee"), 1); MATS[b.m.name] = b.m; return b.m

def mat_perforated(name="diffuser_perforated"):
    b = MB(name); v = b.coord("UV", (1, 1, 1))
    mp = b.n("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (60, 60, 1); b.link(v, mp.inputs["Vector"])
    fr = b.n("ShaderNodeVectorMath", operation="FRACTION"); b.link(mp.outputs[0], fr.inputs[0])
    sub = b.n("ShaderNodeVectorMath", operation="SUBTRACT"); sub.inputs[1].default_value = (0.5, 0.5, 0)
    b.link(fr.outputs[0], sub.inputs[0])
    ln = b.n("ShaderNodeVectorMath", operation="LENGTH"); b.link(sub.outputs[0], ln.inputs[0])
    lt = b.n("ShaderNodeMath", operation="LESS_THAN"); lt.inputs[1].default_value = 0.28; b.link(ln.outputs["Value"], lt.inputs[0])
    col = b.mix(lt.outputs[0], "#f3f3f1", "#3a3b3d")
    b.link(col, b.bs.inputs["Base Color"]); b.set("Roughness", 0.45)
    b.m.diffuse_color = (*srgb("#e5e5e2"), 1); MATS[name] = b.m; return b.m

def mat_glass(name="glass_clear", tint="#eef6f8"):
    b = MB(name)
    b.set("Base Color", (*srgb(tint), 1)); b.set("Roughness", 0.0); b.set("IOR", 1.45)
    for k in ("Transmission Weight", "Transmission"): b.set(k, 1.0)
    b.set("Alpha", 0.35)
    if hasattr(b.m, "surface_render_method"): b.m.surface_render_method = "BLENDED"
    b.m.diffuse_color = (*srgb(tint), 0.3); MATS[name] = b.m; return b.m

def mat_frosted(name="lamp_diffuser"):
    b = MB(name); b.set("Base Color", (*srgb("#f6f5f0"), 1)); b.set("Roughness", 0.35)
    for k in ("Transmission Weight", "Transmission"): b.set(k, 0.6)
    b.m.diffuse_color = (*srgb("#f6f5f0"), 1); MATS[name] = b.m; return b.m

def mat_emit(name, color, strength):
    b = MB(name); b.set("Base Color", (*srgb(color), 1)); b.set("Emission Color", (*srgb(color), 1))
    b.set("Emission Strength", strength); b.set("Roughness", 0.3)
    b.m.diffuse_color = (*srgb(color), 1); MATS[name] = b.m; return b.m

def mat_fabric(name="fabric_black", color="#141517"):
    b = MB(name); v = b.coord()
    ch = b.n("ShaderNodeTexChecker"); ch.inputs["Scale"].default_value = 900; b.link(v, ch.inputs["Vector"])
    b.set("Base Color", (*srgb(color), 1)); b.set("Roughness", 0.92)
    for k, val in (("Sheen Weight", 0.15), ("Sheen", 0.15)): b.set(k, val)
    b.bump(ch.outputs["Fac"], 0.15, 0.001)
    b.m.diffuse_color = (*srgb(color), 1); MATS[name] = b.m; return b.m

def mat_outside():
    """Emissive backdrop seen through the window: overcast sky, a yellow 4-storey facade with windows (left),
    autumn birch crowns with thin white trunks (right). Uses Generated coords of the backdrop box."""
    b = MB("outside_backdrop"); v = b.coord("Generated")
    sep = b.n("ShaderNodeSeparateXYZ"); b.link(v, sep.inputs[0])
    Y, Z = sep.outputs["Y"], sep.outputs["Z"]
    def m(op, x, y=None, val=None):
        n = b.n("ShaderNodeMath", operation=op)
        b.link(x, n.inputs[0]) if not isinstance(x, (int, float)) else setattr(n.inputs[0], "default_value", x)
        if y is not None:
            b.link(y, n.inputs[1]) if not isinstance(y, (int, float)) else setattr(n.inputs[1], "default_value", y)
        return n.outputs[0]
    sky = b.ramp(Z, [(0.35, "#d3d9df"), (1.0, "#b4c2cf")])
    # facade: Y > 0.52, Z < 0.60, warm yellow plaster with a grid of dark windows and white frames
    fac = m("MULTIPLY", m("GREATER_THAN", Y, 0.52), m("LESS_THAN", Z, 0.60))
    wy = m("FRACT", m("MULTIPLY", Y, 17.0)); wz = m("FRACT", m("MULTIPLY", Z, 12.0))
    win = m("MULTIPLY", m("LESS_THAN", wy, 0.42), m("LESS_THAN", wz, 0.50))
    frame = m("MULTIPLY", m("LESS_THAN", wy, 0.46), m("LESS_THAN", wz, 0.54))
    plaster = b.ramp(b.noise(v, 90, 6).outputs["Fac"], [(0.3, "#d9c48c"), (0.7, "#e6d39f")])
    fcol = b.mix(frame, plaster.outputs["Color"], "#f1efe9")
    fcol = b.mix(win, fcol, b.ramp(b.noise(v, 30, 2).outputs["Fac"], [(0.3, "#4e5862"), (0.7, "#6d7983")]).outputs["Color"])
    roof = m("MULTIPLY", m("GREATER_THAN", Y, 0.52), m("MULTIPLY", m("GREATER_THAN", Z, 0.60), m("LESS_THAN", Z, 0.625)))
    col = b.mix(fac, sky.outputs["Color"], fcol)
    col = b.mix(roof, col, "#7b5146")
    # birch crowns: clumped mask x fine leaf noise, mostly on the right part (Y < 0.62), below Z 0.85
    clump = b.ramp(b.noise(v, 9, 12, 0.62).outputs["Fac"], [(0.46, 0.0), (0.56, 1.0)])
    holes = b.ramp(b.noise(v, 220, 10, 0.7).outputs["Fac"], [(0.38, 0.0), (0.5, 1.0)])
    region = b.ramp(Y, [(0.28, 0.0), (0.36, 1.0), (0.66, 1.0), (0.74, 0.0)])
    height = b.ramp(Z, [(0.30, 1.0), (0.85, 0.0)])
    tree = m("MULTIPLY", m("MULTIPLY", clump.outputs["Color"], holes.outputs["Color"]), m("MULTIPLY", region.outputs["Color"], height.outputs["Color"]))
    leaves = b.ramp(b.noise(v, 140, 8).outputs["Fac"], [(0.25, "#8a5a17"), (0.45, "#d29b2a"), (0.6, "#e9c24e"), (0.75, "#b08a3a"), (0.9, "#6b6a3c")])
    # thin white trunks
    wv = b.n("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.bands_direction = "Y"
    wv.inputs["Scale"].default_value = 7; wv.inputs["Distortion"].default_value = 2.5; wv.inputs["Detail"].default_value = 2
    b.link(v, wv.inputs["Vector"])
    trunk = m("MULTIPLY", b.ramp(wv.outputs["Fac"], [(0.0, 1.0), (0.04, 0.0)]).outputs["Color"],
              m("MULTIPLY", region.outputs["Color"], b.ramp(Z, [(0.15, 1.0), (0.6, 0.0)]).outputs["Color"]))
    col = b.mix(trunk, col, "#e4e1da")
    col = b.mix(tree, col, leaves.outputs["Color"])
    em = b.N.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.8
    b.link(col, em.inputs["Color"]); out = b.N.get("Material Output")
    b.link(em.outputs[0], out.inputs["Surface"])
    b.m.diffuse_color = (*srgb("#c9d2da"), 1); MATS["outside_backdrop"] = b.m; return b.m

def mat_qr(name="qr_sticker"):
    b = MB(name); v = b.coord("UV")
    mp = b.n("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (9, 9, 1); b.link(v, mp.inputs["Vector"])
    vo = b.n("ShaderNodeTexWhiteNoise"); vo.noise_dimensions = "2D"
    fl = b.n("ShaderNodeVectorMath", operation="FLOOR"); b.link(mp.outputs[0], fl.inputs[0]); b.link(fl.outputs[0], vo.inputs["Vector"])
    r = b.ramp(vo.outputs["Value"], [(0.0, "#111111"), (0.5, "#f5f5f5")], "CONSTANT")
    b.link(r.outputs["Color"], b.bs.inputs["Base Color"]); b.set("Roughness", 0.4)
    b.m.diffuse_color = (0.5, 0.5, 0.5, 1); MATS[name] = b.m; return b.m

# =====================================================================================
# geometry helpers
# =====================================================================================
COLLS = {}
def coll(name):
    if name not in COLLS:
        c = bpy.data.collections.new(name); ROOTC.children.link(c); COLLS[name] = c
    return COLLS[name]

def empty(name, c, loc=(0, 0, 0), rot=(0, 0, 0), props=None):
    e = bpy.data.objects.new(name, None); e.empty_display_size = 0.2; coll(c).objects.link(e)
    e.location = loc; e.rotation_euler = rot
    for k, v in (props or {}).items(): e[k] = v
    return e

def _finish(ob, c, parent, m, bevel, seg, smooth):
    coll(c).objects.link(ob)
    if parent is not None: ob.parent = parent
    if m is not None: ob.data.materials.append(m)
    if bevel:
        bv = ob.modifiers.new("Bevel", "BEVEL"); bv.width = bevel; bv.segments = seg
        bv.limit_method = "ANGLE"; bv.angle_limit = math.radians(40)
        if smooth:
            for p in ob.data.polygons: p.use_smooth = True
            try: bv.harden_normals = True
            except Exception: pass
    return ob

def box(name, c, m, x0, x1, y0, y1, z0, z1, parent=None, bevel=0.0, seg=2, smooth=False):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((x0 + (v.co.x + 0.5) * (x1 - x0), y0 + (v.co.y + 0.5) * (y1 - y0), z0 + (v.co.z + 0.5) * (z1 - z0)))
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal; ax = max(range(3), key=lambda k: abs(n[k])); a, b_ = [k for k in range(3) if k != ax]
        for lp in f.loops: lp[uv].uv = (lp.vert.co[a], lp.vert.co[b_])
    bm.to_mesh(me); bm.free()
    return _finish(bpy.data.objects.new(name, me), c, parent, m, bevel, seg, smooth)

def cyl(name, c, m, r, h, loc=(0, 0, 0), rot=(0, 0, 0), seg=32, r2=None, parent=None, bevel=0.0):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = len(p.vertices) == 4
    ob = bpy.data.objects.new(name, me); ob.location = loc; ob.rotation_euler = rot
    return _finish(ob, c, parent, m, bevel, 2, False)

def sphere(name, c, m, r, loc=(0, 0, 0), scale=(1, 1, 1), parent=None, seg=32):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=r)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(name, me); ob.location = loc; ob.scale = scale
    return _finish(ob, c, parent, m, 0, 0, False)

def tube(name, c, m, pts, r, parent=None, closed=False):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = r; cu.bevel_resolution = 4
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY"); sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts): p.co = (*co, 1)
    sp.use_cyclic_u = closed
    ob = bpy.data.objects.new(name, cu); cu.materials.append(m)
    coll(c).objects.link(ob)
    if parent is not None: ob.parent = parent
    return ob

def rounded_path(pts, rad=0.04, n=4):
    """Round the inner corners of a polyline (for bent chair tubes, pipes)."""
    out = [Vector(pts[0])]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[i + 1])
        a = (p0 - p1).normalized(); b = (p2 - p1).normalized()
        s = p1 + a * rad; e = p1 + b * rad
        for k in range(n + 1):
            t = k / n; out.append((1 - t) ** 2 * s + 2 * (1 - t) * t * p1 + t * t * e)
    out.append(Vector(pts[-1])); return [tuple(v) for v in out]

def tri(name, c, m, pts, parent=None):
    me = bpy.data.meshes.new(name); me.from_pydata(pts, [], [list(range(len(pts)))]); me.update()
    return _finish(bpy.data.objects.new(name, me), c, parent, m, 0, 0, False)

def text(name, c, body, size, loc, rot, m, parent=None, align="CENTER", extrude=0.0):
    cu = bpy.data.curves.new(name, "FONT"); cu.body = body; cu.size = size; cu.align_x = align; cu.extrude = extrude
    ob = bpy.data.objects.new(name, cu); coll(c).objects.link(ob)
    ob.location = loc; ob.rotation_euler = rot; cu.materials.append(m)
    if parent is not None: ob.parent = parent
    return ob

# =====================================================================================
def build():
    global ROOTC
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections): bpy.data.collections.remove(c)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.lights, bpy.data.cameras, bpy.data.node_groups):
        for d in list(blk):
            if d.users == 0: blk.remove(d)
    sc = bpy.context.scene
    ROOTC = bpy.data.collections.new("IVAR_Room"); sc.collection.children.link(ROOTC)

    # ---- materials
    wall = mat_paint("wall_paint_white", "#e6e4de")
    wall_reveal = mat_paint("wall_paint_reveal", "#e1dfd9")
    floor = mat_terrazzo()
    base_m = simple("baseboard_grey", "#6a6b6c", 0.45)
    tile = mat_ceiling_tile()
    tbar = simple("ceiling_tbar", "#f4f4f2", 0.4, 0.2)
    led = mat_emit("led_panel_diffuser", "#fbfbf7", 12.0)
    pink = simple("door_pink", "#c71f6f", 0.38)
    glass = mat_glass()
    pvc = simple("pvc_white", "#f6f6f3", 0.32)
    plastic = simple("plastic_white", "#f2f2ef", 0.4)
    anth = simple("sideboard_anthracite", "#232222", 0.5)
    anth_top = simple("sideboard_top", "#2a2928", 0.32)
    alu = mat_brushed()
    steel_blk = simple("steel_black_powder", "#1d1e20", 0.45, 0.4)
    black_gl = simple("black_gloss", "#0a0b0c", 0.08)
    screen = simple("screen_glass", "#050607", 0.05)
    desk_top = simple("desk_laminate_white", "#ecebe7", 0.42)
    desk_edge = simple("desk_edge_grey", "#bdbcb7", 0.4)
    fabric = mat_fabric()
    chrome = simple("chrome", "#e0e3e6", 0.08, 1.0)
    osb = mat_osb()
    wood = mat_wood()
    radiator = simple("radiator_enamel", "#f0efea", 0.3)
    grey_dark = simple("plastic_dark", "#2a2b2d", 0.45)
    yellow = simple("warning_yellow", "#f2c200", 0.5)
    lampglass = mat_frosted()
    perfor = mat_perforated()
    qr = mat_qr()
    outside = mat_outside()
    led_strip = mat_emit("led_strip_warm", "#ffd9a0", 3.0)
    copper = simple("cable_black", "#121212", 0.5)

    # ================= room shell =================
    S = "Приміщення"
    box("Floor", S, floor, -0.0, L, 0, W, -0.03, 0)
    box("Wall_Sideboard", S, wall, -T, L + 0.52, -T, 0, 0, H)
    # partition (Y=W) with opening X 0.79..2.24 (h 2.30) and TV niche X 2.95..4.25 (Z 1.05..1.95, depth 0.10)
    box("Wall_Partition_a", S, wall, -T, 0.79, W, W + T, 0, H)
    box("Wall_Partition_b", S, wall, 2.24, 2.95, W, W + T, 0, H)
    box("Wall_Partition_c", S, wall, 4.25, L + 0.52, W, W + T, 0, H)
    box("Wall_Partition_lintel", S, wall, 0.79, 2.24, W, W + T, 2.30, H)
    box("Wall_Partition_niche_low", S, wall, 2.95, 4.25, W, W + T, 0, 1.05)
    box("Wall_Partition_niche_high", S, wall, 2.95, 4.25, W, W + T, 1.95, H)
    box("Wall_Partition_niche_back", S, wall_reveal, 2.95, 4.25, W + 0.10, W + T, 1.05, 1.95)
    # entrance wall (X=0) with door opening Y 1.25..2.40, h 2.25
    box("Wall_Entrance_a", S, wall, -T, 0, -T, 1.25, 0, H)
    box("Wall_Entrance_b", S, wall, -T, 0, 2.40, W + T, 0, H)
    box("Wall_Entrance_lintel", S, wall, -T, 0, 1.25, 2.40, 2.25, H)
    # window wall: inner face X=L, reveal 0.40 deep, window Y 0.40..1.80, sill 0.90, head 2.75
    R = 0.40
    box("Wall_Window_a", S, wall, L, L + R + 0.12, -T, 0.40, 0, H)
    box("Wall_Window_b", S, wall, L, L + R + 0.12, 1.80, W + T, 0, H)
    box("Wall_Window_below", S, wall, L, L + R + 0.12, 0.40, 1.80, 0, 0.88)
    box("Wall_Window_above", S, wall_reveal, L, L + R + 0.12, 0.40, 1.80, 2.75, H)
    box("Window_sill", S, pvc, L - 0.03, L + R - 0.06, 0.37, 1.83, 0.885, 0.915, bevel=0.006)
    # baseboards (7 cm, 1.2 cm proud)
    for i, a in enumerate([(0, L, 0, 0.012), (0, 0.79, W - 0.012, W), (2.24, L, W - 0.012, W),
                           (0, 0.012, 0, 1.25), (0, 0.012, 2.40, W), (L - 0.012, L, 0, 0.40), (L - 0.012, L, 1.80, W)]):
        box("Baseboard_%d" % i, S, base_m, a[0], a[1], a[2], a[3], 0, 0.07, bevel=0.003)
    # corridor outside the door + neighbour lab floor (placeholders until scanned)
    box("Corridor_floor", S, simple("corridor_floor", "#6f7173", 0.3), -3.2, -T, 0.6, 3.6, -0.03, 0)
    box("Corridor_wall", S, wall, -3.3, -3.2, 0.6, 3.6, 0, H)
    NB = W + T + 5.0                       # placeholder depth of the neighbour lab (real scan comes later)
    nb_wall = mat_paint("wall_paint_neighbour", "#e3e1db")
    box("Neighbour_lab_floor", S, floor, -T, L + T, W + T, NB, -0.03, 0)
    box("Neighbour_lab_wall_back", S, nb_wall, -T, L + T, NB, NB + T, 0, H)
    box("Neighbour_lab_wall_left", S, nb_wall, -T - 0.12, -T, W + T, NB, 0, H)
    box("Neighbour_lab_wall_right", S, nb_wall, L + T, L + T + 0.12, W + T, NB, 0, H)
    box("Neighbour_lab_ceiling", S, tile, -T, L + T, W + T, NB, H, H + 0.04)
    for i, cx in enumerate((1.0, 2.8, 4.6)):
        for j, cy in enumerate((W + 1.4, W + 3.6)):
            box("Neighbour_lab_led_%d_%d" % (i, j), S, led, cx - 0.29, cx + 0.29, cy - 0.29, cy + 0.29, H - 0.012, H, parent=None)

    # ---- window (white PVC): outer frame, mullion, transom, two casements + fixed top lights
    Wn = "Вікно"
    gx = L + R - 0.08                      # glass plane
    win = empty("Window", Wn, props={"name_uk": "Вікно", "description": "Пластикове вікно в глибокій ніші: дві стулки та фрамуга з трьома секціями.", "zone": "window"})
    fw, fd = 0.065, 0.07
    def frame_rect(nm, y0, y1, z0, z1, w=fw, d=fd, x=gx):
        box(nm + "_l", Wn, pvc, x - d / 2, x + d / 2, y0, y0 + w, z0, z1, parent=win, bevel=0.004)
        box(nm + "_r", Wn, pvc, x - d / 2, x + d / 2, y1 - w, y1, z0, z1, parent=win, bevel=0.004)
        box(nm + "_b", Wn, pvc, x - d / 2, x + d / 2, y0, y1, z0, z0 + w, parent=win, bevel=0.004)
        box(nm + "_t", Wn, pvc, x - d / 2, x + d / 2, y0, y1, z1 - w, z1, parent=win, bevel=0.004)
    frame_rect("frame", 0.40, 1.80, 0.915, 2.75)
    box("transom", Wn, pvc, gx - fd / 2, gx + fd / 2, 0.40, 1.80, 2.08, 2.15, parent=win, bevel=0.004)
    box("mullion", Wn, pvc, gx - fd / 2, gx + fd / 2, 1.065, 1.135, 0.915, 2.75, parent=win, bevel=0.004)
    for nm, y0, y1 in (("sash_l", 0.465, 1.065), ("sash_r", 1.135, 1.735)):
        frame_rect(nm, y0, y1, 0.98, 2.08, w=0.055, d=0.06, x=gx - 0.012)
        box(nm + "_glass", Wn, glass, gx - 0.016, gx - 0.008, y0 + 0.05, y1 - 0.05, 1.03, 2.03, parent=win)
        hy = y1 - 0.03 if nm == "sash_l" else y0 + 0.03
        box(nm + "_handle_base", Wn, pvc, gx - 0.06, gx - 0.042, hy - 0.015, hy + 0.015, 1.50, 1.58, parent=win, bevel=0.004)
        box(nm + "_handle", Wn, pvc, gx - 0.075, gx - 0.06, hy - 0.01, hy + 0.01, 1.42, 1.56, parent=win, bevel=0.005)
    for k, (y0, y1) in enumerate(((0.465, 0.88), (0.92, 1.28), (1.32, 1.735))):
        box("toplight_glass_%d" % k, Wn, glass, gx - 0.004, gx + 0.004, y0, y1, 2.15, 2.685, parent=win)
    for k, yc in enumerate((0.90, 1.30)):
        box("toplight_mullion_%d" % k, Wn, pvc, gx - fd / 2, gx + fd / 2, yc - 0.02, yc + 0.02, 2.15, 2.69, parent=win, bevel=0.003)
    box("Outside_view", Wn, outside, L + 6.0, L + 6.05, -4.0, 6.5, -1.5, 6.0)

    # ================= ceiling =================
    C = "Стеля"
    box("Ceiling_slab", C, tile, 0, L, 0, W, H, H + 0.02)
    # T-bar grid: 600 mm, aligned to the LED row
    gx0, gy0 = 0.40, 0.17
    xs = [gx0 + 0.6 * i for i in range(10) if gx0 + 0.6 * i < L]
    ys = [gy0 + 0.6 * i for i in range(5) if gy0 + 0.6 * i < W]
    for i, x in enumerate(xs): box("Tbar_x_%d" % i, C, tbar, x - 0.012, x + 0.012, 0, W, H - 0.008, H, bevel=0.002)
    for i, y in enumerate(ys): box("Tbar_y_%d" % i, C, tbar, 0, L, y - 0.012, y + 0.012, H - 0.008, H, bevel=0.002)
    lamps = []
    for i, cx in enumerate((1.0, 2.8, 4.6)):
        e = empty("LED_panel_%d" % (i + 1), C, (cx, 1.37, H), props={"name_uk": "LED-панель 600×600", "zone": "ceiling"})
        box("frame", C, plastic, -0.30, 0.30, -0.30, 0.30, -0.012, 0.0, parent=e, bevel=0.003)
        box("diffuser", C, led, -0.285, 0.285, -0.285, 0.285, -0.014, -0.012, parent=e)
        lamps.append(cx)
    e = empty("Air_diffuser", C, (3.7, 1.37, H), props={"name_uk": "Вентиляційний дифузор", "zone": "ceiling"})
    box("plate", C, perfor, -0.24, 0.24, -0.24, 0.24, -0.03, -0.015, parent=e, bevel=0.004)
    box("rim", C, plastic, -0.29, 0.29, -0.29, 0.29, -0.015, 0.0, parent=e, bevel=0.003)
    e = empty("KNX_presence_sensor", C, (1.9, 0.95, H), props={"name_uk": "Датчик присутності", "description": "Стельовий датчик присутності/освітленості.", "zone": "ceiling"})
    cyl("ring", C, plastic, 0.075, 0.025, (0, 0, -0.0125), parent=e, seg=48, bevel=0.004)
    sphere("lens", C, simple("sensor_lens", "#d8dadd", 0.15), 0.035, (0, 0, -0.026), (1, 1, 0.55), parent=e)
    sphere("led", C, mat_emit("sensor_led_green", "#38d26b", 5), 0.004, (0.045, 0.0, -0.025), parent=e, seg=12)
    e = empty("Smoke_detector", C, (4.1, 0.6, H), props={"name_uk": "Датчик диму", "zone": "ceiling"})
    cyl("body", C, plastic, 0.05, 0.035, (0, 0, -0.0175), parent=e, seg=40, bevel=0.006)

    # ================= entrance: door, frame, electrical boxes, ducts, sockets =================
    E = "Вхід"
    door = empty("Door", E, props={"name_uk": "Двері (рожеві)", "description": "Вхідні двері з коридору зі склом, відчинені назовні.", "zone": "entrance"})
    for nm, a in (("jamb_l", (-T - 0.01, 0.015, 1.18, 1.25, 0, 2.30)), ("jamb_r", (-T - 0.01, 0.015, 2.40, 2.47, 0, 2.30)),
                  ("head", (-T - 0.01, 0.015, 1.18, 2.47, 2.25, 2.32))):
        box("frame_" + nm, E, pink, *a, parent=door, bevel=0.004)
    leaf = empty("Door_leaf", E, (-T, 2.40, 0), (0, 0, math.radians(172)))
    leaf.parent = door
    lw = 1.13
    box("leaf", E, pink, 0.0, lw, -0.045, 0.0, 0.005, 2.24, parent=leaf, bevel=0.005)
    box("glass", E, glass, 0.32, lw - 0.32, -0.05, 0.005, 0.95, 2.05, parent=leaf)
    for side in (-0.06, 0.015):
        box("lever_plate_%d" % (side > 0), E, steel_blk, lw - 0.13, lw - 0.09, side, side + 0.012, 0.95, 1.18, parent=leaf, bevel=0.003)
        box("lever_%d" % (side > 0), E, steel_blk, lw - 0.26, lw - 0.11, side - 0.035 if side < 0 else side + 0.012, side if side < 0 else side + 0.045, 1.04, 1.065, parent=leaf, bevel=0.006)
    for z in (0.25, 1.1, 1.95):
        cyl("hinge", E, steel_blk, 0.01, 0.11, (0.0, 0.0, z), parent=leaf, seg=16)

    for i, (y0, y1) in enumerate(((0.30, 0.74), (0.80, 1.24))):
        e = empty("Electrical_box_%d" % (i + 1), E, props={"name_uk": "Електрощиток %d" % (i + 1), "description": "Білий настінний щиток біля входу (ймовірно, живлення/KNX).", "zone": "entrance"})
        box("body", E, plastic, 0.0, 0.11, y0, y1, 1.22, 1.98, parent=e, bevel=0.006)
        box("door", E, plastic, 0.11, 0.122, y0 + 0.008, y1 - 0.008, 1.228, 1.972, parent=e, bevel=0.004)
        cyl("lock", E, simple("lock_grey", "#9ea1a4", 0.3, 0.6), 0.008, 0.01, (0.125, y1 - 0.03, 1.60), (0, math.radians(90), 0), parent=e, seg=16)
        if i == 0:
            s, yc, zc = 0.045, y0 + 0.07, 1.90
            tri("warning_sticker", E, yellow, [(0.1235, yc - s / 2, zc - s * 0.43), (0.1235, yc + s / 2, zc - s * 0.43), (0.1235, yc, zc + s * 0.43)], parent=e)
        box("duct_vertical", E, plastic, 0.0, 0.05, (y0 + y1) / 2 - 0.05, (y0 + y1) / 2 + 0.05, 1.98, H, parent=e, bevel=0.003)
    e = empty("Cable_duct_long_wall", E, props={"name_uk": "Кабель-канал з розетками", "zone": "entrance"})
    box("duct", E, plastic, 0.0, L, 0.0, 0.055, 1.07, 1.17, parent=e, bevel=0.004)
    box("lid_line", E, simple("duct_seam", "#d6d6d2", 0.5), 0.0, L, 0.055, 0.0565, 1.118, 1.122, parent=e)
    for k, sx in enumerate((0.45, 3.35, 5.2)):
        for j in range(2):
            x = sx + j * 0.085
            box("socket_%d_%d" % (k, j), E, plastic, x - 0.04, x + 0.04, 0.055, 0.068, 1.08, 1.16, parent=e, bevel=0.006)
            cyl("socket_hole_%d_%d" % (k, j), E, simple("socket_recess", "#d9d9d5", 0.5), 0.022, 0.006, (x, 0.068, 1.12), (math.radians(90), 0, 0), parent=e, seg=24)

    # ================= sideboard =================
    K = "Тумба і KNX-стенд"
    x0, x1, d, h = 0.61, 3.01, 0.62, 0.93
    sb = empty("Sideboard", K, props={"name_uk": "Тумба (антрацит)", "description": "Темна тумба ~2,4 × 0,62 м, висота 0,93 м, з шухлядами й дверцятами.", "zone": "sideboard"})
    box("carcass", K, anth, x0, x1, 0.0, d - 0.02, 0.08, h - 0.025, parent=sb, bevel=0.002)
    box("top", K, anth_top, x0 - 0.01, x1 + 0.01, 0.0, d + 0.005, h - 0.025, h, parent=sb, bevel=0.004, seg=3)
    box("plinth", K, steel_blk, x0 + 0.03, x1 - 0.03, 0.03, d - 0.07, 0.0, 0.08, parent=sb, bevel=0.002)
    box("vent_grille", K, perfor, x0 + 0.05, x0 + 0.40, d - 0.071, d - 0.069, 0.01, 0.07, parent=sb)
    cols = [("door", 0.62), ("drawers", 0.58), ("drawers", 0.58), ("door", 0.62)]
    x = x0
    for k, (kind, w) in enumerate(cols):
        a, b = x + 0.003, x + w - 0.003
        if kind == "drawers":
            for j, (z0, z1) in enumerate(((0.09, 0.355), (0.36, 0.625), (0.63, 0.895))):
                box("drawer_%d_%d" % (k, j), K, anth, a, b, d - 0.02, d, z0 + 0.002, z1 - 0.002, parent=sb, bevel=0.002)
                box("drawer_handle_%d_%d" % (k, j), K, alu, a + 0.005, b - 0.005, d, d + 0.010, z1 - 0.016, z1 - 0.004, parent=sb, bevel=0.002)
        else:
            box("door_%d" % k, K, anth, a, b, d - 0.02, d, 0.092, 0.893, parent=sb, bevel=0.002)
            hx = b - 0.016 if k == 0 else a + 0.004
            box("door_handle_%d" % k, K, alu, hx, hx + 0.012, d, d + 0.010, 0.10, 0.885, parent=sb, bevel=0.002)
        x += w

    # ---- KNX demo stand (OSB panel) on the sideboard, entrance end
    knx = empty("KNX_demo_stand", K, (0.95, 0.30, h), (0, 0, math.radians(125)),
                props={"name_uk": "KNX демо-стенд", "description": "Демонстраційна панель на OSB: вентилятор, два світильники-бра, реле, термостат, вимикачі, сенсорна панель, LED-стрічка по краю. Справжні навчальні стенди — у сусідній лабораторії.", "zone": "sideboard"})
    box("base", K, wood, -0.30, 0.30, -0.14, 0.14, 0.0, 0.035, parent=knx, bevel=0.006, seg=3)
    box("lip", K, wood, -0.30, 0.30, -0.14, -0.115, 0.035, 0.07, parent=knx, bevel=0.004)
    box("board", K, osb, -0.27, 0.27, -0.03, -0.012, 0.035, 0.72, parent=knx, bevel=0.003)
    box("back_leg", K, wood, -0.04, 0.04, -0.012, 0.09, 0.035, 0.45, parent=knx, bevel=0.004)
    # LED strip along both sides and the top edge
    box("led_tape_l", K, grey_dark, -0.268, -0.256, -0.0315, -0.03, 0.05, 0.712, parent=knx)
    box("led_tape_r", K, grey_dark, 0.256, 0.268, -0.0315, -0.03, 0.05, 0.712, parent=knx)
    box("led_tape_t", K, grey_dark, -0.268, 0.268, -0.0315, -0.03, 0.699, 0.712, parent=knx)
    for k in range(60):
        t = k / 59
        if t < 0.4:  zc, xc = 0.06 + t / 0.4 * 0.64, -0.262
        elif t < 0.6: zc, xc = 0.705, -0.262 + (t - 0.4) / 0.2 * 0.524
        else:        zc, xc = 0.70 - (t - 0.6) / 0.4 * 0.64, 0.262
        box("led_%d" % k, K, led_strip, xc - 0.0025, xc + 0.0025, -0.0335, -0.0315, zc - 0.0025, zc + 0.0025, parent=knx)
    dz = -0.03   # device mounting plane (front face of board)
    # fan (square body + round grille)
    box("fan_body", K, plastic, -0.24, -0.10, dz - 0.03, dz, 0.55, 0.69, parent=knx, bevel=0.008, seg=3)
    for k, rr in enumerate((0.055, 0.042, 0.029, 0.016)):
        cyl("fan_ring_%d" % k, K, plastic if k % 2 == 0 else grey_dark, rr, 0.004, (-0.17, dz - 0.032 - 0.001 * k, 0.62), (math.radians(90), 0, 0), parent=knx, seg=40)
    # relay / smart switch module
    box("relay", K, plastic, -0.06, 0.06, dz - 0.03, dz, 0.60, 0.67, parent=knx, bevel=0.006)
    box("relay_led", K, mat_emit("relay_led_blue", "#3a8cff", 4), 0.03, 0.045, dz - 0.0305, dz - 0.029, 0.65, 0.655, parent=knx)
    # two bulkhead lamps (oval glass + white base + guard bars)
    for nm, cx, cz in (("lamp_top", 0.16, 0.60), ("lamp_bottom", -0.08, 0.33)):
        sphere(nm + "_base", K, simple("lamp_body_grey", "#6a6d71", 0.45), 0.07, (cx, dz - 0.012, cz), (0.75, 0.25, 1.0), parent=knx)
        sphere(nm + "_glass", K, lampglass, 0.058, (cx, dz - 0.03, cz), (0.72, 0.42, 1.0), parent=knx)
        for g in (-0.025, 0.0, 0.025):
            box(nm + "_bar", K, simple("lamp_cage", "#3b3d40", 0.4, 0.3), cx + g - 0.002, cx + g + 0.002, dz - 0.058, dz - 0.054, cz - 0.055, cz + 0.055, parent=knx)
        sphere(nm + "_bulb", K, mat_emit("bulb_warm", "#ffe2b0", 2.0), 0.018, (cx, dz - 0.03, cz), parent=knx, seg=16)
    # thermostat, switches, touch panel
    box("thermostat", K, plastic, -0.02, 0.06, dz - 0.018, dz, 0.45, 0.53, parent=knx, bevel=0.008, seg=3)
    box("thermostat_display", K, mat_emit("lcd_blue", "#7fb3ff", 1.0), 0.0, 0.04, dz - 0.0185, dz - 0.017, 0.495, 0.515, parent=knx)
    for k, (sx, sz) in enumerate(((0.12, 0.47), (0.17, 0.47))):
        box("switch_%d" % k, K, plastic, sx - 0.022, sx + 0.022, dz - 0.012, dz, sz - 0.022, sz + 0.022, parent=knx, bevel=0.005)
        box("switch_rocker_%d" % k, K, plastic, sx - 0.016, sx + 0.016, dz - 0.016, dz - 0.012, sz - 0.016, sz + 0.016, parent=knx, bevel=0.003)
    box("touch_panel", K, black_gl, 0.05, 0.21, dz - 0.012, dz, 0.18, 0.29, parent=knx, bevel=0.004)
    box("touch_screen", K, mat_emit("touch_ui", "#1f3d5c", 0.6), 0.06, 0.20, dz - 0.0125, dz - 0.0115, 0.19, 0.28, parent=knx)
    for k, (qx, qz) in enumerate(((-0.20, 0.48), (-0.01, 0.39), (0.24, 0.40), (-0.21, 0.16), (0.09, 0.12), (0.22, 0.65))):
        box("qr_%d" % k, K, qr, qx - 0.018, qx + 0.018, dz - 0.0005, dz, qz - 0.018, qz + 0.018, parent=knx)
    tube("power_cable", K, copper, [(0.0, 0.09, 0.2), (0.0, 0.16, 0.05), (0.15, 0.25, 0.0)], 0.004, parent=knx)

    # ================= window corner: desk, chairs, monitor, camera, radiator =================
    D = "Стіл біля вікна"
    dx0, dx1, dy0, dy1 = 4.71, 5.71, 1.50, 2.74
    desk = empty("Desk", D, props={"name_uk": "Стіл біля вікна", "description": "Білий стіл ~1,0 × 1,25 м на чорних металевих ніжках.", "zone": "window"})
    box("top", D, desk_top, dx0, dx1, dy0, dy1, 0.715, 0.74, parent=desk, bevel=0.003)
    box("edge", D, desk_edge, dx0 - 0.002, dx1 + 0.002, dy0 - 0.002, dy1 + 0.002, 0.712, 0.716, parent=desk)
    for lx in (dx0 + 0.02, dx1 - 0.06):
        for ly in (dy0 + 0.02, dy1 - 0.06):
            box("leg", D, steel_blk, lx, lx + 0.04, ly, ly + 0.04, 0.0, 0.712, parent=desk, bevel=0.003)
    box("apron_x", D, steel_blk, dx0 + 0.04, dx1 - 0.04, dy0 + 0.03, dy0 + 0.05, 0.64, 0.712, parent=desk)
    box("apron_x2", D, steel_blk, dx0 + 0.04, dx1 - 0.04, dy1 - 0.05, dy1 - 0.03, 0.64, 0.712, parent=desk)

    mon = empty("Monitor", D, (5.50, 2.12, 0.74), (0, 0, math.radians(90)), props={"name_uk": "Монітор 24\"", "zone": "window"})
    box("bezel", D, steel_blk, -0.28, 0.28, -0.012, 0.012, 0.12, 0.45, parent=mon, bevel=0.004)
    box("screen", D, screen, -0.27, 0.27, 0.012, 0.0125, 0.13, 0.44, parent=mon)
    box("back", D, steel_blk, -0.16, 0.16, -0.05, -0.012, 0.18, 0.38, parent=mon, bevel=0.02, seg=4)
    box("neck", D, steel_blk, -0.025, 0.025, -0.06, -0.035, 0.02, 0.24, parent=mon, bevel=0.004)
    box("foot", D, steel_blk, -0.11, 0.11, -0.13, 0.06, 0.0, 0.015, parent=mon, bevel=0.006, seg=3)
    cam = empty("Webcam_360", D, (5.12, 2.55, 0.74), props={"name_uk": "Камера (міні)", "zone": "window"})
    cyl("base", D, plastic, 0.035, 0.03, (0, 0, 0.015), parent=cam, seg=32, bevel=0.004)
    sphere("head", D, plastic, 0.035, (0, 0, 0.06), parent=cam)
    sphere("lens", D, black_gl, 0.012, (-0.03, 0, 0.065), parent=cam, seg=16)

    for i, cy in enumerate((1.80, 2.40)):
        ch = empty("Chair_%d" % (i + 1), D, (4.45, cy, 0), (0, 0, 0), props={"name_uk": "Стілець ISO", "description": "Чорний стілець ISO на хромованому каркасі.", "zone": "window"})
        box("seat", D, fabric, -0.22, 0.22, -0.23, 0.23, 0.44, 0.49, parent=ch, bevel=0.02, seg=4, smooth=True)
        bk = box("backrest", D, fabric, -0.025, 0.025, -0.22, 0.22, 0.0, 0.30, parent=ch, bevel=0.02, seg=4, smooth=True)
        bk.location = (-0.235, 0, 0.56); bk.rotation_euler = (0, math.radians(-8), 0)
        for sy in (-0.2, 0.2):
            tube("frame_side", D, chrome, rounded_path([(0.24, sy, 0.012), (0.20, sy, 0.43), (-0.20, sy, 0.43), (-0.24, sy, 0.012)], 0.035), 0.011, parent=ch)
            tube("back_post", D, chrome, rounded_path([(-0.18, sy, 0.43), (-0.23, sy, 0.50), (-0.27, sy, 0.85)], 0.03), 0.010, parent=ch)
        tube("seat_brace", D, chrome, [(0.18, -0.2, 0.43), (0.18, 0.2, 0.43)], 0.008, parent=ch)
        for gx_, gy in ((0.24, -0.2), (0.24, 0.2), (-0.24, -0.2), (-0.24, 0.2)):
            cyl("glide", D, grey_dark, 0.013, 0.012, (gx_, gy, 0.006), parent=ch, seg=16)

    rad = empty("Radiator", D, props={"name_uk": "Радіатор", "description": "Чавунний секційний радіатор під вікном.", "zone": "window"})
    n = 14; y0 = 0.58; step = 0.075
    for k in range(n):
        y = y0 + k * step
        for xo in (-0.035, 0.035):
            cyl("col_%d" % k, D, radiator, 0.017, 0.50, (L - 0.11 + xo, y, 0.43), parent=rad, seg=16)
        box("sec_top_%d" % k, D, radiator, L - 0.155, L - 0.065, y - 0.028, y + 0.028, 0.66, 0.72, parent=rad, bevel=0.02, seg=3)
        box("sec_bot_%d" % k, D, radiator, L - 0.155, L - 0.065, y - 0.028, y + 0.028, 0.14, 0.20, parent=rad, bevel=0.02, seg=3)
    tube("pipe_top", D, radiator, rounded_path([(L - 0.11, y0 - 0.06, 0.69), (L - 0.11, 0.42, 0.69), (L - 0.03, 0.42, 0.69)]), 0.012, parent=rad)
    tube("pipe_return", D, radiator, rounded_path([(L - 0.11, y0 + (n - 1) * step + 0.06, 0.17), (L - 0.11, 1.75, 0.17), (L - 0.11, 1.75, 0.66), (L - 0.03, 1.75, 0.66)]), 0.012, parent=rad)
    for yb in (0.62, 1.50):
        box("bracket", D, steel_blk, L - 0.06, L, yb - 0.01, yb + 0.01, 0.62, 0.64, parent=rad)

    # ================= partition: TV in niche =================
    P = "Перегородка і ТВ"
    tv = empty("TV", P, (3.60, W + 0.06, 1.475), (0, 0, 0), props={"name_uk": "Телевізор у ніші", "description": "Телевізор ~50\" у ніші перегородки.", "zone": "partition"})
    box("body", P, steel_blk, -0.56, 0.56, -0.012, 0.035, -0.325, 0.325, parent=tv, bevel=0.004)
    box("screen", P, screen, -0.55, 0.55, -0.0125, -0.012, -0.315, 0.315, parent=tv)
    box("logo", P, chrome, -0.02, 0.02, -0.0128, -0.012, -0.322, -0.318, parent=tv)
    box("tv_box", P, plastic, 0.30, 0.42, -0.10, -0.01, -0.43, -0.40, parent=tv, bevel=0.004)
    tube("tv_cable", P, plastic, [(0.36, -0.06, -0.43), (0.36, -0.03, -0.36), (0.30, 0.0, -0.30)], 0.003, parent=tv)

    # ================= scan reference (hidden) =================
    if os.path.exists(SCAN):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=SCAN)
        rc = coll("Скан LiDAR (референс)")
        for o in [o for o in bpy.data.objects if o not in before]:
            for c in list(o.users_collection): c.objects.unlink(o)
            rc.objects.link(o)
            if o.type == "MESH":
                o.data.transform(o.matrix_world); o.matrix_world = Matrix.Identity(4)
                if max(o.dimensions) < 1.0: o.data.transform(Matrix.Scale(100.0, 4))
                o.data.transform(Matrix.Translation(SCAN_OFFSET) @ Matrix.Rotation(-SCAN_ANGLE, 4, "Z"))
                o.name = "LiDAR_scan"
        rc.hide_render = True

    # ================= convert curves to meshes (Unity-friendly) =================
    dg = bpy.context.evaluated_depsgraph_get()
    for o in [o for o in bpy.data.objects if o.type == "CURVE"]:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        nm, par, cols, mw = o.name, o.parent, list(o.users_collection), o.matrix_world.copy()
        new = bpy.data.objects.new(nm + "_mesh", me)
        for c in cols: c.objects.link(new)
        new.parent = par; new.matrix_basis = o.matrix_basis.copy()
        for p in me.polygons: p.use_smooth = True
        bpy.data.objects.remove(o, do_unlink=True)

    # ================= lights =================
    LC = coll("Світло і камери")
    wd = bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); sc.world = wd
    try: wd.use_nodes = True
    except Exception: pass
    bg = wd.node_tree.nodes.get("Background")
    if bg: bg.inputs[0].default_value = (*srgb("#cdd6df"), 1); bg.inputs[1].default_value = 0.35
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); LC.objects.link(sun)
    sun.data.energy = 3.2; sun.data.angle = math.radians(2.0); sun.data.color = srgb("#fff1dc")
    sun.rotation_euler = (math.radians(58), 0, math.radians(105))
    for i, cx in enumerate(lamps):
        a = bpy.data.objects.new("Area_LED_%d" % i, bpy.data.lights.new("Area_LED_%d" % i, "AREA")); LC.objects.link(a)
        a.data.energy = 70; a.data.size = 0.57; a.data.color = srgb("#fff8ee"); a.location = (cx, 1.37, H - 0.02)
    win_l = bpy.data.objects.new("Window_light", bpy.data.lights.new("Window_light", "AREA")); LC.objects.link(win_l)
    win_l.data.shape = "RECTANGLE"; win_l.data.size = 1.3; win_l.data.size_y = 1.7; win_l.data.energy = 120
    win_l.data.color = srgb("#e8eef5"); win_l.location = (L + 0.25, 1.10, 1.85); win_l.rotation_euler = (0, math.radians(90), 0)
    win_l.visible_camera = False
    for attr in ("visible_glossy", "visible_transmission"):
        try: setattr(win_l, attr, False)
        except Exception: pass
    nb_l = bpy.data.objects.new("Neighbour_light", bpy.data.lights.new("Neighbour_light", "AREA")); LC.objects.link(nb_l)
    nb_l.data.shape = "RECTANGLE"; nb_l.data.size = L; nb_l.data.size_y = 4.0; nb_l.data.energy = 450
    nb_l.data.color = srgb("#fff8ee"); nb_l.location = (L / 2, W + T + 2.5, H - 0.05)
    nb_l.visible_camera = False

    # ================= cameras =================
    def camera(name, loc, tgt, lens=18, ortho=None):
        cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = 0.02
        if ortho: cd.type = "ORTHO"; cd.ortho_scale = ortho
        co = bpy.data.objects.new(name, cd); LC.objects.link(co); co.location = loc
        co.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return co
    c_over = camera("Cam_Overview", (7.5, -3.2, 5.6), (2.6, 1.4, 0.6), 24)
    c_plan = camera("Cam_Plan", (L / 2, W / 2 + 0.4, 12), (L / 2, W / 2 + 0.4, 0), ortho=7.8); c_plan.rotation_euler = (0, 0, 0)
    c_win = camera("Cam_From_Window", (5.3, 0.95, 1.6), (0.0, 1.25, 1.1), 16)
    c_door = camera("Cam_From_Door", (0.35, 1.75, 1.6), (5.8, 1.1, 1.25), 16)
    c_knx = camera("Cam_KNX_Stand", (1.75, 1.05, 1.45), (0.95, 0.30, 1.25), 30)

    # ================= render =================
    r = sc.render
    try:
        r.engine = "CYCLES"
        cyc = sc.cycles; cyc.samples = RENDER_SAMPLES; cyc.use_adaptive_sampling = True; cyc.use_denoising = True
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dt in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = dt; prefs.get_devices()
                gpus = [d for d in prefs.devices if d.type == dt]
                if gpus:
                    for dv in prefs.devices: dv.use = dv.type == dt
                    cyc.device = "GPU"; log("cycles device", dt, gpus[0].name); break
            except Exception: pass
    except Exception as ex:
        log("cycles setup failed", ex)
    try:
        sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception: pass
    sc.view_settings.exposure = -0.65
    r.resolution_x, r.resolution_y = 1600, 1000
    rdir = os.path.join(OUT, "renders"); os.makedirs(rdir, exist_ok=True)
    ceil = COLLS["Стеля"]
    shots = (("v3_overview", c_over, True, True), ("v3_from_window", c_win, False, False), ("v3_from_door", c_door, False, False),
             ("v3_knx_stand", c_knx, False, False), ("v3_plan", c_plan, True, True))
    for nm, c, hide_ceiling, cut in shots:
        ceil.hide_render = hide_ceiling
        for o in bpy.data.objects:
            if o.name.startswith(("Wall_Sideboard", "Wall_Window", "Window_sill")) or (o.parent and o.parent.name == "Window") or o.name == "Window":
                o.hide_render = cut
            if o.name.startswith("Neighbour_lab_ceiling") or o.name.startswith("Neighbour_lab_led"):
                o.hide_render = hide_ceiling
            if o.name.startswith("Cable_duct_long_wall") or (o.parent and o.parent.name == "Cable_duct_long_wall"):
                o.hide_render = cut
        sc.camera = c
        r.filepath = os.path.join(rdir, nm + ".png")
        bpy.ops.render.render(write_still=True); log("rendered", nm)
    for o in bpy.data.objects: o.hide_render = False
    ceil.hide_render = False
    sc.camera = c_door

    # viewport: material preview, scan hidden
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.type = "MATERIAL"
    for lc in bpy.context.view_layer.layer_collection.children["IVAR_Room"].children:
        if lc.name.startswith("Скан"): lc.hide_viewport = True
    path = os.path.join(OUT, "ivar-lab-taltech.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
    log("saved", path, "objects", len(bpy.data.objects), "materials", len(bpy.data.materials))

try:
    build(); log("OK")
except Exception:
    log("ERROR\n" + traceback.format_exc())
finally:
    open(os.path.join(OUT, "build_log_v3.txt"), "w", encoding="utf-8").write("\n".join(LOG))
    print("\n".join(LOG))
