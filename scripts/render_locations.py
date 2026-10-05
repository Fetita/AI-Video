#!/usr/bin/env python3
"""
render_locations.py -- procedural "location scout" photographs for the promo film.

Every scene below is built from code with Blender's Python module (bpy) and
rendered with Cycles on the CPU: geometry is made of primitives (boxes, tubes,
bmesh shapes), all materials are procedural shader graphs (Brick / Noise /
Voronoi / Wave / White-Noise textures), lighting is a physical sun lamp plus a
Nishita sky, the view transform is AgX and the image is denoised with
OpenImageDenoise.  No image textures, no downloaded assets, no AI generation.

Output: video/assets/places/<name>.jpg  (1600x900, sRGB JPEG, ~q88, <350 KB)

Setup: Python 3.11 venv with the Blender wheel (`pip install bpy==5.0.1`, or a local
bpy-5.0.1-cp311-*.whl); headless Linux may need libX11/libXi/libXxf86vm/libXfixes/
libXrender/libSM/libGL from apt.  Then run it with that venv's python, e.g.

    python scripts/render_locations.py                       # all shots, final quality
    python scripts/render_locations.py --only loft studio    # a subset
    python scripts/render_locations.py --only loft --samples 32 --res 0.4   # quick preview
    python scripts/render_locations.py --out /tmp/previews   # write elsewhere

or through Blender:  blender -b -P scripts/render_locations.py -- --only mill

Scenes: loft studio mill rooftop (hero shortlist), warehouse office barn (rejected
candidates), cafe house chapel greenhouse pool library (catalogue thumbnails).
The default budget (48 base samples, scaled per scene, adaptive + OIDN) renders each
shot in roughly 1-4.5 minutes on 4 CPU cores; --blend also saves the .blend file.
"""
import argparse
import math
import os
import random
import sys
import time

import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "video", "assets", "places")
MAX_BYTES = 350 * 1024
LOFT_HAZE = 0.008  # loft volumetric dust density (0 disables)
DETAIL_CAP = 4.0  # fBm octaves are the main shading cost; more is invisible at 1600 px

V = Vector
rad = math.radians


# ----------------------------------------------------------------------------
# shader-graph helper
# ----------------------------------------------------------------------------
class Tree:
    """Tiny DSL around a node tree: every helper returns an output socket."""

    def __init__(self, nt):
        self.nt = nt
        self.nodes = nt.nodes
        self.links = nt.links

    # -- plumbing -----------------------------------------------------------
    def node(self, typ, ins=None, **props):
        n = self.nodes.new(typ)
        for k, v in props.items():
            setattr(n, k, v)
        for k, v in (ins or {}).items():
            self.inp(n, k, v)
        return n

    @staticmethod
    def sock(n, key, outputs=False):
        coll = n.outputs if outputs else n.inputs
        if isinstance(key, int):
            return coll[key]
        for s in coll:
            if s.identifier == key:
                return s
        for s in coll:
            if s.name == key and s.enabled:
                return s
        for s in coll:
            if s.name == key:
                return s
        raise KeyError(f"{n.bl_idname}: no socket {key}")

    def inp(self, n, key, v):
        s = self.sock(n, key)
        if isinstance(v, bpy.types.NodeSocket):
            self.links.new(v, s)
            return
        if isinstance(v, bpy.types.Node):
            self.links.new([o for o in v.outputs if o.enabled][0], s)
            return
        if s.type == "RGBA":
            if isinstance(v, (int, float)):
                v = (v, v, v, 1.0)
            elif len(v) == 3:
                v = (*v, 1.0)
        elif s.type == "VECTOR" and isinstance(v, (int, float)):
            v = (v, v, v)
        elif s.type in ("VALUE", "INT") and isinstance(v, (tuple, list)):
            v = v[0]
        s.default_value = v

    def out(self, n, key=0):
        return self.sock(n, key, outputs=True)

    # -- inputs ---------------------------------------------------------------
    def geo(self, key="Position"):
        return self.out(self.node("ShaderNodeNewGeometry"), key)

    def coord(self, key="Object"):
        return self.out(self.node("ShaderNodeTexCoord"), key)

    def value(self, v):
        n = self.node("ShaderNodeValue")
        n.outputs[0].default_value = v
        return n.outputs[0]

    # -- math -------------------------------------------------------------------
    def math(self, op, a, b=0.5, c=0.0, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.inp(n, 0, a)
        self.inp(n, 1, b)
        if len(n.inputs) > 2:
            self.inp(n, 2, c)
        return n.outputs[0]

    def add(self, a, b):
        return self.math("ADD", a, b)

    def mul(self, a, b):
        return self.math("MULTIPLY", a, b)

    def vmath(self, op, a, b=(0, 0, 0), scale=1.0):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.inp(n, 0, a)
        self.inp(n, 1, b)
        if op == "SCALE":
            self.inp(n, "Scale", scale)
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs["Vector"]

    def sep(self, v):
        n = self.node("ShaderNodeSeparateXYZ")
        self.inp(n, 0, v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def comb(self, x=0.0, y=0.0, z=0.0):
        n = self.node("ShaderNodeCombineXYZ")
        self.inp(n, 0, x)
        self.inp(n, 1, y)
        self.inp(n, 2, z)
        return n.outputs[0]

    def maprange(self, v, a, b, c=0.0, d=1.0, clamp=True, interp="LINEAR"):
        n = self.node("ShaderNodeMapRange", clamp=clamp, interpolation_type=interp)
        self.inp(n, "Value", v)
        self.inp(n, "From Min", a)
        self.inp(n, "From Max", b)
        self.inp(n, "To Min", c)
        self.inp(n, "To Max", d)
        return n.outputs["Result"]

    def mix(self, fac, a, b, blend="MIX", clamp=False):
        n = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend, clamp_result=clamp)
        self.inp(n, "Factor_Float", fac)
        self.inp(n, "A_Color", a)
        self.inp(n, "B_Color", b)
        return self.out(n, "Result_Color")

    def mixf(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="FLOAT")
        self.inp(n, "Factor_Float", fac)
        self.inp(n, "A_Float", a)
        self.inp(n, "B_Float", b)
        return self.out(n, "Result_Float")

    def mixv(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="VECTOR")
        self.inp(n, "Factor_Float", fac)
        self.inp(n, "A_Vector", a)
        self.inp(n, "B_Vector", b)
        return self.out(n, "Result_Vector")

    def ramp(self, fac, stops, interp="LINEAR", alpha=False):
        n = self.node("ShaderNodeValToRGB")
        self.inp(n, 0, fac)
        cr = n.color_ramp
        cr.interpolation = interp
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for el, (p, c) in zip(cr.elements, stops):
            el.position = p
            if isinstance(c, (int, float)):
                c = (c, c, c, 1)
            elif len(c) == 3:
                c = (*c, 1)
            el.color = c
        return n.outputs["Alpha"] if alpha else n.outputs["Color"]

    def hsv(self, col, h=0.5, s=1.0, v=1.0, fac=1.0):
        n = self.node("ShaderNodeHueSaturation")
        self.inp(n, "Hue", h)
        self.inp(n, "Saturation", s)
        self.inp(n, "Value", v)
        self.inp(n, "Fac", fac)
        self.inp(n, "Color", col)
        return n.outputs[0]

    def bw(self, col):
        n = self.node("ShaderNodeRGBToBW")
        self.inp(n, 0, col)
        return n.outputs[0]

    # -- textures ---------------------------------------------------------------
    def noise(self, vec, scale=5.0, detail=4.0, rough=0.5, dist=0.0, dims="3D", w=0.0, key="Fac"):
        n = self.node("ShaderNodeTexNoise", noise_dimensions=dims)
        detail = min(detail, DETAIL_CAP)
        if vec is not None:
            self.inp(n, "Vector", vec)
        self.inp(n, "Scale", scale)
        self.inp(n, "Detail", detail)
        self.inp(n, "Roughness", rough)
        self.inp(n, "Distortion", dist)
        if dims in ("1D", "4D"):
            self.inp(n, "W", w)
        return n.outputs[key]

    def voronoi(self, vec, scale=5.0, feature="F1", dims="3D", rnd=1.0, key="Distance", metric="EUCLIDEAN"):
        n = self.node("ShaderNodeTexVoronoi", feature=feature, voronoi_dimensions=dims, distance=metric)
        if vec is not None:
            self.inp(n, "Vector", vec)
        self.inp(n, "Scale", scale)
        self.inp(n, "Randomness", rnd)
        return n.outputs[key]

    def wave(self, vec, scale=1.0, distortion=0.0, detail=2.0, wtype="BANDS", direction="X", profile="SIN", key="Fac", dscale=1.0):
        n = self.node("ShaderNodeTexWave", wave_type=wtype, bands_direction=direction, rings_direction="X", wave_profile=profile)
        if vec is not None:
            self.inp(n, "Vector", vec)
        self.inp(n, "Scale", scale)
        self.inp(n, "Distortion", distortion)
        self.inp(n, "Detail", detail)
        self.inp(n, "Detail Scale", dscale)
        return n.outputs[key]

    def white(self, vec, dims="3D", key="Value", w=0.0):
        n = self.node("ShaderNodeTexWhiteNoise", noise_dimensions=dims)
        self.inp(n, "Vector", vec)
        if dims in ("1D", "4D"):
            self.inp(n, "W", w)
        return n.outputs[key]

    def brick(self, vec, c1, c2, mortar, bw=0.225, rh=0.075, msize=0.01, smooth=0.1, bias=0.0, offset=0.5, freq=2, scale=1.0):
        n = self.node("ShaderNodeTexBrick", offset=offset, offset_frequency=freq, squash=1.0, squash_frequency=1)
        self.inp(n, "Vector", vec)
        self.inp(n, "Color1", c1)
        self.inp(n, "Color2", c2)
        self.inp(n, "Mortar", mortar)
        self.inp(n, "Scale", scale)
        self.inp(n, "Mortar Size", msize)
        self.inp(n, "Mortar Smooth", smooth)
        self.inp(n, "Bias", bias)
        self.inp(n, "Brick Width", bw)
        self.inp(n, "Row Height", rh)
        return n.outputs["Color"], n.outputs["Fac"]

    def bump(self, height, strength=1.0, distance=0.01, normal=None, invert=False):
        n = self.node("ShaderNodeBump", invert=invert)
        self.inp(n, "Height", height)
        self.inp(n, "Strength", strength)
        self.inp(n, "Distance", distance)
        if normal is not None:
            self.inp(n, "Normal", normal)
        return n.outputs["Normal"]

    # -- shaders ------------------------------------------------------------------
    PRINCIPLED_KEYS = {
        "base": "Base Color", "metal": "Metallic", "rough": "Roughness", "normal": "Normal",
        "spec": "Specular IOR Level", "ior": "IOR", "alpha": "Alpha", "coat": "Coat Weight",
        "coat_rough": "Coat Roughness", "sheen": "Sheen Weight", "sheen_rough": "Sheen Roughness",
        "sss": "Subsurface Weight", "sss_radius": "Subsurface Radius", "sss_scale": "Subsurface Scale",
        "trans": "Transmission Weight", "emit": "Emission Color", "emit_str": "Emission Strength",
        "aniso": "Anisotropic", "sheen_tint": "Sheen Tint", "coat_normal": "Coat Normal",
    }

    def principled(self, **kw):
        n = self.node("ShaderNodeBsdfPrincipled")
        for k, v in kw.items():
            self.inp(n, self.PRINCIPLED_KEYS.get(k, k), v)
        return n.outputs[0]

    def shader(self, typ, **ins):
        n = self.node(typ)
        for k, v in ins.items():
            self.inp(n, k, v)
        return n.outputs[0]

    def mixshader(self, fac, a, b):
        n = self.node("ShaderNodeMixShader")
        self.inp(n, 0, fac)
        self.links.new(a, n.inputs[1])
        self.links.new(b, n.inputs[2])
        return n.outputs[0]

    def addshader(self, a, b):
        n = self.node("ShaderNodeAddShader")
        self.links.new(a, n.inputs[0])
        self.links.new(b, n.inputs[1])
        return n.outputs[0]

    def emission(self, color, strength):
        return self.shader("ShaderNodeEmission", Color=color, Strength=strength)

    def fresnel(self, ior=1.5):
        return self.out(self.node("ShaderNodeFresnel", {"IOR": ior}))

    def layer_weight(self, blend=0.5, key="Facing"):
        return self.out(self.node("ShaderNodeLayerWeight", {"Blend": blend}), key)

    def lightpath(self, key):
        return self.out(self.node("ShaderNodeLightPath"), key)


def new_material(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    m.node_tree.nodes.clear()
    T = Tree(m.node_tree)
    T.output = T.node("ShaderNodeOutputMaterial")
    return m, T


def finish(m, T, surface, volume=None):
    T.links.new(surface, T.output.inputs["Surface"])
    if volume is not None:
        T.links.new(volume, T.output.inputs["Volume"])
    return m


def simple(name, base, rough=0.5, metal=0.0, **kw):
    m, T = new_material(name)
    return finish(m, T, T.principled(base=base, rough=rough, metal=metal, **kw))


# ----------------------------------------------------------------------------
# coordinate helpers (inside a material)
# ----------------------------------------------------------------------------
def planar_uv(T, pos=None, nrm=None):
    """World-space planar projection chosen by the dominant normal axis:
    X-facing -> (y, z), Y-facing -> (x, z), Z-facing -> (x, y).  Lets one brick or
    concrete material wrap consistently around walls, reveals and soffits."""
    pos = pos or T.geo("Position")
    nrm = nrm or T.geo("Normal")
    px, py, pz = T.sep(pos)
    nx, ny, nz = T.sep(nrm)
    ax, ay, az = (T.math("ABSOLUTE", c) for c in (nx, ny, nz))
    isx = T.mul(T.math("GREATER_THAN", ax, ay), T.math("GREATER_THAN", ax, az))
    isz = T.mul(T.math("GREATER_THAN", az, ax), T.math("GREATER_THAN", az, ay))
    v = T.mixv(isx, T.comb(px, pz, 0.0), T.comb(py, pz, 0.0))
    return T.mixv(isz, v, T.comb(px, py, 0.0))


# ----------------------------------------------------------------------------
# material library
# ----------------------------------------------------------------------------
def mat_brick(name="brick", c_dark=(0.20, 0.060, 0.035), c_light=(0.42, 0.15, 0.08), mortar=(0.50, 0.46, 0.40),
              soot=0.35, grime_height=0.9, scale=1.0, bump=1.0, painted=None, efflo=0.25, uv=None):
    """Exposed brick: per-brick colour variation, burnt headers, grit, soot patches,
    efflorescence, rough recessed mortar with irregular edges."""
    m, T = new_material(name)
    pos = T.geo("Position")
    uv = uv if uv is not None else planar_uv(T, pos)
    uv = T.vmath("SCALE", uv, scale=1.0 / scale)
    bwid, rowh = 0.225, 0.0755
    # irregular mortar line: perturb lookup vector slightly
    jitter = T.vmath("SCALE", T.vmath("SUBTRACT", T.noise(uv, 18.0, 3, 0.6, key="Color"), (0.5, 0.5, 0.5)), scale=0.006)
    uvj = T.vmath("ADD", uv, jitter)
    col, fac = T.brick(uvj, c_dark, c_light, mortar, bw=bwid, rh=rowh, msize=0.0105, smooth=0.35, bias=-0.1)
    # independent per-brick random numbers (shift by whole bricks / even rows)
    r2, _ = T.brick(T.vmath("ADD", uvj, (bwid * 13, rowh * 2 * 7, 0)), 0.0, 1.0, 0.0, bw=bwid, rh=rowh, msize=0.0, bias=0.0)
    r3, _ = T.brick(T.vmath("ADD", uvj, (bwid * 29, rowh * 2 * 3, 0)), 0.0, 1.0, 0.0, bw=bwid, rh=rowh, msize=0.0, bias=0.0)
    r2 = T.bw(r2)
    r3 = T.bw(r3)
    # some burnt / dark bricks, some pale salmon ones
    burnt = T.maprange(r2, 0.78, 0.95)
    col = T.mix(T.mul(burnt, 0.75), col, (0.09, 0.035, 0.03))
    pale = T.maprange(r3, 0.85, 1.0)
    col = T.mix(T.mul(pale, 0.5), col, (0.55, 0.30, 0.20))
    # grit inside each brick
    grit = T.noise(pos, 55.0, 6, 0.65)
    col = T.mix(0.55, col, T.ramp(grit, [(0.3, (0.55, 0.52, 0.5)), (0.7, (1.25, 1.2, 1.15))]), blend="MULTIPLY")
    pits = T.voronoi(pos, 140.0, feature="F1")
    pits = T.maprange(pits, 0.0, 0.12, 1.0, 0.0)
    # mortar mask with crumbly edges
    mnoise = T.noise(pos, 45.0, 4, 0.6)
    mask = T.maprange(T.add(fac, T.mul(T.add(mnoise, -0.5), 0.9)), 0.25, 0.55)
    mortar_col = T.mix(T.noise(pos, 9.0, 4, 0.6), (mortar[0] * 0.8, mortar[1] * 0.78, mortar[2] * 0.75), (mortar[0] * 1.12, mortar[1] * 1.1, mortar[2] * 1.08))
    col = T.mix(mask, col, mortar_col)
    # efflorescence (whitish bloom) + soot / grime at large scale
    big = T.noise(pos, 0.45, 5, 0.6, dist=0.3)
    ef = T.mul(T.maprange(big, 0.58, 0.75), efflo)
    col = T.mix(T.mul(ef, T.maprange(T.noise(pos, 12.0, 4), 0.35, 0.7)), col, (0.62, 0.58, 0.52))
    sootn = T.noise(pos, 0.8, 6, 0.7)
    so = T.mul(T.maprange(sootn, 0.45, 0.7), soot)
    col = T.mix(T.mul(so, 0.6), col, (0.10, 0.07, 0.06))
    # vertical rain-washed / soot streaks
    streak = T.noise(T.vmath("MULTIPLY", pos, (2.5, 2.5, 0.12)), 3.0, 3, 0.5)
    col = T.mix(T.mul(T.maprange(streak, 0.5, 0.75), soot * 0.9), col, T.mix(1.0, col, (0.55, 0.5, 0.46), blend="MULTIPLY"))
    _, _, pz = T.sep(pos)
    grime = T.mul(T.maprange(pz, grime_height, 0.0), 0.35)
    col = T.mix(grime, col, (0.08, 0.06, 0.05))
    col = T.mix(T.mul(pits, 0.5), col, (0.05, 0.03, 0.02))
    if painted is not None:
        # whitewashed / painted brick: paint colour with chips showing brick
        chips = T.maprange(T.noise(pos, 3.0, 8, 0.7), 0.6, 0.66)
        pcol = T.mix(T.noise(pos, 2.0, 3), painted, [c * 0.9 for c in painted])
        pcol = T.mix(T.mul(mask, 0.5), pcol, [c * 0.8 for c in painted])
        col = T.mix(chips, pcol, col)
    rough = T.add(T.mul(mask, 0.08), T.maprange(grit, 0.2, 0.8, 0.78, 0.92))
    height = T.add(T.mul(T.math("SUBTRACT", 1.0, mask), 1.0), T.mul(grit, 0.25))
    height = T.add(height, T.mul(pits, -0.3))
    nrm = T.bump(height, strength=0.85 * bump, distance=0.012)
    return finish(m, T, T.principled(base=col, rough=rough, normal=nrm, spec=0.35))


def mat_wood_floor(name="floor", plank_w=0.19, plank_l=2.4, c_dark=(0.13, 0.065, 0.032), c_light=(0.36, 0.20, 0.10),
                   rough=(0.28, 0.55), gap=0.003, worn=0.35, axis="X", grey=0.0):
    """Random-length plank floor: per-plank tint, streaky grain, wear, gaps."""
    m, T = new_material(name)
    pos = T.geo("Position")
    px, py, pz = T.sep(pos)
    if axis == "Y":
        px, py = py, px
    row = T.math("FLOOR", T.math("DIVIDE", py, plank_w))
    rshift = T.mul(T.white(T.comb(row, 0.0, 0.0)), plank_l)
    xs = T.add(px, rshift)
    col_id = T.math("FLOOR", T.math("DIVIDE", xs, plank_l))
    pid = T.comb(row, col_id, 0.0)
    rnd = T.white(pid)
    rnd2 = T.white(T.vmath("ADD", pid, (17.3, 4.1, 0)))
    # gaps
    fy = T.math("FRACT", T.math("DIVIDE", py, plank_w))
    fx = T.math("FRACT", T.math("DIVIDE", xs, plank_l))
    gy = T.math("MINIMUM", fy, T.math("SUBTRACT", 1.0, fy))
    gx = T.math("MINIMUM", fx, T.math("SUBTRACT", 1.0, fx))
    gapm = T.math("MAXIMUM", T.maprange(gy, gap / plank_w, 0.0), T.maprange(gx, gap / plank_l * 0.6, 0.0))
    # grain: noise stretched along the plank, offset per plank
    gv = T.comb(T.mul(xs, 0.6), T.mul(T.add(py, T.mul(rnd, 37.0)), 28.0), T.mul(rnd2, 50.0))
    grain = T.noise(gv, 1.5, 8, 0.62, dist=0.4)
    rings = T.wave(T.comb(T.mul(xs, 0.04), T.add(py, T.mul(rnd, 9.0)), pz), 9.0, 6.0, 4, wtype="BANDS", direction="Y", dscale=1.2)
    base = T.mix(rnd, c_dark, c_light)
    base = T.hsv(base, h=T.maprange(rnd2, 0, 1, 0.48, 0.52), s=T.maprange(rnd2, 0, 1, 0.85, 1.1), v=1.0)
    g = T.ramp(T.add(T.mul(grain, 0.7), T.mul(rings, 0.3)), [(0.25, 0.55), (0.55, 1.0), (0.8, 1.25)])
    col = T.mix(1.0, base, g, blend="MULTIPLY")
    # wear: lighter, drier wood in big patches
    wear = T.mul(T.maprange(T.noise(pos, 0.35, 4, 0.6), 0.45, 0.72), worn)
    col = T.mix(wear, col, T.hsv(col, s=0.75, v=1.45))
    if grey:
        col = T.mix(grey, col, T.hsv(col, s=0.25, v=1.3))
    col = T.mix(gapm, col, (0.02, 0.012, 0.008))
    scratches = T.maprange(T.noise(T.comb(T.mul(px, 3.0), T.mul(py, 0.4), 0.0), 25.0, 2, 0.5), 0.62, 0.7)
    r = T.maprange(T.noise(pos, 1.2, 4, 0.6), 0.3, 0.7, rough[0], rough[1])
    r = T.add(r, T.mul(wear, 0.25))
    r = T.add(r, T.mul(scratches, 0.12))
    r = T.add(r, T.mul(gapm, 0.5))
    h = T.add(T.mul(gapm, -1.0), T.mul(grain, 0.08))
    nrm = T.bump(h, 0.6, 0.004)
    return finish(m, T, T.principled(base=col, rough=r, normal=nrm, spec=0.5))


def mat_concrete(name="concrete", base=(0.42, 0.41, 0.39), rough=(0.65, 0.9), stains=0.5, formwork=False,
                 polished=False, bump=1.0, scale=1.0, var=1.0, pores=0.6):
    m, T = new_material(name)
    pos = T.geo("Position")
    sp = T.vmath("SCALE", pos, scale=1.0 / scale)
    big = T.noise(sp, 0.35, 5, 0.6, dist=0.2)
    mid = T.noise(sp, 3.5, 6, 0.6)
    fine = T.noise(sp, 70.0, 4, 0.6)
    col = T.mix(var, base, T.mix(1.0, base, T.ramp(big, [(0.3, 0.80), (0.5, 1.0), (0.75, 1.12)]), blend="MULTIPLY"))
    col = T.mix(1.0, col, T.ramp(mid, [(0.3, 0.9), (0.7, 1.08)]), blend="MULTIPLY")
    col = T.mix(1.0, col, T.ramp(fine, [(0.35, 0.9), (0.65, 1.07)]), blend="MULTIPLY")
    pw = pores
    pores = T.mul(T.maprange(T.voronoi(sp, 90.0), 0.0, 0.09, 1.0, 0.0), T.maprange(T.noise(sp, 6.0, 2), 0.4, 0.7))
    col = T.mix(T.mul(pores, pw), col, [c * 0.45 for c in base])
    st = T.mul(T.maprange(T.noise(sp, 0.9, 6, 0.7, dist=0.5), 0.55, 0.8), stains)
    col = T.mix(st, col, [c * 0.62 for c in base])
    h = T.add(T.mul(mid, 0.2), T.mul(fine, 0.3))
    h = T.add(h, T.mul(pores, -pw))
    if formwork:
        uv = planar_uv(T, pos)
        u, v, _ = T.sep(uv)
        # panel seams every 1.2 x 2.4 m and tie holes on a 0.6 m grid
        fu = T.math("FRACT", T.math("DIVIDE", u, 1.2))
        fv = T.math("FRACT", T.math("DIVIDE", v, 0.9))
        su = T.math("MINIMUM", fu, T.math("SUBTRACT", 1.0, fu))
        sv = T.math("MINIMUM", fv, T.math("SUBTRACT", 1.0, fv))
        seam = T.math("MAXIMUM", T.maprange(su, 0.004, 0.0), T.maprange(sv, 0.004, 0.0))
        tu = T.math("SUBTRACT", T.math("FRACT", T.math("DIVIDE", T.add(u, 0.3), 0.6)), 0.5)
        tv = T.math("SUBTRACT", T.math("FRACT", T.math("DIVIDE", T.add(v, 0.225), 0.45)), 0.5)
        d = T.vmath("LENGTH", T.comb(T.mul(tu, 0.6), T.mul(tv, 0.45), 0.0))
        hole = T.maprange(d, 0.018, 0.012)
        ring = T.mul(T.maprange(d, 0.04, 0.015), 0.35)
        col = T.mix(seam, col, [c * 0.7 for c in base])
        col = T.mix(ring, col, [c * 0.8 for c in base])
        col = T.mix(hole, col, [c * 0.25 for c in base])
        h = T.add(h, T.mul(T.add(seam, hole), -1.5))
        # board-to-board tonal change per panel
        pid = T.comb(T.math("FLOOR", T.math("DIVIDE", u, 1.2)), T.math("FLOOR", T.math("DIVIDE", v, 0.9)), 0.0)
        col = T.mix(1.0, col, T.maprange(T.white(pid), 0, 1, 0.92, 1.08), blend="MULTIPLY")
    r = T.maprange(T.add(T.mul(big, 0.5), T.mul(mid, 0.5)), 0.3, 0.7, rough[0], rough[1])
    if polished:
        r = T.add(r, T.mul(st, 0.25))
    nrm = T.bump(h, 0.35 * bump, 0.004)
    return finish(m, T, T.principled(base=col, rough=r, normal=nrm, spec=0.5 if polished else 0.4))


def mat_plaster(name="plaster", base=(0.80, 0.78, 0.74), rough=0.9, dirt=0.25):
    m, T = new_material(name)
    pos = T.geo("Position")
    n1 = T.noise(pos, 0.8, 5, 0.6)
    n2 = T.noise(pos, 30.0, 4, 0.5)
    col = T.mix(1.0, base, T.ramp(n1, [(0.3, 0.93), (0.7, 1.03)]), blend="MULTIPLY")
    _, _, pz = T.sep(pos)
    col = T.mix(T.mul(T.maprange(pz, 0.5, 0.0), dirt), col, [c * 0.7 for c in base])
    nrm = T.bump(T.add(n2, T.mul(n1, 0.5)), 0.08, 0.01)
    return finish(m, T, T.principled(base=col, rough=rough, normal=nrm, spec=0.3))


def mat_paint(name, base, rough=0.45, metal=0.0, wear=0.0, scratch_scale=6.0, under=(0.25, 0.2, 0.18), coords="Object"):
    """Painted / powder-coated metal or wood with subtle roughness break-up."""
    m, T = new_material(name)
    pos = T.coord(coords)
    n = T.noise(pos, 4.0, 5, 0.6)
    col = T.mix(T.maprange(n, 0.3, 0.7), base, [c * 0.88 for c in base])
    r = T.maprange(T.noise(pos, 8.0, 3), 0.2, 0.8, rough * 0.8, rough * 1.25)
    if wear:
        w = T.maprange(T.noise(pos, scratch_scale, 8, 0.75), 0.68 - wear * 0.1, 0.7)
        col = T.mix(w, col, under)
        r = T.mixf(w, r, 0.35)
    nrm = T.bump(T.noise(pos, 60.0, 2), 0.05, 0.002)
    return finish(m, T, T.principled(base=col, rough=r, metal=metal, normal=nrm))


def mat_metal(name, base=(0.6, 0.6, 0.6), rough=0.3, aniso=0.0, coords="Object", dirt=0.0):
    m, T = new_material(name)
    pos = T.coord(coords)
    n = T.noise(pos, 6.0, 5, 0.6)
    r = T.maprange(n, 0.3, 0.7, rough * 0.7, rough * 1.35)
    col = base
    if dirt:
        d = T.maprange(T.noise(pos, 2.5, 6, 0.7), 0.5, 0.75, 0.0, dirt)
        col = T.mix(d, base, [c * 0.35 for c in base])
        r = T.mixf(d, r, 0.8)
    return finish(m, T, T.principled(base=col, rough=r, metal=1.0, aniso=aniso))


def mat_glass(name="glass", tint=(0.92, 0.96, 0.95), refl=1.0, rough=0.0, dirt=0.0):
    """Thin architectural glass: transparent (so the sun lamp casts shadows through it)
    with Fresnel reflections."""
    m, T = new_material(name)
    tr = T.shader("ShaderNodeBsdfTransparent", Color=tint)
    gl = T.shader("ShaderNodeBsdfAnisotropic", Color=(1.0, 1.0, 1.0), Roughness=rough)
    fr = T.fresnel(1.52)
    sh = T.mixshader(T.math("MULTIPLY", fr, refl), tr, gl)
    if dirt:
        dif = T.principled(base=(0.5, 0.5, 0.48), rough=0.9)
        dmask = T.mul(T.maprange(T.noise(T.geo("Position"), 3.0, 6, 0.7), 0.5, 0.8), dirt)
        sh = T.mixshader(dmask, sh, dif)
    m.use_backface_culling = False
    return finish(m, T, sh)


def mat_glass_solid(name="glass_solid", tint=(0.95, 0.97, 0.96), rough=0.0):
    m, T = new_material(name)
    return finish(m, T, T.principled(base=tint, rough=rough, trans=1.0, ior=1.5))


def mat_frosted(name, tint=(0.9, 0.9, 0.85), clear=0.35):
    """Dirty polycarbonate / frosted glass: part see-through, part diffusing."""
    m, T = new_material(name)
    tr = T.shader("ShaderNodeBsdfTransparent", Color=tint)
    tl = T.shader("ShaderNodeBsdfTranslucent", Color=tint)
    return finish(m, T, T.mixshader(clear, tl, tr))


def mat_emit(name, color, strength):
    m, T = new_material(name)
    return finish(m, T, T.emission(color, strength))


def mat_bulb(name, color=(1.0, 0.62, 0.3), strength=30.0):
    """Glowing filament bulb: emissive core with glassy falloff."""
    m, T = new_material(name)
    lw = T.layer_weight(0.35, "Facing")
    e = T.emission(color, T.maprange(lw, 0.0, 0.8, strength, strength * 0.25))
    return finish(m, T, e)


def mat_leather(name="leather", base=(0.16, 0.07, 0.035)):
    m, T = new_material(name)
    pos = T.coord("Object")
    cells = T.voronoi(pos, 140.0, feature="DISTANCE_TO_EDGE")
    wrink = T.noise(pos, 12.0, 6, 0.65)
    worn = T.maprange(T.noise(pos, 3.0, 5, 0.6), 0.55, 0.75)
    col = T.mix(worn, base, [min(1, c * 1.9) for c in base])
    col = T.mix(T.maprange(wrink, 0.4, 0.6), [c * 0.8 for c in base], col)
    r = T.add(T.maprange(wrink, 0.3, 0.7, 0.32, 0.5), T.mul(worn, -0.08))
    nrm = T.bump(T.add(T.maprange(cells, 0.0, 0.05), T.mul(wrink, 0.6)), 0.25, 0.003)
    return finish(m, T, T.principled(base=col, rough=r, normal=nrm, sheen=0.15, coat=0.15, coat_rough=0.35))


def mat_fabric(name, base, pattern=None, rough=0.95, sheen=0.6, coords="Object", scale=1.0):
    m, T = new_material(name)
    pos = T.vmath("SCALE", T.coord(coords), scale=1.0 / scale)
    weave = T.wave(pos, 260.0, 0.0, 0, wtype="BANDS", direction="X")
    weave2 = T.wave(pos, 260.0, 0.0, 0, wtype="BANDS", direction="Y")
    w = T.mul(weave, weave2)
    n = T.noise(pos, 6.0, 4, 0.6)
    col = T.mix(T.maprange(n, 0.3, 0.7), [c * 0.85 for c in base], [min(1, c * 1.1) for c in base])
    col = T.mix(T.mul(w, 0.25), col, [c * 0.7 for c in base])
    nrm = T.bump(w, 0.15, 0.002)
    return finish(m, T, T.principled(base=col, rough=rough, sheen=sheen, sheen_rough=0.4, normal=nrm, spec=0.3))


def mat_rug(name="rug", c1=(0.32, 0.06, 0.05), c2=(0.06, 0.07, 0.16), c3=(0.62, 0.50, 0.36), size=(3.0, 2.0)):
    """Faded kilim-ish rug in object space (rug mesh centred on its origin)."""
    m, T = new_material(name)
    p = T.coord("Object")
    px, py, _ = T.sep(p)
    ax = T.math("ABSOLUTE", px)
    ay = T.math("ABSOLUTE", py)
    bx = T.math("SUBTRACT", size[0] / 2, ax)
    by = T.math("SUBTRACT", size[1] / 2, ay)
    edge = T.math("MINIMUM", bx, by)
    border = T.math("LESS_THAN", edge, 0.22)
    border2 = T.mul(T.math("GREATER_THAN", edge, 0.08), T.math("LESS_THAN", edge, 0.12))
    # medallion / diamond lattice in the field
    dia = T.add(T.math("ABSOLUTE", T.math("SINE", T.mul(px, 7.0))), T.math("ABSOLUTE", T.math("SINE", T.mul(py, 7.0))))
    lattice = T.math("GREATER_THAN", dia, 1.55)
    med = T.math("LESS_THAN", T.add(T.mul(ax, 1.0 / (size[0] * 0.28)), T.mul(ay, 1.0 / (size[1] * 0.3))), 1.0)
    col = T.mix(lattice, c1, c3)
    col = T.mix(med, col, T.mix(lattice, c2, c1))
    col = T.mix(border, col, c2)
    col = T.mix(border2, col, c3)
    fade = T.noise(p, 2.0, 5, 0.6)
    col = T.mix(T.maprange(fade, 0.35, 0.7, 0.0, 0.45), col, (0.45, 0.38, 0.32))
    pile = T.noise(p, 300.0, 2, 0.5)
    col = T.mix(T.mul(pile, 0.3), col, (0.0, 0.0, 0.0))
    nrm = T.bump(pile, 0.3, 0.003)
    return finish(m, T, T.principled(base=col, rough=1.0, sheen=1.0, sheen_rough=0.5, normal=nrm, spec=0.2))


def mat_leaf(name="leaf", base=(0.05, 0.16, 0.035), var=0.4):
    m, T = new_material(name)
    p = T.coord("Object")
    n = T.noise(p, 3.0, 3, 0.5)
    rnd = T.out(T.node("ShaderNodeObjectInfo"), "Random")
    col = T.mix(T.mul(T.add(rnd, T.mul(n, 0.5)), var), base, (base[0] * 1.6, base[1] * 1.35, base[2] * 0.9))
    bsdf = T.principled(base=col, rough=0.45, spec=0.45, coat=0.1, coat_rough=0.3)
    tr = T.shader("ShaderNodeBsdfTranslucent", Color=T.hsv(col, s=1.2, v=1.6))
    return finish(m, T, T.mixshader(0.25, bsdf, tr))


def mat_bark(name="bark", base=(0.10, 0.085, 0.07)):
    m, T = new_material(name)
    p = T.coord("Object")
    n = T.noise(T.vmath("MULTIPLY", p, (6.0, 6.0, 0.8)), 4.0, 4, 0.6)
    lich = T.maprange(T.noise(p, 3.0, 4), 0.6, 0.72)
    col = T.mix(T.maprange(n, 0.3, 0.7), [c * 0.5 for c in base], [c * 1.4 for c in base])
    col = T.mix(T.mul(lich, 0.5), col, (0.35, 0.38, 0.3))
    return finish(m, T, T.principled(base=col, rough=0.9, normal=T.bump(n, 0.6, 0.006)))


def mat_terracotta(name="terracotta", base=(0.42, 0.17, 0.08)):
    m, T = new_material(name)
    p = T.coord("Object")
    n = T.noise(p, 8.0, 5, 0.6)
    salt = T.maprange(T.noise(p, 2.5, 6, 0.7), 0.6, 0.75)
    col = T.mix(T.maprange(n, 0.3, 0.7), [c * 0.85 for c in base], base)
    col = T.mix(T.mul(salt, 0.7), col, (0.6, 0.55, 0.5))
    return finish(m, T, T.principled(base=col, rough=0.85, normal=T.bump(n, 0.2, 0.003)))


def mat_wood(name="wood", base=(0.30, 0.16, 0.07), rough=0.45, scale=1.0, axis="X", coat=0.0, coords="Object"):
    """Generic furniture / timber wood with grain along `axis`."""
    m, T = new_material(name)
    p = T.vmath("SCALE", T.coord(coords), scale=1.0 / scale)
    x, y, z = T.sep(p)
    if axis == "Y":
        x, y = y, x
    elif axis == "Z":
        x, z = z, x
    gv = T.comb(T.mul(x, 0.5), T.mul(y, 30.0), T.mul(z, 30.0))
    grain = T.noise(gv, 1.5, 8, 0.65, dist=0.6)
    rings = T.wave(T.comb(T.mul(x, 0.05), y, z), 14.0, 8.0, 3, wtype="RINGS")
    g = T.ramp(T.add(T.mul(grain, 0.6), T.mul(rings, 0.4)), [(0.2, 0.6), (0.5, 1.0), (0.85, 1.3)])
    col = T.mix(1.0, base, g, blend="MULTIPLY")
    r = T.maprange(grain, 0.3, 0.7, rough * 0.8, rough * 1.2)
    nrm = T.bump(T.add(grain, T.mul(rings, 0.3)), 0.12, 0.003)
    return finish(m, T, T.principled(base=col, rough=r, normal=nrm, coat=coat, coat_rough=0.15))


def mat_timber_beam(name="beam", base=(0.20, 0.11, 0.055)):
    """Old rough-sawn timber: darker, checked (split) grain, dusty top faces."""
    m, T = new_material(name)
    p = T.geo("Position")
    nrm_g = T.geo("Normal")
    _, _, nz = T.sep(nrm_g)
    # grain follows the longest axis; we use world position noise stretched in both horizontal axes
    x, y, z = T.sep(p)
    gv = T.comb(T.mul(x, 2.0), T.mul(y, 2.0), T.mul(z, 40.0))
    grain = T.noise(gv, 2.0, 8, 0.65, dist=0.8)
    checks = T.maprange(T.noise(T.comb(T.mul(x, 0.3), T.mul(y, 0.3), T.mul(z, 25.0)), 6.0, 3, 0.5), 0.68, 0.72)
    col = T.mix(1.0, base, T.ramp(grain, [(0.25, 0.55), (0.6, 1.0), (0.85, 1.35)]), blend="MULTIPLY")
    col = T.mix(checks, col, (0.02, 0.012, 0.008))
    sawn = T.noise(T.comb(x, y, T.mul(z, 3.0)), 25.0, 3)
    col = T.mix(T.mul(T.maprange(T.noise(p, 1.0, 4), 0.4, 0.7), 0.4), col, (0.30, 0.26, 0.22))
    nrm = T.bump(T.add(T.add(grain, T.mul(checks, -1.0)), T.mul(sawn, 0.3)), 0.4, 0.004)
    return finish(m, T, T.principled(base=col, rough=0.82, normal=nrm, spec=0.3))


def mat_grass_ground(name="grass", base=(0.06, 0.12, 0.03), dry=(0.30, 0.25, 0.10), dryness=0.4, scale=1.0):
    m, T = new_material(name)
    p = T.vmath("SCALE", T.geo("Position"), scale=1.0 / scale)
    big = T.noise(p, 0.15, 5, 0.6, dist=0.4)
    mid = T.noise(p, 2.0, 5, 0.6)
    fine = T.noise(p, 60.0, 3, 0.7)
    dmask = T.maprange(T.add(big, T.mul(mid, 0.3)), 0.62 - dryness * 0.3, 0.85 - dryness * 0.3)
    col = T.mix(dmask, base, dry)
    col = T.mix(1.0, col, T.ramp(fine, [(0.3, 0.6), (0.7, 1.25)]), blend="MULTIPLY")
    col = T.mix(T.maprange(mid, 0.3, 0.7), [c * 0.8 for c in base], col)
    nrm = T.bump(fine, 0.5, 0.003)
    return finish(m, T, T.principled(base=col, rough=0.95, normal=nrm, spec=0.25))


def mat_cobbles(name="cobbles", base=(0.22, 0.21, 0.20), scale=0.13):
    m, T = new_material(name)
    p = T.geo("Position")
    x, y, _ = T.sep(p)
    p2 = T.comb(x, y, 0.0)
    pv = T.vmath("SCALE", T.vmath("ADD", p2, T.vmath("SCALE", T.noise(p2, 3.0, 2, key="Color"), scale=0.04)), scale=1.0 / scale)
    edge = T.voronoi(pv, 1.0, feature="DISTANCE_TO_EDGE", dims="2D")
    cell = T.voronoi(pv, 1.0, feature="F1", dims="2D", key="Color")
    stone = T.maprange(edge, 0.02, 0.12)
    tone = T.bw(cell)
    col = T.mix(tone, [c * 0.7 for c in base], [min(1, c * 1.35) for c in base])
    col = T.hsv(col, h=T.maprange(tone, 0, 1, 0.47, 0.53), s=1.0, v=1.0)
    col = T.mix(1.0, col, T.ramp(T.noise(p, 20.0, 4), [(0.3, 0.75), (0.7, 1.15)]), blend="MULTIPLY")
    joint = T.mix(T.noise(p, 3.0, 3), (0.06, 0.06, 0.04), (0.10, 0.14, 0.05))
    col = T.mix(stone, joint, col)
    height = T.math("SQRT", stone)
    r = T.maprange(stone, 0, 1, 0.95, 0.55)
    nrm = T.bump(T.add(height, T.mul(T.noise(p, 30.0, 3), 0.15)), 0.8, 0.006)
    return finish(m, T, T.principled(base=col, rough=r, normal=nrm))


def mat_slate(name="slate", base=(0.10, 0.11, 0.12)):
    m, T = new_material(name)
    p = T.geo("Position")
    x, y, z = T.sep(p)
    col, fac = T.brick(T.comb(T.add(x, y), z, 0.0), [c * 0.8 for c in base], [c * 1.3 for c in base], (0.03, 0.03, 0.03),
                       bw=0.3, rh=0.14, msize=0.006, smooth=0.2)
    lich = T.maprange(T.noise(p, 1.5, 6, 0.7), 0.62, 0.72)
    col = T.mix(T.mul(lich, 0.5), col, (0.25, 0.24, 0.16))
    nrm = T.bump(T.math("SUBTRACT", 1.0, fac), 0.5, 0.004)
    return finish(m, T, T.principled(base=col, rough=0.55, normal=nrm))


def mat_water(name="water", deep=(0.02, 0.05, 0.06), scale=1.0, rough=0.02, pool=False):
    m, T = new_material(name)
    p = T.vmath("SCALE", T.geo("Position"), scale=1.0 / scale)
    w = T.noise(T.vmath("MULTIPLY", p, (1.0, 2.5, 1.0)), 2.0, 6, 0.6)
    w2 = T.noise(p, 9.0, 4, 0.5)
    nrm = T.bump(T.add(w, T.mul(w2, 0.4)), 0.25 if not pool else 0.15, 0.02)
    if pool:
        sh = T.principled(base=(1, 1, 1), rough=rough, trans=1.0, ior=1.33, normal=nrm)
        return finish(m, T, sh)
    gl = T.shader("ShaderNodeBsdfAnisotropic", Color=(1, 1, 1), Roughness=rough, Normal=nrm)
    body = T.principled(base=deep, rough=0.4)
    fr = T.out(T.node("ShaderNodeFresnel", {"IOR": 1.33, "Normal": nrm}))
    return finish(m, T, T.mixshader(fr, body, gl))


# ----------------------------------------------------------------------------
# geometry helpers
# ----------------------------------------------------------------------------
def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


class MB:
    """Mesh builder: accumulate primitives into one bmesh (one object, many material slots)."""

    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")

    def _tag(self, verts, mi):
        faces = {f for v in verts for f in v.link_faces}
        for f in faces:
            f.material_index = mi
        return faces

    def box(self, mn, mx, mi=0):
        mn, mx = V(mn), V(mx)
        size = mx - mn
        c = (mn + mx) * 0.5
        M = Matrix.Translation(c) @ Matrix.Diagonal((max(size.x, 1e-4), max(size.y, 1e-4), max(size.z, 1e-4), 1.0))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M)
        return self._tag(r["verts"], mi)

    def box_c(self, center, size, mi=0, rot=(0, 0, 0)):
        M = Matrix.Translation(V(center)) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*size, 1.0))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M)
        return self._tag(r["verts"], mi)

    def box_m(self, M, mi=0):
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M)
        return self._tag(r["verts"], mi)

    def cyl(self, p0, p1, r, segs=16, mi=0, r2=None, cap=True):
        p0, p1 = V(p0), V(p1)
        d = p1 - p0
        L = d.length
        if L < 1e-6:
            return
        q = d.normalized().to_track_quat("Z", "Y")
        M = Matrix.Translation((p0 + p1) * 0.5) @ q.to_matrix().to_4x4()
        res = bmesh.ops.create_cone(self.bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=r,
                                    radius2=r if r2 is None else r2, depth=L, matrix=M)
        return self._tag(res["verts"], mi)

    def sphere(self, c, r, mi=0, segs=16, rings=8, scale=(1, 1, 1)):
        M = Matrix.Translation(V(c)) @ Matrix.Diagonal((*scale, 1.0))
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=segs, v_segments=rings, radius=r, matrix=M)
        return self._tag(res["verts"], mi)

    def poly(self, pts, mi=0):
        vs = [self.bm.verts.new(p) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = mi
        return f

    def grid(self, fn, nu, nv, mi=0):
        """Parametric surface fn(u,v)->(x,y,z), u,v in [0,1]."""
        vs = [[self.bm.verts.new(fn(i / nu, j / nv)) for j in range(nv + 1)] for i in range(nu + 1)]
        for i in range(nu):
            for j in range(nv):
                f = self.bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]))
                f.material_index = mi
                for loop, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                    loop[self.uv].uv = (a / nu, b / nv)

    def prism(self, outline, z0, z1, mi=0, axis="Z"):
        """Extrude a 2D outline [(a,b),...] between z0 and z1 along axis."""
        def P(a, b, z):
            if axis == "Z":
                return (a, b, z)
            if axis == "Y":
                return (a, z, b)
            return (z, a, b)
        bot = [self.bm.verts.new(P(a, b, z0)) for a, b in outline]
        top = [self.bm.verts.new(P(a, b, z1)) for a, b in outline]
        n = len(outline)
        fs = [self.bm.faces.new(bot[::-1]), self.bm.faces.new(top)]
        for i in range(n):
            j = (i + 1) % n
            fs.append(self.bm.faces.new((bot[i], bot[j], top[j], top[i])))
        for f in fs:
            f.material_index = mi
        return fs

    def obj(self, name, mats, bevel=0.0, segs=2, smooth=False, loc=(0, 0, 0), rot=(0, 0, 0), angle=40, recalc=True):
        if recalc:
            bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in mats if isinstance(mats, (list, tuple)) else [mats]:
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        ob.location = loc
        ob.rotation_euler = rot
        link(ob)
        if smooth:
            me.shade_smooth()
        if bevel:
            md = ob.modifiers.new("bevel", "BEVEL")
            md.width = bevel
            md.segments = segs
            md.limit_method = "ANGLE"
            md.angle_limit = rad(angle)
            md.harden_normals = smooth
        return ob


def box(name, mn, mx, mat, bevel=0.0, segs=2, smooth=False):
    b = MB()
    b.box(mn, mx)
    return b.obj(name, mat, bevel=bevel, segs=segs, smooth=smooth)


def plane(name, x0, x1, y0, y1, z, mat):
    b = MB()
    b.poly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)])
    return b.obj(name, mat)


# ----------------------------------------------------------------------------
# lights / world / camera
# ----------------------------------------------------------------------------
def sun_dir(elev, azim):
    e, a = rad(elev), rad(azim)
    return V((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))


def add_sun(elev, azim, strength=4.0, angle=0.6, color=(1.0, 0.9, 0.78)):
    """elev/azim describe where the sun IS (azimuth from +X, counter-clockwise)."""
    ld = bpy.data.lights.new("sun", "SUN")
    ld.energy = strength
    ld.angle = rad(angle)
    ld.color = color
    ob = bpy.data.objects.new("sun", ld)
    ob.rotation_euler = sun_dir(elev, azim).to_track_quat("Z", "Y").to_euler()
    link(ob)
    return ob


def add_area(name, loc, size, energy, color=(1, 1, 1), target=None, rot=None, shape="RECTANGLE", portal=False, spread=180):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = shape
    if isinstance(size, (tuple, list)):
        ld.size, ld.size_y = size
    else:
        ld.size = ld.size_y = size
    ld.energy = energy
    ld.color = color
    ld.spread = rad(spread)
    if portal:
        ld.cycles.is_portal = True
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    if target is not None:
        d = V(target) - V(loc)
        ob.rotation_euler = (-d).to_track_quat("Z", "Y").to_euler()
    elif rot is not None:
        ob.rotation_euler = rot
    link(ob)
    return ob


def add_point(name, loc, energy, color=(1, 0.8, 0.6), radius=0.05):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = energy
    ld.color = color
    ld.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    link(ob)
    return ob


def add_spot(name, loc, target, energy, size_deg=40, blend=0.5, color=(1, 1, 1), radius=0.05):
    ld = bpy.data.lights.new(name, "SPOT")
    ld.energy = energy
    ld.color = color
    ld.spot_size = rad(size_deg)
    ld.spot_blend = blend
    ld.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_euler = (V(loc) - V(target)).to_track_quat("Z", "Y").to_euler()
    link(ob)
    return ob


def sky_world(elev, azim, strength=1.0, air=1.0, dust=1.0, ozone=1.0, clouds=0.0, cloud_col=(1.0, 0.93, 0.85),
              cloud_scale=1.0, tint=(1, 1, 1), ground=None, cloud_seed=0.0, cloud_cover=0.5, cloud_bright=5.0):
    """Nishita sky (no sun disc; the sun lamp provides direct light), optional procedural
    cloud layer projected on a dome, optional ground colour below the horizon."""
    w = bpy.data.worlds.new("world")
    bpy.context.scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    nt.nodes.clear()
    T = Tree(nt)
    out = T.node("ShaderNodeOutputWorld")
    sky = T.node("ShaderNodeTexSky", sky_type="MULTIPLE_SCATTERING")
    sky.sun_disc = False
    sky.sun_elevation = rad(elev)
    sky.sun_rotation = rad(90.0 - azim)  # Blender measures clockwise from +Y
    sky.air_density = air
    sky.aerosol_density = dust
    sky.ozone_density = ozone
    col = sky.outputs[0]
    col = T.mix(1.0, col, tint, blend="MULTIPLY")
    if clouds or ground is not None:
        # world "Object" coordinates are the view direction in world space
        dv = T.vmath("NORMALIZE", T.coord("Object"))
        dx, dy, dz = T.sep(dv)
        if clouds:
            inv = T.math("DIVIDE", 1.0, T.math("MAXIMUM", T.add(dz, 0.06), 0.02))
            cp = T.comb(T.mul(dx, inv), T.mul(dy, inv), cloud_seed)
            cp = T.vmath("SCALE", cp, scale=0.35 / cloud_scale)
            c1 = T.noise(cp, 1.2, 8, 0.62, dist=0.35)
            c2 = T.noise(T.vmath("MULTIPLY", cp, (1.0, 3.0, 1.0)), 4.0, 6, 0.55)
            cov = T.add(T.mul(c1, 0.8), T.mul(c2, 0.25))
            cmask = T.maprange(cov, 0.66 - cloud_cover * 0.35, 0.80 - cloud_cover * 0.3)
            cmask = T.mul(T.mul(cmask, T.maprange(dz, 0.0, 0.25)), clouds)
            sd = sun_dir(elev, azim)
            facing = T.maprange(T.vmath("DOT_PRODUCT", dv, tuple(sd)), -0.3, 1.0, 0.55, 1.6)
            shade = T.maprange(c2, 0.2, 0.8, 0.7, 1.15)
            k = T.mul(T.mul(facing, shade), cloud_bright)
            ccol = T.vmath("MULTIPLY", cloud_col, T.comb(k, k, k))
            col = T.mix(cmask, col, ccol)
        if ground is not None:
            col = T.mix(T.maprange(dz, 0.0, -0.03), col, ground)
    bg = T.node("ShaderNodeBackground")
    T.inp(bg, "Color", col)
    T.inp(bg, "Strength", strength)
    T.links.new(bg.outputs[0], out.inputs["Surface"])
    return w


def flat_world(color, strength=1.0):
    w = bpy.data.worlds.new("world")
    bpy.context.scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    T = Tree(nt)
    out = T.node("ShaderNodeOutputWorld")
    bg = T.node("ShaderNodeBackground", {"Color": color, "Strength": strength})
    T.links.new(bg.outputs[0], out.inputs["Surface"])


def add_camera(loc, look, lens=24, shift_x=0.0, shift_y=0.0, pitch=0.0, dof=None, fstop=5.6):
    """Level camera (verticals stay vertical) at loc looking toward `look` (x,y).
    Use shift_y instead of tilting to frame higher/lower."""
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cd.sensor_width = 36
    cd.shift_x = shift_x
    cd.shift_y = shift_y
    cd.clip_start = 0.05
    cd.clip_end = 5000
    if dof:
        cd.dof.use_dof = True
        cd.dof.focus_distance = dof
        cd.dof.aperture_fstop = fstop
    ob = bpy.data.objects.new("cam", cd)
    ob.location = loc
    dx, dy = look[0] - loc[0], look[1] - loc[1]
    yaw = math.atan2(-dx, dy)
    ob.rotation_euler = (rad(90 + pitch), 0, yaw)
    link(ob)
    bpy.context.scene.camera = ob
    return ob


def distant_mat(name, base, haze=(0.8, 0.75, 0.7), haze_strength=1.0, falloff=400.0, windows=None, rough=0.8):
    """Far-away buildings: diffuse surface blended into an emissive haze by camera distance
    (cheap aerial perspective instead of a volume)."""
    m, T = new_material(name)
    pos = T.geo("Position")
    dist = T.out(T.node("ShaderNodeCameraData"), "View Distance")
    fac = T.math("SUBTRACT", 1.0, T.math("EXPONENT", T.math("DIVIDE", T.mul(dist, -1.0), falloff)))
    col = T.mix(T.maprange(T.noise(pos, 0.05, 3), 0.3, 0.7), [c * 0.8 for c in base], base)
    emit_c = (0, 0, 0)
    emit_s = 0.0
    if windows:
        # facade window grid: darker glass by day, optional warm lit windows
        uv = planar_uv(T, pos)
        u, v, _ = T.sep(uv)
        fu = T.math("FRACT", T.math("DIVIDE", u, windows[0]))
        fv = T.math("FRACT", T.math("DIVIDE", v, windows[1]))
        win = T.mul(T.mul(T.math("GREATER_THAN", fu, 0.25), T.math("LESS_THAN", fu, 0.8)),
                    T.mul(T.math("GREATER_THAN", fv, 0.3), T.math("LESS_THAN", fv, 0.85)))
        _, _, nz = T.sep(T.geo("Normal"))
        win = T.mul(win, T.math("LESS_THAN", T.math("ABSOLUTE", nz), 0.5))
        col = T.mix(win, col, (0.04, 0.045, 0.05))
        if len(windows) > 2 and windows[2] > 0:
            cell = T.comb(T.math("FLOOR", T.math("DIVIDE", u, windows[0])), T.math("FLOOR", T.math("DIVIDE", v, windows[1])), 0.0)
            lit = T.mul(win, T.math("GREATER_THAN", T.white(T.vmath("ADD", cell, pos)), 1.0 - windows[2]))
            emit_c = (1.0, 0.7, 0.4)
            emit_s = T.mul(lit, windows[3] if len(windows) > 3 else 2.0)
    sh = T.principled(base=col, rough=rough, emit=emit_c, emit_str=emit_s)
    return finish(m, T, T.mixshader(fac, sh, T.emission(haze, haze_strength)))


# ----------------------------------------------------------------------------
# architectural kit
# ----------------------------------------------------------------------------
def _ab(axis, a0, a1, p0, p1, z0, z1):
    """Box corners for a wall-aligned piece. axis='X': wall runs along X (a=x, p=y);
    axis='Y': wall runs along Y (a=y, p=x)."""
    if axis == "X":
        return (a0, p0, z0), (a1, p1, z1)
    return (p0, a0, z0), (p1, a1, z1)


def wall_with_openings(mb, axis, a0, a1, p0, p1, z0, z1, openings, mi=0):
    """Solid wall slab with rectangular openings [(oa0, oa1, oz0, oz1), ...]."""
    ops = sorted(openings)
    cur = a0
    for oa0, oa1, oz0, oz1 in ops:
        if oa0 > cur:
            mb.box(*_ab(axis, cur, oa0, p0, p1, z0, z1), mi=mi)
        if oz0 > z0:
            mb.box(*_ab(axis, oa0, oa1, p0, p1, z0, oz0), mi=mi)
        if oz1 < z1:
            mb.box(*_ab(axis, oa0, oa1, p0, p1, oz1, z1), mi=mi)
        cur = oa1
    if cur < a1:
        mb.box(*_ab(axis, cur, a1, p0, p1, z0, z1), mi=mi)


def steel_window(frames, glass, axis, a0, a1, z0, z1, p, cols, rows, fw=0.06, mw=0.032, depth=0.05,
                 mdepth=0.035, glass_mi=0, frame_mi=0, transom=None):
    """Industrial steel window: outer frame + glazing-bar grid + one glass plane."""
    d = depth / 2
    md = mdepth / 2
    # outer frame
    frames.box(*_ab(axis, a0, a1, p - d, p + d, z0, z0 + fw), mi=frame_mi)
    frames.box(*_ab(axis, a0, a1, p - d, p + d, z1 - fw, z1), mi=frame_mi)
    frames.box(*_ab(axis, a0, a0 + fw, p - d, p + d, z0, z1), mi=frame_mi)
    frames.box(*_ab(axis, a1 - fw, a1, p - d, p + d, z0, z1), mi=frame_mi)
    ia0, ia1, iz0, iz1 = a0 + fw, a1 - fw, z0 + fw, z1 - fw
    for i in range(1, cols):
        a = ia0 + (ia1 - ia0) * i / cols
        frames.box(*_ab(axis, a - mw / 2, a + mw / 2, p - md, p + md, iz0, iz1), mi=frame_mi)
    for j in range(1, rows):
        z = iz0 + (iz1 - iz0) * j / rows
        w = mw * (1.6 if transom == j else 1.0)
        frames.box(*_ab(axis, ia0, ia1, p - md, p + md, z - w / 2, z + w / 2), mi=frame_mi)
    if axis == "X":
        glass.poly([(ia0, p, iz0), (ia1, p, iz0), (ia1, p, iz1), (ia0, p, iz1)], mi=glass_mi)
    else:
        glass.poly([(p, ia0, iz0), (p, ia1, iz0), (p, ia1, iz1), (p, ia0, iz1)], mi=glass_mi)


# ----------------------------------------------------------------------------
# props
# ----------------------------------------------------------------------------
class Local:
    """Wraps an MB so props can be authored in local coordinates and placed with a matrix."""

    def __init__(self, mb, M):
        self.mb, self.M = mb, M
        self.R = M.to_3x3()

    def P(self, p):
        return self.M @ V(p)

    def box(self, mn, mx, mi=0, rot=(0, 0, 0)):
        mn, mx = V(mn), V(mx)
        c = (mn + mx) / 2
        s = mx - mn
        M = self.M @ Matrix.Translation(c) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*s, 1.0))
        return self.mb.box_m(M, mi)

    def cyl(self, p0, p1, r, mi=0, segs=16, r2=None, cap=True):
        return self.mb.cyl(self.P(p0), self.P(p1), r, segs=segs, mi=mi, r2=r2, cap=cap)

    def sphere(self, c, r, mi=0, segs=12, rings=6, scale=(1, 1, 1)):
        M = self.M @ Matrix.Translation(V(c)) @ Matrix.Diagonal((*scale, 1.0))
        res = bmesh.ops.create_uvsphere(self.mb.bm, u_segments=segs, v_segments=rings, radius=r, matrix=M)
        return self.mb._tag(res["verts"], mi)


def prop_sofa(M, leather, wood):
    """Leather club sofa (2.2 m), local origin at floor centre, facing -Y."""
    soft = MB()
    L = Local(soft, M)
    W, D = 2.2, 0.92
    L.box((-W / 2 + 0.2, -D / 2 + 0.04, 0.12), (W / 2 - 0.2, D / 2 - 0.05, 0.40))            # base
    L.box((-W / 2, -D / 2, 0.12), (-W / 2 + 0.22, D / 2, 0.64))                               # arms
    L.box((W / 2 - 0.22, -D / 2, 0.12), (W / 2, D / 2, 0.64))
    L.box((-W / 2 + 0.2, D / 2 - 0.24, 0.12), (W / 2 - 0.2, D / 2, 0.80))                    # back
    for i in range(2):                                                                        # seat cushions
        x0 = -W / 2 + 0.22 + i * (W - 0.44) / 2
        L.box((x0 + 0.01, -D / 2 + 0.02, 0.40), (x0 + (W - 0.44) / 2 - 0.01, D / 2 - 0.22, 0.55), rot=(rad(-2), 0, 0))
        L.box((x0 + 0.02, D / 2 - 0.36, 0.52), (x0 + (W - 0.44) / 2 - 0.02, D / 2 - 0.20, 0.92), rot=(rad(-12), 0, 0))
    s = soft.obj("sofa", leather, bevel=0.045, segs=4, smooth=True, angle=30)
    legs = MB()
    L2 = Local(legs, M)
    for x in (-W / 2 + 0.08, W / 2 - 0.08):
        for y in (-D / 2 + 0.08, D / 2 - 0.08):
            L2.cyl((x, y, 0), (x, y, 0.13), 0.025, r2=0.032, segs=12)
    legs.obj("sofa_legs", wood, smooth=True)
    return s


def prop_table(M, top_mat, leg_mat, W=1.2, D=0.6, H=0.42, thick=0.05, leg="frame"):
    t = MB()
    L = Local(t, M)
    L.box((-W / 2, -D / 2, H - thick), (W / 2, D / 2, H))
    t.obj("table_top", top_mat, bevel=0.004, segs=2)
    l = MB()
    L = Local(l, M)
    s = 0.035
    for x in (-W / 2 + 0.06, W / 2 - 0.06 - s):
        for y in (-D / 2 + 0.06, D / 2 - 0.06 - s):
            L.box((x, y, 0), (x + s, y + s, H - thick))
    if leg == "frame":
        for y in (-D / 2 + 0.06, D / 2 - 0.06 - s):
            L.box((-W / 2 + 0.06, y, H - thick - 0.05), (W / 2 - 0.06, y + s, H - thick))
        for x in (-W / 2 + 0.06, W / 2 - 0.06 - s):
            L.box((x, -D / 2 + 0.06, 0.08), (x + s, D / 2 - 0.06, 0.11))
    l.obj("table_legs", leg_mat, bevel=0.002)


def leaf_shape(length=0.28, width=0.19, fold=0.25, droop=0.12, seed=0, kind="fig"):
    """Return a parametric leaf function in local leaf space (+X along the leaf)."""
    rnd = random.Random(seed)
    tw = rnd.uniform(-0.15, 0.15)

    def fn(u, v):
        t = u
        if kind == "fig":
            prof = math.sin(math.pi * min(1.0, t * 1.05)) ** 0.75 * (0.82 + 0.25 * t)
        elif kind == "long":
            prof = math.sin(math.pi * t) ** 0.6
        else:
            prof = math.sin(math.pi * t) ** 0.9
        prof = max(prof, 0.0)
        s = (v - 0.5) * 2
        x = t * length
        y = s * width * 0.5 * prof
        z = abs(s) * width * 0.5 * prof * fold - droop * t * t + tw * s * t * 0.05
        return (x, y, z)
    return fn


def prop_plant(origin, pot_mat, soil_mat, stem_mat, leaf_mat, height=1.8, seed=3, pot_r=0.24, pot_h=0.45, kind="fig",
               nleaves=48, spread=0.45, leaf_len=0.28, leaf_w=0.19):
    rnd = random.Random(seed)
    ox, oy, oz = origin
    pot = MB()
    pot.cyl((ox, oy, oz), (ox, oy, oz + pot_h), pot_r * 0.78, r2=pot_r, segs=32)
    pot.obj("pot", pot_mat, bevel=0.01, segs=2, smooth=True)
    soil = MB()
    soil.cyl((ox, oy, oz + pot_h - 0.06), (ox, oy, oz + pot_h - 0.04), pot_r * 0.95, segs=32)
    soil.obj("soil", soil_mat)
    stems = MB()
    leaves = MB()
    ntr = 3 if kind == "fig" else 1
    tips = []
    for k in range(ntr):
        a = rnd.uniform(0, 2 * math.pi)
        lean = rnd.uniform(0.05, 0.18)
        h = height * rnd.uniform(0.75, 1.0)
        base = V((ox + math.cos(a) * 0.04, oy + math.sin(a) * 0.04, oz + pot_h - 0.05))
        pts = [base + V((math.cos(a) * lean * (i / 6) ** 1.5, math.sin(a) * lean * (i / 6) ** 1.5, (h - pot_h) * i / 6)) for i in range(7)]
        for i in range(6):
            stems.cyl(pts[i], pts[i + 1], 0.014 * (1 - i / 9), segs=8)
        tips.append(pts)
    stems.obj("stems", stem_mat, smooth=True)
    for i in range(nleaves):
        pts = tips[i % ntr]
        t = rnd.uniform(0.35, 1.0) ** 0.7
        idx = min(5, int(t * 6))
        f = t * 6 - idx
        p = pts[idx].lerp(pts[idx + 1], f)
        yaw = rnd.uniform(0, 2 * math.pi)
        pitch = rad(rnd.uniform(-25, 35)) + (1 - t) * rad(15)
        L = leaf_len * rnd.uniform(0.75, 1.15) * (0.75 + 0.35 * t)
        fn = leaf_shape(L, leaf_w * rnd.uniform(0.8, 1.1) * L / leaf_len, seed=rnd.randint(0, 9999), kind=kind)
        Mx = Matrix.Translation(p) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(-pitch, 4, "Y") @ Matrix.Rotation(rnd.uniform(-0.4, 0.4), 4, "X")

        def g(u, v, fn=fn, Mx=Mx):
            return Mx @ V(fn(u, v))
        leaves.grid(g, 8, 4)
    leaves.obj("leaves", leaf_mat, smooth=True, recalc=False)


def prop_cstand(origin, rot, metal, black, height=2.1, arm_len=1.0, flag=True):
    M = Matrix.Translation(V(origin)) @ Matrix.Rotation(rot, 4, "Z")
    mb = MB()
    L = Local(mb, M)
    for i, (ang, hz) in enumerate(((0, 0.32), (2.1, 0.22), (4.2, 0.12))):
        foot = (math.cos(ang) * 0.62, math.sin(ang) * 0.62, 0.015)
        L.cyl((0, 0, hz), foot, 0.011, segs=10)
        L.cyl((0, 0, hz - 0.05), (0, 0, hz + 0.05), 0.022, segs=12)
        L.box((foot[0] - 0.03, foot[1] - 0.03, 0), (foot[0] + 0.03, foot[1] + 0.03, 0.02))
    L.cyl((0, 0, 0.0), (0, 0, height * 0.55), 0.016, segs=14)
    L.cyl((0, 0, height * 0.55 - 0.04), (0, 0, height * 0.55 + 0.03), 0.024, segs=14)
    L.cyl((0, 0, height * 0.55), (0, 0, height), 0.0125, segs=14)
    # grip head + gobo arm
    L.cyl((0, 0, height - 0.02), (0, 0, height + 0.06), 0.035, segs=16)
    L.cyl((-0.25, 0, height + 0.02), (arm_len, 0, height + 0.02), 0.0105, segs=10)
    L.cyl((arm_len * 0.82, -0.04, height + 0.02), (arm_len * 0.82, 0.04, height + 0.02), 0.03, segs=14)
    mb.obj("cstand", metal, smooth=True)
    if flag:
        fb = MB()
        L = Local(fb, M)
        fx = arm_len * 0.82
        L.box((fx - 0.0, 0.03, height - 0.40), (fx + 0.62, 0.042, height + 0.06), rot=(0, 0, 0))
        fb.obj("flag", black, bevel=0.004)


def prop_lightstand(origin, rot, metal, black, diffuser, height=1.9, box=(0.6, 0.9), emit=None):
    """Tripod light stand with a rectangular softbox aimed along local +Y."""
    M = Matrix.Translation(V(origin)) @ Matrix.Rotation(rot, 4, "Z")
    mb = MB()
    L = Local(mb, M)
    for i in range(3):
        ang = i * 2 * math.pi / 3 + 0.4
        L.cyl((0, 0, 0.55), (math.cos(ang) * 0.5, math.sin(ang) * 0.5, 0.0), 0.012, segs=10)
        L.cyl((0, 0, 0.35), (math.cos(ang) * 0.3, math.sin(ang) * 0.3, 0.55), 0.007, segs=8)
    L.cyl((0, 0, 0.3), (0, 0, height * 0.6), 0.017, segs=14)
    L.cyl((0, 0, height * 0.6), (0, 0, height), 0.0135, segs=14)
    L.cyl((0, 0, height * 0.6 - 0.03), (0, 0, height * 0.6 + 0.03), 0.024, segs=12)
    mb.obj("lstand", metal, smooth=True)
    # softbox: tapered prism from a head unit toward +Y
    sb = MB()
    L = Local(sb, M)
    bw, bh = box
    L.box((-0.09, -0.32, height - 0.04), (0.09, -0.12, height + 0.14))
    ring = [(-0.08, -0.12, height - 0.03), (0.08, -0.12, height - 0.03), (0.08, -0.12, height + 0.13), (-0.08, -0.12, height + 0.13)]
    front = [(-bw / 2, 0.38, height + 0.05 - bh / 2), (bw / 2, 0.38, height + 0.05 - bh / 2),
             (bw / 2, 0.38, height + 0.05 + bh / 2), (-bw / 2, 0.38, height + 0.05 + bh / 2)]
    rv = [sb.bm.verts.new(L.P(p)) for p in ring]
    fv = [sb.bm.verts.new(L.P(p)) for p in front]
    for i in range(4):
        j = (i + 1) % 4
        sb.bm.faces.new((rv[i], rv[j], fv[j], fv[i]))
    f = sb.bm.faces.new(fv)
    f.material_index = 1
    sb.obj("softbox", [black, diffuser], recalc=True)


def prop_rack(origin, rot, chrome, cloth_mats, length=1.5, height=1.65, seed=1, n=11):
    M = Matrix.Translation(V(origin)) @ Matrix.Rotation(rot, 4, "Z")
    rnd = random.Random(seed)
    mb = MB()
    L = Local(mb, M)
    for x in (-length / 2, length / 2):
        L.cyl((x, 0, 0.09), (x, 0, height), 0.014, segs=12)
        L.cyl((x, -0.28, 0.09), (x, 0.28, 0.09), 0.014, segs=12)
        for y in (-0.26, 0.26):
            L.sphere((x, y, 0.04), 0.035, segs=10, rings=6)
    L.cyl((-length / 2 - 0.03, 0, height), (length / 2 + 0.03, 0, height), 0.013, segs=12)
    L.cyl((-length / 2, 0, 0.3), (length / 2, 0, 0.3), 0.01, segs=10)
    mb.obj("rack", chrome, smooth=True)
    cl = MB()
    L = Local(cl, M)
    hangers = MB()
    LH = Local(hangers, M)
    xs = sorted(rnd.uniform(-length / 2 + 0.12, length / 2 - 0.12) for _ in range(n))
    for i, x in enumerate(xs):
        mi = rnd.randrange(len(cloth_mats))
        ln = rnd.uniform(0.65, 1.1)
        w = rnd.uniform(0.44, 0.52)
        th = rnd.uniform(0.03, 0.07)
        yaw = rnd.uniform(-0.12, 0.12)
        top = height - 0.09
        L.box((x - th / 2, -w / 2, top - ln), (x + th / 2, w / 2, top), mi=mi, rot=(0, 0, yaw))
        # shoulders: a slightly wider short block
        L.box((x - th / 2 - 0.005, -w / 2 - 0.02, top - 0.18), (x + th / 2 + 0.005, w / 2 + 0.02, top - 0.02), mi=mi, rot=(0, 0, yaw))
        LH.cyl((x, 0, height - 0.01), (x, 0, top + 0.02), 0.002, segs=6)
        LH.cyl((x, -0.21, top - 0.01), (x, 0, top + 0.04), 0.003, segs=6)
        LH.cyl((x, 0.21, top - 0.01), (x, 0, top + 0.04), 0.003, segs=6)
    cl.obj("clothes", cloth_mats, bevel=0.045, segs=4, smooth=True)
    hangers.obj("hangers", chrome, smooth=True)


def prop_apple_boxes(origin, rot, wood, n=3, seed=0):
    rnd = random.Random(seed)
    mb = MB()
    for i in range(n):
        M = Matrix.Translation(V(origin) + V((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), i * 0.2))) @ Matrix.Rotation(rot + rnd.uniform(-0.15, 0.15), 4, "Z")
        L = Local(mb, M)
        L.box((-0.25, -0.15, 0), (0.25, 0.15, 0.2))
    mb.obj("appleboxes", wood, bevel=0.006, segs=2)


def prop_pendant(mb_shade, mb_cord, mb_bulb, x, y, z_ceiling, drop, r=0.2):
    z = z_ceiling - drop
    mb_cord.cyl((x, y, z_ceiling), (x, y, z + 0.18), 0.004, segs=6)
    mb_shade.cyl((x, y, z + 0.12), (x, y, z + 0.2), 0.035, segs=16)
    # cone shade, open bottom
    mb_shade.cyl((x, y, z), (x, y, z + 0.13), r, r2=0.05, segs=32, cap=False)
    mb_bulb.sphere((x, y, z + 0.06), 0.045, segs=12, rings=8)


def prop_radiator(mb, axis, a0, p, z0, length=1.2, h=0.62, fins=None):
    n = fins or int(length / 0.06)
    for i in range(n):
        a = a0 + i * length / n
        mb.box(*_ab(axis, a, a + length / n * 0.75, p - 0.09, p + 0.09, z0 + 0.08, z0 + h))
        mb.box(*_ab(axis, a, a + length / n * 0.75, p - 0.05, p + 0.05, z0 + 0.06, z0 + h + 0.02))
    # legs + top header
    mb.box(*_ab(axis, a0, a0 + 0.04, p - 0.08, p + 0.08, z0, z0 + 0.1))
    mb.box(*_ab(axis, a0 + length - 0.06, a0 + length - 0.02, p - 0.08, p + 0.08, z0, z0 + 0.1))



_LEAF_CACHE = {}


def leaf_object(mat, length=0.11, width=0.06, kind="ovate"):
    """A single leaf mesh used as a particle instance (hidden itself)."""
    key = (mat.name, length, width, kind)
    if key in _LEAF_CACHE:
        return _LEAF_CACHE[key]
    mb = MB()
    fn = leaf_shape(length, width, fold=0.2, droop=0.02, seed=1, kind="fig" if kind == "ovate" else kind)
    mb.grid(fn, 5, 2)
    ob = mb.obj("leaf_inst", mat, smooth=True, recalc=False)
    # template sits at the origin but is shrunk to nothing; particle instances use their own size
    ob.scale = (1e-4, 1e-4, 1e-4)
    _LEAF_CACHE[key] = ob
    return ob


def prop_tree(base, height=9.0, crown_r=3.2, leaf_mat=None, bark_mat=None, seed=0, leaves=9000, leaf_size=1.0,
              nblobs=7, trunk_r=0.22, kind="ovate"):
    """Deciduous tree: tapered trunk + branches, crown of hidden blobs filled with instanced leaves."""
    rnd = random.Random(seed)
    bx, by, bz = base
    tr = MB()
    top = V((bx + rnd.uniform(-0.3, 0.3), by + rnd.uniform(-0.3, 0.3), bz + height * 0.55))
    pts = [V((bx, by, bz)).lerp(top, i / 6) + V((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), 0)) for i in range(7)]
    for i in range(6):
        tr.cyl(pts[i], pts[i + 1], trunk_r * (1 - i * 0.1), r2=trunk_r * (1 - (i + 1) * 0.1), segs=12)
    crown_c = V((top.x, top.y, bz + height - crown_r))
    blobs = []
    for k in range(nblobs):
        d = V((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.6, 0.8)))
        if d.length > 1:
            d.normalize()
        c = crown_c + V((d.x * crown_r * 0.65, d.y * crown_r * 0.65, d.z * crown_r * 0.5))
        r = crown_r * rnd.uniform(0.45, 0.62)
        blobs.append((c, r))
        # branch from trunk top towards the blob
        start = pts[rnd.randint(3, 6)]
        mid = start.lerp(c, 0.5) + V((0, 0, rnd.uniform(0.2, 0.6)))
        tr.cyl(start, mid, trunk_r * 0.45, r2=trunk_r * 0.28, segs=8)
        tr.cyl(mid, c, trunk_r * 0.28, r2=trunk_r * 0.1, segs=8)
    tr.obj("trunk", bark_mat, smooth=True)
    em = MB()
    for c, r in blobs:
        em.sphere(c, r, segs=14, rings=8, scale=(1, 1, 0.8))
    eo = em.obj("crown_emitter", bark_mat)
    eo.show_instancer_for_render = False
    md = eo.modifiers.new("leaves", "PARTICLE_SYSTEM")
    ps = md.particle_system.settings
    ps.type = "EMITTER"
    ps.count = leaves
    ps.frame_start = ps.frame_end = 1
    ps.lifetime = 10000
    ps.physics_type = "NO"
    ps.emit_from = "VOLUME"
    ps.distribution = "RAND"
    ps.use_emit_random = True
    ps.render_type = "OBJECT"
    ps.instance_object = leaf_object(leaf_mat, 0.12 * leaf_size, 0.07 * leaf_size, kind)
    ps.particle_size = 1.0
    ps.size_random = 0.4
    ps.use_scale_instance = False
    ps.use_rotations = True
    ps.rotation_mode = "GLOB_Z"
    ps.rotation_factor_random = 1.0
    ps.phase_factor_random = 2.0
    ps.use_rotation_instance = True
    md.particle_system.seed = seed
    return eo


# ----------------------------------------------------------------------------
# render settings
# ----------------------------------------------------------------------------
class Q:
    samples = 48
    res = 1.0
    out = OUT_DIR


def setup_render(exposure=0.0, look="AgX - Medium High Contrast", samples=1.0, bounces=(4, 3, 6), threshold=0.035,
                 clamp=6.0, gamma=1.0, filmic_sat=None):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    c = s.cycles
    c.device = "CPU"
    c.samples = max(8, int(Q.samples * samples))
    c.use_adaptive_sampling = True
    c.adaptive_threshold = threshold
    c.adaptive_min_samples = 0
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    c.denoising_prefilter = "ACCURATE"
    try:
        c.denoising_quality = "HIGH"
    except Exception:
        pass
    c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces = bounces
    c.max_bounces = max(bounces) + 2
    c.transparent_max_bounces = 16
    c.volume_bounces = 0
    c.sample_clamp_direct = 0.0
    c.sample_clamp_indirect = clamp
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 1.0
    c.use_light_tree = True
    s.render.resolution_x = int(1600 * Q.res)
    s.render.resolution_y = int(900 * Q.res)
    s.render.resolution_percentage = 100
    s.render.film_transparent = False
    s.render.threads_mode = "AUTO"
    vs = s.view_settings
    vs.view_transform = "AgX"
    vs.look = look
    vs.exposure = exposure
    vs.gamma = gamma
    s.display_settings.display_device = "sRGB"
    s.sequencer_colorspace_settings.name = "sRGB"
    s.render.image_settings.file_format = "JPEG"
    s.render.image_settings.color_mode = "RGB"
    s.render.image_settings.quality = 88


def save_jpeg(path):
    s = bpy.context.scene
    img = bpy.data.images["Render Result"]
    for q in (88, 86, 84, 82, 80, 78, 75, 72, 68, 64):
        s.render.image_settings.quality = q
        img.save_render(path, scene=s)
        if os.path.getsize(path) <= MAX_BYTES:
            break
    return q, os.path.getsize(path)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _LEAF_CACHE.clear()
    random.seed(0)


# ============================================================================
# SCENES
# ============================================================================
def city_blocks(rnd, region, n, mat_list, ground_z=0.0, hmin=8, hmax=40, wmin=8, wmax=25, avoid=None):
    """Scatter simple block buildings (with a roof kicker) inside region=(x0,x1,y0,y1)."""
    mb = MB()
    x0, x1, y0, y1 = region
    for i in range(n):
        cx, cy = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        if avoid and avoid(cx, cy):
            continue
        w, d, h = rnd.uniform(wmin, wmax), rnd.uniform(wmin, wmax), rnd.uniform(hmin, hmax)
        mi = rnd.randrange(len(mat_list))
        mb.box((cx - w / 2, cy - d / 2, ground_z), (cx + w / 2, cy + d / 2, ground_z + h), mi=mi)
        if rnd.random() < 0.5:
            mb.box((cx - w / 4, cy - d / 4, ground_z + h), (cx + w / 6, cy + d / 6, ground_z + h + rnd.uniform(2, 5)), mi=mi)
    return mb.obj("city", mat_list)


def scene_loft():
    """The Foundry Loft: sunlit brick loft, tall steel windows, late-afternoon west sun."""
    rnd = random.Random(7)
    X0, X1, Y0, Y1, H = 0.0, 18.0, 0.0, 10.0, 5.4
    T = 0.5
    sun_el, sun_az = 15.0, 296.0
    brick = mat_brick("brick", soot=0.3, efflo=0.25)
    floor = mat_wood_floor("floor", c_dark=(0.12, 0.062, 0.03), c_light=(0.33, 0.18, 0.09), worn=0.45, rough=(0.25, 0.5))
    ceil = mat_wood_floor("ceiling", plank_w=0.14, plank_l=4.0, c_dark=(0.10, 0.06, 0.035), c_light=(0.22, 0.13, 0.07),
                          rough=(0.6, 0.85), worn=0.0, axis="Y")
    beam = mat_timber_beam("beam")
    steel = mat_paint("steel_black", (0.018, 0.018, 0.018), rough=0.38, metal=0.6, wear=0.25, under=(0.12, 0.09, 0.07))
    iron = mat_paint("iron", (0.035, 0.045, 0.042), rough=0.45, metal=0.3, wear=0.2, under=(0.15, 0.08, 0.05))
    glass = mat_glass("glass", dirt=0.12)
    sill = mat_concrete("sill", base=(0.45, 0.43, 0.40), rough=(0.6, 0.85), stains=0.6)
    leather = mat_leather("leather", base=(0.065, 0.026, 0.012))
    oak = mat_wood("oak", base=(0.36, 0.20, 0.09), rough=0.5, coat=0.3)
    dark_wood = mat_wood("dark_wood", base=(0.08, 0.04, 0.02), rough=0.4)
    plywood = mat_wood("plywood", base=(0.55, 0.38, 0.22), rough=0.6, scale=0.6)
    chrome = mat_metal("chrome", (0.75, 0.75, 0.75), rough=0.12)
    alu = mat_metal("alu", (0.62, 0.62, 0.64), rough=0.35, dirt=0.4)
    black = mat_fabric("black_cloth", (0.012, 0.012, 0.012), sheen=0.3)
    diffuser = mat_fabric("diffuser", (0.85, 0.85, 0.83), sheen=0.2)
    rug = mat_rug("rug", size=(3.4, 2.4))
    terracotta = mat_terracotta("pot", base=(0.30, 0.30, 0.29))
    soil = simple("soil", (0.04, 0.03, 0.02), 1.0)
    stem = simple("stem", (0.12, 0.09, 0.05), 0.7)
    leaf = mat_leaf("leaf", base=(0.035, 0.11, 0.025))
    cloth = [mat_fabric(f"cloth{i}", c) for i, c in enumerate([(0.55, 0.45, 0.32), (0.04, 0.05, 0.09), (0.02, 0.02, 0.02),
                                                               (0.20, 0.22, 0.12), (0.35, 0.10, 0.05), (0.7, 0.68, 0.62)])]
    enamel = mat_paint("enamel", (0.03, 0.08, 0.06), rough=0.25, wear=0.15, under=(0.7, 0.7, 0.68))
    bulbm = mat_bulb("bulb", strength=6.0)
    cord = simple("cord", (0.01, 0.01, 0.01), 0.5)

    # ---- shell -----------------------------------------------------------------
    walls = MB()
    win_x = [2.0 + 3.4 * i for i in range(5)]
    ww, wz0, wz1 = 2.1, 0.8, 4.55
    wall_with_openings(walls, "X", X0 - T, X1 + T, Y0 - T, Y0, -0.3, H + 0.6, [(x - ww / 2, x + ww / 2, wz0, wz1) for x in win_x])
    back_y = [2.9, 7.1]
    wall_with_openings(walls, "Y", Y0, Y1, X0 - T, X0, -0.3, H + 0.6, [(y - 1.0, y + 1.0, wz0, wz1) for y in back_y])
    walls.box((X0 - T, Y1, -0.3), (X1 + T, Y1 + T, H + 0.6))
    walls.box((X1, Y0, -0.3), (X1 + T, Y1, H + 0.6))
    # segmental brick lintels read as a slightly darker soldier course: small projecting band
    walls.obj("walls", brick)
    plane("floor", X0 - 0.01, X1 + 0.01, Y0 - 0.01, Y1 + 0.01, 0.0, floor)
    # skirting-level grime strip isn't needed; ceiling deck
    plane_c = MB()
    plane_c.box((X0, Y0, H), (X1, Y1, H + 0.05))
    plane_c.obj("ceiling", ceil)
    # beams (along Y) and joists (along X)
    bm_ = MB()
    beam_x = [3.7 + 3.4 * i for i in range(4)]
    for x in beam_x:
        bm_.box((x - 0.16, Y0 - 0.1, H - 0.62), (x + 0.16, Y1 + 0.1, H - 0.2))
    for j in range(1, 17):
        y = Y0 + j * (Y1 - Y0) / 17
        bm_.box((X0, y - 0.04, H - 0.2), (X1, y + 0.04, H))
    bm_.obj("beams", beam, bevel=0.012, segs=2)
    # cast-iron columns with simple capitals
    col = MB()
    for x in beam_x[:3]:
        y = 5.0
        col.cyl((x, y, 0), (x, y, 0.25), 0.2, segs=24)
        col.cyl((x, y, 0.25), (x, y, H - 0.75), 0.12, r2=0.105, segs=24)
        col.cyl((x, y, H - 0.75), (x, y, H - 0.62), 0.14, r2=0.22, segs=24)
        col.box((x - 0.2, y - 0.2, H - 0.66), (x + 0.2, y + 0.2, H - 0.62))
    col.obj("columns", iron, smooth=True, bevel=0.01)
    # steel windows (frame towards outside of the reveal) + sills
    fr, gl, sl = MB(), MB(), MB()
    for x in win_x:
        steel_window(fr, gl, "X", x - ww / 2, x + ww / 2, wz0, wz1, Y0 - 0.36, 4, 7, transom=5)
        sl.box((x - ww / 2 - 0.05, Y0 - T + 0.05, wz0 - 0.06), (x + ww / 2 + 0.05, Y0 + 0.04, wz0))
    for y in back_y:
        steel_window(fr, gl, "Y", y - 1.0, y + 1.0, wz0, wz1, X0 - 0.36, 4, 7, transom=5)
        sl.box((X0 - T + 0.05, y - 1.05, wz0 - 0.06), (X0 + 0.04, y + 1.05, wz0))
    fr.obj("frames", steel, bevel=0.004)
    gl.obj("glass", glass)
    sl.obj("sills", sill, bevel=0.008)
    # radiators under windows
    rad_mb = MB()
    for x in win_x[1:4]:
        prop_radiator(rad_mb, "X", x - 0.6, Y0 + 0.16, 0.0, length=1.2)
    rad_mb.obj("radiators", iron, bevel=0.006)
    # sprinkler / service pipe along the window wall, conduit on the right wall
    pipes = MB()
    pipes.cyl((X0, Y0 + 0.5, H - 0.75), (X1, Y0 + 0.5, H - 0.75), 0.04, segs=16)
    pipes.cyl((X0, Y1 - 0.08, 3.2), (X1, Y1 - 0.08, 3.2), 0.016, segs=10)
    for x in range(1, 18, 2):
        pipes.box((x - 0.02, Y0 + 0.44, H - 0.75), (x + 0.02, Y0 + 0.56, H - 0.62))
    pipes.obj("pipes", mat_paint("pipe_red", (0.35, 0.03, 0.02), rough=0.35, wear=0.2), smooth=True)

    # ---- outside: street-level city far below ------------------------------------
    haze = (0.95, 0.72, 0.5)
    city_m = [distant_mat("far1", (0.35, 0.2, 0.14), haze, 2.2, falloff=70, windows=(3.5, 3.4)),
              distant_mat("far2", (0.5, 0.48, 0.45), haze, 2.2, falloff=70, windows=(4.0, 3.2)),
              distant_mat("far3", (0.25, 0.25, 0.27), haze, 2.2, falloff=70, windows=(2.5, 3.3))]
    city_blocks(rnd, (-160, 120, -300, -70), 50, city_m, ground_z=-14, hmin=6, hmax=22)
    city_blocks(rnd, (-300, -70, -60, 160), 35, city_m, ground_z=-14, hmin=6, hmax=22)
    plane("street", -800, 800, -800, 800, -14, distant_mat("ground", (0.15, 0.14, 0.13), haze, 2.2, falloff=70))

    # ---- props --------------------------------------------------------------------
    rug_mb = MB()
    rug_mb.box((-1.7, -1.2, 0), (1.7, 1.2, 0.012))
    rug_mb.obj("rug", rug, bevel=0.004, loc=(10.2, 7.3, 0.0), rot=(0, 0, rad(2)))
    prop_sofa(Matrix.Translation((10.2, 8.35, 0.012)), leather, dark_wood)
    prop_table(Matrix.Translation((10.2, 6.8, 0.012)), oak, steel, W=1.25, D=0.65, H=0.43)
    # stuff on the coffee table: books + mug
    misc = MB()
    misc.box((9.75, 6.65, 0.442), (10.05, 6.87, 0.47))
    misc.box((9.78, 6.67, 0.47), (10.02, 6.85, 0.49))
    misc.cyl((10.5, 6.9, 0.442), (10.5, 6.9, 0.54), 0.04, segs=20)
    misc.obj("tablestuff", [mat_paint("book", (0.55, 0.52, 0.45), rough=0.7)], bevel=0.003)
    # armchair-ish leather lounge chair near the rug
    prop_sofa(Matrix.Translation((11.4, 6.2, 0.0)) @ Matrix.Rotation(rad(-115), 4, "Z") @ Matrix.Diagonal((0.42, 1.0, 1.0, 1.0)), leather, dark_wood)
    # big work table with laptop / case
    prop_table(Matrix.Translation((5.2, 6.6, 0.0)) @ Matrix.Rotation(rad(90), 4, "Z"), oak, steel, W=2.6, D=1.0, H=0.76)
    tt = MB()
    tt.box((5.0, 6.0, 0.76), (5.33, 6.24, 0.775))                       # laptop
    tt.box((4.95, 7.1, 0.76), (5.45, 7.45, 0.92))                         # hard case
    tt.cyl((5.5, 6.4, 0.76), (5.5, 6.4, 0.86), 0.04, segs=20)
    tt.obj("worktop_items", [mat_paint("case", (0.02, 0.02, 0.02), rough=0.55)], bevel=0.008)
    stools = MB()
    for (x, y) in ((4.5, 5.6), (4.4, 7.4), (6.05, 6.1)):
        stools.cyl((x, y, 0.62), (x, y, 0.66), 0.18, segs=24)
        for k in range(4):
            a = k * math.pi / 2 + 0.6
            stools.cyl((x + math.cos(a) * 0.12, y + math.sin(a) * 0.12, 0.62), (x + math.cos(a) * 0.2, y + math.sin(a) * 0.2, 0.0), 0.013, segs=8)
    stools.obj("stools", steel, smooth=True)
    # pendants over the work table
    sh, cd, bl = MB(), MB(), MB()
    for y in (5.9, 7.3):
        prop_pendant(sh, cd, bl, 5.2, y, H - 0.2, 1.75, r=0.22)
    sh.obj("shades", enamel, smooth=True)
    cd.obj("cords", cord)
    bl.obj("bulbs", bulbm, smooth=True)
    for y in (5.9, 7.3):
        add_point("pendant", (5.2, y, H - 0.2 - 1.75 + 0.03), 25, color=(1.0, 0.65, 0.35), radius=0.04)
    # crew gear: c-stands, light on stand, apple boxes, rolling rack, plant
    prop_cstand((8.6, 2.6, 0), rad(120), alu, black)
    prop_cstand((14.7, 3.2, 0), rad(160), alu, black, height=1.6, arm_len=0.8, flag=False)
    prop_lightstand((11.6, 3.9, 0), rad(140), alu, black, diffuser, height=1.8, box=(0.55, 0.75))
    prop_apple_boxes((9.4, 1.9, 0), rad(10), plywood, n=3, seed=2)
    prop_apple_boxes((13.6, 8.6, 0), rad(-20), plywood, n=2, seed=5)
    prop_rack((12.9, 9.45, 0), rad(2), chrome, cloth, length=1.6, seed=4)
    prop_plant((11.3, 0.9, 0), terracotta, soil, stem, leaf, height=2.0, seed=11, nleaves=60)
    prop_plant((2.0, 8.9, 0), terracotta, soil, stem, leaf, height=1.6, seed=21, nleaves=40)
    # a stack of flight cases against the right wall
    fc = MB()
    fc.box((16.6, 7.4, 0), (17.6, 8.0, 0.55))
    fc.box((16.7, 7.45, 0.55), (17.5, 7.95, 0.95))
    fc.obj("cases", [mat_paint("flightcase", (0.03, 0.03, 0.03), rough=0.5, wear=0.2, under=(0.4, 0.4, 0.4))], bevel=0.02, segs=2)

    # ---- light --------------------------------------------------------------------
    add_sun(sun_el, sun_az, strength=18.0, angle=0.5, color=(1.0, 0.80, 0.58))
    sky_world(sun_el, sun_az, strength=0.35, dust=1.6, tint=(1.0, 0.93, 0.85))
    for x in win_x:
        add_area("portal", (x, Y0 - T - 0.02, (wz0 + wz1) / 2), (ww, wz1 - wz0), 1.0, rot=(rad(-90), 0, 0), portal=True)
    for y in back_y:
        add_area("portal", (X0 - T - 0.02, y, (wz0 + wz1) / 2), (2.0, wz1 - wz0), 1.0, rot=(0, rad(90), 0), portal=True)
    # faint dust in the air so the sun shafts read
    if LOFT_HAZE:
        vol_m, VT = new_material("air_dust")
        vs = VT.shader("ShaderNodeVolumeScatter", Color=(1.0, 0.95, 0.9), Density=LOFT_HAZE, Anisotropy=0.6)
        VT.links.new(vs, VT.output.inputs["Volume"])
        vb = MB()
        vb.box((X0 + 0.02, Y0 - 0.3, 0.01), (X1 - 0.02, Y1 - 0.02, H - 0.65))
        vb.obj("dust", vol_m)
    add_camera((17.2, 8.4, 1.5), (0.0, 2.2), lens=24, shift_y=0.1)
    setup_render(exposure=1.2, samples=0.85, bounces=(4, 3, 4))
    bpy.context.scene.cycles.volume_step_rate = 4.0



def cyc_corner(mat, floor_mat, corner=(0.0, 12.0), len_a=6.0, len_b=6.0, R=1.4, Rc=0.7, H=5.5, floor_ext=5.5):
    """Two-wall photo cyclorama in the corner where the x=cx and y=cy walls meet: rounded
    vertical corner (radius R), coved floor junction (radius Rc) and a painted floor apron."""
    cx, cy = corner[0] + 0.03, corner[1] - 0.03   # stand slightly proud of the concrete walls
    C = V((cx + R, cy - R, 0))
    path = []   # (point on wall line, inward normal)
    n_lin = 8
    for i in range(n_lin + 1):          # along x=cx wall, from y=cy-len_a up to corner start
        y = cy - len_a + (len_a - R) * i / n_lin
        path.append((V((cx, y, 0)), V((1, 0, 0))))
    for i in range(1, 16):
        a = math.pi - (math.pi / 2) * i / 16
        d = V((math.cos(a), math.sin(a), 0))
        path.append((C + d * R, -d))
    for i in range(n_lin + 1):
        x = cx + R + (len_b - R) * i / n_lin
        path.append((V((x, cy, 0)), V((0, -1, 0))))
    prof = []
    for j in range(9):
        t = (math.pi / 2) * j / 8
        prof.append((Rc * (1 - math.sin(t)), Rc * (1 - math.cos(t))))
    prof.append((0.0, H))
    mb = MB()
    vs = [[mb.bm.verts.new(p + n * d + V((0, 0, z))) for (d, z) in prof] for (p, n) in path]
    for i in range(len(path) - 1):
        for j in range(len(prof) - 1):
            mb.bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]))
    # painted floor area following the cove's foot
    foot = [p + n * Rc for (p, n) in path]
    poly = [V((cx + Rc + floor_ext, cy - len_a, 0.0))] + [V((f.x, f.y, 0.0)) for f in foot] + [V((cx + len_b, cy - Rc - floor_ext, 0.0))]
    poly.append(V((cx + Rc + floor_ext, cy - Rc - floor_ext, 0.0)))
    fb = MB()
    fb.poly([V((p.x, p.y, 0.003)) for p in poly])
    mb.obj("cyc", mat, smooth=True)
    fb.obj("cyc_floor", floor_mat)


def mat_cyc_paint(name="cyc_paint", base=(0.80, 0.80, 0.78), scuff=0.5):
    m, T = new_material(name)
    pos = T.geo("Position")
    _, _, pz = T.sep(pos)
    sc = T.mul(T.maprange(T.noise(T.vmath("MULTIPLY", pos, (1.0, 1.0, 0.0)), 1.2, 6, 0.65, dist=0.4), 0.55, 0.8), scuff)
    sc = T.mul(sc, T.maprange(pz, 0.9, 0.0))
    marks = T.mul(T.maprange(T.noise(T.vmath("MULTIPLY", pos, (3.0, 0.4, 0.0)), 5.0, 3), 0.66, 0.7), T.maprange(pz, 0.2, 0.0))
    col = T.mix(T.add(sc, T.mul(marks, 0.4)), base, (0.42, 0.40, 0.37))
    r = T.add(0.8, T.mul(sc, -0.25))
    return finish(m, T, T.principled(base=col, rough=r, spec=0.3))


def mat_diffuser_lit(name, strength=8.0, color=(1.0, 0.97, 0.92)):
    m, T = new_material(name)
    bsdf = T.principled(base=(0.9, 0.9, 0.9), rough=0.9, emit=color, emit_str=strength)
    return finish(m, T, bsdf)


def prop_octabox(origin, rot, metal, black, diffuser, height=1.9, radius=0.55, tilt=-10, depth=0.45):
    """Monolight in a deep octagonal softbox on a C-stand-like tripod, aimed along local +Y."""
    M = Matrix.Translation(V(origin)) @ Matrix.Rotation(rot, 4, "Z")
    mb = MB()
    L = Local(mb, M)
    for i in range(3):
        ang = i * 2 * math.pi / 3 + 0.4
        L.cyl((0, 0, 0.6), (math.cos(ang) * 0.55, math.sin(ang) * 0.55, 0.0), 0.013, segs=10)
        L.cyl((0, 0, 0.38), (math.cos(ang) * 0.32, math.sin(ang) * 0.32, 0.6), 0.008, segs=8)
    L.cyl((0, 0, 0.3), (0, 0, height), 0.018, segs=14)
    mb.obj("ostand", metal, smooth=True)
    Mh = M @ Matrix.Translation((0, 0, height + 0.1)) @ Matrix.Rotation(rad(tilt), 4, "X")
    hb = MB()
    Lh = Local(hb, Mh)
    Lh.cyl((0, -0.45, 0), (0, -0.12, 0), 0.075, segs=20)        # head
    Lh.cyl((0, -0.12, 0), (0, depth, 0), 0.09, r2=radius, segs=8, cap=False)
    hb.obj("ohead", black, smooth=False)
    db = MB()
    Ld = Local(db, Mh)
    Ld.cyl((0, depth - 0.005, 0), (0, depth, 0), radius * 0.97, segs=8)
    db.obj("odiff", diffuser)
    return Mh


def prop_tripod_camera(origin, rot, metal, black, height=1.45):
    M = Matrix.Translation(V(origin)) @ Matrix.Rotation(rot, 4, "Z")
    mb = MB()
    L = Local(mb, M)
    for i in range(3):
        a = i * 2 * math.pi / 3
        L.cyl((0, 0, height - 0.12), (math.cos(a) * 0.45, math.sin(a) * 0.45, 0), 0.014, segs=10)
    L.cyl((0, 0, height - 0.15), (0, 0, height - 0.05), 0.03, segs=14)
    mb.obj("tripod", metal, smooth=True)
    cb = MB()
    L = Local(cb, M)
    L.box((-0.07, -0.08, height - 0.05), (0.07, 0.08, height + 0.08))
    L.cyl((0, 0.08, height + 0.01), (0, 0.24, height + 0.01), 0.045, segs=24)
    L.box((-0.03, -0.12, height + 0.03), (0.03, 0.02, height + 0.12))
    cb.obj("camera_body", black, bevel=0.008, segs=2)


def prop_vflat(origin, rot, white, black, w=1.2, h=2.4, t=0.05, open_deg=70):
    M = Matrix.Translation(V(origin)) @ Matrix.Rotation(rot, 4, "Z")
    mb = MB()
    L = Local(mb, M)
    L.box((0, -t, 0), (w, 0, h), mi=0)
    L.box((0, 0, 0), (w, 0.002, h), mi=1)
    M2 = M @ Matrix.Rotation(rad(open_deg), 4, "Z")
    L2 = Local(mb, M2)
    L2.box((0, 0, 0), (w, t, h), mi=0)
    L2.box((0, -0.002, 0), (w, 0, h), mi=1)
    mb.obj("vflat", [white, black], bevel=0.004)


def scene_studio():
    """Canal Street Studio: double-height concrete studio, giant steel window wall, cyc corner."""
    X1, Y1, H = 16.0, 12.0, 7.6
    T_ = 0.4
    sun_el, sun_az = 38.0, 70.0  # sun behind the building: soft daylight through the north windows
    conc_wall = mat_concrete("conc_wall", base=(0.50, 0.49, 0.46), rough=(0.7, 0.92), stains=0.55, formwork=True)
    conc_floor = mat_concrete("conc_floor", base=(0.34, 0.335, 0.32), rough=(0.22, 0.5), stains=0.7, polished=True, bump=0.5, pores=0.15)
    conc_ceil = mat_concrete("conc_ceil", base=(0.45, 0.44, 0.42), rough=(0.8, 0.95), stains=0.4)
    steel = mat_paint("steel", (0.02, 0.022, 0.024), rough=0.4, metal=0.5, wear=0.2, under=(0.2, 0.12, 0.08))
    glass = mat_glass("glass", dirt=0.08)
    cyc = mat_cyc_paint("cyc", base=(0.83, 0.83, 0.81))
    cyc_floor = mat_cyc_paint("cyc_floor", base=(0.80, 0.80, 0.78), scuff=0.9)
    alu = mat_metal("alu", (0.6, 0.6, 0.62), rough=0.3, dirt=0.3)
    black = mat_paint("black", (0.012, 0.012, 0.012), rough=0.6)
    blackcloth = mat_fabric("blackcloth", (0.01, 0.01, 0.01), sheen=0.2)
    lit = mat_diffuser_lit("lit", 6.0)
    whitefoam = simple("foam", (0.85, 0.85, 0.84), 0.9)
    paper = mat_cyc_paint("paper", base=(0.30, 0.31, 0.32), scuff=0.2)
    plywood = mat_wood("ply", base=(0.55, 0.38, 0.22), rough=0.6, scale=0.6)
    duct = mat_metal("duct", (0.55, 0.56, 0.58), rough=0.4, dirt=0.3)
    # ---- shell ------------------------------------------------------------
    w = MB()
    win_bays = [(0.9, 5.1), (5.9, 10.1), (10.9, 15.1)]
    wz0, wz1 = 0.7, 6.9
    wall_with_openings(w, "X", -T_, X1 + T_, -T_, 0.0, -0.2, H + 0.4, [(a, b, wz0, wz1) for a, b in win_bays])
    w.box((-T_, 0, -0.2), (0, Y1, H + 0.4))
    w.box((-T_, Y1, -0.2), (X1 + T_, Y1 + T_, H + 0.4))
    w.box((X1, 0, -0.2), (X1 + T_, Y1, H + 0.4))
    # pilasters + downstand beams
    for x in (0.0, 5.5, 10.5, 16.0):
        w.box((x - 0.25, 0.0, 0.0), (x + 0.25, 0.35, H))
    for x in (5.5, 10.5):
        w.box((x - 0.25, 0.0, H - 0.7), (x + 0.25, Y1, H))
    w.obj("walls", conc_wall, bevel=0.01)
    plane("floor", -0.01, X1 + 0.01, -0.01, Y1 + 0.01, 0.0, conc_floor)
    cb = MB()
    cb.box((0, 0, H), (X1, Y1, H + 0.3))
    cb.obj("ceiling", conc_ceil)
    fr, gl = MB(), MB()
    for a, b in win_bays:
        steel_window(fr, gl, "X", a, b, wz0, wz1, -0.22, 7, 10, fw=0.08, transom=3)
    fr.obj("frames", steel, bevel=0.004)
    gl.obj("glass", glass)
    # spiral duct along the ceiling + industrial pendants (off)
    d = MB()
    d.cyl((0, 8.0, H - 1.1), (X1, 8.0, H - 1.1), 0.32, segs=32)
    for x in range(1, 16, 3):
        d.cyl((x, 8.0, H - 0.78), (x, 8.0, H - 0.3), 0.01, segs=6)
    d.obj("duct", duct, smooth=True)
    sh, cd, bl = MB(), MB(), MB()
    for x in (3.0, 8.0, 13.0):
        for y in (3.5,):
            prop_pendant(sh, cd, bl, x, y, H, 3.0, r=0.32)
    sh.obj("shades", mat_paint("shade", (0.05, 0.05, 0.05), rough=0.4), smooth=True)
    cd.obj("cords", black)
    bl.obj("bulbs", simple("bulb_off", (0.8, 0.8, 0.8), 0.1))
    # ---- outside: building across the canal, lit by the sun --------------------
    opp = [distant_mat("opp1", (0.42, 0.22, 0.15), (0.85, 0.85, 0.9), 1.2, falloff=220, windows=(3.0, 3.5)),
           distant_mat("opp2", (0.55, 0.52, 0.48), (0.85, 0.85, 0.9), 1.2, falloff=220, windows=(3.6, 3.3))]
    ob = MB()
    ob.box((-30, -45, -6), (6, -30, 22), mi=0)
    ob.box((8, -50, -6), (40, -32, 16), mi=1)
    ob.box((42, -48, -6), (70, -34, 26), mi=0)
    ob.obj("across", opp)
    plane("ground", -400, 400, -400, 400, -6, distant_mat("gnd", (0.2, 0.2, 0.2), (0.85, 0.85, 0.9), 1.2, falloff=220))
    # ---- cyclorama + gear ----------------------------------------------------------
    cyc_corner(cyc, cyc_floor, corner=(0.0, Y1), len_a=6.2, len_b=7.0, R=1.5, Rc=0.75, H=5.2, floor_ext=4.2)
    Mh = prop_octabox((5.6, 4.6, 0), rad(25), alu, black, lit, height=1.9, radius=0.6, tilt=-12)
    add_area("octa", (Mh @ V((0, 0.5, 0))), 1.1, 400, color=(1.0, 0.97, 0.93), target=(2.5, 10.5, 0.8), shape="DISK", spread=120)
    prop_lightstand((8.3, 10.6, 0), rad(140), alu, black, whitefoam, height=2.3, box=(0.7, 1.0))
    prop_cstand((7.2, 8.0, 0), rad(-160), alu, blackcloth, height=2.4, arm_len=1.1)
    prop_tripod_camera((11.2, 7.4, 0), rad(120), alu, black)
    prop_vflat((12.6, 11.9, 0), rad(180), whitefoam, black, open_deg=-80)
    prop_apple_boxes((3.0, 9.4, 0), rad(15), plywood, n=1, seed=1)
    prop_apple_boxes((10.4, 9.7, 0), rad(-25), plywood, n=2, seed=3)
    # stool on the cyc
    st = MB()
    st.cyl((2.6, 9.6, 0.62), (2.6, 9.6, 0.66), 0.17, segs=24)
    for k in range(4):
        a = k * math.pi / 2 + 0.3
        st.cyl((2.6 + math.cos(a) * 0.1, 9.6 + math.sin(a) * 0.1, 0.62), (2.6 + math.cos(a) * 0.2, 9.6 + math.sin(a) * 0.2, 0), 0.012, segs=8)
    st.obj("stool", plywood, smooth=True)
    # grey seamless paper on a background stand by the windows
    bp = MB()
    for y in (1.3, 4.3):
        bp.cyl((9.8, y, 0), (9.8, y, 3.1), 0.02, segs=10)
        for k in range(3):
            a = k * 2 * math.pi / 3
            bp.cyl((9.8, y, 0.5), (9.8 + math.cos(a) * 0.45, y + math.sin(a) * 0.45, 0), 0.012, segs=8)
    bp.cyl((9.8, 1.1, 3.0), (9.8, 4.5, 3.0), 0.05, segs=24)
    bp.obj("bg_stand", alu, smooth=True)
    pp = MB()

    def paper_fn(u, v):
        # hangs from the roll, sweeps onto the floor towards +x
        t = v * 4.3
        y = 1.5 + u * 2.6
        if t < 2.95:
            return (9.8 + 0.05, y, 3.0 - t)
        a = (t - 2.95) / 0.5 * (math.pi / 2)
        if a <= math.pi / 2:
            return (9.85 + 0.5 * (1 - math.cos(a)), y, 0.5 * (1 - math.sin(a)) + 0.004)
        return (10.35 + (t - 2.95 - 0.785), y, 0.004)
    pp.grid(paper_fn, 4, 40)
    pp.obj("paper", paper, smooth=True)
    # client area: sofa + work table with laptop near the window wall
    prop_sofa(Matrix.Translation((7.6, 1.5, 0)) @ Matrix.Rotation(rad(180), 4, "Z"),
              mat_leather("leather", base=(0.03, 0.028, 0.026)), steel)
    prop_table(Matrix.Translation((11.4, 3.2, 0)) @ Matrix.Rotation(rad(90), 4, "Z"), mat_wood("oak", base=(0.4, 0.25, 0.12), coat=0.2), steel,
               W=1.8, D=0.8, H=0.92)
    lt = MB()
    lt.box((11.25, 2.8, 0.92), (11.55, 3.15, 0.935))
    lt.box((11.53, 2.8, 0.935), (11.55, 3.15, 1.16), mi=0)
    lt.box((11.2, 3.4, 0.92), (11.5, 3.7, 1.05))
    lt.obj("laptop", [mat_metal("lap", (0.5, 0.5, 0.52), rough=0.3)], bevel=0.005)
    # sandbags
    sb = MB()
    for (x, y) in ((7.6, 8.3), (8.5, 10.9), (6.0, 4.8)):
        sb.sphere((x, y, 0.06), 0.18, scale=(1.0, 0.55, 0.38))
    sb.obj("sandbags", mat_fabric("sandbag", (0.14, 0.11, 0.06)), smooth=True)
    # ---- light ---------------------------------------------------------------------
    add_sun(sun_el, sun_az, strength=5.0, angle=1.0, color=(1.0, 0.95, 0.88))
    sky_world(sun_el, sun_az, strength=0.55, clouds=0.8, cloud_cover=0.45, cloud_col=(0.95, 0.95, 0.97))
    for a, b in win_bays:
        add_area("portal", ((a + b) / 2, -T_ - 0.02, (wz0 + wz1) / 2), (b - a, wz1 - wz0), 1.0, rot=(rad(-90), 0, 0), portal=True)
    add_camera((15.2, 9.6, 1.55), (0.0, 4.2), lens=22, shift_y=0.12)
    setup_render(exposure=1.3, samples=0.7, bounces=(4, 3, 4))



def arch_outline(a0, a1, z0, z1, rise, n=12):
    """Segmental-arch window outline, CCW in the (a, z) plane, plus arch parameters."""
    w = (a1 - a0) / 2
    c = (a0 + a1) / 2
    R = (w * w + rise * rise) / (2 * rise)   # circle through both springings and the crown
    zc = z1 - R
    th = math.asin(w / R)
    pts = [(a0, z0), (a1, z0)]
    for i in range(n + 1):
        t = th - 2 * th * i / n
        pts.append((c + R * math.sin(t), zc + R * math.cos(t)))
    return pts, (c, zc, R, th)


def voussoirs(mb, axis, plane_p, depth_out, arch, ring=0.23, brick_w=0.075, mi=0):
    """Ring of radial bricks above a segmental arch; plane_p is the wall face coordinate,
    bricks project depth_out in front of it (towards -p for axis X)."""
    c, zc, R, th = arch
    arc_len = 2 * th * (R + ring / 2)
    n = max(5, int(arc_len / brick_w))
    for i in range(n):
        t0 = -th + 2 * th * i / n
        t1 = -th + 2 * th * (i + 1) / n - 0.004 / R
        quad_in = [(c + R * math.sin(t), zc + R * math.cos(t)) for t in (t0, t1)]
        quad_out = [(c + (R + ring) * math.sin(t), zc + (R + ring) * math.cos(t)) for t in (t1, t0)]
        pts = quad_in + quad_out
        if axis == "X":
            mb.prism(pts, plane_p - depth_out, plane_p + 0.02, mi=mi, axis="Y")
        else:
            mb.prism(pts, plane_p - depth_out, plane_p + 0.02, mi=mi, axis="X")


def scene_mill():
    """Mill House No. 9: converted 19th-century brick mill at golden hour."""
    rnd = random.Random(9)
    L0, L1, D, storey, nst = -24.0, 24.0, 16.0, 3.7, 4
    Hwall = storey * nst + 0.9
    T_ = 0.6
    sun_el, sun_az = 8.0, -16.0
    brick = mat_brick("brick", c_dark=(0.22, 0.07, 0.04), c_light=(0.44, 0.17, 0.09), soot=0.45, efflo=0.2, grime_height=1.5)
    arch_brick = mat_brick("arch_brick", c_dark=(0.26, 0.085, 0.05), c_light=(0.38, 0.14, 0.08), soot=0.2, efflo=0.0, bump=0.6)
    eng = mat_brick("eng_brick", c_dark=(0.06, 0.04, 0.04), c_light=(0.14, 0.08, 0.07), mortar=(0.3, 0.3, 0.28), soot=0.1, efflo=0.1)
    stone = mat_concrete("sandstone", base=(0.52, 0.44, 0.33), rough=(0.7, 0.9), stains=0.8, scale=0.6)
    slate = mat_slate("slate")
    frame_paint = mat_paint("sash", (0.72, 0.71, 0.66), rough=0.4, wear=0.15, under=(0.3, 0.25, 0.2), coords="Generated")
    glass = mat_glass("glass", tint=(0.85, 0.88, 0.88), dirt=0.05)
    interior = simple("interior", (0.06, 0.05, 0.045), 0.9)
    iron = mat_paint("iron", (0.02, 0.022, 0.022), rough=0.5, wear=0.2, under=(0.25, 0.1, 0.05))
    cob = mat_cobbles("cobbles", base=(0.24, 0.22, 0.20))
    grass = mat_grass_ground("grass_ground", base=(0.05, 0.10, 0.025), dryness=0.5)
    # ---- facade slabs with arched openings (boolean) ------------------------------------
    walls = MB()
    # front and left gable are separate closed solids so the boolean stays manifold
    ridge = Hwall + 5.0
    walls.box((L0, 0.0, 0.0), (L1, T_, Hwall))                       # front
    front = walls.obj("front_wall", brick)
    gw = MB()
    gw.prism([(T_, 0.0), (D, 0.0), (D, Hwall), (D / 2, ridge), (0.0, Hwall), (T_, Hwall)], L0, L0 + T_, axis="X")
    gable = gw.obj("gable_wall", brick)
    rest = MB()
    rest.box((L1 - T_, T_, 0.0), (L1, D - T_, Hwall))
    rest.box((L0 + T_, D - T_, 0.0), (L1, D, Hwall))
    rest.prism([(0.0, Hwall), (D, Hwall), (D / 2, ridge)], L1 - T_, L1, axis="X")
    rest.obj("other_walls", brick)
    cut = MB()
    vs_mb = MB()
    fr, gl, sl = MB(), MB(), MB()
    bay = 3.0
    xs = [L0 + 2.6 + bay * i for i in range(int((L1 - L0 - 4) / bay) + 1)]
    win_w, win_h, rise = 1.45, 2.25, 0.28
    openings = []
    for k in range(nst):
        z0 = 0.95 + k * storey + 0.55
        for x in xs:
            openings.append(("X", x, z0))
    gy = [2.3 + 2.9 * i for i in range(5)]
    for k in range(nst):
        z0 = 0.95 + k * storey + 0.55
        for y in gy:
            openings.append(("Y", y, z0))
    for axis, a, z0 in openings:
        a0, a1, z1 = a - win_w / 2, a + win_w / 2, z0 + win_h
        pts, arch = arch_outline(a0, a1, z0, z1, rise)
        if axis == "X":
            cut.prism(pts, -0.5, T_ + 0.5, axis="Y")
            voussoirs(vs_mb, "X", 0.0, 0.025, arch)
            # sash window set back 0.18 from the face
            p = 0.2
            gl.prism(pts, p, p + 0.001, axis="Y")
            steel_window(fr, MB(), "X", a0, a1, z0, z1 - rise + 0.02, p, 3, 4, fw=0.07, mw=0.03, depth=0.07, mdepth=0.04, transom=2)
            # arched head: frame band following the arch
            for i in range(len(pts) - 1):
                pa, pb = pts[i], pts[i + 1]
                if pa[1] > z1 - rise - 0.01 and pb[1] > z1 - rise - 0.01:
                    fr.cyl((pa[0], p, pa[1] - 0.035), (pb[0], p, pb[1] - 0.035), 0.035, segs=6)
            fr.box((a0, p - 0.035, z1 - rise - 0.02), (a1, p + 0.035, z1 - rise + 0.05))
            sl.box((a0 - 0.12, -0.08, z0 - 0.14), (a1 + 0.12, 0.25, z0 - 0.01))
        else:
            xw = L0
            cut.prism(pts, xw - 0.5, xw + T_ + 0.5, axis="X")
            voussoirs(vs_mb, "Y", xw, 0.025, arch)
            p = xw + 0.2
            gl.prism(pts, p, p + 0.001, axis="X")
            steel_window(fr, MB(), "Y", a0, a1, z0, z1 - rise + 0.02, p, 3, 4, fw=0.07, mw=0.03, depth=0.07, mdepth=0.04, transom=2)
            for i in range(len(pts) - 1):
                pa, pb = pts[i], pts[i + 1]
                if pa[1] > z1 - rise - 0.01 and pb[1] > z1 - rise - 0.01:
                    fr.cyl((p, pa[0], pa[1] - 0.035), (p, pb[0], pb[1] - 0.035), 0.035, segs=6)
            fr.box((p - 0.035, a0, z1 - rise - 0.02), (p + 0.035, a1, z1 - rise + 0.05))
            sl.box((xw - 0.08, a0 - 0.12, z0 - 0.14), (xw + 0.25, a1 + 0.12, z0 - 0.01))
    cobj = cut.obj("cutters", interior)
    cobj.hide_render = True
    cobj.display_type = "WIRE"
    for wobj in (front, gable):
        md = wobj.modifiers.new("holes", "BOOLEAN")
        md.operation = "DIFFERENCE"
        md.object = cobj
        md.solver = "EXACT"
    vs_mb.obj("voussoirs", arch_brick)
    fr.obj("sashes", frame_paint, bevel=0.004)
    gl.obj("glass", glass)
    sl.obj("sills", stone, bevel=0.01)
    # dark interior + some warm lit rooms
    inn = MB()
    for k in range(nst + 1):
        inn.box((L0 + T_, T_, k * storey + 0.95 - 0.3), (L1 - T_, D - T_, k * storey + 0.95))
    inn.box((L0 + T_, 7.0, 0), (L1 - T_, 7.3, Hwall))
    inn.box((L0 + T_ + 6, T_, 0), (L0 + T_ + 6.3, D - T_, Hwall))
    inn.obj("interior", interior)
    lamp = mat_emit("roomlight", (1.0, 0.62, 0.32), 3.0)
    lm = MB()
    for k in range(nst):
        for x in xs:
            if rnd.random() < 0.16:
                lm.box((x - 1.3, 6.9, k * storey + 1.3), (x + 1.3, 6.95, k * storey + 3.8))
    lm.obj("lit_rooms", lamp)
    # ---- trim: plinth, string courses, cornice, downpipes ---------------------------------
    trim = MB()
    trim.box((L0 - 0.08, -0.08, -0.2), (L1 + 0.08, 0.4, 0.95))
    trim.box((L0 - 0.08, -0.08, -0.2), (L0 + 0.4, D + 0.08, 0.95))
    trim.obj("plinth", eng, bevel=0.01)
    sc = MB()
    for k in range(1, nst):
        z = 0.95 + k * storey - 0.05
        sc.box((L0 - 0.05, -0.05, z), (L1 + 0.05, 0.3, z + 0.18))
        sc.box((L0 - 0.05, -0.05, z), (L0 + 0.3, D + 0.05, z + 0.18))
    sc.box((L0 - 0.15, -0.15, Hwall - 0.05), (L1 + 0.15, 0.4, Hwall + 0.3))
    sc.box((L0 - 0.15, -0.15, Hwall - 0.05), (L0 + 0.4, D + 0.15, Hwall + 0.3))
    sc.obj("courses", stone, bevel=0.015)
    corb = MB()
    for x in [L0 + 0.15 + 0.45 * i for i in range(int((L1 - L0) / 0.45))]:
        corb.box((x, -0.12, Hwall - 0.4), (x + 0.23, 0.1, Hwall - 0.05))
    for y in [0.15 + 0.45 * i for i in range(int(D / 0.45))]:
        corb.box((L0 - 0.12, y, Hwall - 0.4), (L0 + 0.1, y + 0.23, Hwall - 0.05))
    corb.obj("corbels", brick)
    dp = MB()
    for x in (L0 + 0.9, -6.0 + 0.5, 12.0 + 0.5):
        dp.cyl((x, -0.12, 0.0), (x, -0.12, Hwall), 0.06, segs=12)
        for z in range(1, int(Hwall), 2):
            dp.cyl((x, -0.12, z), (x, -0.12, z + 0.08), 0.075, segs=12)
    dp.obj("downpipes", iron, smooth=True)
    # roof: slate pitched + ridge, chimney
    roof = MB()
    ov = 0.35
    roof.poly([(L0 - ov, -ov, Hwall + 0.2), (L1 + ov, -ov, Hwall + 0.2), (L1 + ov, D / 2, ridge + 0.25), (L0 - ov, D / 2, ridge + 0.25)])
    roof.poly([(L0 - ov, D / 2, ridge + 0.25), (L1 + ov, D / 2, ridge + 0.25), (L1 + ov, D + ov, Hwall + 0.2), (L0 - ov, D + ov, Hwall + 0.2)])
    ro = roof.obj("roof", slate)
    sol = ro.modifiers.new("thick", "SOLIDIFY")
    sol.thickness = 0.12
    ch = MB()
    ch.box((14.0, 9.0, 0), (16.6, 11.6, ridge + 13.0))
    ch.box((13.8, 8.8, ridge + 12.4), (16.8, 11.8, ridge + 13.3))
    ch.obj("chimney", brick, bevel=0.02)
    # ---- ground ---------------------------------------------------------------------------
    plane("cobbles", -200, 200, -14, 30, 0.0, cob)
    gb = MB()
    gb.box((-200, -400, -0.4), (200, -14.0, 0.06))
    g = gb.obj("verge", grass)
    kerb = MB()
    kerb.box((-200, -14.15, 0.0), (200, -13.85, 0.12))
    kerb.obj("kerb", stone, bevel=0.02)
    grass_hair(g, 150000, length=0.14, region=(-50, -20, -30, -14), color=(0.06, 0.12, 0.03), dry=(0.35, 0.3, 0.12))
    # bollards + a lamp post
    bo = MB()
    for x in (-30.0, -24.0, -18.0, -12.0, -6.0, 0.0):
        bo.cyl((x, -13.0, 0), (x, -13.0, 0.95), 0.1, segs=20)
        bo.sphere((x, -13.0, 0.95), 0.1, segs=20, rings=10)
    bo.cyl((-21.0, -12.6, 0), (-21.0, -12.6, 4.2), 0.07, r2=0.05, segs=16)
    bo.cyl((-21.0, -12.6, 0), (-21.0, -12.6, 0.6), 0.14, r2=0.09, segs=16)
    bo.box((-21.2, -12.8, 4.2), (-20.8, -12.4, 4.7))
    bo.obj("street_iron", iron, smooth=True)
    # distant town + trees silhouettes behind the mill
    haze = (1.0, 0.72, 0.48)
    far = [distant_mat("far1", (0.35, 0.22, 0.16), haze, 0.45, falloff=300),
           distant_mat("far2", (0.25, 0.23, 0.22), haze, 0.45, falloff=300)]
    city_blocks(rnd, (-120, 260, 80, 300), 40, far, ground_z=0.0, hmin=5, hmax=14)
    # trees along the street
    leafm = mat_leaf("tree_leaf", base=(0.045, 0.10, 0.025), var=0.5)
    barkm = mat_bark()
    prop_tree((-37.5, -9.0, 0), height=10.5, crown_r=3.6, leaf_mat=leafm, bark_mat=barkm, seed=4, leaves=45000, leaf_size=1.5)
    prop_tree((-12.0, -18.5, 0), height=9.0, crown_r=3.2, leaf_mat=leafm, bark_mat=barkm, seed=8, leaves=35000, leaf_size=1.5)
    prop_tree((-52.0, 6.0, 0), height=12.0, crown_r=4.2, leaf_mat=leafm, bark_mat=barkm, seed=12, leaves=50000, leaf_size=1.6)
    # ---- light ----------------------------------------------------------------------------
    add_sun(sun_el, sun_az, strength=26.0, angle=0.6, color=(1.0, 0.56, 0.28))
    sky_world(sun_el, sun_az, strength=0.1, dust=3.0, clouds=0.8, cloud_cover=0.4, cloud_col=(1.0, 0.72, 0.50),
              cloud_scale=1.2, tint=(1.0, 0.88, 0.76))
    add_camera((-40.0, -22.0, 1.6), (-2.0, 6.0), lens=28, shift_y=0.17)
    setup_render(exposure=0.2, look="AgX - Punchy", samples=0.8, bounces=(3, 3, 4))


def grass_hair(ob, count, length=0.1, region=None, color=(0.06, 0.12, 0.03), dry=(0.35, 0.3, 0.12), seed=1, radius=0.0035):
    """Hair-particle grass on an object (only faces inside region get hairs via vertex group)."""
    me = ob.data
    if region is not None:
        # subdivide a dedicated emitter plane instead of the whole object
        x0, x1, y0, y1 = region
        bm = bmesh.new()
        z = max(v.co.z for v in me.vertices)
        bmesh.ops.create_grid(bm, x_segments=60, y_segments=60, size=0.5,
                              matrix=Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, z)) @ Matrix.Diagonal((x1 - x0, y1 - y0, 1, 1)))
        em = bpy.data.meshes.new("grass_emitter")
        bm.to_mesh(em)
        bm.free()
        e = bpy.data.objects.new("grass_emitter", em)
        link(e)
        e.data.materials.append(ob.data.materials[0])
        ob = e
    m, T = new_material("grass_blades")
    info = T.node("ShaderNodeHairInfo")
    rnd = T.out(info, "Random")
    isect = T.out(info, "Intercept")
    col = T.mix(T.maprange(rnd, 0.6, 1.0), color, dry)
    col = T.mix(T.maprange(isect, 0.0, 0.5, 1.0, 0.0), col, [c * 0.3 for c in color])
    sh = T.principled(base=col, rough=0.5, spec=0.4)
    tr = T.shader("ShaderNodeBsdfTranslucent", Color=T.hsv(col, s=1.1, v=1.5))
    finish(m, T, T.mixshader(0.3, sh, tr))
    ob.data.materials.append(m)
    md = ob.modifiers.new("grass", "PARTICLE_SYSTEM")
    ps = md.particle_system.settings
    ps.type = "HAIR"
    ps.count = count
    ps.hair_length = length
    ps.use_advanced_hair = True
    ps.material = len(ob.data.materials)
    ps.root_radius = 1.0
    ps.tip_radius = 0.0
    ps.radius_scale = radius
    ps.use_rotations = True
    ps.rotation_mode = "NOR"
    ps.phase_factor_random = 2.0
    ps.normal_factor = length          # with advanced hair the length comes from the velocity
    ps.factor_random = length * 0.35
    ps.length_random = 0.6
    ps.brownian_factor = 0.02
    ps.hair_step = 3
    ps.render_step = 3
    ps.display_step = 2
    ps.child_type = "NONE"
    md.particle_system.seed = seed
    bpy.context.scene.cycles_curves.shape = "RIBBONS"
    return ob



def mat_corten(name="corten"):
    m, T = new_material(name)
    p = T.coord("Object")
    n1 = T.noise(p, 3.0, 8, 0.7, dist=0.3)
    n2 = T.noise(p, 40.0, 4, 0.6)
    col = T.ramp(T.add(T.mul(n1, 0.8), T.mul(n2, 0.2)), [(0.3, (0.10, 0.035, 0.015)), (0.5, (0.22, 0.08, 0.03)), (0.7, (0.34, 0.14, 0.05))])
    streak = T.maprange(T.noise(T.vmath("MULTIPLY", p, (8.0, 8.0, 0.5)), 3.0, 4), 0.55, 0.75)
    col = T.mix(T.mul(streak, 0.5), col, (0.06, 0.025, 0.012))
    return finish(m, T, T.principled(base=col, rough=T.maprange(n2, 0, 1, 0.65, 0.95), normal=T.bump(n2, 0.4, 0.003)))


def catenary(p0, p1, sag, n=40):
    p0, p1 = V(p0), V(p1)
    return [p0.lerp(p1, i / n) - V((0, 0, 4 * sag * (i / n) * (1 - i / n))) for i in range(n + 1)]


def string_lights(wire_mb, socket_mb, bulb_mb, p0, p1, sag=0.35, spacing=0.6):
    pts = catenary(p0, p1, sag, n=60)
    for a, b in zip(pts, pts[1:]):
        wire_mb.cyl(a, b, 0.0035, segs=5)
    L = sum(((b - a).length for a, b in zip(pts, pts[1:])))
    nb = int(L / spacing)
    for i in range(1, nb):
        t = i / nb
        p = V(p0).lerp(V(p1), t) - V((0, 0, 4 * sag * t * (1 - t)))
        socket_mb.cyl(p, p - V((0, 0, 0.07)), 0.012, segs=8)
        bulb_mb.sphere(p - V((0, 0, 0.11)), 0.04, segs=10, rings=6, scale=(1, 1, 1.25))


def prop_lounge_chair(M, wood, cushion=None):
    """Slatted teak lounge chair, local origin at the floor centre, facing -Y."""
    mb = MB()
    L = Local(mb, M)
    w, d = 0.7, 0.8
    for x in (-w / 2, w / 2 - 0.05):
        L.box((x, -d / 2, 0), (x + 0.05, -d / 2 + 0.05, 0.6))
        L.box((x, d / 2 - 0.05, 0), (x + 0.05, d / 2, 0.42))
        L.box((x - 0.03, -d / 2 - 0.03, 0.58), (x + 0.08, d / 2 - 0.05, 0.62))    # arm
        L.box((x, -d / 2, 0.30), (x + 0.05, d / 2, 0.36))                          # side rail
    for i in range(7):
        y = -d / 2 + 0.06 + i * 0.1
        L.box((-w / 2 + 0.05, y, 0.33 - i * 0.008), (w / 2 - 0.05, y + 0.07, 0.36 - i * 0.008))
    for i in range(6):
        z = 0.42 + i * 0.1
        L.box((-w / 2 + 0.05, d / 2 - 0.04 + i * 0.035, z), (w / 2 - 0.05, d / 2 - 0.0 + i * 0.035, z + 0.07), rot=(rad(-18), 0, 0))
    mb.obj("lounge", wood, bevel=0.006, segs=2)
    if cushion is not None:
        c = MB()
        L = Local(c, M)
        L.box((-w / 2 + 0.06, -d / 2 + 0.05, 0.36), (w / 2 - 0.06, d / 2 - 0.05, 0.44))
        c.obj("cushion", cushion, bevel=0.03, segs=3, smooth=True)


def prop_bistro(origin, metal, seed=0):
    rnd = random.Random(seed)
    ox, oy = origin
    mb = MB()
    mb.cyl((ox, oy, 0.72), (ox, oy, 0.74), 0.32, segs=32)
    mb.cyl((ox, oy, 0.0), (ox, oy, 0.72), 0.025, segs=12)
    mb.cyl((ox, oy, 0.0), (ox, oy, 0.02), 0.22, segs=24)
    for k in range(2):
        a = rnd.uniform(0, 0.4) + k * math.pi
        cx, cy = ox + math.cos(a) * 0.62, oy + math.sin(a) * 0.62
        face = math.atan2(oy - cy, ox - cx)
        mb.cyl((cx, cy, 0.45), (cx, cy, 0.47), 0.2, segs=24)
        for j in range(4):
            b = j * math.pi / 2 + 0.785
            mb.cyl((cx + math.cos(b) * 0.14, cy + math.sin(b) * 0.14, 0.45), (cx + math.cos(b) * 0.2, cy + math.sin(b) * 0.2, 0), 0.01, segs=8)
        bx, by = cx - math.cos(face) * 0.18, cy - math.sin(face) * 0.18
        px, py = -math.sin(face) * 0.17, math.cos(face) * 0.17
        mb.cyl((bx + px, by + py, 0.46), (bx + px * 1.1, by + py * 1.1, 0.85), 0.009, segs=8)
        mb.cyl((bx - px, by - py, 0.46), (bx - px * 1.1, by - py * 1.1, 0.85), 0.009, segs=8)
        arc = [(bx + px * 1.1 * math.cos(t) - math.cos(face) * 0.05 * math.sin(t), by + py * 1.1 * math.cos(t) - math.sin(face) * 0.05 * math.sin(t), 0.85 + 0.04 * math.sin(t)) for t in [i * math.pi / 10 for i in range(11)]]
        for a_, b_ in zip(arc, arc[1:]):
            mb.cyl(a_, b_, 0.012, segs=8)
    mb.obj("bistro", metal, smooth=True)


def water_tower(mb, x, y, z, mi_wood=0, mi_steel=1):
    mb.cyl((x, y, z + 4.0), (x, y, z + 8.5), 2.2, segs=32, mi=mi_wood)
    mb.cyl((x, y, z + 8.5), (x, y, z + 10.0), 2.3, r2=0.15, segs=32, mi=mi_steel)
    for k in range(4):
        a = k * math.pi / 2 + 0.785
        mb.cyl((x + math.cos(a) * 1.6, y + math.sin(a) * 1.6, z), (x + math.cos(a) * 1.6, y + math.sin(a) * 1.6, z + 4.0), 0.12, segs=8, mi=mi_steel)
    mb.box((x - 1.8, y - 1.8, z + 3.8), (x + 1.8, y + 1.8, z + 4.0), mi=mi_steel)


def scene_rooftop():
    """Pier 4 Rooftop Studio: decked roof terrace at golden hour, harbour skyline."""
    rnd = random.Random(4)
    sun_el, sun_az = 9.0, -18.0
    X0, X1, Y0, Y1 = -7.0, 7.0, -4.0, 9.0
    deck = mat_wood_floor("deck", plank_w=0.145, plank_l=3.6, c_dark=(0.16, 0.10, 0.06), c_light=(0.36, 0.25, 0.16),
                          rough=(0.55, 0.8), gap=0.006, worn=0.3, grey=0.45)
    brick = mat_brick("brick", c_dark=(0.20, 0.07, 0.045), c_light=(0.38, 0.15, 0.09), soot=0.35, efflo=0.3, grime_height=0.3)
    coping = mat_concrete("coping", base=(0.48, 0.46, 0.43), rough=(0.7, 0.9), stains=0.8, scale=0.5)
    steel = mat_paint("steel", (0.015, 0.015, 0.015), rough=0.45, wear=0.2, under=(0.2, 0.1, 0.05))
    teak = mat_wood("teak", base=(0.30, 0.18, 0.09), rough=0.55)
    canvas = mat_fabric("canvas", (0.62, 0.60, 0.55))
    canvas2 = mat_fabric("canvas2", (0.15, 0.20, 0.22))
    corten = mat_corten()
    soil = simple("soil", (0.05, 0.035, 0.02), 1.0)
    bulb = mat_bulb("bulb", strength=40.0)
    leaf = mat_leaf("leaf", base=(0.06, 0.12, 0.04))
    stem = simple("stem", (0.2, 0.16, 0.1), 0.7)
    terracotta = mat_terracotta()
    # ---- deck + parapet --------------------------------------------------------------
    roof = MB()
    roof.box((X0 - 30, Y0 - 30, -1.0), (X1 + 30, Y1 + 0.6, -0.16))
    roof.obj("roofslab", coping)
    db = MB()
    db.box((X0, Y0, -0.16), (X1, Y1, 0.0))
    db.obj("deck", deck)
    par = MB()
    ph = 1.05
    par.box((X0 - 0.35, Y1, -0.16), (X1 + 0.35, Y1 + 0.35, ph))
    par.box((X1, Y0, -0.16), (X1 + 0.35, Y1, 0.25))
    par.box((X0 - 0.35, Y0, -0.16), (X0, Y1, ph))
    par.obj("parapet", brick, bevel=0.01)
    cp = MB()
    cp.box((X0 - 0.42, Y1 - 0.06, ph), (X1 + 0.42, Y1 + 0.42, ph + 0.08))
    cp.box((X1 - 0.06, Y0 - 1, 0.25), (X1 + 0.42, Y1, 0.31))
    # glass balustrade on the sunny side (keeps the deck in sun)
    gb_, gp_ = MB(), MB()
    for y in [Y0 - 1 + 1.25 * i for i in range(int((Y1 - Y0 + 1) / 1.25) + 1)]:
        gp_.box((X1 + 0.1, y - 0.03, 0.31), (X1 + 0.16, y + 0.03, ph + 0.05))
    gp_.box((X1 + 0.08, Y0 - 1, ph + 0.02), (X1 + 0.18, Y1, ph + 0.08))
    gb_.poly([(X1 + 0.13, Y0 - 1, 0.33), (X1 + 0.13, Y1, 0.33), (X1 + 0.13, Y1, ph + 0.02), (X1 + 0.13, Y0 - 1, ph + 0.02)])
    gp_.obj("balustrade", steel, bevel=0.004)
    gb_.obj("balustrade_glass", mat_glass("bglass", tint=(0.9, 0.95, 0.93)))
    cp.box((X0 - 0.42, Y0 - 1, ph), (X0 + 0.06, Y1, ph + 0.08))
    cp.obj("coping", coping, bevel=0.012)
    # ---- string lights between steel posts -------------------------------------------
    posts = MB()
    P = [(X0 + 0.25, Y1 - 0.25), (X1 - 0.25, Y1 - 0.25), (X0 + 0.25, Y0 + 2.0), (X1 - 0.25, Y0 + 2.0), (0.0, Y1 - 0.25)]
    for x, y in P:
        posts.box((x - 0.04, y - 0.04, 0), (x + 0.04, y + 0.04, 3.2))
    posts.obj("posts", steel, bevel=0.004)
    wi, so, bu = MB(), MB(), MB()
    top = lambda p: (p[0], p[1], 3.1)
    for a, b, sag in ((P[0], P[3], 0.55), (P[1], P[2], 0.55), (P[2], P[4], 0.4), (P[3], P[4], 0.4), (P[0], P[1], 0.3)):
        string_lights(wi, so, bu, top(a), top(b), sag=sag, spacing=0.55)
    wi.obj("wires", steel)
    so.obj("sockets", steel)
    bu.obj("bulbs", bulb, smooth=True)
    # ---- furniture ---------------------------------------------------------------------
    prop_sofa(Matrix.Translation((-3.2, 4.8, 0)) @ Matrix.Rotation(rad(-90), 4, "Z"), canvas, teak)
    prop_sofa(Matrix.Translation((-1.0, 7.1, 0)) @ Matrix.Rotation(rad(0), 4, "Z") @ Matrix.Diagonal((0.85, 1, 1, 1)), canvas, teak)
    rugm = mat_rug("rug", c1=(0.55, 0.50, 0.42), c2=(0.12, 0.16, 0.18), c3=(0.75, 0.70, 0.6), size=(2.6, 1.8))
    r = MB()
    r.box((-1.3, -0.9, 0), (1.3, 0.9, 0.01))
    r.obj("rug", rugm, loc=(-1.0, 5.1, 0.0), rot=(0, 0, rad(3)))
    prop_table(Matrix.Translation((-1.0, 5.1, 0.01)), teak, steel, W=1.1, D=0.6, H=0.38)
    prop_lounge_chair(Matrix.Translation((2.4, 4.4, 0)) @ Matrix.Rotation(rad(150), 4, "Z"), teak, canvas2)
    prop_lounge_chair(Matrix.Translation((3.6, 5.6, 0)) @ Matrix.Rotation(rad(175), 4, "Z"), teak, canvas2)
    prop_bistro((4.6, 1.5), steel, seed=2)
    # planters with ornamental grass + an olive-ish tree
    pl = MB()
    pm = []
    for (x0, y0, x1, y1) in ((X0 + 0.1, Y1 - 0.7, -2.4, Y1 - 0.1), (1.2, Y1 - 0.7, X1 - 0.1, Y1 - 0.1), (X1 - 0.7, 0.5, X1 - 0.1, 4.0)):
        pl.box((x0, y0, 0), (x1, y1, 0.65))
        pm.append((x0 + 0.03, y0 + 0.03, x1 - 0.03, y1 - 0.03))
    pl.obj("planters", corten, bevel=0.006)
    for i, (x0, y0, x1, y1) in enumerate(pm):
        sb = MB()
        sb.poly([(x0, y0, 0.6), (x1, y0, 0.6), (x1, y1, 0.6), (x0, y1, 0.6)])
        so_ = sb.obj(f"soil{i}", soil)
        bm = bmesh.new()
        bm.from_mesh(so_.data)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=12, use_grid_fill=True)
        bm.to_mesh(so_.data)
        bm.free()
        grass_hair(so_, int((x1 - x0) * (y1 - y0) * 3000), length=0.5, color=(0.12, 0.16, 0.05), dry=(0.55, 0.45, 0.25), seed=i + 3, radius=0.004)
    prop_plant((5.6, 7.8, 0), terracotta, soil, stem, leaf, height=2.2, seed=31, nleaves=90, kind="long", leaf_len=0.12, leaf_w=0.03, pot_r=0.3, pot_h=0.55)
    # ---- surroundings: neighbouring roofs, water, far skyline -----------------------------------
    haze = (1.0, 0.70, 0.45)
    near = [distant_mat("nb1", (0.30, 0.16, 0.11), haze, 0.55, falloff=150, windows=(1.6, 3.4)),
            distant_mat("nb2", (0.30, 0.27, 0.24), haze, 0.55, falloff=150, windows=(1.8, 3.3))]
    nbm = MB()
    nbm.box((-70, 14, -25), (-22, 48, -3), mi=0)
    nbm.box((-150, 30, -25), (-80, 90, 6), mi=1)
    nbm.box((20, 30, -25), (60, 70, -6), mi=0)
    nbm.box((70, 10, -25), (120, 60, 12), mi=1)
    nbm.obj("neighbours", near)
    wt = MB()
    water_tower(wt, -40, 30, -3)
    wt.obj("watertower", [mat_wood("tank", base=(0.20, 0.13, 0.08), rough=0.8, axis="Z", coords="Generated"), steel])
    plane("harbour", -6000, 6000, 40, 6000, -22, mat_water("water", deep=(0.03, 0.04, 0.05), scale=3.0, rough=0.04))
    far = [distant_mat("f1", (0.3, 0.3, 0.32), haze, 0.6, falloff=1600, windows=(4, 4, 0.12, 3.0)),
           distant_mat("f2", (0.4, 0.33, 0.28), haze, 0.6, falloff=1600, windows=(3, 3.5, 0.1, 3.0)),
           distant_mat("f3", (0.22, 0.24, 0.27), haze, 0.6, falloff=1600, windows=(3.5, 4, 0.15, 3.0))]
    city_blocks(rnd, (-2500, 2500, 1300, 2600), 140, far, ground_z=-22, hmin=15, hmax=140, wmin=25, wmax=70)
    plane("farshore", -6000, 6000, 1250, 9000, -21.9, distant_mat("fs", (0.2, 0.2, 0.2), haze, 0.6, falloff=1600))
    # ---- light -------------------------------------------------------------------------
    add_sun(sun_el, sun_az, strength=20.0, angle=0.7, color=(1.0, 0.54, 0.27))
    sky_world(sun_el, sun_az, strength=0.14, dust=2.6, clouds=1.0, cloud_cover=0.45, cloud_col=(1.0, 0.72, 0.55), cloud_scale=1.5,
              tint=(1.0, 0.94, 0.88))
    add_camera((4.6, -3.2, 1.55), (-1.5, 9.0), lens=24, shift_y=0.06)
    setup_render(exposure=0.0, look="AgX - Punchy", samples=0.8, bounces=(3, 3, 4))



def mat_corrugated(name, base=(0.32, 0.36, 0.38), pitch=0.076, rust=0.4, axis="Z", rough=0.45, metal=0.6):
    """Painted corrugated sheet: sine profile as bump, chalky paint, rust runs."""
    m, T = new_material(name)
    pos = T.geo("Position")
    uv = planar_uv(T, pos)
    u, v, _ = T.sep(uv)
    coord = u if axis == "Z" else v
    prof = T.math("SINE", T.mul(coord, 2 * math.pi / pitch))
    big = T.noise(pos, 0.6, 4, 0.6)
    col = T.mix(T.maprange(big, 0.3, 0.7), [c * 0.75 for c in base], [min(1, c * 1.15) for c in base])
    runs = T.noise(T.vmath("MULTIPLY", pos, (3.0, 3.0, 0.25)), 2.5, 4, 0.6)
    r = T.mul(T.maprange(T.add(T.mul(runs, 0.6), T.mul(big, 0.4)), 0.55, 0.75), rust)
    col = T.mix(r, col, T.mix(T.noise(pos, 20.0, 3), (0.18, 0.07, 0.03), (0.35, 0.15, 0.06)))
    rr = T.mixf(r, rough, 0.85)
    mt = T.mixf(r, metal, 0.0)
    nrm = T.bump(T.add(prof, T.mul(T.noise(pos, 30.0, 2), 0.1)), 0.6, 0.006)
    return finish(m, T, T.principled(base=col, rough=rr, metal=mt, normal=nrm))


def truss(mb, x, y0, y1, z0, rise, depth=1.0, n=10, r=0.05, mi=0):
    """Pitched steel roof truss in the YZ plane at x (tube members)."""
    ym = (y0 + y1) / 2
    def top(y):
        return z0 + depth + rise * (1 - abs(y - ym) / (ym - y0))
    def bot(y):
        return z0
    mb.cyl((x, y0, z0 + depth), (x, ym, top(ym)), r * 1.4, segs=10, mi=mi)
    mb.cyl((x, ym, top(ym)), (x, y1, z0 + depth), r * 1.4, segs=10, mi=mi)
    mb.cyl((x, y0, z0), (x, y1, z0), r * 1.2, segs=10, mi=mi)
    for i in range(n + 1):
        y = y0 + (y1 - y0) * i / n
        mb.cyl((x, y, bot(y)), (x, y, top(y)), r * 0.7, segs=8, mi=mi)
        if i < n:
            y2 = y0 + (y1 - y0) * (i + 1) / n
            if y < ym:
                mb.cyl((x, y, top(y)), (x, y2, bot(y2)), r * 0.6, segs=8, mi=mi)
            else:
                mb.cyl((x, y, bot(y)), (x, y2, top(y2)), r * 0.6, segs=8, mi=mi)


def prop_pallet(mb, x, y, z, rot=0.0, mi=0):
    M = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, "Z")
    L = Local(mb, M)
    for i in range(7):
        yy = -0.6 + i * 0.19
        L.box((-0.5, yy, 0.124), (0.5, yy + 0.1, 0.144), mi=mi)
    for yy in (-0.6, -0.05, 0.5):
        L.box((-0.5, yy, 0.02), (0.5, yy + 0.1, 0.124), mi=mi)
    for i in range(5):
        xx = -0.5 + i * 0.225
        L.box((xx, -0.6, 0.0), (xx + 0.1, 0.6, 0.02), mi=mi)


def scene_warehouse():
    """Harbour warehouse: dim steel-truss shed, corrugated walls, sun shaft through a roller door."""
    rnd = random.Random(5)
    X1, Y1, Hs, rise = 42.0, 24.0, 8.0, 3.0
    sun_el, sun_az = 28.0, 100.0
    wall = mat_corrugated("cladding", base=(0.30, 0.34, 0.36), pitch=0.2, rust=0.55)
    roofm = mat_corrugated("roof", base=(0.25, 0.26, 0.27), pitch=0.2, rust=0.3, axis="Z")
    floor = mat_concrete("floor", base=(0.36, 0.35, 0.33), rough=(0.45, 0.8), stains=0.9, bump=0.4, pores=0.05)
    steel = mat_paint("truss", (0.10, 0.11, 0.12), rough=0.5, metal=0.4, wear=0.3, under=(0.25, 0.1, 0.05))
    orange = mat_paint("rack_beam", (0.55, 0.16, 0.02), rough=0.4, wear=0.2)
    blue = mat_paint("rack_up", (0.04, 0.10, 0.25), rough=0.4, wear=0.2)
    pallet = mat_wood("pallet", base=(0.42, 0.30, 0.18), rough=0.8, scale=0.5)
    card = mat_paint("cardboard", (0.42, 0.29, 0.16), rough=0.85, coords="Generated")
    door = mat_corrugated("door", base=(0.45, 0.42, 0.35), pitch=0.1, rust=0.4, axis="Y")
    # shell: side walls with a roller-door opening on the sunny side (y = Y1)
    w = MB()
    d0, d1, dz = 24.0, 30.0, 5.2
    wall_with_openings(w, "X", 0, X1, Y1, Y1 + 0.1, 0.0, Hs + 0.05, [(d0, d1, 0.0, dz)])
    w.box((0, -0.1, 0), (X1, 0, Hs + 0.05))
    for x0, x1 in ((-0.1, 0.0), (X1, X1 + 0.1)):
        w.box((x0, 0, 0), (x1, Y1, Hs))
        w.prism([(0, Hs), (Y1, Hs), (Y1 / 2, Hs + rise + 1.0)], x0, x1, axis="X")
    w.obj("walls", wall)
    plane("floor", 0, X1, 0, Y1, 0.0, floor)
    plane("apron", 0, X1, Y1, Y1 + 40, 0.0, mat_concrete("apron", base=(0.45, 0.44, 0.42), stains=0.8))
    # roof sheets with frosted skylight strips in alternate bays
    r = MB()
    ym = Y1 / 2

    def rz(y):
        return Hs + 1.0 + rise * (1 - abs(y - ym) / (ym - 0.3))
    ov = 0.25
    for x0 in range(0, int(X1), 6):
        cuts = [-ov, 4.0, 6.0, ym, Y1 - 6.0, Y1 - 4.0, Y1 + ov]
        for k, (ya, yb) in enumerate(zip(cuts, cuts[1:])):
            mi = 1 if (k in (1, 4) and (x0 // 6) % 2 == 0) else 0
            r.poly([(x0, ya, rz(ya)), (x0 + 6, ya, rz(ya)), (x0 + 6, yb, rz(yb)), (x0, yb, rz(yb))], mi=mi)
    sky_panel = mat_frosted("skylight")
    r.obj("roof", [roofm, sky_panel])
    # trusses + columns + purlins
    t = MB()
    for x in range(3, int(X1), 6):
        truss(t, x, 0.3, Y1 - 0.3, Hs - 0.2, rise, depth=1.0, n=12, r=0.06)
        for y in (0.25, Y1 - 0.25):
            t.box((x - 0.15, y - 0.12, 0), (x + 0.15, y + 0.12, Hs))
    for k in range(9):
        y = 0.3 + (Y1 - 0.6) * k / 8
        ym = Y1 / 2
        z = Hs + 0.8 + rise * (1 - abs(y - ym) / (ym - 0.3))
        t.box((0, y - 0.05, z - 0.18), (X1, y + 0.05, z))
    t.obj("steel", steel, bevel=0.005)
    # roller door, rolled up partially, with its drum
    dr = MB()
    dr.box((d0, Y1 + 0.12, dz - 1.4), (d1, Y1 + 0.16, dz))
    dr.obj("door", door)
    dm = MB()
    dm.cyl((d0 - 0.2, Y1 + 0.35, dz + 0.4), (d1 + 0.2, Y1 + 0.35, dz + 0.4), 0.35, segs=24)
    dm.box((d0 - 0.25, Y1 + 0.08, 0), (d0 - 0.05, Y1 + 0.2, dz))
    dm.box((d1 + 0.05, Y1 + 0.08, 0), (d1 + 0.25, Y1 + 0.2, dz))
    dm.obj("door_frame", steel, smooth=True)
    # pallet racking along the back wall (y = 0)
    rk = MB()
    upr = MB()
    for i in range(7):
        x = 6 + i * 2.8
        for y in (0.6, 1.7):
            upr.box((x - 0.05, y - 0.04, 0), (x + 0.05, y + 0.04, 6.4))
        for z in (0.15, 2.1, 4.1, 6.1):
            if i < 6:
                for y in (0.6, 1.7):
                    rk.box((x, y - 0.05, z), (x + 2.8, y + 0.05, z + 0.14))
    rk.obj("rack_beams", orange, bevel=0.004)
    upr.obj("rack_uprights", blue, bevel=0.004)
    pal = MB()
    boxes = MB()
    for i in range(6):
        x = 6 + i * 2.8
        for z in (0.29, 2.24, 4.24):
            for k in range(2):
                if rnd.random() < 0.8:
                    px = x + 0.75 + k * 1.3
                    prop_pallet(pal, px, 1.15, z, rot=rad(90))
                    h = rnd.uniform(0.6, 1.3)
                    boxes.box((px - 0.55, 0.65, z + 0.145), (px + 0.55, 1.65, z + 0.145 + h))
    # floor stacks
    for (x, y, n) in ((14.0, 9.0, 4), (15.4, 9.2, 2), (33.0, 6.0, 6), (34.5, 7.5, 3), (20.0, 15.5, 1)):
        for k in range(n):
            prop_pallet(pal, x, y, k * 0.145, rot=rnd.uniform(-0.1, 0.1))
    boxes.box((33.0 - 0.55, 6.0 - 0.6, 0.87), (33.0 + 0.55, 6.0 + 0.6, 1.9))
    pal.obj("pallets", pallet)
    boxes.obj("cartons", card, bevel=0.01)
    # high-bay lamps (off)
    hb = MB()
    for x in range(6, int(X1), 6):
        for y in (7.0, 17.0):
            hb.cyl((x, y, Hs + 1.5), (x, y, 6.6), 0.008, segs=6)
            hb.cyl((x, y, 6.0), (x, y, 6.6), 0.42, r2=0.12, segs=24, cap=False)
    hb.obj("highbays", mat_metal("hb", (0.6, 0.6, 0.6), rough=0.35, dirt=0.5), smooth=True)
    # outside: quay + water + cranes far off
    plane("water", -500, 500, Y1 + 40, 2000, -1.5, mat_water("sea", deep=(0.02, 0.04, 0.05), scale=3.0))
    # dust volume inside the shed (makes the sun shaft visible)
    vol_m, VT = new_material("haze")
    vs = VT.shader("ShaderNodeVolumeScatter", Color=(1.0, 0.95, 0.88), Density=0.06, Anisotropy=0.6)
    VT.links.new(vs, VT.output.inputs["Volume"])
    vb = MB()
    vb.box((0.05, 0.05, 0.01), (X1 - 0.05, Y1 + 6.0, Hs + 0.8))
    vb.obj("dust", vol_m)
    add_sun(sun_el, sun_az, strength=14.0, angle=0.5, color=(1.0, 0.82, 0.62))
    sky_world(sun_el, sun_az, strength=0.3, dust=2.5, tint=(1.0, 0.92, 0.82))
    add_area("door_portal", ((d0 + d1) / 2, Y1 + 0.3, (dz - 1.4) / 2), (d1 - d0, dz - 1.4), 1.0, rot=(rad(90), 0, 0), portal=True)
    add_camera((2.5, 5.5, 1.6), (40.0, 13.0), lens=24, shift_y=0.12)
    setup_render(exposure=0.6, samples=0.8, bounces=(3, 2, 2))
    bpy.context.scene.cycles.volume_bounces = 0
    bpy.context.scene.cycles.volume_step_rate = 4.0
    # the dusty air leaves grain the albedo/normal guides cannot see; denoise on colour alone
    bpy.context.scene.cycles.denoising_input_passes = "RGB"


def prop_office_chair(mb_fabric, mb_metal, x, y, rot):
    M = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(rot, 4, "Z")
    Lf, Lm = Local(mb_fabric, M), Local(mb_metal, M)
    for k in range(5):
        a = k * 2 * math.pi / 5
        Lm.cyl((0, 0, 0.1), (math.cos(a) * 0.32, math.sin(a) * 0.32, 0.06), 0.015, segs=6)
        Lm.sphere((math.cos(a) * 0.32, math.sin(a) * 0.32, 0.03), 0.03, segs=8, rings=4)
    Lm.cyl((0, 0, 0.08), (0, 0, 0.45), 0.025, segs=10)
    Lf.box((-0.25, -0.25, 0.43), (0.25, 0.23, 0.5))
    Lf.box((-0.23, 0.22, 0.55), (0.23, 0.27, 1.0), rot=(rad(-8), 0, 0))
    Lm.box((-0.03, 0.2, 0.45), (0.03, 0.26, 0.6))


def scene_office():
    """Glasshouse Offices: bright modern open-plan office with full-height glazing."""
    rnd = random.Random(2)
    X1, Y1, H = 28.0, 16.0, 3.4
    sun_el, sun_az = 42.0, 225.0
    floor = mat_concrete("floor", base=(0.62, 0.61, 0.59), rough=(0.22, 0.32), stains=0.0, polished=True, bump=0.1, scale=3.0, var=0.3, pores=0.03)
    ceil = simple("ceiling", (0.85, 0.85, 0.84), 0.9)
    white = mat_paint("white", (0.82, 0.82, 0.80), rough=0.35, coords="Generated")
    oak = mat_wood("oak", base=(0.55, 0.38, 0.22), rough=0.4, coat=0.2)
    mullion = mat_metal("mullion", (0.25, 0.26, 0.27), rough=0.35)
    glass = mat_glass("glass", tint=(0.88, 0.93, 0.93))
    black = mat_paint("black", (0.015, 0.015, 0.015), rough=0.3)
    chairf = mat_fabric("chair", (0.05, 0.05, 0.055))
    led = mat_emit("led", (1.0, 0.97, 0.93), 6.0)
    leaf = mat_leaf("leaf", base=(0.04, 0.12, 0.03))
    pot = simple("pot", (0.85, 0.85, 0.83), 0.4)
    soil = simple("soil", (0.04, 0.03, 0.02), 1.0)
    plane("floor", 0, X1, 0, Y1, 0.0, floor)
    c = MB()
    c.box((0, 0, H), (X1, Y1, H + 0.1))
    c.obj("ceiling", ceil)
    # solid core wall on the right (y=Y1) and back (x=0) painted white
    w = MB()
    w.box((-0.2, 0, 0), (0, Y1, H))
    w.box((0, Y1, 0), (X1, Y1 + 0.2, H))
    w.obj("walls", mat_plaster("plaster", base=(0.86, 0.86, 0.84), dirt=0.0))
    # full-height glazing along y=0 and x=X1... mullions every 1.5 m
    m, g = MB(), MB()
    for i in range(int(X1 / 1.5) + 1):
        x = i * 1.5
        m.box((x - 0.03, -0.12, 0), (x + 0.03, 0.0, H))
    m.box((0, -0.12, 0), (X1, 0.0, 0.08))
    m.box((0, -0.12, H - 0.1), (X1, 0.0, H))
    g.poly([(0, -0.06, 0), (X1, -0.06, 0), (X1, -0.06, H), (0, -0.06, H)])
    m.obj("mullions", mullion, bevel=0.004)
    g.obj("glazing", glass)
    # glass meeting room in the back left corner
    mr, mg = MB(), MB()
    mx0, mx1, my0, my1 = 0.0, 6.0, 9.5, Y1
    for (a, b) in (((mx1, my0), (mx1, my1)), ((mx0, my0), (mx1, my0))):
        if a[0] == b[0]:
            mg.poly([(a[0], a[1], 0), (b[0], b[1], 0), (b[0], b[1], H), (a[0], a[1], H)])
            for yy in [a[1] + k * 1.6 for k in range(int((b[1] - a[1]) / 1.6) + 1)]:
                mr.box((a[0] - 0.025, yy - 0.025, 0), (a[0] + 0.025, yy + 0.025, H))
        else:
            mg.poly([(a[0], a[1], 0), (b[0], b[1], 0), (b[0], b[1], H), (a[0], a[1], H)])
            for xx in [a[0] + k * 1.5 for k in range(int((b[0] - a[0]) / 1.5) + 1)]:
                mr.box((xx - 0.025, a[1] - 0.025, 0), (xx + 0.025, a[1] + 0.025, H))
    mr.obj("mr_frame", mullion)
    mg.obj("mr_glass", mat_glass("mrglass", tint=(0.9, 0.95, 0.94)))
    prop_table(Matrix.Translation((3.0, 12.8, 0)), oak, black, W=3.2, D=1.2, H=0.74)
    # desks: benching rows
    desks, legs, mons, chf, chm = MB(), MB(), MB(), MB(), MB()
    for row in range(3):
        y = 2.6 + row * 2.4
        for k in range(5):
            x = 8.5 + k * 3.4
            for side in (-1, 1):
                yy = y + side * 0.42
                desks.box((x - 0.8, yy - 0.4, 0.72), (x + 0.8, yy + 0.4, 0.745))
                mons.box((x - 0.3, y + side * 0.06 - 0.01, 0.95), (x + 0.3, y + side * 0.06 + 0.01, 1.3))
                mons.box((x - 0.03, y + side * 0.06 - 0.02, 0.745), (x + 0.03, y + side * 0.06 + 0.02, 0.95))
                if rnd.random() < 0.85:
                    prop_office_chair(chf, chm, x + rnd.uniform(-0.3, 0.3), y + side * 1.05, rad(90 - 90 * side) + rnd.uniform(-0.4, 0.4))
            for xx in (x - 0.78, x + 0.74):
                legs.box((xx, y - 0.8, 0), (xx + 0.04, y + 0.8, 0.72))
    desks.obj("desks", white, bevel=0.004)
    legs.obj("desk_legs", white, bevel=0.003)
    mons.obj("monitors", black, bevel=0.005)
    chf.obj("chairs", chairf, bevel=0.02, segs=2, smooth=True)
    chm.obj("chair_bases", black, smooth=True)
    # linear LED pendants
    lm = MB()
    for row in range(3):
        y = 2.6 + row * 2.4
        lm.box((8, y - 0.03, H - 0.62), (25, y + 0.03, H - 0.6))
    lm.obj("leds", led)
    for (x, y, h) in ((7.0, 1.0, 1.7), (26.8, 1.0, 1.9), (7.2, 8.6, 1.5), (23.5, 15.2, 1.8)):
        prop_plant((x, y, 0), pot, soil, simple("stem", (0.12, 0.09, 0.05), 0.7), leaf, height=h, seed=int(x * 10 + y), nleaves=50, pot_r=0.28, pot_h=0.5)
    # city outside
    haze = (0.85, 0.88, 0.95)
    cm = [distant_mat("o1", (0.55, 0.57, 0.6), haze, 1.4, falloff=500, windows=(3.0, 3.6)),
          distant_mat("o2", (0.35, 0.38, 0.42), haze, 1.4, falloff=500, windows=(2.0, 3.6)),
          distant_mat("o3", (0.7, 0.66, 0.6), haze, 1.4, falloff=500, windows=(3.5, 3.3))]
    city_blocks(rnd, (-300, 340, -500, -60), 70, cm, ground_z=-40, hmin=20, hmax=110, wmin=20, wmax=50)
    plane("street", -2000, 2000, -2000, 2000, -40, distant_mat("st", (0.3, 0.3, 0.3), haze, 1.4, falloff=500))
    add_sun(sun_el, sun_az, strength=4.5, angle=0.6, color=(1.0, 0.95, 0.88))
    sky_world(sun_el, sun_az, strength=0.4, clouds=0.6, cloud_cover=0.35, cloud_col=(1, 1, 1), tint=(1.0, 0.93, 0.86))
    add_area("portal", (X1 / 2, -0.2, H / 2), (X1, H), 1.0, rot=(rad(-90), 0, 0), portal=True)
    add_camera((27.0, 15.0, 1.5), (4.0, 4.5), lens=24, shift_y=0.0)
    setup_render(exposure=0.6, samples=0.8, bounces=(4, 3, 4))


def mat_barn_boards(name="barn_boards", base=(0.27, 0.05, 0.035), weather=0.5):
    m, T = new_material(name)
    pos = T.geo("Position")
    uv = planar_uv(T, pos)
    u, v, _ = T.sep(uv)
    bw = 0.25
    bid = T.math("FLOOR", T.math("DIVIDE", u, bw))
    fu = T.math("FRACT", T.math("DIVIDE", u, bw))
    seam = T.maprange(T.math("MINIMUM", fu, T.math("SUBTRACT", 1.0, fu)), 0.03, 0.0)
    rnd = T.white(T.comb(bid, 0.0, 0.0))
    grain = T.noise(T.comb(T.mul(u, 40.0), T.mul(v, 1.2), T.mul(rnd, 20.0)), 3.0, 4, 0.6)
    paint = T.mix(rnd, [c * 0.8 for c in base], [min(1, c * 1.2) for c in base])
    bare = T.mix(grain, (0.18, 0.15, 0.12), (0.35, 0.31, 0.26))
    peel_n = T.noise(T.vmath("MULTIPLY", pos, (2.5, 2.5, 0.6)), 2.0, 4, 0.7)
    peel = T.maprange(T.add(T.mul(peel_n, 0.6), T.mul(grain, 0.4)), 0.62 - weather * 0.08, 0.66 - weather * 0.08)
    col = T.mix(peel, paint, bare)
    col = T.mix(T.mul(grain, 0.3), col, [c * 0.6 for c in base])
    col = T.mix(seam, col, (0.02, 0.015, 0.01))
    nrm = T.bump(T.add(T.mul(seam, -1.0), T.mul(grain, 0.3)), 0.5, 0.004)
    return finish(m, T, T.principled(base=col, rough=T.mixf(peel, 0.7, 0.9), normal=nrm))


def mat_metal_roof(name="tin_roof", base=(0.45, 0.45, 0.44), rust=0.6):
    return mat_corrugated(name, base=base, pitch=0.2, rust=rust, axis="Z", rough=0.4, metal=0.8)


def terrain(name, mat, size=600, res=160, height=6.0, ridge=True, seed=0, offset=(0, 0)):
    """Rolling terrain: a grid displaced in Python with layered sines/noise, highest near y=0."""
    from mathutils import noise as mnoise
    mb = MB()
    ox, oy = offset

    def h(x, y):
        z = mnoise.noise(V((x * 0.012 + seed, y * 0.012, 0))) * height * 0.6
        z += mnoise.noise(V((x * 0.05, y * 0.05 + seed, 1))) * height * 0.12
        if ridge:
            z += height * math.exp(-((y - 10.0) / 45.0) ** 2) - height * 0.5 * max(0, (y - 60) / 200)
        return z

    def fn(u, v):
        x = ox + (u - 0.5) * size
        y = oy + (v - 0.5) * size
        return (x, y, h(x, y))
    mb.grid(fn, res, res)
    ob = mb.obj(name, mat, smooth=True, recalc=False)
    return ob, h


def scene_barn():
    """Ridgeline Barn: weathered red barn on a grassy ridge under a big sky."""
    sun_el, sun_az = 24.0, 200.0
    boards = mat_barn_boards()
    trim = mat_paint("trim", (0.75, 0.73, 0.68), rough=0.5, wear=0.4, under=(0.25, 0.2, 0.15), coords="Generated")
    roof = mat_metal_roof()
    grass_m = mat_grass_ground("meadow", base=(0.08, 0.13, 0.035), dry=(0.36, 0.30, 0.13), dryness=0.6, scale=1.5)
    ground, h = terrain("ridge", grass_m, size=900, res=180, height=7.0, seed=3)
    bx, by, bw, bd, wh = 0.0, 12.0, 10.0, 16.0, 5.0
    bz = h(bx, by) - 0.3
    b = MB()
    b.box((bx - bw / 2, by - bd / 2, bz - 1.0), (bx + bw / 2, by + bd / 2, bz + wh))
    # gambrel gable ends
    prof = [(by - bd / 2, bz + wh), (by + bd / 2, bz + wh), (by + bd / 2 - 1.8, bz + wh + 2.6), (by, bz + wh + 3.6), (by - bd / 2 + 1.8, bz + wh + 2.6)]
    for x0, x1 in ((bx - bw / 2, bx - bw / 2 + 0.01), (bx + bw / 2 - 0.01, bx + bw / 2)):
        b.prism(prof, x0, x1, axis="X")
    b.obj("barn", boards)
    rf = MB()
    ov = 0.4
    pts = [(by - bd / 2 - ov, bz + wh - 0.25), (by - bd / 2 + 1.8, bz + wh + 2.6), (by, bz + wh + 3.6), (by + bd / 2 - 1.8, bz + wh + 2.6), (by + bd / 2 + ov, bz + wh - 0.25)]
    for (y0, z0), (y1, z1) in zip(pts, pts[1:]):
        rf.poly([(bx - bw / 2 - ov, y0, z0), (bx + bw / 2 + ov, y0, z0), (bx + bw / 2 + ov, y1, z1), (bx - bw / 2 - ov, y1, z1)])
    ro = rf.obj("roof", roof)
    sol = ro.modifiers.new("t", "SOLIDIFY")
    sol.thickness = 0.06
    # big doors + trim on the visible gable (x = bx - bw/2) and a hay loft door
    t = MB()
    gx = bx - bw / 2 - 0.05
    t.box((gx - 0.04, by - 2.2, bz), (gx, by + 2.2, bz + 3.6))
    for (ya, yb) in ((by - 2.2, by), (by, by + 2.2)):
        t.box((gx - 0.08, ya, bz + 3.45), (gx - 0.04, yb, bz + 3.6))
        t.box((gx - 0.08, ya, bz), (gx - 0.04, yb, bz + 0.15))
        t.box((gx - 0.08, ya, bz), (gx - 0.04, ya + 0.15, bz + 3.6))
        t.box((gx - 0.08, yb - 0.15, bz), (gx - 0.04, yb, bz + 3.6))
    t.box((gx - 0.04, by - 0.8, bz + wh + 0.4), (gx, by + 0.8, bz + wh + 2.0))
    t.box((gx - 0.05, by - bd / 2, bz + wh - 0.1), (gx + 0.0, by + bd / 2, bz + wh + 0.05))
    t.obj("trim", trim, bevel=0.01)
    xb = MB()
    for (ya, yb) in ((by - 2.2, by), (by, by + 2.2)):
        xb.cyl((gx - 0.07, ya + 0.1, bz + 0.1), (gx - 0.07, yb - 0.1, bz + 3.5), 0.05, segs=4)
        xb.cyl((gx - 0.07, yb - 0.1, bz + 0.1), (gx - 0.07, ya + 0.1, bz + 3.5), 0.05, segs=4)
    xb.obj("braces", trim)
    # fence line + a lone tree
    f = MB()
    fw = mat_wood("fence", base=(0.25, 0.22, 0.18), rough=0.9, axis="Z")
    for i in range(14):
        x = -26 + i * 3.0
        y = -6 + i * 0.6
        z = h(x, y)
        f.box((x - 0.06, y - 0.06, z - 0.3), (x + 0.06, y + 0.06, z + 1.2))
        if i < 13:
            x2, y2 = x + 3.0, y + 0.6
            z2 = h(x2, y2)
            for dz in (0.5, 1.0):
                f.cyl((x, y, z + dz), (x2, y2, z2 + dz), 0.035, segs=6)
    f.obj("fence", fw)
    leafm = mat_leaf("tree_leaf", base=(0.04, 0.09, 0.02), var=0.4)
    prop_tree((-9.0, 34.0, h(-9.0, 34.0) - 0.2), height=11.0, crown_r=4.5, leaf_mat=leafm, bark_mat=mat_bark(), seed=21, leaves=50000, leaf_size=1.7)
    # foreground grass (hair) around the camera
    cam = V((-25.0, -14.0, 0))
    gr = MB()
    gr.grid(lambda u, v: (cam.x - 10 + u * 34, cam.y - 2 + v * 30, h(cam.x - 10 + u * 34, cam.y - 2 + v * 30) + 0.01), 50, 50)
    gobj = gr.obj("grass_emitter", grass_m, smooth=True, recalc=False)
    grass_hair(gobj, 260000, length=0.3, color=(0.07, 0.12, 0.03), dry=(0.45, 0.38, 0.18), seed=4, radius=0.003)
    add_sun(sun_el, sun_az, strength=6.0, angle=0.6, color=(1.0, 0.86, 0.68))
    sky_world(sun_el, sun_az, strength=0.25, clouds=1.0, cloud_cover=0.55, cloud_col=(1.0, 0.95, 0.9), cloud_scale=2.0, cloud_seed=3.0)
    add_camera((cam.x, cam.y, h(cam.x, cam.y) + 1.5), (2.0, 12.0), lens=30, shift_y=0.1)
    setup_render(exposure=0.3, look="AgX - Punchy", samples=0.7, bounces=(3, 2, 2))



# ----------------------------------------------------------------------------
# catalogue thumbnails (seen ~76x50 px): simpler builds, same rendering pipeline
# ----------------------------------------------------------------------------
def room_shell(X1, Y1, H, wall_mat, floor_mat, ceil_mat, window_wall=None, openings=(), T_=0.3):
    """Box room x:[0,X1] y:[0,Y1]; window_wall in {'y0','x0'} gets the openings."""
    w = MB()
    if window_wall == "y0":
        wall_with_openings(w, "X", -T_, X1 + T_, -T_, 0.0, 0.0, H, list(openings))
    else:
        w.box((-T_, -T_, 0), (X1 + T_, 0, H))
    if window_wall == "x0":
        wall_with_openings(w, "Y", 0, Y1, -T_, 0.0, 0.0, H, list(openings))
    else:
        w.box((-T_, 0, 0), (0, Y1, H))
    w.box((-T_, Y1, 0), (X1 + T_, Y1 + T_, H))
    w.box((X1, 0, 0), (X1 + T_, Y1, H))
    w.obj("walls", wall_mat)
    plane("floor", -0.01, X1 + 0.01, -0.01, Y1 + 0.01, 0.0, floor_mat)
    c = MB()
    c.box((-T_, -T_, H), (X1 + T_, Y1 + T_, H + 0.2))
    c.obj("ceiling", ceil_mat)


def scene_cafe():
    rnd = random.Random(8)
    X1, Y1, H = 10.0, 7.0, 3.6
    brick = mat_brick("brick", c_dark=(0.20, 0.08, 0.05), c_light=(0.40, 0.18, 0.10), soot=0.2)
    floor = mat_wood_floor("floor", plank_w=0.12, plank_l=1.2, c_dark=(0.10, 0.05, 0.025), c_light=(0.26, 0.14, 0.07), rough=(0.3, 0.5))
    ceil = mat_plaster("ceiling", base=(0.30, 0.27, 0.24))
    ops = [(1.0, 4.0, 0.5, 3.1), (5.0, 8.6, 0.5, 3.1)]
    room_shell(X1, Y1, H, brick, floor, ceil, "y0", ops)
    fr, gl = MB(), MB()
    steel = mat_paint("frame", (0.02, 0.03, 0.025), rough=0.4)
    for a, b, z0, z1 in ops:
        steel_window(fr, gl, "X", a, b, z0, z1, -0.2, 3, 2, fw=0.06)
    fr.obj("frames", steel)
    gl.obj("glass", mat_glass("glass"))
    # counter along the right wall
    oak = mat_wood("oak", base=(0.30, 0.16, 0.07), coat=0.3)
    marble = mat_concrete("marble", base=(0.78, 0.77, 0.74), rough=(0.15, 0.3), stains=0.1, polished=True, bump=0.1, pores=0.15)
    ct = MB()
    ct.box((2.5, Y1 - 1.6, 0), (8.5, Y1 - 0.9, 1.0))
    ct.obj("counter", oak, bevel=0.01)
    top = MB()
    top.box((2.45, Y1 - 1.65, 1.0), (8.55, Y1 - 0.85, 1.05))
    top.obj("countertop", marble, bevel=0.005)
    chrome = mat_metal("chrome", (0.8, 0.8, 0.8), rough=0.12)
    em = MB()
    em.box((4.0, Y1 - 1.45, 1.05), (4.8, Y1 - 0.95, 1.5))
    em.cyl((4.2, Y1 - 1.5, 1.2), (4.2, Y1 - 1.6, 1.2), 0.04, segs=12)
    em.cyl((4.6, Y1 - 1.5, 1.2), (4.6, Y1 - 1.6, 1.2), 0.04, segs=12)
    em.obj("espresso", chrome, bevel=0.02, segs=3, smooth=True)
    # back shelves with jars/cups
    sh = MB()
    jars = MB()
    for z in (1.5, 1.95, 2.4):
        sh.box((2.5, Y1 - 0.3, z), (8.5, Y1 - 0.02, z + 0.04))
        for i in range(18):
            x = 2.7 + i * 0.32 + rnd.uniform(-0.05, 0.05)
            hgt = rnd.uniform(0.12, 0.3)
            jars.cyl((x, Y1 - 0.16, z + 0.04), (x, Y1 - 0.16, z + 0.04 + hgt), rnd.uniform(0.04, 0.07), segs=14, mi=rnd.randrange(3))
    sh.obj("shelves", oak, bevel=0.004)
    jars.obj("jars", [simple("cup", (0.85, 0.84, 0.8), 0.25), mat_glass_solid("jar"), simple("tin", (0.08, 0.15, 0.12), 0.35, metal=0.6)], smooth=True)
    # tables + chairs
    black = mat_paint("black", (0.02, 0.02, 0.02), rough=0.4)
    for (x, y) in ((2.0, 1.6), (4.6, 1.5), (7.2, 1.6), (6.2, 3.4), (3.0, 3.6)):
        prop_bistro((x, y), black, seed=int(x * 7))
    # pendants (on)
    sh_, cd, bl = MB(), MB(), MB()
    for x in (3.0, 4.6, 6.2, 7.8):
        prop_pendant(sh_, cd, bl, x, Y1 - 1.25, H, 1.25, r=0.16)
        add_point("pendant", (x, Y1 - 1.25, H - 1.25 + 0.04), 30, color=(1.0, 0.6, 0.3), radius=0.04)
    sh_.obj("shades", mat_metal("brass", (0.8, 0.55, 0.3), rough=0.25), smooth=True)
    cd.obj("cords", black)
    bl.obj("bulbs", mat_bulb("bulb", strength=25.0), smooth=True)
    prop_plant((9.3, 0.6, 0), mat_terracotta(), simple("soil", (0.04, 0.03, 0.02), 1.0), simple("stem", (0.12, 0.09, 0.05), 0.7),
               mat_leaf("leaf"), height=1.7, seed=3, nleaves=50)
    add_sun(30, 250, strength=6.0, color=(1.0, 0.85, 0.65))
    sky_world(30, 250, strength=0.35, ground=(0.25, 0.24, 0.22))
    plane("street", -100, 100, -100, -0.3, -0.02, mat_concrete("pavement", base=(0.4, 0.39, 0.37)))
    add_camera((9.3, 1.0, 1.5), (1.5, 5.5), lens=24, shift_y=0.05)
    setup_render(exposure=1.6, samples=0.5, bounces=(3, 2, 3))


def scene_house():
    X1, Y1, H = 9.0, 7.0, 3.0
    plaster = mat_plaster("plaster", base=(0.84, 0.83, 0.80), dirt=0.0)
    oak = mat_wood_floor("floor", plank_w=0.22, plank_l=2.2, c_dark=(0.33, 0.22, 0.13), c_light=(0.52, 0.38, 0.24), rough=(0.3, 0.45), worn=0.0)
    room_shell(X1, Y1, H, plaster, oak, simple("ceil", (0.85, 0.85, 0.84), 0.9), "y0", [(0.4, 8.6, 0.0, 2.85)])
    m, g = MB(), MB()
    alu = mat_metal("alu", (0.15, 0.15, 0.16), rough=0.3)
    for x in (0.4, 2.5, 4.5, 6.5, 8.6):
        m.box((x - 0.03, -0.25, 0), (x + 0.03, -0.15, 2.85))
    g.poly([(0.4, -0.2, 0), (8.6, -0.2, 0), (8.6, -0.2, 2.85), (0.4, -0.2, 2.85)])
    m.obj("frames", alu)
    g.obj("glass", mat_glass("glass"))
    # garden outside
    grass = mat_grass_ground("lawn", base=(0.06, 0.13, 0.03), dryness=0.2)
    plane("lawn", -60, 60, -60, -0.3, -0.05, grass)
    leafm = mat_leaf("tree_leaf", base=(0.04, 0.10, 0.025))
    bark = mat_bark()
    prop_tree((-2.0, -14.0, 0), height=8, crown_r=3.0, leaf_mat=leafm, bark_mat=bark, seed=3, leaves=30000, leaf_size=1.4)
    prop_tree((9.0, -18.0, 0), height=10, crown_r=3.8, leaf_mat=leafm, bark_mat=bark, seed=5, leaves=35000, leaf_size=1.5)
    hedge = MB()
    hedge.box((-30, -9.0, 0), (40, -8.0, 1.6))
    hedge.obj("hedge", mat_grass_ground("hedge_m", base=(0.03, 0.08, 0.02), dryness=0.0, scale=0.2))
    # furniture
    fabric = mat_fabric("sofa", (0.42, 0.41, 0.38))
    prop_sofa(Matrix.Translation((4.2, 5.6, 0)), fabric, mat_wood("dark", base=(0.06, 0.04, 0.03)))
    rug = mat_rug("rug", c1=(0.65, 0.62, 0.56), c2=(0.45, 0.42, 0.38), c3=(0.75, 0.72, 0.66), size=(3.0, 2.0))
    r = MB()
    r.box((-1.5, -1.0, 0), (1.5, 1.0, 0.01))
    r.obj("rug", rug, loc=(4.2, 4.2, 0))
    prop_table(Matrix.Translation((4.2, 4.2, 0.01)), mat_wood("walnut", base=(0.18, 0.09, 0.05), coat=0.4), mat_paint("blk", (0.02, 0.02, 0.02)), W=1.1, D=0.6, H=0.38)
    prop_sofa(Matrix.Translation((1.5, 3.6, 0)) @ Matrix.Rotation(rad(-80), 4, "Z") @ Matrix.Diagonal((0.42, 1, 1, 1)), mat_fabric("chair", (0.55, 0.4, 0.26)), mat_wood("dark2", base=(0.06, 0.04, 0.03)))
    prop_plant((0.7, 6.3, 0), simple("pot", (0.1, 0.1, 0.1), 0.5), simple("soil", (0.04, 0.03, 0.02), 1.0), simple("stem", (0.12, 0.09, 0.05), 0.7),
               mat_leaf("leaf"), height=1.9, seed=8, nleaves=60)
    art = MB()
    art.box((3.0, Y1 - 0.04, 1.3), (5.4, Y1 - 0.01, 2.4))
    art.obj("art", mat_fabric("canvas_art", (0.55, 0.45, 0.35)), bevel=0.005)
    add_sun(35, 235, strength=5.0, color=(1.0, 0.92, 0.8))
    sky_world(35, 235, strength=0.35, clouds=0.6)
    add_area("portal", (4.5, -0.35, 1.425), (8.2, 2.85), 1.0, rot=(rad(-90), 0, 0), portal=True)
    add_camera((8.6, 5.2, 1.4), (1.0, 1.6), lens=24, shift_y=0.0)
    setup_render(exposure=1.5, samples=0.5, bounces=(4, 2, 3))


def scene_chapel():
    X1, Y1, H = 20.0, 9.0, 6.0
    white = mat_plaster("whitewash", base=(0.86, 0.85, 0.82), dirt=0.15)
    stone = mat_concrete("flags", base=(0.55, 0.52, 0.47), rough=(0.5, 0.75), stains=0.4)
    w = MB()
    w.box((0, -0.6, 0), (X1, 0, H))
    w.box((0, Y1, 0), (X1, Y1 + 0.6, H))
    w.box((-0.6, -0.6, 0), (0, Y1 + 0.6, H + 3))
    w.box((X1, -0.6, 0), (X1 + 0.6, Y1 + 0.6, H + 3))
    w.prism([(-0.6, H), (Y1 + 0.6, H), (Y1 / 2, H + 3.2)], -0.6, 0.0, axis="X")
    w.prism([(-0.6, H), (Y1 + 0.6, H), (Y1 / 2, H + 3.2)], X1, X1 + 0.6, axis="X")
    wo = w.obj("walls", white)
    cut, gl = MB(), MB()
    for x in (3.0, 7.0, 11.0, 15.0):
        for (y0, y1) in ((-1.0, 0.1), (Y1 - 0.1, Y1 + 1.0)):
            pts, arch = arch_outline(x - 0.75, x + 0.75, 1.6, 5.0, 0.75)
            cut.prism(pts, y0, y1, axis="Y")
            yy = -0.4 if y0 < 0 else Y1 + 0.4
            gl.prism(pts, yy, yy + 0.001, axis="Y")
    # end window
    pts, _ = arch_outline(Y1 / 2 - 1.2, Y1 / 2 + 1.2, 2.0, 7.0, 1.2)
    cut.prism(pts, X1 - 0.2, X1 + 1.0, axis="X")
    gl.prism(pts, X1 + 0.35, X1 + 0.351, axis="X")
    co = cut.obj("cutters", white)
    co.hide_render = True
    md = wo.modifiers.new("holes", "BOOLEAN")
    md.object = co
    md.solver = "MANIFOLD"
    gl.obj("glass", mat_glass("glass", tint=(0.95, 0.96, 0.93), dirt=0.2))
    plane("floor", 0, X1, 0, Y1, 0, stone)
    # scissor trusses + roof boards
    timber = mat_timber_beam("timber", base=(0.25, 0.15, 0.08))
    t = MB()
    for x in range(1, int(X1), 3):
        t.cyl((x, 0.2, H - 0.2), (x, Y1 / 2, H + 3.0), 0.11, segs=4)
        t.cyl((x, Y1 - 0.2, H - 0.2), (x, Y1 / 2, H + 3.0), 0.11, segs=4)
        t.cyl((x, 0.2, H - 0.1), (x, Y1 * 0.7, H + 1.8), 0.08, segs=4)
        t.cyl((x, Y1 - 0.2, H - 0.1), (x, Y1 * 0.3, H + 1.8), 0.08, segs=4)
    t.obj("trusses", timber)
    rb = MB()
    rb.poly([(0, -0.6, H), (X1, -0.6, H), (X1, Y1 / 2, H + 3.2), (0, Y1 / 2, H + 3.2)])
    rb.poly([(0, Y1 / 2, H + 3.2), (X1, Y1 / 2, H + 3.2), (X1, Y1 + 0.6, H), (0, Y1 + 0.6, H)])
    rbo = rb.obj("roof_boards", mat_wood_floor("boards", plank_w=0.15, plank_l=6.0, c_dark=(0.30, 0.20, 0.12), c_light=(0.45, 0.32, 0.2), worn=0.0, axis="X"))
    sol = rbo.modifiers.new("t", "SOLIDIFY")
    sol.thickness = 0.1
    # pews
    oak = mat_wood("pew", base=(0.35, 0.21, 0.10), coat=0.3)
    pw = MB()
    for i in range(8):
        x = 3.0 + i * 1.6
        for (y0, y1) in ((0.8, 3.9), (5.1, 8.2)):
            pw.box((x, y0, 0.42), (x + 0.42, y1, 0.47))
            pw.box((x + 0.42, y0, 0.45), (x + 0.47, y1, 0.95))
            for yy in (y0, y1 - 0.05):
                pw.box((x, yy, 0), (x + 0.47, yy + 0.05, 0.9))
    pw.obj("pews", oak, bevel=0.008)
    add_sun(32, 120, strength=6.0, color=(1.0, 0.93, 0.82))
    sky_world(32, 120, strength=0.4, ground=(0.3, 0.32, 0.25))
    add_camera((0.8, Y1 / 2 - 0.6, 1.6), (X1, Y1 / 2), lens=24, shift_y=0.15)
    setup_render(exposure=0.9, samples=0.5, bounces=(4, 2, 3))


def scene_greenhouse():
    rnd = random.Random(12)
    X1, Y1, He, Hr = 16.0, 8.0, 2.6, 4.6
    white = mat_paint("frame", (0.82, 0.82, 0.8), rough=0.35, wear=0.2, under=(0.4, 0.3, 0.2))
    glass = mat_glass("glass", tint=(0.94, 0.97, 0.95), dirt=0.1, refl=0.3)
    gravel = mat_cobbles("gravel", base=(0.45, 0.42, 0.38), scale=0.015)
    plane("floor", -50, 50, -50, 50, 0, gravel)
    fr, gl = MB(), MB()
    for i in range(int(X1 / 1.0) + 1):
        x = i * 1.0
        for y in (0, Y1):
            fr.box((x - 0.025, y - 0.025, 0), (x + 0.025, y + 0.025, He))
        fr.cyl((x, 0, He), (x, Y1 / 2, Hr), 0.03, segs=4)
        fr.cyl((x, Y1, He), (x, Y1 / 2, Hr), 0.03, segs=4)
    for z in (0.6, He):
        for y in (0, Y1):
            fr.box((0, y - 0.03, z - 0.03), (X1, y + 0.03, z + 0.03))
    fr.box((0, Y1 / 2 - 0.04, Hr - 0.04), (X1, Y1 / 2 + 0.04, Hr + 0.04))
    for i in range(int(Y1 / 1.0) + 1):
        y = i * 1.0
        for x in (0, X1):
            fr.box((x - 0.025, y - 0.025, 0), (x + 0.025, y + 0.025, He + (Hr - He) * (1 - abs(y - Y1 / 2) / (Y1 / 2))))
    fr.obj("frame", white)
    for y in (0, Y1):
        gl.poly([(0, y, 0.6), (X1, y, 0.6), (X1, y, He), (0, y, He)])
    gl.poly([(0, 0, He), (X1, 0, He), (X1, Y1 / 2, Hr), (0, Y1 / 2, Hr)])
    gl.poly([(0, Y1 / 2, Hr), (X1, Y1 / 2, Hr), (X1, Y1, He), (0, Y1, He)])
    for x in (0, X1):
        gl.poly([(x, 0, 0.6), (x, Y1, 0.6), (x, Y1, He), (x, Y1 / 2, Hr), (x, 0, He)])
    gl.obj("glass", glass)
    low = MB()
    low.box((0, -0.1, 0), (X1, 0.1, 0.6))
    low.box((0, Y1 - 0.1, 0), (X1, Y1 + 0.1, 0.6))
    low.obj("dwarf_wall", mat_brick("brick"))
    # benches with pots
    wood = mat_wood("bench", base=(0.35, 0.25, 0.16), rough=0.8)
    bench = MB()
    for (y0, y1) in ((0.4, 1.6), (6.4, 7.6), (3.4, 4.6)):
        bench.box((1.0, y0, 0.8), (15.0, y1, 0.85))
        for x in range(1, 16, 2):
            for y in (y0 + 0.05, y1 - 0.1):
                bench.box((x, y, 0), (x + 0.05, y + 0.05, 0.8))
    bench.obj("benches", wood, bevel=0.003)
    leaf = mat_leaf("leaf", base=(0.05, 0.14, 0.03), var=0.6)
    leaf2 = mat_leaf("leaf2", base=(0.08, 0.16, 0.03), var=0.5)
    soil = simple("soil", (0.04, 0.03, 0.02), 1.0)
    stem = simple("stem", (0.1, 0.12, 0.05), 0.7)
    tc = mat_terracotta()
    k = 0
    for (y0, y1) in ((0.4, 1.6), (6.4, 7.6), (3.4, 4.6)):
        for x in [1.4 + 0.75 * i for i in range(18)]:
            y = rnd.uniform(y0 + 0.3, y1 - 0.3)
            prop_plant((x, y, 0.85), tc, soil, stem, leaf if k % 2 else leaf2, height=rnd.uniform(0.35, 0.8), seed=k, nleaves=14,
                       pot_r=0.11, pot_h=0.16, kind="fig" if k % 3 else "long", leaf_len=0.14, leaf_w=0.08)
            k += 1
    prop_plant((15.2, 2.5, 0), tc, soil, stem, leaf, height=2.6, seed=99, nleaves=80, pot_r=0.35, pot_h=0.5)
    leafm = mat_leaf("tree_leaf", base=(0.04, 0.10, 0.025))
    prop_tree((-8, 16, 0), height=11, crown_r=4.5, leaf_mat=leafm, bark_mat=mat_bark(), seed=2, leaves=40000, leaf_size=1.6)
    add_sun(48, 200, strength=5.5, color=(1.0, 0.95, 0.88))
    sky_world(48, 200, strength=0.45, clouds=0.7, ground=(0.15, 0.2, 0.1))
    add_camera((0.6, 2.6, 1.6), (16.0, 5.0), lens=24, shift_y=0.1)
    setup_render(exposure=0.4, samples=0.5, bounces=(3, 2, 4))


def scene_pool():
    stone = mat_concrete("limestone", base=(0.55, 0.51, 0.45), rough=(0.6, 0.8), stains=0.4, scale=0.5)
    tile = mat_paint("pool_tile", (0.20, 0.50, 0.55), rough=0.2, coords="Generated")
    px0, px1, py0, py1 = -2.0, 10.0, 4.0, 9.0
    ter = MB()
    ter.poly([(-40, -40, 0), (40, -40, 0), (40, py0, 0), (-40, py0, 0)])
    ter.poly([(-40, py1, 0), (40, py1, 0), (40, 40, 0), (-40, 40, 0)])
    ter.poly([(-40, py0, 0), (px0, py0, 0), (px0, py1, 0), (-40, py1, 0)])
    ter.poly([(px1, py0, 0), (40, py0, 0), (40, py1, 0), (px1, py1, 0)])
    ter.obj("terrace", stone)
    pool = MB()
    pool.box((px0, py0, -1.5), (px1, py1, -1.45))
    pool.box((px0 - 0.05, py0, -1.5), (px0, py1, 0.0))
    pool.box((px1, py0, -1.5), (px1 + 0.05, py1, 0.0))
    pool.box((px0, py0 - 0.05, -1.5), (px1, py0, 0.0))
    pool.box((px0, py1, -1.5), (px1, py1 + 0.05, 0.0))
    pool.obj("pool_shell", tile)
    # cut the terrace: simple coping slabs around the pool instead of a hole
    t = MB()
    t.box((px0 - 0.4, py0 - 0.4, 0.0), (px1 + 0.4, py0, 0.06))
    t.box((px0 - 0.4, py1, 0.0), (px1 + 0.4, py1 + 0.4, 0.06))
    t.box((px0 - 0.4, py0, 0.0), (px0, py1, 0.06))
    t.box((px1, py0, 0.0), (px1 + 0.4, py1, 0.06))
    t.obj("coping", stone, bevel=0.01)
    plane("water", px0, px1, py0, py1, -0.12, mat_water("water", scale=0.8, rough=0.0, pool=True))
    # house wall behind, white render with big glazing
    house = MB()
    house.box((-8, 13, 0), (16, 20, 3.4))
    house.box((-8, 13, 3.4), (16, 20.5, 3.7))
    house.obj("house", mat_plaster("render", base=(0.88, 0.87, 0.84), dirt=0.2))
    g = MB()
    g.poly([(-2, 12.98, 0.1), (8, 12.98, 0.1), (8, 12.98, 3.2), (-2, 12.98, 3.2)])
    g.obj("house_glass", mat_glass("hg", tint=(0.6, 0.65, 0.66)))
    # loungers + umbrella
    teak = mat_wood("teak", base=(0.32, 0.19, 0.10), rough=0.5)
    cush = mat_fabric("cushion", (0.85, 0.84, 0.8))
    for i, x in enumerate((0.0, 2.2, 4.4)):
        M = Matrix.Translation((x, 11.2, 0.06)) @ Matrix.Rotation(rad(180), 4, "Z")
        lb = MB()
        L = Local(lb, M)
        L.box((-0.35, -1.0, 0.25), (0.35, 0.95, 0.32))
        for xx in (-0.33, 0.28):
            for yy in (-0.95, 0.85):
                L.box((xx, yy, 0), (xx + 0.05, yy + 0.08, 0.25))
        lb.obj("lounger", teak, bevel=0.005)
        cb = MB()
        L = Local(cb, M)
        L.box((-0.33, -0.95, 0.32), (0.33, 0.35, 0.4))
        L.box((-0.33, 0.35, 0.32), (0.33, 0.95, 0.4), rot=(rad(35), 0, 0))
        cb.obj("cushion", cush, bevel=0.03, segs=3, smooth=True)
    um = MB()
    um.cyl((6.8, 11.0, 0), (6.8, 11.0, 2.4), 0.025, segs=10)
    um.obj("pole", teak, smooth=True)
    can = MB()
    can.cyl((6.8, 11.0, 2.0), (6.8, 11.0, 2.45), 1.4, r2=0.05, segs=8, cap=False)
    can.obj("umbrella", mat_fabric("umb", (0.82, 0.78, 0.68)), smooth=False)
    # planting + trees
    leafm = mat_leaf("tree_leaf", base=(0.05, 0.11, 0.03))
    bark = mat_bark()
    prop_tree((13.0, 9.5, 0), height=7, crown_r=2.6, leaf_mat=leafm, bark_mat=bark, seed=5, leaves=25000, leaf_size=1.3)
    prop_tree((-6.5, 11.0, 0), height=8, crown_r=3.0, leaf_mat=leafm, bark_mat=bark, seed=9, leaves=28000, leaf_size=1.3)
    pots = MB()
    for x in (-4.5, 11.5):
        pots.cyl((x, 2.5, 0), (x, 2.5, 0.7), 0.35, r2=0.45, segs=24)
    pots.obj("pots", mat_terracotta())
    for x in (-4.5, 11.5):
        prop_plant((x, 2.5, 0.0), mat_terracotta("tc2"), simple("soil", (0.04, 0.03, 0.02), 1.0), simple("stem", (0.15, 0.12, 0.06), 0.7),
                   leafm, height=1.6, seed=int(x), nleaves=70, kind="long", leaf_len=0.18, leaf_w=0.05, pot_r=0.3, pot_h=0.7)
    add_sun(50, 150, strength=6.0, color=(1.0, 0.95, 0.86))
    sky_world(50, 150, strength=0.35, clouds=0.5, cloud_cover=0.3)
    add_camera((12.5, -1.0, 1.6), (2.0, 9.0), lens=26, shift_y=0.0)
    setup_render(exposure=-0.7, look="AgX - Punchy", samples=0.5, bounces=(3, 3, 6))


def scene_library():
    rnd = random.Random(15)
    X1, Y1, H = 8.0, 6.0, 3.6
    panel = mat_wood("panel", base=(0.18, 0.09, 0.04), rough=0.35, coat=0.4, coords="Generated", scale=0.3)
    floor = mat_wood_floor("floor", plank_w=0.09, plank_l=0.6, c_dark=(0.10, 0.05, 0.02), c_light=(0.22, 0.11, 0.05), rough=(0.25, 0.4), worn=0.1)
    room_shell(X1, Y1, H, panel, floor, mat_plaster("ceil", base=(0.75, 0.70, 0.62)), "x0", [(2.0, 4.0, 0.9, 3.1)])
    fr, gl = MB(), MB()
    steel_window(fr, gl, "Y", 2.0, 4.0, 0.9, 3.1, -0.15, 2, 4, fw=0.08)
    fr.obj("frames", mat_paint("sash", (0.8, 0.78, 0.72), rough=0.4))
    gl.obj("glass", mat_glass("glass"))
    # shelves on the back (y=Y1) and right (x=X1) walls, filled with books
    sh = MB()
    books = MB()
    bmats = [mat_fabric(f"book{i}", c, rough=0.6, sheen=0.1) for i, c in enumerate(
        [(0.25, 0.04, 0.03), (0.05, 0.08, 0.15), (0.06, 0.12, 0.06), (0.45, 0.35, 0.2), (0.08, 0.06, 0.05), (0.55, 0.5, 0.42), (0.3, 0.15, 0.05)])]

    def shelf_run(axis, a0, a1, p_back, p_front):
        for z in [0.1 + 0.42 * k for k in range(8)]:
            sh.box(*_ab(axis, a0, a1, min(p_back, p_front), max(p_back, p_front), z, z + 0.03))
            a = a0 + 0.02
            while a < a1 - 0.06:
                th = rnd.uniform(0.025, 0.06)
                hgt = rnd.uniform(0.22, 0.34)
                dp = rnd.uniform(0.17, 0.24)
                pa, pb = (p_back, p_back + (dp if p_front > p_back else -dp))
                books.box(*_ab(axis, a, a + th, min(pa, pb), max(pa, pb), z + 0.03, z + 0.03 + hgt), mi=rnd.randrange(len(bmats)))
                a += th + rnd.uniform(0.0, 0.006)
                if rnd.random() < 0.03:
                    a += rnd.uniform(0.1, 0.25)
        for a in [a0 + (a1 - a0) * k / 4 for k in range(5)]:
            sh.box(*_ab(axis, a - 0.02, a + 0.02, min(p_back, p_front), max(p_back, p_front), 0.0, 3.5))
    shelf_run("X", 0.2, X1 - 0.2, Y1, Y1 - 0.3)
    shelf_run("Y", 0.2, Y1 - 0.4, X1, X1 - 0.3)
    sh.obj("shelves", panel, bevel=0.004)
    books.obj("books", bmats, bevel=0.003)
    leather = mat_leather("leather", base=(0.22, 0.07, 0.03))
    prop_sofa(Matrix.Translation((2.6, 2.4, 0)) @ Matrix.Rotation(rad(-60), 4, "Z") @ Matrix.Diagonal((0.45, 1, 1, 1)), leather, mat_wood("dk", base=(0.05, 0.03, 0.02)))
    rug = mat_rug("rug", size=(3.0, 2.2))
    r = MB()
    r.box((-1.5, -1.1, 0), (1.5, 1.1, 0.01))
    r.obj("rug", rug, loc=(3.6, 3.0, 0))
    prop_table(Matrix.Translation((5.2, 2.0, 0)), mat_wood("desk", base=(0.15, 0.07, 0.03), coat=0.5), mat_wood("desk_leg", base=(0.12, 0.06, 0.03)), W=1.5, D=0.75, H=0.76)
    lamp = MB()
    lamp.cyl((5.6, 2.2, 0.76), (5.6, 2.2, 1.15), 0.012, segs=8)
    lamp.cyl((5.6, 2.2, 1.12), (5.6, 2.2, 1.3), 0.16, r2=0.08, segs=24, cap=False)
    lamp.obj("lamp", mat_metal("brass", (0.8, 0.55, 0.3), rough=0.25), smooth=True)
    add_point("lamp", (5.6, 2.2, 1.18), 25, color=(1.0, 0.62, 0.3), radius=0.05)
    add_sun(25, 200, strength=6.0, color=(1.0, 0.86, 0.66))
    sky_world(25, 200, strength=0.35)
    add_area("portal", (-0.35, 3.0, 2.0), (2.0, 2.2), 1.0, rot=(0, rad(90), 0), portal=True)
    add_camera((7.4, 0.6, 1.5), (1.5, 4.8), lens=22, shift_y=0.05)
    setup_render(exposure=2.3, samples=0.5, bounces=(4, 2, 3))


SCENES = {
    "loft": scene_loft,
    "studio": scene_studio,
    "mill": scene_mill,
    "rooftop": scene_rooftop,
    "warehouse": scene_warehouse,
    "office": scene_office,
    "barn": scene_barn,
    "cafe": scene_cafe,
    "house": scene_house,
    "chapel": scene_chapel,
    "greenhouse": scene_greenhouse,
    "pool": scene_pool,
    "library": scene_library,
}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="scene names to render (default: all)")
    ap.add_argument("--samples", type=int, default=48, help="base Cycles samples; each scene scales it (OIDN denoises)")
    ap.add_argument("--res", type=float, default=1.0, help="resolution scale of 1600x900")
    ap.add_argument("--out", default=OUT_DIR, help="output directory")
    ap.add_argument("--blend", action="store_true", help="also save a .blend next to each JPEG")
    a = ap.parse_args(argv)
    Q.samples, Q.res, Q.out = a.samples, a.res, a.out
    os.makedirs(Q.out, exist_ok=True)
    names = a.only or list(SCENES)
    for n in names:
        if n not in SCENES:
            sys.exit(f"unknown scene {n!r}; choose from {', '.join(SCENES)}")
    for n in names:
        reset()
        t0 = time.time()
        SCENES[n]()
        t1 = time.time()
        bpy.ops.render.render(write_still=False)
        path = os.path.join(Q.out, f"{n}.jpg")
        q, size = save_jpeg(path)
        if a.blend:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(Q.out, f"{n}.blend"))
        print(f"[{n}] build {t1 - t0:.1f}s render {time.time() - t1:.1f}s -> {path} (q{q}, {size // 1024} KB)", flush=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv)
