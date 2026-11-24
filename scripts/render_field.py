#!/usr/bin/env python3
"""
render_field.py -- the field case's two Blender plates (agri scene, chapter "Real-world AI").

  --shot tractor   (200 frames, 1920×1080)  Dusk. A graphite tractor with its work lights on drives along lettuce
                   rows; a camera on a boom over the rows lights its footprint. The shot tracks alongside, then
                   pushes into the boom camera, where the film cuts to that camera's feed.
  --shot feed      (120 frames, shown in the 1620×826 feed frame)  That feed: a straight-down ORTHOGRAPHIC view
                   of the rows under the boom's flood light, scrolling at the film's SPEED. Every lettuce comes
                   from the film's own field model (plantAt: gaps, off-row plants, jitter, size), so the film's
                   boxes, IDs, GAP/OFF-ROW flags and measurements land on the rendered plants unchanged.

Inputs: video/build/shots/inputs.json (node video/tools/dump_shot_inputs.mjs).
Overlay data: video/src/shots/tractor.js (camera lens, its ground footprint); the feed needs none.

    python scripts/render_field.py --shot feed --res 0.25 --samples 8 --step 10     # preview
    python scripts/render_field.py --shot tractor --samples 28                      # final (res 0.6667)
    scripts/pack_plates.sh tractor feed
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector, Matrix, noise  # noqa: E402
from blender_common import (  # noqa: E402
    FPS, Keyer, Nodes, args, area, box, camera, clamp, cyl, empty, finish, inputs, instancer, ioc, lerp, look_at,
    mesh_object, new_scene, principled, project, render_frames, setup_render, wear, write_shot, ios, rad,
)

IN = inputs()


# ---------------------------------------------------------------------------- materials (photoreal pass)
def lettuce_material(name, hue_shift=0.0):
    """Butterhead leaf: a pale, almost yellow heart, deep green tips, real translucency (light passes through
    the thin leaves), a waxy sheen with dew, fine veins and a crinkled surface."""
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    n.link(tc.outputs["Object"], sep.inputs[0])
    rr = n.math("SQRT", n.math("ADD", n.math("MULTIPLY", sep.outputs[0], sep.outputs[0]), n.math("MULTIPLY", sep.outputs[1], sep.outputs[1])))
    mott = n.new("ShaderNodeTexNoise", Scale=14.0, Detail=6.0, Roughness=0.6)
    n.link(tc.outputs["Object"], mott.inputs["Vector"])
    fac = n.math("ADD", n.math("MULTIPLY", rr, 2.0), n.math("MULTIPLY", mott.outputs["Fac"], 0.25))
    col = n.ramp(fac, [(0.05, (0.42 + hue_shift, 0.55, 0.15)), (0.35, (0.19 + hue_shift, 0.4, 0.07)), (0.7, (0.07, 0.24 + hue_shift * 0.5, 0.04)), (1.1, (0.03, 0.12, 0.022))])
    n.link(col, n.bsdf.inputs["Base Color"])
    n.bsdf.inputs["Subsurface Weight"].default_value = 0.35
    n.bsdf.inputs["Subsurface Radius"].default_value = (0.25, 0.6, 0.12)
    n.bsdf.inputs["Subsurface Scale"].default_value = 0.02
    n.bsdf.inputs["Transmission Weight"].default_value = 0.08
    n.bsdf.inputs["Coat Weight"].default_value = 0.12
    n.bsdf.inputs["Coat Roughness"].default_value = 0.25
    # dew: tiny bright droplets as low-roughness specks
    dew = n.new("ShaderNodeTexVoronoi", Scale=90.0)
    n.link(tc.outputs["Object"], dew.inputs["Vector"])
    drop = n.math("LESS_THAN", dew.outputs["Distance"], 0.08)
    n.link(n.math("SUBTRACT", 0.52, n.math("MULTIPLY", drop, 0.3)), n.bsdf.inputs["Roughness"])
    # veins radiating from the heart + crinkle
    vein = n.new("ShaderNodeTexWave", Scale=7.0, Distortion=3.0, Detail=4.0)
    vein.wave_type = "RINGS"
    vein.rings_direction = "SPHERICAL"
    n.link(tc.outputs["Object"], vein.inputs["Vector"])
    crinkle = n.new("ShaderNodeTexNoise", Scale=55.0, Detail=4.0)
    n.link(tc.outputs["Object"], crinkle.inputs["Vector"])
    h = n.math("ADD", n.math("MULTIPLY", vein.outputs["Fac"], 0.5), n.math("MULTIPLY", crinkle.outputs["Fac"], 0.5))
    bump = n.new("ShaderNodeBump", Strength=0.45, Distance=0.015)
    n.link(h, bump.inputs["Height"])
    n.link(bump.outputs["Normal"], n.bsdf.inputs["Normal"])
    return m


def soil_material(scale=1.0, wet=0.35):
    """Tilled loam: dark where damp, paler dry crust on the ridges, crumbs and small stones in the bump,
    a little sheen where it is wet."""
    m = bpy.data.materials.new("soil")
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    n.link(tc.outputs["Object"], mp.inputs["Vector"])
    big = n.new("ShaderNodeTexNoise", Scale=0.8, Detail=8.0, Roughness=0.62)
    mid = n.new("ShaderNodeTexNoise", Scale=7.0, Detail=10.0, Roughness=0.68)
    fine = n.new("ShaderNodeTexNoise", Scale=60.0, Detail=10.0, Roughness=0.75)
    crumbs = n.new("ShaderNodeTexVoronoi", Scale=34.0)
    crumbs.feature = "SMOOTH_F1"
    pebbles = n.new("ShaderNodeTexVoronoi", Scale=9.0)
    for t in (big, mid, fine, crumbs, pebbles):
        n.link(mp.outputs[0], t.inputs["Vector"])
    dry = n.math("MULTIPLY", n.math("SUBTRACT", big.outputs["Fac"], 0.42), 3.0, clamp_=True)
    col = n.ramp(n.math("ADD", n.math("MULTIPLY", dry, 0.7), n.math("MULTIPLY", mid.outputs["Fac"], 0.3)),
                 [(0.15, (0.028, 0.019, 0.013)), (0.45, (0.062, 0.043, 0.03)), (0.7, (0.118, 0.087, 0.062)), (0.95, (0.19, 0.15, 0.11))])
    mix = n.new("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    mix.inputs["Factor"].default_value = 0.55
    n.link(col, mix.inputs[6])
    n.link(n.ramp(fine.outputs["Fac"], [(0.3, (0.6, 0.6, 0.6)), (0.7, (1.0, 1.0, 1.0))]), mix.inputs[7])
    # pale stones where the pebble cells are small
    stone = n.math("LESS_THAN", pebbles.outputs["Distance"], 0.045)
    mix2 = n.new("ShaderNodeMix", _data_type="RGBA")
    n.link(stone, mix2.inputs["Factor"])
    n.link(mix.outputs[2], mix2.inputs[6])
    mix2.inputs[7].default_value = (0.12, 0.11, 0.1, 1)
    n.link(mix2.outputs[2], n.bsdf.inputs["Base Color"])
    n.link(n.math("ADD", 0.62, n.math("MULTIPLY", dry, 0.33)), n.bsdf.inputs["Roughness"])
    n.bsdf.inputs["Specular IOR Level"].default_value = 0.5 + wet * 0.3
    h = n.math("ADD", n.math("MULTIPLY", n.math("SUBTRACT", 1.0, crumbs.outputs["Distance"]), 0.6),
               n.math("ADD", n.math("MULTIPLY", fine.outputs["Fac"], 0.4), n.math("MULTIPLY", stone, 0.5)))
    bump = n.new("ShaderNodeBump", Strength=0.9, Distance=0.05 / scale)
    n.link(h, bump.inputs["Height"])
    n.link(bump.outputs["Normal"], n.bsdf.inputs["Normal"])
    return m


# ---------------------------------------------------------------------------- lettuce
def lettuce_mesh(seed, mat):
    """A butterhead rosette of radius ~0.5 (unit scale): outer leaves splay out with ruffled, wavy edges, inner
    ones cup up around a tight heart; every leaf is a curved sheet, not a blob."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    rot0 = rnd.random() * math.tau
    layers = [(8 + rnd.randint(0, 2), 0.52, 0.42, rad(12)), (7, 0.40, 0.36, rad(34)), (6, 0.27, 0.27, rad(58)), (4, 0.16, 0.17, rad(76))]
    for li, (count, L, Wd, tilt) in enumerate(layers):
        for i in range(count):
            az = rot0 + i / count * math.tau + li * 0.5 + (rnd.random() - 0.5) * 0.4
            Ls = L * (0.85 + rnd.random() * 0.25)
            nu, nv = 14, 12
            g = bmesh.ops.create_grid(bm, x_segments=nu, y_segments=nv, size=0.5)
            verts = g["verts"]
            for v in verts:
                u = v.co.x + 0.5                     # 0 at the base, 1 at the tip
                w = v.co.y * 2                       # -1 .. 1 across
                half = Wd * 0.5 * (0.25 + 0.75 * math.sin(clamp(u * 0.92 + 0.08) * math.pi) ** 0.7)
                x = u * Ls
                y = w * half
                # cupped across, lifted towards the tip, wavy edge
                z = (w * w) * half * 0.55 + (u ** 2) * 0.05
                edge = abs(w) ** 3
                z += math.sin(u * 22 + w * 3 + i) * 0.018 * edge * u + noise.noise(Vector((x * 14 + seed, y * 14, li * 2.3 + i))) * 0.02 * u
                v.co = Vector((x, y, z))
            bmesh.ops.transform(bm, matrix=Matrix.Rotation(az, 4, "Z") @ Matrix.Rotation(-tilt, 4, "Y"), verts=verts)
    g = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.07)
    bmesh.ops.translate(bm, vec=Vector((0, 0, 0.1)), verts=g["verts"])
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(f"lettuce{seed}")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    return me


def scatter_soil(rnd, region, count, scale=1.0):
    """Clods and pebbles, and a little crop residue (straw), lying on the soil (region = x0, x1, y0, y1, zfn)."""
    x0, x1, y0, y1, zfn = region
    clod = principled("clod", (0.07, 0.05, 0.035), rough=0.9)
    pebble = principled("pebble", (0.1, 0.092, 0.085), rough=0.65)
    straw = principled("straw", (0.42, 0.33, 0.18), rough=0.75)
    meshes = []
    for i in range(6):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        for v in bm.verts:
            v.co *= 1 + noise.noise(v.co * 2.2 + Vector((i, 0, 0))) * 0.35
            v.co.z *= 0.6
        me = bpy.data.meshes.new(f"clod{i}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(clod if i < 5 else pebble)
        meshes.append(me)
    stalk = bpy.data.meshes.new("straw")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.012, radius2=0.01, depth=1.0)
    bm.to_mesh(stalk)
    bm.free()
    stalk.materials.append(straw)
    for i in range(count):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        if rnd.random() < 0.82:
            s = rnd.uniform(0.012, 0.05) * scale
            ob = instance(f"c{i}", meshes[rnd.randrange(6)], (x, y, zfn(x, y) + s * 0.2), rnd.random() * math.tau, s)
        else:
            ob = instance(f"s{i}", stalk, (x, y, zfn(x, y) + 0.01), 0, rnd.uniform(0.1, 0.35) * scale)
            ob.rotation_euler = (rad(90), 0, rnd.random() * math.tau)


def instance(name, mesh, loc, rot_z=0.0, scale=1.0):
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (0, 0, rot_z)
    ob.scale = (scale, scale, scale)
    return ob


def lettuce_variants(n=10):
    mats = [lettuce_material(f"lettuce_mat{i}", (i % 3 - 1) * 0.04) for i in range(3)]
    return [lettuce_mesh(100 + i, mats[i % 3]) for i in range(n)]


# ---------------------------------------------------------------------------- FEED (orthographic, film pixels / 100)
def build_feed(sc, a):
    """The boom camera's feed, in the same world as the tractor shot: metres, the same beds, soil, lettuce, sun and
    sky, so the push into the boom camera cuts to a matching image. The film's feed is laid out in its own pixels
    (rows ROW_DX apart); one uniform scale maps that layout onto the real 0.76 m rows, and the orthographic
    camera scales with it, so every plant still lands exactly where the film's overlays expect it."""
    import numpy as np
    F = IN["feed"]
    FR, SPEED, PITCH = F["FRAME"], F["SPEED"], F["PITCH"]
    S = ROW_W / F["ROW_DX"]                    # metres per feed pixel
    X0 = 0.5 * ROW_W - (F["ROW_X0"] - FR["x"]) * S   # shift so the feed's rows fall on the field's row centres
    t0 = F["t0"]
    plate = IN["plates"]["feed"]
    nfr = plate["frames"]
    sky_world(sc)
    sun_lamp(sc)
    # ground: the tractor shot's beds (field_z with full bed relief), its soil and true displacement
    y_lo = (FR["h"] * 0.5 + 120 + (t0 - 0.5) * SPEED - FR["h"]) * S - 1.5
    y_hi = (FR["h"] * 0.5 + 120 + (t0 + nfr / FPS + 0.5) * SPEED + FR["h"]) * S + 1.5
    x_lo, x_hi = X0 - 0.6, X0 + FR["w"] * S + 0.6
    xs = [x_lo + i * ROW_W / 16 for i in range(int((x_hi - x_lo) / (ROW_W / 16)) + 2)]
    ys = [y_lo + i * 0.05 for i in range(int((y_hi - y_lo) / 0.05) + 2)]

    def feed_z(x, y):
        und = noise.noise(Vector((x * 0.35, y * 0.35, 0.7))) * 0.035 + noise.noise(Vector((x * 1.3, y * 1.3, 2.1))) * 0.01
        return bed_z(x) + und
    V = [(x, y, feed_z(x, y)) for y in ys for x in xs]
    nx = len(xs)
    Fc = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i) for j in range(len(ys) - 1) for i in range(nx - 1)]
    mat = field_material(True, ruts=False, edge=False)
    g = mesh_object("ground", V, Fc, [mat])
    sm = g.modifiers.new("dice", "SUBSURF")
    sm.subdivision_type = "SIMPLE"
    sm.use_adaptive_subdivision = True
    sm.adaptive_space = "PIXEL"
    sm.adaptive_pixel_size = 2.0
    sm.levels = 0
    # clods, stones, straw on the soil
    rnd = random.Random(9)
    bits = []
    for _ in range(int((x_hi - x_lo) * (y_hi - y_lo) * 9)):
        x, y = rnd.uniform(x_lo, x_hi), rnd.uniform(y_lo, y_hi)
        dr = abs((x % ROW_W) - ROW_W * 0.5)
        if dr < 0.12 and rnd.random() < 0.8:
            continue
        k = rnd.random()
        if k < 0.86:
            sz = rnd.uniform(0.012, 0.045)
            bits.append((x, y, feed_z(x, y) + sz * 0.15, rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, math.tau), sz, sz * rnd.uniform(0.7, 1.2), sz * rnd.uniform(0.5, 0.8), rnd.randrange(5)))
        elif k < 0.93:
            sz = rnd.uniform(0.01, 0.03)
            bits.append((x, y, feed_z(x, y) + sz * 0.2, 0, 0, rnd.uniform(0, math.tau), sz, sz * 0.8, sz * 0.6, 5))
        else:
            L = rnd.uniform(0.08, 0.3)
            bits.append((x, y, feed_z(x, y) + 0.008, rad(90) + rnd.uniform(-0.15, 0.15), 0, rnd.uniform(0, math.tau), 1, 1, L, 6))
    instancer("soil_bits", soil_bits(), bits)
    # plants, straight from the film's field model (gaps, off-row plants, jitter, size)
    variants = lettuce_variants(10)
    lets = []
    for p in F["plants"]:
        if p["missing"]:
            continue
        x = X0 + (F["ROW_X0"] - FR["x"] + p["r"] * F["ROW_DX"] + p["jx"]) * S
        y = (p["k"] * PITCH + p["jy"]) * S
        if y < y_lo + 0.3 or y > y_hi - 0.3:
            continue
        sz = 116 * p["s"] * S * 0.92          # same footprint as the film's sprite
        r2 = random.Random(p["r"] * 1000 + p["k"])
        lets.append((x, y, feed_z(x, y) - 0.012, 0, 0, r2.random() * math.tau, sz, sz, sz, p["v"]))
    instancer("lettuce", [bpy.data.objects.new(f"lv{i}", me) for i, me in enumerate(variants)], lets)
    cam = camera(sc, ortho_scale=FR["w"] * S)
    K = Keyer()
    for f in range(-1, nfr + 2):
        t = t0 + f / FPS
        yc = (FR["h"] * 0.5 + 120 + t * SPEED) * S
        K.mat(cam, Matrix.Translation((X0 + FR["w"] * S * 0.5, yc, 8.0)), f)
    Keyer.linear()
    return {"frames": nfr, "w": plate["w"], "h": plate["h"], "export": None}


# ---------------------------------------------------------------------------- TRACTOR (late afternoon, perspective)
# World layout (metres, z up). The lettuce rows run along +y, 0.76 m apart, at x = (r + ½)·0.76; the tractor
# straddles the two rows at x = ±0.38 with its wheels in the furrows (tramlines) at x = ±0.76 and drives +y.
# The camera sits at x ≈ 5–7 looking back across the field (towards −x, −y): the field runs to the horizon there,
# bounded by a headland at y = −57 (irrigation main, grass verge, a dirt farm track with puddles, a fence, the
# utility line and a hedgerow), with a farmstead, woodland belts, a poplar windbreak and rolling farmland beyond.
ROW_W, PLANT_P, SPEED_M = 0.76, 0.38, 2.2      # row spacing, plant pitch (m), tractor speed (m/s)
BOOM = Vector((1.55, 3.2, 2.55))               # camera housing, tractor-local (x right, y forward, z up)
BOOM_TILT = rad(62)                             # looking down-forward
TRACK_X = 0.76                                  # wheel tracks (tramlines), in the furrows beside the straddled rows
F_PX = 1600.0                                   # the shot's focal length in pixels (1920 wide)
FIELD = (-420.0, 44.0, -57.0, 1400.0)           # the lettuce field: x0, x1, y0, y1
FMESH = (-170.0, 44.0, -57.0, 170.0)            # ... the part that is real geometry (beyond it, the terrain's texture)
NEAR = (-13.0, 9.0, -9.0, 31.0)                 # true-displacement soil where the camera is close
LETTUCE_R = 150.0                               # real lettuce instances out to here; band-limited rows beyond
FOG_START, FOG_LEN = 180.0, 5000.0              # aerial perspective: none in front of FOG_START, e-folding length
SUN = {"el": 15.0, "az": 150.0, "aerosol": 0.4}  # degrees; az counter-clockwise from +x (set by --sun-el/--sun-az)
# sun-disc irradiance of the physical sky at strength 1, as a sun lamp (W/m², per channel), measured from the sky
# itself (white plane lit by the sky's disc vs. by a 1 W/m² lamp): keeps lamp and sky in physical balance
SUN_RGB = {(15.0, 0.4): (130.2, 96.9, 55.4)}


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def sun_dir():
    el, az = rad(SUN["el"]), rad(SUN["az"])
    return Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))


# ---------------------------------------------------------------------------- terrain heights (shared by meshes and placement)
def relief(x, y):
    """Rolling farmland: flat around the field, rising gently into low hills towards the horizon."""
    r = math.hypot(x + 60, y + 40)
    a = smoothstep(380, 2600, r) * 34 + smoothstep(1800, 6000, r) * 70
    if a <= 0:
        return 0.0
    n = noise.noise(Vector((x / 1400, y / 1400, 0.37))) * 0.6 + noise.noise(Vector((x / 520, y / 520, 1.9))) * 0.3 + 0.55
    return a * max(n, 0.05)


def bed_amp(x, y):
    """Modelled beds near the camera only (the far field's rows are in the texture)."""
    return smoothstep(-40, -33, x) * smoothstep(31, 25, x) * smoothstep(62, 54, y)


def bed_z(x):
    dr = abs((x % ROW_W) - ROW_W * 0.5)                 # distance to the nearest row centre
    return 0.11 * (1 - smoothstep(0.13, 0.35, dr))


def rut_w(x):
    return 1 - smoothstep(0.17, 0.27, abs(abs(x) - TRACK_X))


def field_z(x, y):
    """Ground height of the field: raised beds under each row, furrows between, gentle undulation, and the two
    compacted tramline ruts the wheels run in."""
    und = noise.noise(Vector((x * 0.35, y * 0.35, 0.7))) * 0.035 + noise.noise(Vector((x * 1.3, y * 1.3, 2.1))) * 0.01
    z = bed_z(x) * bed_amp(x, y) + und
    if abs(x) < 1.1:
        w = rut_w(x)
        z = lerp(z, -0.03 + und * 0.25, w)
    return z


def graded(lo, hi, a, b, fine, coarse, grow=1.06):
    """Grid coordinates: spacing `fine` on [a, b] (aligned to multiples of fine), growing to `coarse` outside."""
    xs = [a + i * fine for i in range(int(round((b - a) / fine)) + 1)]
    x, s = xs[-1], fine
    while x < hi - 1e-6:
        s = min(s * grow, coarse)
        x = min(x + s, hi)
        xs.append(x)
    x, s, lo_part = xs[0], fine, []
    while x > lo + 1e-6:
        s = min(s * grow, coarse)
        x = max(x - s, lo)
        lo_part.append(x)
    return lo_part[::-1] + xs


# ---------------------------------------------------------------------------- shading building blocks
def aerial(n, shader_out, glossy_too=True):
    """Aerial perspective as a material term: past FOG_START the surface fades towards the horizon sky in that
    azimuth (the same physical sky, sampled just above the horizon), so distant trees, hills and poles sit in the
    air with no volume and no veil over the foreground. Returns the new shader socket."""
    cd = n.new("ShaderNodeCameraData")
    d = n.math("MAXIMUM", n.math("SUBTRACT", cd.outputs["View Distance"], FOG_START), 0.0)
    f = n.math("SUBTRACT", 1.0, n.math("EXPONENT", n.math("MULTIPLY", d, -1.0 / FOG_LEN)))
    geo = n.new("ShaderNodeNewGeometry")
    inc = n.sep(geo.outputs["Incoming"])
    hz = n.vmath("NORMALIZE", n.comb(n.math("MULTIPLY", inc[0], -1.0), n.math("MULTIPLY", inc[1], -1.0), 0.035))
    em = n.new("ShaderNodeEmission", Strength=1.0)
    if os.environ.get("AIV_FLATFOG"):
        em.inputs["Color"].default_value = (2, 2.5, 3.5, 1)
    else:
        sky = sky_node(n.nt)
        n.link(hz, sky.inputs["Vector"])
        n.link(sky.outputs[0], em.inputs["Color"])
    lp = n.new("ShaderNodeLightPath")
    ray = n.math("ADD", lp.outputs["Is Camera Ray"], lp.outputs["Is Glossy Ray"]) if glossy_too else lp.outputs["Is Camera Ray"]
    fac = n.math("MULTIPLY", f, n.math("MINIMUM", ray, 1.0))
    mx = n.new("ShaderNodeMixShader")
    n.link(fac, mx.inputs[0])
    n.link(shader_out, mx.inputs[1])
    n.link(em.outputs[0], mx.inputs[2])
    return mx.outputs[0]


def sky_node(nt):
    s = nt.nodes.new("ShaderNodeTexSky")
    s.sky_type = "MULTIPLE_SCATTERING"
    s.sun_elevation = rad(SUN["el"])
    s.sun_rotation = rad(90 - SUN["az"])
    s.air_density, s.aerosol_density, s.ozone_density = 1.0, SUN["aerosol"], 1.0
    s.sun_disc = False
    return s


def finish_aerial(m, n):
    """Route a material's Principled BSDF through aerial()."""
    out = m.node_tree.nodes["Material Output"]
    n.link(aerial(n, n.bsdf.outputs[0]), out.inputs["Surface"])
    return m


def far_lettuce(n, pos):
    """The lettuce field where single plants are below a pixel: rows as stripes whose contrast fades out once a
    pixel's footprint on the ground spans a row (estimated from the view distance and the grazing angle), so the
    far rows never alias or shimmer; at grazing angles the plants hide the soil, so the mean leans to leaf green."""
    p = n.sep(pos)
    cd = n.new("ShaderNodeCameraData")
    dist = cd.outputs["View Distance"]
    geo = n.new("ShaderNodeNewGeometry")
    inc = n.sep(geo.outputs["Incoming"])
    iz = n.math("MAXIMUM", n.math("ABSOLUTE", inc[2]), 0.002)
    xext = n.math("MULTIPLY", n.math("DIVIDE", dist, F_PX),
                  n.math("ADD", n.math("DIVIDE", n.math("ABSOLUTE", inc[0]), iz), n.math("ABSOLUTE", inc[1])))
    contrast = n.smooth(0.42, 0.12, xext)
    ph = n.math("FLOORED_MODULO", p[0], ROW_W)
    dr = n.math("ABSOLUTE", n.math("SUBTRACT", ph, ROW_W * 0.5))
    stripe = n.smooth(0.22, 0.1, dr)                       # 1 on the plants, 0 in the furrows
    mean = n.math("SUBTRACT", 0.96, n.math("MULTIPLY", n.math("POWER", iz, 0.5), 0.6))
    cov = n.math("ADD", mean, n.math("MULTIPLY", n.math("SUBTRACT", stripe, mean), contrast))
    patch = n.new("ShaderNodeTexNoise", Scale=0.035, Detail=4.0, Roughness=0.55)
    n.link(pos, patch.inputs["Vector"])
    leaf = n.ramp(patch.outputs["Fac"], [(0.3, (0.07, 0.19, 0.035)), (0.5, (0.1, 0.24, 0.045)), (0.7, (0.13, 0.25, 0.05))])
    soil = (0.085, 0.062, 0.045)
    return n.mix(cov, soil, leaf), cov


def field_material(near, ruts=True, edge=True):
    """Tilled loam of the beds. Dry pale crust (with fine cracks) on the ridges, dark damp soil in the furrows,
    compacted tramline ruts printed with the tyres' chevron tread; true displacement (clods, crumbs, cracks,
    tread) on the near patch, fading out at its edges; far away it becomes the band-limited lettuce rows."""
    m = bpy.data.materials.new("field_near" if near else "field")
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    pos = tc.outputs["Object"]
    p = n.sep(pos)
    ph = n.math("FLOORED_MODULO", p[0], ROW_W)
    dr = n.math("ABSOLUTE", n.math("SUBTRACT", ph, ROW_W * 0.5))
    ridge = n.smooth(0.2, 0.08, dr)                                   # 1 on the bed tops
    rut = n.smooth(0.27, 0.17, n.math("ABSOLUTE", n.math("SUBTRACT", n.math("ABSOLUTE", p[0]), TRACK_X)))
    rut = n.math("MULTIPLY", rut, n.smooth(1.2, 1.0, n.math("ABSOLUTE", p[0])))
    if not ruts:
        rut = n.math("MULTIPLY", rut, 0.0)
    big = n.new("ShaderNodeTexNoise", Scale=0.45, Detail=6.0, Roughness=0.6)
    mid = n.new("ShaderNodeTexNoise", Scale=6.0, Detail=8.0, Roughness=0.62)
    fine = n.new("ShaderNodeTexNoise", Scale=70.0, Detail=6.0, Roughness=0.7)
    crumbs = n.new("ShaderNodeTexVoronoi", Scale=28.0, _feature="SMOOTH_F1")
    crumbs.inputs["Smoothness"].default_value = 0.6
    clods = n.new("ShaderNodeTexVoronoi", Scale=7.0, _feature="SMOOTH_F1")
    clods.inputs["Smoothness"].default_value = 0.4
    cracks = n.new("ShaderNodeTexVoronoi", Scale=5.0, _feature="DISTANCE_TO_EDGE")
    stones = n.new("ShaderNodeTexVoronoi", Scale=14.0)
    warp = n.new("ShaderNodeTexNoise", Scale=2.0, Detail=3.0)
    n.link(pos, warp.inputs["Vector"])
    wpos = n.vmath("ADD", pos, n.vmath("SCALE", n.vmath("SUBTRACT", warp.outputs["Color"], (0.5, 0.5, 0.5)), 0.12))
    for t in (big, mid, fine, crumbs, clods, stones):
        n.link(pos, t.inputs["Vector"])
    n.link(wpos, cracks.inputs["Vector"])
    # moisture: damp in the furrows and the ruts, patchy; the crust on the ridges is dry
    damp = n.math("MINIMUM", n.math("ADD", n.math("MULTIPLY", n.math("SUBTRACT", 1.0, ridge), 0.75),
                                    n.math("MULTIPLY", n.math("SUBTRACT", big.outputs["Fac"], 0.35), 0.8)), 1.0)
    damp = n.math("MAXIMUM", n.math("MINIMUM", damp, 1.0), 0.0)
    damp = n.math("MAXIMUM", damp, n.math("MULTIPLY", rut, 0.7))
    dry_col = n.ramp(mid.outputs["Fac"], [(0.3, (0.2, 0.155, 0.11)), (0.55, (0.255, 0.2, 0.145)), (0.8, (0.3, 0.245, 0.18))])
    wet_col = n.ramp(mid.outputs["Fac"], [(0.3, (0.045, 0.032, 0.024)), (0.6, (0.07, 0.05, 0.036)), (0.85, (0.095, 0.07, 0.05))])
    col = n.mix(damp, dry_col, wet_col)
    col = n.mix(0.5, col, n.ramp(fine.outputs["Fac"], [(0.3, (0.75, 0.75, 0.75)), (0.7, (1.0, 1.0, 1.0))]), blend="MULTIPLY")
    crack = n.math("MULTIPLY", n.smooth(0.035, 0.008, cracks.outputs["Distance"]), n.math("MULTIPLY", ridge, n.math("SUBTRACT", 1.0, damp)))
    col = n.mix(n.math("MULTIPLY", crack, 0.8), col, (0.03, 0.022, 0.017))
    stone = n.math("MULTIPLY", n.smooth(0.09, 0.05, stones.outputs["Distance"]), n.math("GREATER_THAN", n.sep(stones.outputs["Color"])[0], 0.75))
    col = n.mix(stone, col, n.ramp(stones.outputs["Color"], [(0.0, (0.17, 0.155, 0.14)), (1.0, (0.3, 0.28, 0.25))]))
    # tread: the rear tyres' chevron lugs pressed into the rut floor, alternating sides (pitch 0.235 m)
    ax = n.math("SUBTRACT", n.math("ABSOLUTE", p[0]), TRACK_X)
    side = n.math("SIGN", ax)
    tread_v = n.math("ADD", p[1], n.math("MULTIPLY", n.math("ABSOLUTE", ax), 0.42))
    tread_v = n.math("ADD", tread_v, n.math("MULTIPLY", side, 0.0587))
    lug = n.smooth(0.05, 0.02, n.math("ABSOLUTE", n.math("SUBTRACT", n.math("FLOORED_MODULO", tread_v, 0.235), 0.1175)))
    lug = n.math("MULTIPLY", lug, n.math("MULTIPLY", rut, n.smooth(0.21, 0.15, n.math("ABSOLUTE", ax))))
    col = n.mix(n.math("MULTIPLY", lug, 0.25), col, (0.12, 0.09, 0.065))
    if not near:
        cd = n.new("ShaderNodeCameraData")
        far = n.smooth(110.0, LETTUCE_R + 15.0, cd.outputs["View Distance"])
        fcol, _ = far_lettuce(n, pos)
        col = n.mix(far, col, fcol)
    n.link(col, n.bsdf.inputs["Base Color"])
    n.link(n.math("SUBTRACT", 0.95, n.math("MULTIPLY", damp, 0.32)), n.bsdf.inputs["Roughness"])
    n.bsdf.inputs["Specular IOR Level"].default_value = 0.45
    if not near:                     # far rows: matte (no grazing sheen towards the sun at the horizon)
        n.link(n.fmix(far, 0.45, 0.12), n.bsdf.inputs["Specular IOR Level"])
    # height (metres): crumbs + clods + crust cracks + stones + tread, plus fine grain
    h = n.math("MULTIPLY", n.math("SUBTRACT", 1.0, crumbs.outputs["Distance"]), 0.006)
    h = n.math("ADD", h, n.math("MULTIPLY", n.math("MULTIPLY", n.math("SUBTRACT", 1.0, clods.outputs["Distance"]), n.math("SUBTRACT", 1.0, ridge)), 0.018))
    h = n.math("SUBTRACT", h, n.math("MULTIPLY", crack, 0.007))
    h = n.math("ADD", h, n.math("MULTIPLY", stone, 0.012))
    h = n.math("SUBTRACT", h, n.math("MULTIPLY", lug, 0.022))
    h = n.math("ADD", h, n.math("MULTIPLY", fine.outputs["Fac"], 0.003))
    h = n.math("MULTIPLY", h, n.math("SUBTRACT", 1.0, n.math("MULTIPLY", rut, 0.55)))
    out = m.node_tree.nodes["Material Output"]
    if near:
        # fade the displacement to nothing at the patch edges so it meets the plain mesh around it without a seam
        ex = n.math("MINIMUM", n.math("SUBTRACT", p[0], NEAR[0]), n.math("SUBTRACT", NEAR[1], p[0]))
        ey = n.math("MINIMUM", n.math("SUBTRACT", p[1], NEAR[2]), n.math("SUBTRACT", NEAR[3], p[1]))
        edge = n.smooth(0.3, 2.5, n.math("MINIMUM", ex, ey)) if edge else 1.0
        disp = n.new("ShaderNodeDisplacement", Midlevel=0.0, Scale=1.0)
        n.link(n.math("MULTIPLY", h, edge), disp.inputs["Height"])
        n.link(disp.outputs[0], out.inputs["Displacement"])
        m.displacement_method = "BOTH"
    else:
        bump = n.new("ShaderNodeBump", Strength=1.0, Distance=1.0)
        n.link(h, bump.inputs["Height"])
        n.link(bump.outputs["Normal"], n.bsdf.inputs["Normal"])
        m.displacement_method = "BUMP"
    return finish_aerial(m, n) if not near else m


def terrain_material():
    """Farmland to the horizon: a patchwork of fields (pasture, golden stubble, ploughed soil, young crops), the
    lettuce field's rows continuing inside its bounds, and darker hedge lines along field boundaries."""
    m = bpy.data.materials.new("terrain")
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    pos = tc.outputs["Object"]
    p = n.sep(pos)
    sc = n.vmath("MULTIPLY", pos, (1 / 190.0, 1 / 130.0, 0.0))
    cells = n.new("ShaderNodeTexVoronoi", Randomness=0.75)
    cells.distance = "CHEBYCHEV"
    n.link(sc, cells.inputs["Vector"])
    edges = n.new("ShaderNodeTexVoronoi", Randomness=0.75, _feature="DISTANCE_TO_EDGE")
    edges.distance = "CHEBYCHEV"
    n.link(sc, edges.inputs["Vector"])
    pick = n.sep(cells.outputs["Color"])[0]
    crop = n.ramp(pick, [(0.0, (0.06, 0.11, 0.03)), (0.22, (0.06, 0.11, 0.03)), (0.24, (0.33, 0.25, 0.12)), (0.45, (0.3, 0.22, 0.11)),
                         (0.47, (0.085, 0.06, 0.042)), (0.62, (0.1, 0.07, 0.048)), (0.64, (0.08, 0.15, 0.04)), (0.8, (0.1, 0.16, 0.05)),
                         (0.82, (0.18, 0.16, 0.09)), (1.0, (0.2, 0.17, 0.1))])
    var = n.new("ShaderNodeTexNoise", Scale=0.02, Detail=6.0, Roughness=0.6)
    n.link(pos, var.inputs["Vector"])
    crop = n.mix(0.35, crop, n.ramp(var.outputs["Fac"], [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.2, 1.2, 1.2))]), blend="MULTIPLY")
    hedge = n.smooth(0.012, 0.004, edges.outputs["Distance"])
    col = n.mix(hedge, crop, (0.03, 0.05, 0.02))
    inside = n.math("MULTIPLY", n.math("MULTIPLY", n.math("GREATER_THAN", p[0], FIELD[0]), n.math("LESS_THAN", p[0], FIELD[1])),
                    n.math("MULTIPLY", n.math("GREATER_THAN", p[1], FIELD[2]), n.math("LESS_THAN", p[1], FIELD[3])))
    fcol, _ = far_lettuce(n, pos)
    col = n.mix(inside, col, fcol)
    n.link(col, n.bsdf.inputs["Base Color"])
    n.bsdf.inputs["Roughness"].default_value = 0.95
    n.bsdf.inputs["Specular IOR Level"].default_value = 0.12
    return finish_aerial(m, n)


def headland_material():
    """The headland strip by y: grass verge, a dirt farm track (two wheel ruts, a grassy crown, puddles in the
    ruts that mirror the sky), another verge under the fence and the utility line."""
    m = bpy.data.materials.new("headland")
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    pos = tc.outputs["Object"]
    p = n.sep(pos)
    nz = n.new("ShaderNodeTexNoise", Scale=1.5, Detail=8.0, Roughness=0.65)
    n.link(pos, nz.inputs["Vector"])
    fine = n.new("ShaderNodeTexNoise", Scale=40.0, Detail=6.0)
    n.link(pos, fine.inputs["Vector"])
    dy = n.math("SUBTRACT", p[1], -66.5)
    track = n.smooth(2.3, 1.9, n.math("ABSOLUTE", dy))
    rutd = n.math("ABSOLUTE", n.math("SUBTRACT", n.math("ABSOLUTE", dy), 0.8))
    rut = n.math("MULTIPLY", n.smooth(0.3, 0.12, rutd), track)
    pn = n.new("ShaderNodeTexNoise", Scale=0.09, Detail=3.0)
    n.link(pos, pn.inputs["Vector"])
    puddle = n.math("MULTIPLY", n.smooth(0.62, 0.66, pn.outputs["Fac"]), n.smooth(0.2, 0.08, rutd))
    puddle = n.math("MULTIPLY", puddle, track)
    grass = n.ramp(nz.outputs["Fac"], [(0.3, (0.07, 0.085, 0.03)), (0.6, (0.13, 0.13, 0.055)), (0.8, (0.2, 0.18, 0.09))])
    dirt = n.ramp(nz.outputs["Fac"], [(0.3, (0.12, 0.095, 0.068)), (0.7, (0.17, 0.135, 0.098))])
    dirt = n.mix(n.math("MULTIPLY", rut, 0.6), dirt, (0.07, 0.052, 0.038))
    crown = n.math("MULTIPLY", n.smooth(0.45, 0.25, n.math("ABSOLUTE", dy)), track)
    dirt = n.mix(n.math("MULTIPLY", crown, 0.7), dirt, (0.1, 0.11, 0.045))
    col = n.mix(track, grass, dirt)
    col = n.mix(0.4, col, n.ramp(fine.outputs["Fac"], [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.0, 1.0, 1.0))]), blend="MULTIPLY")
    col = n.mix(puddle, col, (0.012, 0.012, 0.012))
    n.link(col, n.bsdf.inputs["Base Color"])
    n.link(n.fmix(puddle, 0.9, 0.02), n.bsdf.inputs["Roughness"])
    n.link(n.fmix(puddle, 0.25, 1.0), n.bsdf.inputs["Specular IOR Level"])
    rip = n.new("ShaderNodeTexNoise", Scale=9.0, Detail=2.0)
    n.link(pos, rip.inputs["Vector"])
    h = n.math("ADD", n.math("MULTIPLY", fine.outputs["Fac"], n.math("SUBTRACT", 1.0, puddle)), n.math("MULTIPLY", rip.outputs["Fac"], n.math("MULTIPLY", puddle, 0.05)))
    bump = n.new("ShaderNodeBump", Strength=0.5, Distance=0.02)
    n.link(h, bump.inputs["Height"])
    n.link(bump.outputs["Normal"], n.bsdf.inputs["Normal"])
    return finish_aerial(m, n)


def headland_z(x, y):
    dy = y + 66.5
    z = 0.04 * smoothstep(-57.0, -58.5, y)                      # the verge sits a little above the field's edge
    if abs(dy) < 2.3:
        rd = abs(abs(dy) - 0.8)
        z += -0.07 * (1 - smoothstep(0.12, 0.32, rd)) - 0.02
    return z + noise.noise(Vector((x * 0.2, y * 0.2, 4.4))) * 0.04


# ---------------------------------------------------------------------------- sky
def sky_world(sc):
    """The physical sky (clean late-afternoon air, no sun disc: the sun lamp is the sun) under a deck of
    fair-weather cumulus: clouds projected on a plane 1.8 km up, lit warm on the sun side with bright edges,
    blue-grey on their shadowed undersides, thinning into the haze at the horizon."""
    w = bpy.data.worlds.new("sky")
    n = Nodes(w)
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc = n.new("ShaderNodeTexCoord")
    d = n.vmath("NORMALIZE", tc.outputs["Generated"])
    sky = sky_node(nt)
    n.link(d, sky.inputs["Vector"])
    dx, dy, dz = n.sep(d)
    dzc = n.math("MAXIMUM", dz, 0.012)
    H = 1800.0
    u = n.math("DIVIDE", n.math("MULTIPLY", dx, H), dzc)
    v = n.math("DIVIDE", n.math("MULTIPLY", dy, H), dzc)
    uv = n.comb(n.math("ADD", u, 1700.0), n.math("ADD", v, -900.0), 0.0)
    s = sun_dir()
    sxy = Vector((s.x, s.y, 0)).normalized()

    def density(offset):
        q = n.vmath("ADD", uv, (sxy.x * offset, sxy.y * offset, 0.0))
        wp = n.new("ShaderNodeTexNoise", Scale=1 / 2600.0, Detail=3.0, Roughness=0.5)
        n.link(q, wp.inputs["Vector"])
        q2 = n.vmath("ADD", q, n.vmath("SCALE", n.vmath("SUBTRACT", wp.outputs["Color"], (0.5, 0.5, 0.5)), 1400.0))
        base = n.new("ShaderNodeTexNoise", Scale=1 / 2100.0, Detail=9.0, Roughness=0.58)
        n.link(q2, base.inputs["Vector"])
        cover = n.new("ShaderNodeTexNoise", Scale=1 / 9000.0, Detail=2.0)
        n.link(q, cover.inputs["Vector"])
        thr = n.math("SUBTRACT", 0.555, n.math("MULTIPLY", n.math("SUBTRACT", cover.outputs["Fac"], 0.5), 0.4))
        return n.math("SUBTRACT", base.outputs["Fac"], thr)

    c0 = density(0.0)
    c1 = density(180.0)
    dens = n.smooth(0.0, 0.16, c0)
    dens = n.math("MULTIPLY", dens, n.smooth(0.015, 0.09, dz))      # thin out into the horizon haze
    # lit: forward-scattering lobe towards the sun, self-shadow from the density towards the sun
    cosg = n.vmath("DOT_PRODUCT", d, tuple(s))
    lobe = n.math("ADD", 0.45, n.math("MULTIPLY", n.math("POWER", n.math("MAXIMUM", cosg, 0.0), 6.0), 1.6))
    shade = n.smooth(0.12, -0.04, n.math("SUBTRACT", c1, c0))      # 1 where the cloud thins towards the sun
    edge = n.smooth(0.07, 0.0, c0)                                   # thin edges glow
    lit = n.math("ADD", n.math("MULTIPLY", shade, 0.75), n.math("MULTIPLY", edge, 0.35))
    rgb = SUN_RGB[(SUN["el"], SUN["aerosol"])]
    sun_rad = tuple(c / math.pi * 0.62 for c in rgb)                 # a white diffuser in sunlight, a bit less
    lit_col = n.mix(1.0, (1, 1, 1), sun_rad, blend="MULTIPLY")
    lit_col = n.vmath("SCALE", lit_col, lobe)
    under = (1.15, 1.45, 2.1)                                        # blue-grey undersides (lit by the sky)
    ccol = n.mix(n.math("MINIMUM", n.math("MULTIPLY", lit, 0.9), 1.0), under, lit_col)
    out = n.mix(dens, sky.outputs[0], ccol)
    # below the horizon (never seen past the terrain, but lights the scene): sky colour with a dark ground
    below = n.smooth(0.0, -0.05, dz)
    out = n.mix(below, out, (0.06, 0.06, 0.05))
    n.link(out, bg.inputs[0])
    bg.inputs[1].default_value = 1.0
    sc.world = w


def sun_lamp(sc):
    rgb = SUN_RGB[(SUN["el"], SUN["aerosol"])]
    e = max(rgb)
    ld = bpy.data.lights.new("sun", "SUN")
    ld.energy = e
    ld.color = tuple(c / e for c in rgb)
    ld.angle = rad(0.53)
    ob = bpy.data.objects.new("sun", ld)
    sc.collection.objects.link(ob)
    ob.rotation_euler = (-sun_dir()).to_track_quat("-Z", "Y").to_euler()
    return ob


# ---------------------------------------------------------------------------- ground meshes
def build_ground(sc):
    import numpy as np
    # 1. the field: graded rectilinear grid, fine across the rows near the camera; split into the true-displacement
    #    near patch (adaptive subdivision) and the rest, sharing their boundary vertices exactly
    xs = graded(FMESH[0], FMESH[1], -40.09, 30.97, ROW_W / 8, 1.5)
    ys = graded(FMESH[2], FMESH[3], -56.0, 62.0, 0.25, 2.5)
    nx, ny = len(xs), len(ys)
    V = [(x, y, field_z(x, y)) for y in ys for x in xs]
    near_f, far_f = [], []
    for j in range(ny - 1):
        yc = (ys[j] + ys[j + 1]) / 2
        for i in range(nx - 1):
            xc = (xs[i] + xs[i + 1]) / 2
            q = (j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i)
            (near_f if NEAR[0] < xc < NEAR[1] and NEAR[2] < yc < NEAR[3] else far_f).append(q)
    print(f"field grid {nx}×{ny} = {nx * ny} verts", flush=True)

    def sub(name, faces, mat):
        used = sorted({k for f in faces for k in f})
        remap = {k: i for i, k in enumerate(used)}
        return mesh_object(name, [V[k] for k in used], [tuple(remap[k] for k in f) for f in faces], [mat])
    near = sub("field_near", near_f, field_material(True))
    if os.environ.get("AIV_NODICE"):
        return near
    sm = near.modifiers.new("dice", "SUBSURF")
    sm.subdivision_type = "SIMPLE"
    sm.use_adaptive_subdivision = True
    sm.adaptive_space = "PIXEL"
    sm.adaptive_pixel_size = 4.0       # micro-polygons ~4 px (bump adds the finer grain): memory on an 8 GB Mac
    sm.levels = 0
    sub("field", far_f, field_material(False))
    # 2. the headland strip: verge, farm track, verge, under the fence and the utility line
    hx = [FIELD[0] - 12 + i * 1.0 for i in range(int(FIELD[1] - FIELD[0] + 30))]
    hy = [-80.0 + i * 0.25 for i in range(93)]
    HV = [(x, y, headland_z(x, y)) for y in hy for x in hx]
    HF = [(j * len(hx) + i, j * len(hx) + i + 1, (j + 1) * len(hx) + i + 1, (j + 1) * len(hx) + i) for j in range(len(hy) - 1) for i in range(len(hx) - 1)]
    mesh_object("headland", HV, HF, [headland_material()])
    # 3. terrain to the horizon: a polar grid (rings widen with distance), just below the field and headland
    rings = [0.0]
    r, s = 0.0, 4.0
    while r < 9000:
        s = min(s * 1.07, 400.0)
        r += s
        rings.append(r)
    na = 720
    TV, TF = [], []
    for ri, r in enumerate(rings):
        for k in range(na):
            a = k / na * math.tau
            x, y = -60 + r * math.cos(a), -40 + r * math.sin(a)
            z = relief(x, y)
            if FIELD[0] - 14 < x < FIELD[1] + 14 and -82 < y < FIELD[3]:
                z -= 0.06 if y < 175 else 0.0
            TV.append((x, y, z))
    for ri in range(len(rings) - 1):
        for k in range(na):
            a0, a1 = ri * na + k, ri * na + (k + 1) % na
            TF.append((a0, a1, a1 + na, a0 + na))
    t = mesh_object("terrain", TV, TF, [terrain_material()])
    print(f"terrain {len(TV)} verts", flush=True)
    return near


# ---------------------------------------------------------------------------- vegetation generators
def leaf_material(name, greens, dry=0.0):
    """Leaves: per-tree colour (Object Info random) and per-leaf variation (random per island), a waxy sheen,
    and light passing through them (translucent), so trees against the low sun glow at their edges."""
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    oi = n.new("ShaderNodeObjectInfo")
    geo = n.new("ShaderNodeNewGeometry")
    pick = n.math("ADD", n.math("MULTIPLY", oi.outputs["Random"], 0.75), n.math("MULTIPLY", geo.outputs["Random Per Island"], 0.25))
    col = n.ramp(pick, [(i / (len(greens) - 1), c) for i, c in enumerate(greens)])
    if dry:
        col = n.mix(n.math("MULTIPLY", n.math("GREATER_THAN", geo.outputs["Random Per Island"], 1 - dry), 0.8), col, (0.35, 0.27, 0.1))
    n.link(col, n.bsdf.inputs["Base Color"])
    n.bsdf.inputs["Roughness"].default_value = 0.5
    n.bsdf.inputs["Specular IOR Level"].default_value = 0.45
    tr = n.new("ShaderNodeBsdfTranslucent")
    n.link(n.mix(1.0, col, (1.4, 1.5, 0.7), blend="MULTIPLY"), tr.inputs["Color"])
    mx = n.new("ShaderNodeMixShader")
    mx.inputs[0].default_value = 0.32
    n.link(n.bsdf.outputs[0], mx.inputs[1])
    n.link(tr.outputs[0], mx.inputs[2])
    out = m.node_tree.nodes["Material Output"]
    n.link(aerial(n, mx.outputs[0]), out.inputs["Surface"])
    return m


def bark_material(name, col=(0.11, 0.095, 0.08)):
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (9.0, 9.0, 1.6)
    n.link(tc.outputs["Object"], mp.inputs["Vector"])
    fur = n.new("ShaderNodeTexNoise", Scale=3.0, Detail=8.0, Roughness=0.7, Distortion=0.6)
    n.link(mp.outputs[0], fur.inputs["Vector"])
    moss = n.new("ShaderNodeTexNoise", Scale=1.2, Detail=4.0)
    n.link(tc.outputs["Object"], moss.inputs["Vector"])
    c = n.mix(n.smooth(0.55, 0.7, moss.outputs["Fac"]), col, (0.07, 0.085, 0.04))
    c = n.mix(0.6, c, n.ramp(fur.outputs["Fac"], [(0.35, (0.55, 0.55, 0.55)), (0.65, (1.15, 1.15, 1.15))]), blend="MULTIPLY")
    n.link(c, n.bsdf.inputs["Base Color"])
    n.bsdf.inputs["Roughness"].default_value = 0.88
    bump = n.new("ShaderNodeBump", Strength=0.8, Distance=0.02)
    n.link(fur.outputs["Fac"], bump.inputs["Height"])
    n.link(bump.outputs["Normal"], n.bsdf.inputs["Normal"])
    return finish_aerial(m, n)


TREE_KINDS = {
    #            height, trunk r, fork h, levels: (children, angle°, length ratio, start), leaf size, leaves/twig, up bias
    "oak":     dict(H=14.0, R=0.36, fork=3.2, kids=[(5, 48, 0.62, 0.0), (6, 42, 0.5, 0.2), (8, 45, 0.42, 0.25)], leaf=0.27, per=95, up=[0.25, 0.15, 0.3], spread=1.0),
    "oak2":    dict(H=11.0, R=0.3, fork=2.4, kids=[(6, 55, 0.66, 0.0), (6, 40, 0.5, 0.2), (7, 45, 0.45, 0.25)], leaf=0.26, per=95, up=[0.2, 0.1, 0.3], spread=1.15),
    "ash":     dict(H=16.0, R=0.3, fork=5.0, kids=[(5, 38, 0.5, 0.0), (6, 40, 0.5, 0.25), (7, 40, 0.42, 0.3)], leaf=0.26, per=90, up=[0.45, 0.3, 0.35], spread=0.85),
    "poplar":  dict(H=24.0, R=0.32, fork=0.0, kids=[(46, 22, 0.16, 0.08), (6, 30, 0.45, 0.2), (0, 0, 0, 0)], leaf=0.26, per=85, up=[1.2, 0.9, 0.6], spread=0.4, columnar=True, branch_leaves=2.5),
    "poplar2": dict(H=20.0, R=0.28, fork=0.0, kids=[(40, 26, 0.18, 0.06), (6, 32, 0.45, 0.2), (0, 0, 0, 0)], leaf=0.26, per=85, up=[1.0, 0.8, 0.6], spread=0.45, columnar=True, branch_leaves=2.5),
    "willow":  dict(H=10.0, R=0.32, fork=2.2, kids=[(6, 50, 0.6, 0.0), (6, 45, 0.55, 0.2), (6, 50, 0.5, 0.2)], leaf=0.22, per=90, up=[0.3, 0.0, -0.45], spread=1.1),
    "shrub":   dict(H=3.2, R=0.07, fork=0.0, kids=[(7, 32, 0.9, 0.0), (6, 45, 0.45, 0.2), (0, 0, 0, 0)], leaf=0.15, per=85, up=[0.35, 0.25, 0.2], spread=1.0, multistem=True),
    "shrub2":  dict(H=2.4, R=0.06, fork=0.0, kids=[(9, 40, 0.9, 0.0), (5, 50, 0.5, 0.2), (0, 0, 0, 0)], leaf=0.14, per=85, up=[0.25, 0.2, 0.2], spread=1.2, multistem=True),
}


def make_tree(seed, kind, bark, leaf):
    """A procedural tree: a tapered, bending trunk, recursive branches (phyllotaxis, up/down bias per level),
    twigs carrying real leaf-shaped blades (a pointed oval folded along the midrib), each a separate island so
    the leaf material varies leaf by leaf."""
    from mathutils import Quaternion
    K = TREE_KINDS[kind]
    rnd = random.Random(seed)
    V, F, LV, LF = [], [], [], []
    up = Vector((0, 0, 1))

    def tube(pts, rads, sides):
        base, n_ = len(V), len(pts)
        t = (pts[1] - pts[0]).normalized()
        nrm = t.orthogonal().normalized()
        for i, p in enumerate(pts):
            if 0 < i < n_ - 1:
                t2 = (pts[i + 1] - pts[i - 1]).normalized()
            elif i == n_ - 1:
                t2 = (pts[i] - pts[i - 1]).normalized()
            else:
                t2 = t
            ax = t.cross(t2)
            if ax.length > 1e-6:
                nrm = Quaternion(ax.normalized(), t.angle(t2)) @ nrm
            t = t2
            b = t.cross(nrm)
            for k in range(sides):
                a = k / sides * math.tau
                V.append(tuple(p + (nrm * math.cos(a) + b * math.sin(a)) * rads[i]))
        for i in range(n_ - 1):
            for k in range(sides):
                a0, a1 = base + i * sides + k, base + i * sides + (k + 1) % sides
                F.append((a0, a1, a1 + sides, a0 + sides))

    def leaf_at(p, d):
        L = K["leaf"] * rnd.uniform(0.75, 1.25)
        W = L * rnd.uniform(0.5, 0.62)
        x = d.normalized()
        y = x.cross(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))).normalized()
        z = x.cross(y)
        if z.z < 0:
            y, z = -y, -z
        shape = [(0, 0, 0), (0.3, 0.45, 0.12), (0.72, 0.36, 0.12), (1.0, 0, 0), (0.72, -0.36, 0.12), (0.3, -0.45, 0.12)]
        base = len(LV)
        for u, w, f in shape:
            LV.append(tuple(p + x * (u * L) + y * (w * W) + z * (f * W * 0.5)))
        LF.append(tuple(range(base, base + 6)))

    def grow(p0, d, length, radius, level):
        segs = max(3, min(10, int(length / 0.8) + 2))
        pts, rads = [p0.copy()], [radius]
        p, dd = p0.copy(), d.copy()
        for i in range(1, segs + 1):
            dd = (dd + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.18 + up * K["up"][min(level, 2)] * 0.12).normalized()
            p = p + dd * (length / segs)
            pts.append(p.copy())
            rads.append(radius * (1 - i / segs * 0.75))
        sides = 10 if level == 0 else 6 if level == 1 else 4
        tube(pts, rads, sides)
        kids = K["kids"][level] if level < 3 else (0, 0, 0, 0)
        cnt, ang, lr, start = kids
        if cnt == 0:
            # a twig: leaves along it and a spray at its tip
            for i in range(K["per"]):
                u = rnd.uniform(0.15, 1.0)
                k = min(int(u * segs), segs - 1)
                q = pts[k].lerp(pts[k + 1], u * segs - k)
                dl = (dd + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.6, 1))) * 1.1).normalized()
                leaf_at(q + dl * rnd.uniform(0, 0.25) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * K["leaf"] * 1.6, dl)
            return
        if K["kids"][min(level + 1, 2)][0] == 0 or level == 2:
            for i in range(int(K["per"] * K.get("branch_leaves", 0.6))):     # foliage along the branch itself
                u = rnd.uniform(0.25, 1.0)
                k = min(int(u * segs), segs - 1)
                q = pts[k].lerp(pts[k + 1], u * segs - k)
                dl = (dd + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.6, 1))) * 1.3).normalized()
                leaf_at(q + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * K["leaf"] * 2.2, dl)
        phi = rnd.random() * math.tau
        for c in range(cnt):
            u = start + (1 - start) * (c + rnd.random() * 0.8) / cnt
            if K.get("columnar") and level == 0:
                u = 0.06 + 0.92 * (c + rnd.random()) / cnt
            k = min(int(u * segs), segs - 1)
            q = pts[k].lerp(pts[k + 1], u * segs - k)
            rq = lerp(rads[k], rads[k + 1], u * segs - k)
            phi += rad(137.5) + rnd.uniform(-0.3, 0.3)
            perp = d.orthogonal().normalized()
            perp = Quaternion(d, phi) @ perp
            a = rad(ang * rnd.uniform(0.8, 1.2))
            cdir = (d * math.cos(a) + perp * math.sin(a) * K["spread"]).normalized()
            cdir = (cdir + up * K["up"][min(level + 1, 2)] * 0.5).normalized()
            clen = length * lr * rnd.uniform(0.8, 1.2)
            if K.get("columnar") and level == 0:
                env = math.sin(math.pi * clamp(u * 1.05)) ** 0.6           # a spindle: longest low-middle, short at the top
                clen = K["H"] * lr * (0.35 + env) * rnd.uniform(0.85, 1.15)
            elif level == 0:
                clen = (K["H"] - K["fork"]) * lr * rnd.uniform(0.8, 1.15)
            grow(q, cdir, clen, max(rq * 0.62, 0.012), level + 1)

    if K.get("multistem"):
        for s in range(K["kids"][0][0]):
            a = rnd.random() * math.tau
            tilt = rad(K["kids"][0][1] * rnd.uniform(0.3, 1.0))
            d = Vector((math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt)))
            grow(Vector((rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), -0.05)), d, K["H"] * rnd.uniform(0.7, 1.0), K["R"], 1)
    elif K.get("columnar"):
        grow(Vector((0, 0, -0.2)), Vector((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), 1)).normalized(), K["H"], K["R"], 0)
    else:
        # trunk to the fork, then limbs from the fork
        trunk_top = Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), K["fork"]))
        pts = [Vector((0, 0, -0.3)), Vector((0, 0, K["fork"] * 0.5)), trunk_top]
        tube(pts, [K["R"] * 1.25, K["R"], K["R"] * 0.85], 12)
        K0 = K["kids"][0]
        phi = rnd.random() * math.tau
        for c in range(K0[0]):
            phi += math.tau / K0[0] + rnd.uniform(-0.4, 0.4)
            a = rad(K0[1] * rnd.uniform(0.7, 1.2))
            d = Vector((math.cos(phi) * math.sin(a) * K["spread"], math.sin(phi) * math.sin(a) * K["spread"], math.cos(a))).normalized()
            grow(trunk_top - Vector((0, 0, rnd.uniform(0, 0.6))), d, (K["H"] - K["fork"]) * K0[2] * rnd.uniform(0.8, 1.15), K["R"] * 0.6, 1)
    wood = mesh_object(f"tree_{kind}_{seed}_wood", V, F, [bark], link=False)
    leaves = mesh_object(f"tree_{kind}_{seed}_leaves", LV, LF, [leaf], link=False)
    # one object: join leaves into the wood mesh
    import bmesh as _bm
    bm = _bm.new()
    bm.from_mesh(wood.data)
    me2 = leaves.data
    off = len(bm.verts)
    bm.verts.ensure_lookup_table()
    nv = [bm.verts.new(v.co) for v in me2.vertices]
    for poly in me2.polygons:
        f = bm.faces.new([nv[i] for i in poly.vertices])
        f.material_index = 1
        f.smooth = False
    me = bpy.data.meshes.new(f"tree_{kind}_{seed}")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(bark)
    me.materials.append(leaf)
    ob = bpy.data.objects.new(f"tree_{kind}_{seed}", me)
    print(f"tree {kind:8s} seed {seed}: {len(F)} wood quads, {len(LF)} leaves", flush=True)
    return ob


def grass_material(name, dry=0.0):
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    geo = n.new("ShaderNodeNewGeometry")
    oi = n.new("ShaderNodeObjectInfo")
    tc = n.new("ShaderNodeTexCoord")
    hgt = n.sep(tc.outputs["Object"])[2]
    pick = n.math("ADD", n.math("MULTIPLY", geo.outputs["Random Per Island"], 0.6), n.math("MULTIPLY", oi.outputs["Random"], 0.4))
    green = n.ramp(pick, [(0.0, (0.05, 0.1, 0.025)), (0.5, (0.09, 0.15, 0.035)), (1.0, (0.16, 0.19, 0.06))])
    straw = n.ramp(pick, [(0.0, (0.28, 0.22, 0.1)), (1.0, (0.42, 0.34, 0.17))])
    col = n.mix(n.math("ADD", dry, n.math("MULTIPLY", n.math("GREATER_THAN", pick, 1 - dry * 0.5), 0.6)), green, straw)
    col = n.mix(n.smooth(0.0, 0.25, hgt), (0.04, 0.05, 0.02), col)
    n.link(col, n.bsdf.inputs["Base Color"])
    n.bsdf.inputs["Roughness"].default_value = 0.55
    tr = n.new("ShaderNodeBsdfTranslucent")
    n.link(col, tr.inputs["Color"])
    mx = n.new("ShaderNodeMixShader")
    mx.inputs[0].default_value = 0.3
    n.link(n.bsdf.outputs[0], mx.inputs[1])
    n.link(tr.outputs[0], mx.inputs[2])
    out = m.node_tree.nodes["Material Output"]
    n.link(aerial(n, mx.outputs[0]), out.inputs["Surface"])
    return m


def make_clump(seed, mat, blades=32, h=(0.25, 0.6), radius=0.12, seedheads=False):
    """A tussock of grass: curved, tapering blades (4 segments each) splaying out from a tight base."""
    rnd = random.Random(seed)
    V, F = [], []
    for b in range(blades):
        a = rnd.random() * math.tau
        r0 = rnd.random() ** 0.5 * radius * 0.4
        L = rnd.uniform(*h)
        lean = rnd.uniform(0.15, 0.7)
        w0 = rnd.uniform(0.004, 0.008)
        ca, sa = math.cos(a), math.sin(a)
        tw = rnd.uniform(-0.6, 0.6)
        base = len(V)
        for i in range(5):
            u = i / 4
            out_ = r0 + lean * L * u * u
            z = L * u * (1 - 0.35 * lean * u)
            w = w0 * (1 - u * 0.92)
            px, py = ca * out_, sa * out_
            nx_, ny_ = -sa * math.cos(tw * u) , ca * math.cos(tw * u)
            V.append((px + nx_ * w, py + ny_ * w, z))
            V.append((px - nx_ * w, py - ny_ * w, z))
        for i in range(4):
            F.append((base + i * 2, base + i * 2 + 1, base + i * 2 + 3, base + i * 2 + 2))
    if seedheads:
        for b in range(5):
            a = rnd.random() * math.tau
            L = h[1] * rnd.uniform(1.0, 1.3)
            base = len(V)
            for i in range(4):
                z = L * (0.7 + 0.3 * i / 3)
                V.append((math.cos(a) * 0.05 * i / 3 + 0.006, math.sin(a) * 0.05 * i / 3, z))
                V.append((math.cos(a) * 0.05 * i / 3 - 0.006, math.sin(a) * 0.05 * i / 3, z))
            for i in range(3):
                F.append((base + i * 2, base + i * 2 + 1, base + i * 2 + 3, base + i * 2 + 2))
    return mesh_object(f"clump{seed}", V, F, [mat], link=False)


# ---------------------------------------------------------------------------- man-made things in the landscape
def wood_material(name, col=(0.2, 0.16, 0.11)):
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (30.0, 30.0, 1.0)
    n.link(tc.outputs["Object"], mp.inputs["Vector"])
    g = n.new("ShaderNodeTexNoise", Scale=4.0, Detail=6.0, Distortion=1.5)
    n.link(mp.outputs[0], g.inputs["Vector"])
    n.link(n.mix(0.6, col, n.ramp(g.outputs["Fac"], [(0.3, (0.6, 0.6, 0.6)), (0.7, (1.1, 1.1, 1.1))]), blend="MULTIPLY"), n.bsdf.inputs["Base Color"])
    n.bsdf.inputs["Roughness"].default_value = 0.85
    return finish_aerial(m, n)


def plain(name, col, rough=0.5, metal=0.0):
    m = principled(name, col, rough=rough, metal=metal)
    return finish_aerial(m, Nodes(m))


def tube_mesh(name, pts, r, sides, mat, link=False):
    V, F = [], []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = t.orthogonal().normalized()
        b = t.cross(a)
        for k in range(sides):
            ang = k / sides * math.tau
            V.append(tuple(p + (a * math.cos(ang) + b * math.sin(ang)) * r))
    for i in range(len(pts) - 1):
        for k in range(sides):
            a0, a1 = i * sides + k, i * sides + (k + 1) % sides
            F.append((a0, a1, a1 + sides, a0 + sides))
    return V, F


def merge_meshes(name, parts, mats, link=True):
    """parts: list of (V, F, material index) -> one mesh object."""
    V, F, MI = [], [], []
    for pv, pf, mi in parts:
        o = len(V)
        V += pv
        F += [tuple(k + o for k in f) for f in pf]
        MI += [mi] * len(pf)
    return mesh_object(name, V, F, mats, mat_index=MI, link=link)


def box_vf(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    V = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return V, F


def cyl_vf(r0, r1, z0, z1, sides=12, cx=0.0, cy=0.0, cap=True):
    V, F = [], []
    for z, r in ((z0, r0), (z1, r1)):
        for k in range(sides):
            a = k / sides * math.tau
            V.append((cx + math.cos(a) * r, cy + math.sin(a) * r, z))
    for k in range(sides):
        F.append((k, (k + 1) % sides, sides + (k + 1) % sides, sides + k))
    if cap:
        F.append(tuple(range(sides - 1, -1, -1)))
        F.append(tuple(range(sides, 2 * sides)))
    return V, F


def xform(vf, M):
    V, F = vf
    return [tuple(M @ Vector(v)) for v in V], F


def build_landscape(sc, rnd):
    """Fence, utility line, irrigation main, farmstead."""
    import numpy as np
    wood = wood_material("post_wood")
    grey_wood = wood_material("pole_wood", (0.16, 0.14, 0.12))
    wire = plain("wire", (0.35, 0.35, 0.36), rough=0.35, metal=1.0)
    galv = plain("galv", (0.55, 0.56, 0.58), rough=0.32, metal=1.0)
    alu = plain("alu", (0.36, 0.36, 0.35), rough=0.55, metal=0.85)
    ceramic = plain("insulator", (0.32, 0.36, 0.4), rough=0.15)
    # fence along the headland: posts every 3.5 m, four wire strands sagging a little between posts
    fy = -70.2
    posts, parts = [], []
    pv = [cyl_vf(0.055, 0.05, -0.3, 1.25, 8)]
    post_src = [merge_meshes(f"post{i}", [(*pv[0], 0)], [wood], link=False) for i in range(1)]
    xs = np.arange(FIELD[0] - 8, FIELD[1] + 14, 3.5)
    for x in xs:
        z = headland_z(x, fy)
        posts.append((x, fy + rnd.uniform(-0.05, 0.05), z, rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), rnd.uniform(0, 6.28), 1, 1, 1, 0))
    instancer("fence_posts", post_src, posts)
    for h in (0.45, 0.7, 0.95, 1.18):
        pts = []
        for i in range(len(xs) - 1):
            for k in range(4):
                u = k / 4
                x = xs[i] + (xs[i + 1] - xs[i]) * u
                pts.append(Vector((x, fy - 0.06, headland_z(x, fy) + h - 0.04 * math.sin(math.pi * u))))
        V, F = tube_mesh("w", pts, 0.006, 4, wire)
        parts.append((V, F, 0))
    merge_meshes("fence_wire", parts, [wire])
    # the utility line: wooden poles every 62 m along the track, crossarm, insulators, three sagging conductors
    py = -74.6
    pole_parts = [(*cyl_vf(0.15, 0.11, -1.5, 11.0, 10), 0), (*box_vf((-0.06, -1.25, 10.2), (0.06, 1.25, 10.34)), 0)]
    for yo in (-1.05, 0.0, 1.05):
        pole_parts.append((*cyl_vf(0.05, 0.035, 10.34, 10.62, 8, cy=yo), 1))
    pole_src = [merge_meshes("pole", pole_parts, [grey_wood, ceramic], link=False)]
    pxs = np.arange(-3400.0, 3400.0, 62.0)
    poles = [(x, py, relief(x, py) + (headland_z(x, py) if FIELD[0] - 12 < x < FIELD[1] + 17 else 0.0), 0, rnd.uniform(-0.015, 0.015), rnd.uniform(-0.03, 0.03), 1, 1, 1, 0) for x in pxs]
    instancer("poles", pole_src, poles)
    parts = []
    for yo in (-1.05, 0.0, 1.05):                                     # the crossarm runs across the line (along y)
        for i in range(len(poles) - 1):
            x0, x1 = poles[i][0], poles[i + 1][0]
            z0, z1 = poles[i][2] + 10.62, poles[i + 1][2] + 10.62
            pts = [Vector((lerp(x0, x1, k / 12), py + yo, lerp(z0, z1, k / 12) - 1.1 * math.sin(math.pi * k / 12))) for k in range(13)]
            V, F = tube_mesh("c", pts, 0.011, 4, wire)
            parts.append((V, F, 0))
    merge_meshes("conductors", parts, [wire])
    # irrigation main along the field edge, risers with impact sprinklers every 9.1 m
    iy = -57.7
    pts = [Vector((x, iy, 0.12)) for x in np.arange(FIELD[0], FIELD[1] + 0.1, 4.0)]
    for p in pts:
        p.z = headland_z(p.x, iy) + 0.07
    V, F = tube_mesh("main", pts, 0.1, 14, alu)
    merge_meshes("irrigation_main", [(V, F, 0)], [alu])
    riser = merge_meshes("riser", [(*cyl_vf(0.018, 0.018, 0.0, 1.5, 8), 0), (*box_vf((-0.02, -0.12, 1.48), (0.02, 0.12, 1.54)), 0),
                                   (*cyl_vf(0.03, 0.02, 1.5, 1.62, 8), 0)], [galv], link=False)
    risers = [(x, iy, headland_z(x, iy) + 0.18, 0, 0, rnd.uniform(0, 6.28), 1, 1, 1, 0) for x in np.arange(FIELD[0] + 3, FIELD[1], 9.14)]
    instancer("risers", [riser], risers)
    # farmstead: a gabled barn, a machine shed, two galvanised silos and a house, among trees
    fx, fy2 = -330.0, -205.0
    red = plain("barn_red", (0.23, 0.07, 0.05), rough=0.6)
    roof = plain("roof_metal", (0.3, 0.31, 0.32), rough=0.4, metal=0.8)
    white = plain("house_white", (0.6, 0.58, 0.54), rough=0.7)
    dark = plain("dark_roof", (0.07, 0.065, 0.06), rough=0.6)
    door = plain("door", (0.04, 0.035, 0.03), rough=0.8)

    def gable(cx, cy, w, l, h, rh, wall, rf, rot=0.0):
        M = Matrix.Translation((cx, cy, relief(cx, cy))) @ Matrix.Rotation(rot, 4, "Z")
        V = [(-w / 2, -l / 2, 0), (w / 2, -l / 2, 0), (w / 2, l / 2, 0), (-w / 2, l / 2, 0), (-w / 2, -l / 2, h), (w / 2, -l / 2, h), (w / 2, l / 2, h), (-w / 2, l / 2, h), (0, -l / 2, h + rh), (0, l / 2, h + rh)]
        F = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 8), (6, 7, 9)]
        RV = [(-w / 2 - 0.5, -l / 2 - 0.4, h - 0.25), (0, -l / 2 - 0.4, h + rh), (0, l / 2 + 0.4, h + rh), (-w / 2 - 0.5, l / 2 + 0.4, h - 0.25), (w / 2 + 0.5, -l / 2 - 0.4, h - 0.25), (w / 2 + 0.5, l / 2 + 0.4, h - 0.25)]
        RF = [(0, 1, 2, 3), (1, 4, 5, 2)]
        return [(xform((V, F), M)[0], F, wall), (xform((RV, RF), M)[0], RF, rf)]
    parts = gable(fx, fy2, 16, 30, 7, 5, 0, 1, rad(8)) + gable(fx + 34, fy2 - 10, 14, 22, 5.5, 2.5, 2, 1, rad(8)) + gable(fx - 30, fy2 + 18, 9, 12, 5.5, 3.5, 3, 4, rad(-20))
    for k, (sx, sy, r, h) in enumerate(((fx + 22, fy2 + 16, 3.4, 17), (fx + 30, fy2 + 18, 3.0, 15))):
        z0 = relief(sx, sy)
        V, F = cyl_vf(r, r, z0, z0 + h, 28, sx, sy)
        parts.append((V, F, 5))
        dv = []
        for i in range(6):
            a = i / 5 * math.pi / 2
            dv.append((math.cos(a) * r, math.sin(a) * r * 0.55))
        DV, DF = [], []
        for i, (rr, zz) in enumerate(dv):
            for k2 in range(28):
                a2 = k2 / 28 * math.tau
                DV.append((sx + math.cos(a2) * rr, sy + math.sin(a2) * rr, z0 + h + zz))
        for i in range(5):
            for k2 in range(28):
                a0, a1 = i * 28 + k2, i * 28 + (k2 + 1) % 28
                DF.append((a0, a1, a1 + 28, a0 + 28))
        parts.append((DV, DF, 5))
    merge_meshes("farmstead", parts, [red, roof, galv, white, dark, galv])


def build_vegetation(sc, rnd, cam_eyes):
    """Trees (8 procedural variants as instances), hedgerows, verge grass, weeds."""
    import numpy as np
    bark = bark_material("bark")
    bark_pale = bark_material("bark_pale", (0.2, 0.19, 0.17))
    greens_oak = [(0.035, 0.07, 0.018), (0.05, 0.09, 0.022), (0.07, 0.11, 0.03), (0.09, 0.12, 0.03)]
    greens_pop = [(0.05, 0.1, 0.025), (0.07, 0.13, 0.03), (0.1, 0.15, 0.04)]
    greens_shr = [(0.04, 0.075, 0.02), (0.06, 0.1, 0.025), (0.09, 0.1, 0.03), (0.12, 0.12, 0.035)]
    leaf_oak = leaf_material("leaf_oak", greens_oak, dry=0.04)
    leaf_pop = leaf_material("leaf_poplar", greens_pop)
    leaf_shr = leaf_material("leaf_shrub", greens_shr, dry=0.06)
    spec = [("oak", 1, bark, leaf_oak), ("oak", 2, bark, leaf_oak), ("oak2", 3, bark, leaf_oak), ("ash", 4, bark_pale, leaf_oak),
            ("poplar", 5, bark_pale, leaf_pop), ("poplar2", 6, bark_pale, leaf_pop), ("willow", 7, bark, leaf_pop),
            ("shrub", 8, bark, leaf_shr), ("shrub2", 9, bark, leaf_shr), ("shrub", 10, bark, leaf_shr)]
    trees = [make_tree(seed * 31 + 7, kind, b, l) for kind, seed, b, l in spec]
    OAKS, POPS, SHRUBS = [0, 1, 2, 3, 6], [4, 5], [7, 8, 9]
    pts = []

    def put(x, y, idx, s=1.0, z=None):
        zz = relief(x, y) if z is None else z
        pts.append((x, y, zz - 0.05, rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), rnd.uniform(0, math.tau), s, s, s * rnd.uniform(0.9, 1.1), idx))
    # hedgerow behind the utility line: shrubs with gaps, standard trees here and there
    x = FIELD[0] - 10
    while x < FIELD[1] + 30:
        if noise.noise(Vector((x * 0.03, 0.5, 0.2))) > -0.25:
            put(x + rnd.uniform(-0.8, 0.8), -78.0 + rnd.uniform(-0.8, 0.8), rnd.choice(SHRUBS), rnd.uniform(0.75, 1.25), z=0.0)
        if rnd.random() < 0.07:
            put(x, -78.5 + rnd.uniform(-1, 1), rnd.choice(OAKS), rnd.uniform(0.7, 1.05), z=0.0)
        x += rnd.uniform(1.8, 3.2)
    # the east side of the field (behind the camera: seen in the cab glass and on the push), a hedgerow with oaks
    y = -70.0
    while y < 420:
        put(56 + rnd.uniform(-1, 1), y, rnd.choice(SHRUBS), rnd.uniform(0.8, 1.3))
        if rnd.random() < 0.12:
            put(58 + rnd.uniform(-1, 1), y, rnd.choice(OAKS), rnd.uniform(0.8, 1.1))
        y += rnd.uniform(2.0, 3.5)
    # poplar windbreak along the west edge of the field
    y = -75.0
    while y < 900:
        put(-433 + rnd.uniform(-0.4, 0.4), y, rnd.choice(POPS), rnd.uniform(0.85, 1.15))
        y += rnd.uniform(3.8, 5.0)
    # woodland belts and copses, 150 m to a few km out (the horizon's treeline)
    def belt(x0, x1, y0, y1, spacing, kinds, smin=0.85, smax=1.25, gaps=-1.0):
        nx_ = max(1, int((x1 - x0) / spacing))
        ny_ = max(1, int((y1 - y0) / spacing))
        for i in range(nx_):
            for j in range(ny_):
                xx = x0 + (i + rnd.random()) * spacing
                yy = y0 + (j + rnd.random()) * spacing
                if noise.noise(Vector((xx / 160, yy / 160, 3.3))) < gaps:
                    continue
                put(xx, yy, rnd.choice(kinds), rnd.uniform(smin, smax))
    belt(-950, 260, -335, -280, 7.0, OAKS + SHRUBS[:1], gaps=-0.3)
    belt(-400, -250, -262, -238, 8.0, OAKS)                         # a copse right behind the farmstead
    for xx, yy in ((-372, -196), (-366, -176), (-348, -172), (-290, -196), (-352, -226)):
        put(xx + rnd.uniform(-2, 2), yy + rnd.uniform(-2, 2), rnd.choice(OAKS), rnd.uniform(0.9, 1.2))
    belt(-1600, 900, -760, -690, 9.0, OAKS + POPS, 1.0, 1.4, gaps=-0.2)
    belt(-900, -830, -680, 1100, 8.0, OAKS + POPS, 0.9, 1.3, gaps=-0.25)
    belt(-200, 900, 760, 830, 8.0, OAKS, 0.9, 1.3, gaps=-0.3)
    belt(260, 330, -700, 700, 8.0, OAKS + POPS, 0.9, 1.3, gaps=-0.3)
    for _ in range(14):                                               # lone field trees
        a = rnd.uniform(rad(150), rad(300))
        r = rnd.uniform(160, 600)
        put(-60 + math.cos(a) * r, -40 + math.sin(a) * r, rnd.choice(OAKS), rnd.uniform(1.0, 1.4))
    for ring_r, cnt, sz in ((1500, 900, 1.6), (2600, 900, 2.2), (4200, 700, 3.0)):   # distant treelines on the hills
        for _ in range(cnt):
            a = rnd.uniform(0, math.tau)
            if noise.noise(Vector((math.cos(a) * 4, math.sin(a) * 4, ring_r / 1000))) < -0.15:
                continue
            r = ring_r + rnd.uniform(-250, 250)
            put(-60 + math.cos(a) * r, -40 + math.sin(a) * r, rnd.choice(OAKS + POPS), sz * rnd.uniform(0.8, 1.2))
    instancer("trees", trees, pts)
    print(f"{len(pts)} trees", flush=True)
    # verge grass and weeds along the headland, the field's west edge and under the fence
    gmat = grass_material("grass", 0.1)
    gdry = grass_material("grass_dry", 0.55)
    clumps = [make_clump(1, gmat), make_clump(2, gmat, h=(0.2, 0.45)), make_clump(3, gdry, seedheads=True), make_clump(4, gdry, h=(0.3, 0.7), seedheads=True), make_clump(5, gmat, blades=18, h=(0.12, 0.25), radius=0.15)]
    g = []
    for _ in range(36000):
        x = rnd.uniform(FIELD[0] - 10, FIELD[1] + 15)
        y = rnd.uniform(-80.0, -57.3)
        if abs(y + 66.5) < 1.9 and not abs(y + 66.5) < 0.35:
            continue                                                  # the track's wheel ruts are bare
        if y < -57.3 and y > -58.1:
            continue                                                  # under the irrigation main
        s = rnd.uniform(0.7, 1.5)
        g.append((x, y, headland_z(x, y), 0, 0, rnd.uniform(0, math.tau), s, s, s * rnd.uniform(0.8, 1.3), rnd.randrange(5)))
    # a few weeds in the near furrows
    for _ in range(160):
        x = rnd.uniform(NEAR[0], NEAR[1])
        x = (math.floor(x / ROW_W)) * ROW_W + rnd.uniform(-0.08, 0.08)
        if abs(abs(x) - TRACK_X) < 0.35:
            continue
        y = rnd.uniform(NEAR[2], NEAR[3])
        s = rnd.uniform(0.3, 0.6)
        g.append((x, y, field_z(x, y) - 0.01, 0, 0, rnd.uniform(0, math.tau), s, s, s, 4))
    instancer("grass", clumps, g)
    print(f"{len(g)} grass clumps", flush=True)


# ---------------------------------------------------------------------------- tractor materials
def mud_mask(n, low=0.25, high=1.25):
    """1 near the ground, fading out with height (world z), broken up by noise: where dried mud and dust sit."""
    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    n.link(geo.outputs["Position"], sep.inputs[0])
    nz = n.new("ShaderNodeTexNoise", Scale=9.0, Detail=12.0, Roughness=0.7)
    tc = n.new("ShaderNodeTexCoord")
    n.link(tc.outputs["Object"], nz.inputs["Vector"])
    h = n.new("ShaderNodeMapRange")
    h.inputs["From Min"].default_value, h.inputs["From Max"].default_value = high, low
    n.link(sep.outputs[2], h.inputs["Value"])
    m = n.math("SUBTRACT", n.math("MULTIPLY", h.outputs[0], 1.4), n.math("MULTIPLY", nz.outputs["Fac"], 0.9))
    return n.math("MULTIPLY", m, 1.6, clamp_=True)


def grime(n, base_col, mud=0.8, dust=0.5, wear_col=None, edge=0.0):
    """Dirt on a machine that works the field: mud splashed up from the wheels (by height), a film of dust on
    upward-facing surfaces, grime in the crevices (local AO) and, optionally, worn bright edges (bevel normal).
    Returns (colour socket, dirt mask socket)."""
    mudm = n.math("MULTIPLY", mud_mask(n), mud)
    geo = n.new("ShaderNodeNewGeometry")
    nzz = n.sep(geo.outputs["Normal"])[2]
    dn = n.new("ShaderNodeTexNoise", Scale=3.0, Detail=8.0, Roughness=0.6)
    tc = n.new("ShaderNodeTexCoord")
    n.link(tc.outputs["Object"], dn.inputs["Vector"])
    dustm = n.math("MULTIPLY", n.math("MULTIPLY", n.smooth(0.45, 0.95, nzz), n.smooth(0.35, 0.7, dn.outputs["Fac"])), dust)
    ao = n.new("ShaderNodeAmbientOcclusion", Distance=0.12, _only_local=True, _samples=8)
    cav = n.math("MULTIPLY", n.smooth(0.85, 0.35, ao.outputs["AO"]), 0.7)
    col = base_col
    if edge and wear_col:
        bev = n.new("ShaderNodeBevel", Radius=0.008, _samples=6)
        e = n.math("SUBTRACT", 1.0, n.vmath("DOT_PRODUCT", bev.outputs[0], geo.outputs["Normal"]))
        en = n.new("ShaderNodeTexNoise", Scale=40.0, Detail=6.0)
        n.link(tc.outputs["Object"], en.inputs["Vector"])
        em = n.math("MULTIPLY", n.smooth(0.02, 0.12, e), n.smooth(0.45, 0.62, en.outputs["Fac"]))
        col = n.mix(n.math("MULTIPLY", em, edge), col, wear_col)
    col = n.mix(cav, col, (0.045, 0.035, 0.026))
    col = n.mix(dustm, col, (0.3, 0.25, 0.19))
    col = n.mix(mudm, col, (0.15, 0.115, 0.082))
    dirt = n.math("MINIMUM", n.math("ADD", n.math("ADD", mudm, dustm), n.math("MULTIPLY", cav, 0.5)), 1.0)
    return col, dirt


def paint(name, color, mud=0.8, dust=0.5, metallic=0.55, flake=True, edge=0.6):
    """Automotive paint: metallic-flake base under a clearcoat with orange peel; dirt kills the clearcoat."""
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    b = n.bsdf
    col, dirt = grime(n, (*color,), mud, dust, (0.3, 0.3, 0.31), edge)
    n.link(col, b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = metallic
    tc = n.new("ShaderNodeTexCoord")
    if flake:
        fl = n.new("ShaderNodeTexVoronoi", Scale=2200.0)
        n.link(tc.outputs["Object"], fl.inputs["Vector"])
        fb = n.new("ShaderNodeBump", Strength=0.06, Distance=0.0004)
        n.link(fl.outputs["Distance"], fb.inputs["Height"])
        n.link(fb.outputs["Normal"], b.inputs["Normal"])
    n.link(n.math("ADD", wear(n, 0.3, 0.12, 4.0, scratches=0.06), n.math("MULTIPLY", dirt, 0.55)), b.inputs["Roughness"])
    n.link(n.math("SUBTRACT", 1.0, dirt), b.inputs["Coat Weight"])
    b.inputs["Coat Roughness"].default_value = 0.035
    peel = n.new("ShaderNodeTexNoise", Scale=180.0, Detail=2.0)
    n.link(tc.outputs["Object"], peel.inputs["Vector"])
    pb = n.new("ShaderNodeBump", Strength=0.035, Distance=0.002)
    n.link(peel.outputs["Fac"], pb.inputs["Height"])
    n.link(pb.outputs["Normal"], b.inputs["Coat Normal"])
    return m


def plastic(name, color=(0.022, 0.022, 0.024), rough=0.55, mud=0.6, dust=0.4):
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    col, dirt = grime(n, color, mud, dust)
    n.link(col, n.bsdf.inputs["Base Color"])
    n.link(n.math("ADD", rough, n.math("MULTIPLY", dirt, 0.3)), n.bsdf.inputs["Roughness"])
    tc = n.new("ShaderNodeTexCoord")
    tx = n.new("ShaderNodeTexNoise", Scale=900.0, Detail=2.0)
    n.link(tc.outputs["Object"], tx.inputs["Vector"])
    bp = n.new("ShaderNodeBump", Strength=0.12, Distance=0.0008)
    n.link(tx.outputs["Fac"], bp.inputs["Height"])
    n.link(bp.outputs["Normal"], n.bsdf.inputs["Normal"])
    return m


def metal(name, color, rough=0.35, mud=0.7, dust=0.3):
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    col, dirt = grime(n, color, mud, dust)
    n.link(col, n.bsdf.inputs["Base Color"])
    n.bsdf.inputs["Metallic"].default_value = 1.0
    n.link(n.math("ADD", wear(n, rough, 0.15, 8.0), n.math("MULTIPLY", dirt, 0.4)), n.bsdf.inputs["Roughness"])
    return m


def glass_material(name="glass", tint=(0.86, 0.93, 0.9)):
    """Thin cab glass: real refraction for camera and reflection rays (IOR 1.5, a light green tint), but shadow
    rays pass straight through (a flat thin pane barely bends light), so sunlight reaches the interior."""
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    b = n.bsdf
    b.inputs["Base Color"].default_value = (*tint, 1)
    b.inputs["Roughness"].default_value = 0.0
    b.inputs["IOR"].default_value = 1.5
    b.inputs["Transmission Weight"].default_value = 1.0
    dust = n.new("ShaderNodeTexNoise", Scale=6.0, Detail=6.0)
    tc = n.new("ShaderNodeTexCoord")
    n.link(tc.outputs["Object"], dust.inputs["Vector"])
    n.link(n.math("MULTIPLY", n.smooth(0.5, 0.75, dust.outputs["Fac"]), 0.12), b.inputs["Roughness"])
    lp = n.new("ShaderNodeLightPath")
    tr = n.new("ShaderNodeBsdfTransparent")
    tr.inputs[0].default_value = (*tint, 1)
    mx = n.new("ShaderNodeMixShader")
    n.link(lp.outputs["Is Shadow Ray"], mx.inputs[0])
    n.link(b.outputs[0], mx.inputs[1])
    n.link(tr.outputs[0], mx.inputs[2])
    n.link(mx.outputs[0], m.node_tree.nodes["Material Output"].inputs["Surface"])
    return m


def tyre_rubber():
    """Tyre rubber: near-black, slightly glossy where clean, sidewall ribs and a band of raised lettering-like
    blocks (generic, no brand), caked soil on the tread and lower sidewall."""
    m = bpy.data.materials.new("tyre")
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    p = n.sep(tc.outputs["Object"])
    rr = n.math("SQRT", n.math("ADD", n.math("MULTIPLY", p[1], p[1]), n.math("MULTIPLY", p[2], p[2])))
    ang = n.math("ARCTAN2", p[2], p[1])
    side = n.math("ABSOLUTE", p[0])
    # caked soil: in the tread grooves and on the lower half of the tyre in world space
    soil = n.new("ShaderNodeTexNoise", Scale=14.0, Detail=10.0, Roughness=0.7)
    n.link(tc.outputs["Object"], soil.inputs["Vector"])
    dust = mud_mask(n, 0.0, 1.9)
    caked = n.math("MULTIPLY", n.smooth(0.42, 0.62, soil.outputs["Fac"]), n.math("ADD", 0.35, n.math("MULTIPLY", dust, 0.65)))
    col = n.mix(caked, (0.017, 0.017, 0.019), (0.16, 0.12, 0.085))
    col = n.mix(n.math("MULTIPLY", dust, 0.5), col, (0.11, 0.09, 0.07))
    n.link(col, n.bsdf.inputs["Base Color"])
    n.link(n.math("ADD", 0.5, n.math("MULTIPLY", caked, 0.45)), n.bsdf.inputs["Roughness"])
    # sidewall: concentric ribs + a lettering band (blocky cells along the circumference)
    ribs = n.math("SINE", n.math("MULTIPLY", rr, 260.0))
    cells = n.new("ShaderNodeTexVoronoi", Scale=1.0)
    cells.distance = "CHEBYCHEV"
    n.link(n.comb(n.math("MULTIPLY", ang, 60.0), n.math("MULTIPLY", rr, 40.0), 0.0), cells.inputs["Vector"])
    band = n.math("MULTIPLY", n.smooth(0.0, 0.01, n.math("SUBTRACT", rr, n.math("MULTIPLY", 1.0, 0.0))), 1.0)
    h = n.math("ADD", n.math("MULTIPLY", ribs, 0.3), n.math("MULTIPLY", n.math("GREATER_THAN", n.sep(cells.outputs["Color"])[0], 0.55), 0.6))
    h = n.math("MULTIPLY", h, n.smooth(0.12, 0.17, side))
    bp = n.new("ShaderNodeBump", Strength=0.5, Distance=0.002)
    n.link(n.math("ADD", h, n.math("MULTIPLY", soil.outputs["Fac"], n.math("MULTIPLY", caked, 3.0))), bp.inputs["Height"])
    n.link(bp.outputs["Normal"], n.bsdf.inputs["Normal"])
    return m


def honeycomb_material(name="grille", cell=0.028):
    """A honeycomb grille: hexagonal openings (black, as if deep) in a dark satin metal web."""
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    p = n.sep(tc.outputs["Object"])
    q = n.comb(n.math("ADD", p[0], 10.0), n.math("ADD", p[2], 10.0), 0.0)
    q = n.vmath("SCALE", q, 1.0 / cell)
    S = (1.0, 1.7320508, 1.0)
    h = (0.5, 0.8660254, 0.5)
    a = n.vmath("SUBTRACT", n.vmath("WRAP", q, S, (0, 0, 0)), h)
    b = n.vmath("SUBTRACT", n.vmath("WRAP", n.vmath("SUBTRACT", q, h), S, (0, 0, 0)), h)
    da, db = n.vmath("DOT_PRODUCT", a, a), n.vmath("DOT_PRODUCT", b, b)
    pick = n.math("LESS_THAN", da, db)
    g = n.new("ShaderNodeMix", _data_type="VECTOR")
    n.link(pick, g.inputs["Factor"])
    n.link(b, g.inputs[4])
    n.link(a, g.inputs[5])
    gs = n.sep(n.vmath("ABSOLUTE", g.outputs[1]))
    hexd = n.math("MAXIMUM", n.math("ADD", n.math("MULTIPLY", gs[0], 0.5), n.math("MULTIPLY", gs[1], 0.8660254)), gs[0])
    web = n.smooth(0.4, 0.445, hexd)                 # 1 on the web between the cells
    col = n.mix(web, (0.003, 0.003, 0.004), (0.05, 0.05, 0.055))
    n.link(col, n.bsdf.inputs["Base Color"])
    n.bsdf.inputs["Metallic"].default_value = 0.7
    n.link(n.fmix(web, 0.9, 0.38), n.bsdf.inputs["Roughness"])
    bp = n.new("ShaderNodeBump", Strength=1.0, Distance=0.006)
    n.link(web, bp.inputs["Height"])
    n.link(bp.outputs["Normal"], n.bsdf.inputs["Normal"])
    return m


def screen_material():
    """The cab's terminal: a dark UI with a map-like row view and a few status bars (generic, no brand)."""
    m = bpy.data.materials.new("screen")
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    p = n.sep(tc.outputs["Object"])
    rows = n.smooth(0.3, 0.1, n.math("ABSOLUTE", n.math("SUBTRACT", n.math("FRACT", n.math("MULTIPLY", p[0], 60.0)), 0.5)))
    left = n.math("LESS_THAN", p[0], 0.02)
    bars = n.math("MULTIPLY", n.math("GREATER_THAN", p[0], 0.04), n.smooth(0.3, 0.1, n.math("ABSOLUTE", n.math("SUBTRACT", n.math("FRACT", n.math("MULTIPLY", p[1], 40.0)), 0.5))))
    col = n.mix(n.math("MULTIPLY", rows, left), (0.02, 0.03, 0.05), (0.12, 0.5, 0.25))
    col = n.mix(n.math("MULTIPLY", bars, 0.8), col, (0.45, 0.2, 1.0))
    em = n.new("ShaderNodeEmission", Strength=4.0)
    n.link(col, em.inputs["Color"])
    mx = n.new("ShaderNodeMixShader")
    mx.inputs[0].default_value = 0.85
    n.bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1)
    n.bsdf.inputs["Roughness"].default_value = 0.1
    n.link(n.bsdf.outputs[0], mx.inputs[1])
    n.link(em.outputs[0], mx.inputs[2])
    n.link(mx.outputs[0], m.node_tree.nodes["Material Output"].inputs["Surface"])
    return m


def emissive(name, col, strength, base=None):
    return principled(name, base or col, rough=0.25, emit=col, emit_strength=strength)


# ---------------------------------------------------------------------------- tractor geometry helpers
def loft(name, sections, mat, parent, closed=False, subd=2, crease_cols=(), crease_rows=(), cap_end=False, smooth=True):
    """A subdivision-surface panel lofted through cross-sections (lists of points, same count each);
    crease_cols: profile indices whose edges along the loft stay sharp; crease_rows: sections kept sharp."""
    bm = bmesh.new()
    rows = [[bm.verts.new(p) for p in sec] for sec in sections]
    n = len(sections[0])
    for i in range(len(rows) - 1):
        for k in range(n if closed else n - 1):
            k2 = (k + 1) % n
            bm.faces.new((rows[i][k], rows[i][k2], rows[i + 1][k2], rows[i + 1][k]))
    if cap_end:
        bm.faces.new(list(reversed(rows[-1])))
    bm.normal_update()
    cl = bm.edges.layers.float.new("crease_edge")
    for i in range(len(rows) - 1):
        for k in crease_cols:
            e = bm.edges.get((rows[i][k], rows[i + 1][k]))
            if e:
                e[cl] = 1.0
    for i in crease_rows:
        for k in range(n - 1):
            e = bm.edges.get((rows[i][k], rows[i][k + 1]))
            if e:
                e[cl] = 1.0
    for f in bm.faces:
        f.smooth = smooth
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    me.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    if subd:
        s = ob.modifiers.new("subd", "SUBSURF")
        s.levels = s.render_levels = subd
    return ob


def solid(ob, t, offset=-1.0):
    s = ob.modifiers.new("solid", "SOLIDIFY")
    s.thickness, s.offset = t, offset
    s.use_even_offset = True
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
    return ob


def bar(name, mat, a, b, r, parent, sides=12, bevel=0.004):
    a, b = Vector(a), Vector(b)
    d = b - a
    o = cyl(name, mat, r, d.length, parent=parent, segs=sides, bevel=bevel)
    o.matrix_basis = Matrix.Translation((a + b) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    return o


def torus(name, mat, R, r, parent, M, seg=48, sides=12):
    bm = bmesh.new()
    vs = []
    for i in range(seg):
        a = i / seg * math.tau
        ring = []
        for k in range(sides):
            b = k / sides * math.tau
            ring.append(bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b))))
        vs.append(ring)
    for i in range(seg):
        for k in range(sides):
            bm.faces.new((vs[i][k], vs[(i + 1) % seg][k], vs[(i + 1) % seg][(k + 1) % sides], vs[i][(k + 1) % sides]))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return finish(name, bm, mat, parent, 0)


def revolve(name, prof, mat, parent, steps=96, smooth=True):
    """Revolve an (x across, r radial) profile around the x axis (wheel parts)."""
    bm = bmesh.new()
    verts = [bm.verts.new((x, 0, r)) for x, r in prof]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(1, 0, 0), angle=math.tau, steps=steps, use_merge=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, mat, parent, 0, smooth=smooth)


# ---------------------------------------------------------------------------- tyres and wheels
def tyre_profile_r(x, w, r, r_in, p=4.0):
    t = min(abs(2 * x / w), 1.0)
    return r_in + (r - r_in) * (1 - t ** p) ** (1 / p)


def tyre(name, mat, r, w, r_rim, parent, lugs=23, lug_h=0.055, lug_w=0.075, angle=24.0):
    """An R1W ag tyre: a rounded carcass (flat crown, round shoulders, bulging sidewalls) and deep chevron lugs
    that run from over each shoulder to just past the centre line, alternating sides, wrapped on the carcass."""
    car_r = r - lug_h
    prof = []
    for i in range(41):
        a = i / 40 * math.pi
        x = -math.cos(a) * w * 0.52
        prof.append((x, tyre_profile_r(x, w * 1.04, car_r, r_rim + 0.01, 3.2)))
    prof = [(prof[0][0] * 0.92, r_rim)] + prof + [(prof[-1][0] * 0.92, r_rim)]
    bm = bmesh.new()
    verts = [bm.verts.new((x, 0, rr)) for x, rr in prof]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(1, 0, 0), angle=math.tau, steps=144, use_merge=True)
    # lugs: parametric bars wrapped on the carcass
    ta = math.tan(rad(angle))
    for side in (-1, 1):
        for k in range(lugs):
            th0 = (k + (0.5 if side > 0 else 0.0)) / lugs * math.tau
            x_out, x_in = side * w * 0.56, -side * w * 0.04
            nu = 10
            grid = {}
            for iu in range(nu + 1):
                u = iu / nu
                x = lerp(x_out, x_in, u)
                surf = tyre_profile_r(x, w * 1.04, car_r, r_rim + 0.01, 3.2)
                shoulder = smoothstep(0.42, 0.56, abs(x) / w)
                top = surf + lug_h * (1 - 0.55 * shoulder) * (1 - 0.25 * smoothstep(0.7, 1.0, u))
                arc = (abs(x - x_out)) * ta
                bw = lug_w * (1.0 - 0.2 * u)
                for iv, v in enumerate((-1, 1)):
                    for il, rad_ in enumerate((surf - 0.012, top)):
                        bwl = bw * (1.0 if il == 0 else 0.82)
                        phi = th0 + (arc + v * bwl * 0.5) / car_r
                        grid[(iu, iv, il)] = bm.verts.new((x, math.cos(phi) * rad_, math.sin(phi) * rad_))
            for iu in range(nu):
                for (a, b, c, d) in (((iu, 0, 1), (iu, 1, 1), (iu + 1, 1, 1), (iu + 1, 0, 1)),     # top
                                     ((iu, 0, 0), (iu, 0, 1), (iu + 1, 0, 1), (iu + 1, 0, 0)),     # leading flank
                                     ((iu, 1, 1), (iu, 1, 0), (iu + 1, 1, 0), (iu + 1, 1, 1))):    # trailing flank
                    bm.faces.new((grid[a], grid[b], grid[c], grid[d]))
            for iu in (0, nu):
                f = [grid[(iu, 0, 0)], grid[(iu, 1, 0)], grid[(iu, 1, 1)], grid[(iu, 0, 1)]]
                bm.faces.new(f if iu == nu else f[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = finish(name, bm, mat, parent, 0, smooth=True)
    bv = ob.modifiers.new("bevel", "BEVEL")
    bv.width, bv.segments, bv.limit_method, bv.angle_limit = 0.006, 2, "ANGLE", rad(40)
    bv.harden_normals = False
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
    bulge_modifier(ob, r)
    return ob


def bulge_group():
    """Geometry Nodes: the contact patch. The tyre spins with its hub, so the patch (always at the bottom) is
    found by rotating into the axle frame by the hub's current angle (keyed per frame): flatten the bottom
    1.6 cm and bulge the lower sidewalls a little, then rotate back."""
    if "tyre_bulge" in bpy.data.node_groups:
        return bpy.data.node_groups["tyre_bulge"]
    g = bpy.data.node_groups.new("tyre_bulge", "GeometryNodeTree")
    g.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    sa = g.interface.new_socket("Angle", in_out="INPUT", socket_type="NodeSocketFloat")
    sr = g.interface.new_socket("Radius", in_out="INPUT", socket_type="NodeSocketFloat")
    g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = g.nodes, g.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    pos = N.new("GeometryNodeInputPosition")
    rot = N.new("ShaderNodeVectorRotate")
    rot.rotation_type = "X_AXIS"
    L.new(pos.outputs[0], rot.inputs["Vector"])
    L.new(gi.outputs["Angle"], rot.inputs["Angle"])
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(rot.outputs[0], sep.inputs[0])

    def m(op, a, b):
        x = N.new("ShaderNodeMath")
        x.operation = op
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                x.inputs[i].default_value = v
            else:
                L.new(v, x.inputs[i])
        return x.outputs[0]
    flat = m("ADD", m("MULTIPLY", gi.outputs["Radius"], -1.0), 0.016)            # z of the flattened patch
    pen = m("MAXIMUM", m("SUBTRACT", flat, sep.outputs[2]), 0.0)                  # how far below the patch
    lowz = m("DIVIDE", sep.outputs[2], m("MULTIPLY", gi.outputs["Radius"], -1.0))  # 1 at the bottom, 0 at the axle
    side = m("ADD", 1.0, m("MULTIPLY", m("POWER", m("MAXIMUM", lowz, 0.0), 8.0), 0.035))
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(m("MULTIPLY", sep.outputs[0], m("ADD", side, m("MULTIPLY", pen, 2.5))), comb.inputs[0])
    L.new(sep.outputs[1], comb.inputs[1])
    L.new(m("ADD", sep.outputs[2], pen), comb.inputs[2])
    back = N.new("ShaderNodeVectorRotate")
    back.rotation_type = "X_AXIS"
    back.invert = True
    L.new(comb.outputs[0], back.inputs["Vector"])
    L.new(gi.outputs["Angle"], back.inputs["Angle"])
    sp = N.new("GeometryNodeSetPosition")
    L.new(gi.outputs[0], sp.inputs["Geometry"])
    L.new(back.outputs[0], sp.inputs["Position"])
    L.new(sp.outputs[0], go.inputs[0])
    return g


def bulge_modifier(ob, r):
    md = ob.modifiers.new("bulge", "NODES")
    md.node_group = bulge_group()
    ids = {s.name: s.identifier for s in md.node_group.interface.items_tree if getattr(s, "in_out", "") == "INPUT"}
    getattr(md.properties.inputs, ids["Radius"]).value = r     # Blender 5.2: modifier inputs live here
    ob["bulge_angle_id"] = ids["Angle"]
    return md


def rim(name, mat, nut_mat, r_rim, w, parent, holes=8, outer=1):
    """A steel ag wheel: barrel with flanges and a drop centre, a dished centre disc with handhold holes,
    a bolt circle of hex nuts and a hub."""
    hw = w * 0.5
    prof = [(-hw - 0.01, r_rim + 0.035), (-hw, r_rim + 0.03), (-hw + 0.012, r_rim - 0.005), (-hw * 0.6, r_rim - 0.012),
            (-hw * 0.35, r_rim - 0.06), (hw * 0.35, r_rim - 0.06), (hw * 0.6, r_rim - 0.012), (hw - 0.012, r_rim - 0.005),
            (hw, r_rim + 0.03), (hw + 0.01, r_rim + 0.035)]
    barrel = revolve(f"{name}_barrel", prof, mat, parent, steps=96)
    solid(barrel, 0.008)
    # centre disc: a fine polar grid, faces dropped inside rounded slots (the handholds)
    bm = bmesh.new()
    rings = [lerp(r_rim - 0.065, r_rim * 0.26, i / 13) for i in range(14)]
    seg = holes * 16
    dish = lambda rr: outer * (hw * 0.15 + (r_rim - rr) / r_rim * 0.16)
    V = [[bm.verts.new((dish(rr), math.cos(k / seg * math.tau) * rr, math.sin(k / seg * math.tau) * rr)) for k in range(seg)] for rr in rings]
    rc, rw, aw = r_rim * 0.63, r_rim * 0.1, math.tau / holes * 0.18
    for i in range(len(rings) - 1):
        for k in range(seg):
            rm = (rings[i] + rings[i + 1]) / 2
            am = ((k + 0.5) / seg * math.tau) % (math.tau / holes) - math.tau / holes / 2
            if ((rm - rc) / rw) ** 2 + (am / aw) ** 2 < 1.0:
                continue                                             # a handhold
            bm.faces.new((V[i][k], V[i][(k + 1) % seg], V[i + 1][(k + 1) % seg], V[i + 1][k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    disc = finish(f"{name}_disc", bm, mat, parent, 0)
    solid(disc, 0.012, 0.0)
    disc.modifiers.new("wn", "WEIGHTED_NORMAL")
    x_face = dish(rings[-1]) + outer * 0.006
    cyl(f"{name}_hub", nut_mat, r_rim * 0.24, 0.16, center=(x_face + outer * 0.07, 0, 0), axis="X", parent=parent, bevel=0.01, segs=32)
    cyl(f"{name}_cap", nut_mat, r_rim * 0.12, 0.06, center=(x_face + outer * 0.16, 0, 0), axis="X", parent=parent, bevel=0.012, segs=24)
    for k in range(10):
        a = k / 10 * math.tau
        rr = r_rim * 0.3
        cyl(f"{name}_nut{k}", nut_mat, 0.018, 0.035, center=(x_face + outer * 0.015, math.cos(a) * rr, math.sin(a) * rr), axis="X", parent=parent, bevel=0.003, segs=6)


# ---------------------------------------------------------------------------- the tractor
def build_tractor_model():
    """A modern, autonomy-ready row-crop tractor (generic, no brand): long tapered bonnet with a honeycomb
    grille and LED headlight clusters, a four-post glass cab with a visible interior, white roof with work lights,
    GPS dome and beacon, curved fenders, deep-lug tyres on dished rims, chassis, engine, axles, hitch, exhaust."""
    body = paint("graphite", (0.085, 0.09, 0.1), metallic=0.7)
    white = paint("white_roof", (0.72, 0.73, 0.74), mud=0.15, dust=0.35, metallic=0.0, flake=False, edge=0.0)
    blackp = plastic("black_plastic")
    rubber = tyre_rubber()
    rimp = paint("rim_paint", (0.42, 0.43, 0.45), mud=1.0, dust=0.4, metallic=0.4, edge=0.4)
    steel = metal("steel", (0.32, 0.32, 0.33), 0.4)
    darkmetal = metal("cast", (0.07, 0.07, 0.075), 0.5, mud=1.0)
    chrome = principled("chrome", (0.85, 0.85, 0.87), rough=0.06, metal=1.0)
    glass = glass_material()
    lens = glass_material("lens", (0.95, 0.95, 0.95))
    violet = emissive("violet_led", (0.51, 0.2, 1.0), 9.0, base=(0.3, 0.1, 0.9))
    drl = emissive("drl", (1.0, 0.97, 0.92), 14.0)
    headl = emissive("headlamp", (1.0, 0.95, 0.88), 6.0)
    worklamp = emissive("worklamp", (1.0, 0.95, 0.86), 5.0)
    amber = emissive("beacon", (1.0, 0.42, 0.04), 6.0, base=(1.0, 0.45, 0.05))
    tail = emissive("tail", (0.9, 0.05, 0.02), 1.5, base=(0.5, 0.02, 0.01))
    indic = principled("indicator", (0.9, 0.42, 0.05), rough=0.15)
    grille = honeycomb_material()
    seat = plastic("seat_fabric", (0.03, 0.03, 0.032), rough=0.9, mud=0.0, dust=0.1)
    trim = plastic("interior", (0.05, 0.05, 0.055), rough=0.6, mud=0.0, dust=0.15)
    screen = screen_material()
    root = empty("tractor")

    # ---- wheels: hub empties spin (keyed to distance); tyres carry the contact-patch deformer
    wheels = []
    for (x, y, r, w, rr, lugs) in [(-TRACK_X, 0.0, 0.86, 0.40, 0.57, 23), (TRACK_X, 0.0, 0.86, 0.40, 0.57, 23),
                                   (-TRACK_X, 2.45, 0.52, 0.30, 0.33, 20), (TRACK_X, 2.45, 0.52, 0.30, 0.33, 20)]:
        hub = empty(f"hub{x:+.2f}{y}", root)
        hub.location = (x, y, r - 0.012)
        s = 1 if x > 0 else -1
        t = tyre(f"tyre{x:+.2f}{y}", rubber, r, w, rr, hub, lugs=lugs, lug_h=0.06 if r > 0.6 else 0.045, lug_w=0.08 if r > 0.6 else 0.06)
        rim(f"rim{x:+.2f}{y}", rimp, steel, rr, w * 0.92, hub, outer=s)
        wheels.append((hub, r, t))

    # ---- chassis, engine, axles
    for s in (-1, 1):
        box(f"rail{s}", darkmetal, (s * 0.34 - 0.06, -0.6, 0.58), (s * 0.34 + 0.06, 3.45, 0.86), root, bevel=0.012)
    box("engine_block", darkmetal, (-0.3, 1.05, 0.62), (0.3, 2.75, 1.0), root, bevel=0.03)
    box("sump", darkmetal, (-0.22, 1.2, 0.5), (0.22, 2.3, 0.64), root, bevel=0.03)
    box("bellhousing", darkmetal, (-0.36, 0.35, 0.55), (0.36, 1.05, 1.25), root, bevel=0.06)
    box("transmission", darkmetal, (-0.4, -0.55, 0.5), (0.4, 0.4, 1.2), root, bevel=0.06)
    cyl("rear_axle", darkmetal, 0.12, 1.25, center=(0, 0, 0.848), axis="X", parent=root, bevel=0.01, r2=0.1)
    for s in (-1, 1):
        cyl(f"rear_trumpet{s}", darkmetal, 0.16, 0.2, center=(s * 0.42, 0, 0.848), axis="X", parent=root, bevel=0.02)
    box("front_axle", darkmetal, (-0.58, 2.36, 0.44), (0.58, 2.54, 0.6), root, bevel=0.025)
    box("axle_pivot", darkmetal, (-0.16, 2.2, 0.52), (0.16, 2.7, 0.72), root, bevel=0.03)
    for s in (-1, 1):
        cyl(f"kingpin{s}", darkmetal, 0.07, 0.3, center=(s * 0.6, 2.45, 0.52), parent=root, bevel=0.01)
        cyl(f"front_hub{s}", darkmetal, 0.11, 0.12, center=(s * 0.62, 2.45, 0.508), axis="X", parent=root, bevel=0.01)
    cyl("alternator", steel, 0.06, 0.12, center=(0.32, 2.55, 0.9), axis="Y", parent=root, bevel=0.006)
    cyl("oil_filter", principled("filter_blue", (0.05, 0.08, 0.15), rough=0.4), 0.05, 0.14, center=(0.33, 1.9, 0.72), parent=root, bevel=0.008)
    hose_m = plastic("hose", (0.012, 0.012, 0.012), rough=0.5, mud=0.8)
    for pts, r_ in ((((0.3, 2.85, 0.95), (0.36, 2.6, 0.85), (0.33, 2.2, 0.82), (0.31, 1.6, 0.92)), 0.028),
                    (((-0.3, 2.9, 0.92), (-0.36, 2.5, 0.8), (-0.34, 1.9, 0.76)), 0.022),
                    (((-0.31, 1.3, 0.95), (-0.37, 0.9, 0.9), (-0.42, 0.5, 0.9)), 0.018)):
        V, F = tube_mesh("h", [Vector(p) for p in pts], r_, 10, hose_m)
        hose = mesh_object("hose", V, F, [hose_m])
        hose.parent = root
        hose.modifiers.new("subd", "SUBSURF").render_levels = 2
    # front weights: a compact stack of suitcase weights hanging on a carrier under the nose
    box("weight_carrier", darkmetal, (-0.26, 3.2, 0.6), (0.26, 3.36, 0.9), root, bevel=0.02)
    for k in range(6):
        y0 = 3.36 + k * 0.042
        box(f"weight{k}", body, (-0.28, y0, 0.58), (0.28, y0 + 0.038, 0.94 - k * 0.012), root, bevel=0.01)
        box(f"weight_handle{k}", darkmetal, (-0.08, y0 + 0.008, 0.94 - k * 0.012), (0.08, y0 + 0.03, 0.98 - k * 0.012), root, bevel=0.006)
    # ---- bonnet: a lofted subdivision panel, tapering towards the nose and sloping down for visibility
    def hood_sec(t, inset=0.0, dz=0.0):
        w = lerp(0.47, 0.405, t) - inset
        zt = lerp(1.94, 1.71, t ** 1.15) - inset * 0.6 + dz
        zb = 0.98 + inset * 0.5
        y = lerp(0.86, 3.22, t)
        pr = [(-w, zb), (-w, lerp(zb, zt, 0.45)), (-w, zt - 0.2), (-w * 0.985, zt - 0.075), (-w * 0.9, zt - 0.018), (-w * 0.55, zt), (0, zt + 0.012)]
        pr = pr + [(-x, z) for x, z in reversed(pr[:-1])]
        return [Vector((x, y, z)) for x, z in pr]
    secs = [hood_sec(t) for t in (0.0, 0.08, 0.3, 0.55, 0.8, 0.95, 1.0)]
    nose = [Vector((v.x * 0.9, v.y + 0.02, lerp(v.z, 1.42, 0.12))) for v in secs[-1]]
    secs.append(nose)
    hood = loft("bonnet", secs, body, root, subd=2, crease_cols=(3, 9))
    solid(hood, 0.02)
    # honeycomb grille in the nose, its frame, and the side vents
    box("grille", grille, (-0.33, 3.2, 1.0), (0.33, 3.23, 1.62), root, bevel=0.01)
    for s in (-1, 1):
        sv = box(f"side_vent{s}", grille, (-0.003, 2.45, 1.08), (0.003, 3.0, 1.42), root, bevel=0.002)
        sv.location.x = s * (lerp(0.47, 0.405, 0.85) + 0.004)
    # panel gap and a lower skirt line along each bonnet side (dark grooves just proud of the surface)
    gap = principled("panel_gap", (0.005, 0.005, 0.006), rough=0.7)
    for s_ in (-1, 1):
        for (dz, hh, t0_, t1_) in ((-0.42, 0.006, 0.05, 0.97), (-0.62, 0.008, 0.08, 0.99)):
            V, F = [], []
            for i in range(25):
                t = lerp(t0_, t1_, i / 24)
                w = lerp(0.47, 0.405, t) + 0.0035
                zt = lerp(1.94, 1.71, t ** 1.15) + dz if dz > -0.5 else 1.08     # follows the bonnet line / level skirt
                y = lerp(0.86, 3.22, t)
                V += [(s_ * w, y, zt - hh), (s_ * w, y, zt + hh)]
            F = [(2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1) if s_ > 0 else (2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(24)]
            mesh_object(f"bonnet_gap{s_}{dz}", V, F, [gap]).parent = root
    box("nose_trim", chrome, (-0.34, 3.235, 0.985), (0.34, 3.25, 1.0), root, bevel=0.004)
    # LED stripe along each side of the bonnet (violet: the only violet on the machine besides the camera)
    for s in (-1, 1):
        V, F = [], []
        for i in range(25):
            t = 0.12 + i / 24 * 0.8
            w = lerp(0.47, 0.405, t) + 0.006
            zt = lerp(1.94, 1.71, t ** 1.15) - 0.19
            y = lerp(0.86, 3.22, t)
            V += [(s * w, y, zt - 0.012), (s * w, y, zt + 0.012)]
        F = [(2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1) if s > 0 else (2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(24)]
        mesh_object(f"led_stripe{s}", V, F, [violet]).parent = root
    # headlight clusters at the nose corners: housing, two reflector cups with LED cores, a DRL bar, lens
    for s in (-1, 1):
        hx = s * 0.27
        box(f"hl_housing{s}", blackp, (hx - 0.1, 3.18, 1.52), (hx + 0.1, 3.26, 1.64), root, bevel=0.012)
        for k in (-1, 1):
            cx = hx + k * 0.045
            cyl(f"hl_cup{s}{k}", chrome, 0.035, 0.02, center=(cx, 3.255, 1.575), axis="Y", parent=root, bevel=0.004, segs=24, r2=0.02)
            cyl(f"hl_led{s}{k}", headl, 0.012, 0.012, center=(cx, 3.262, 1.575), axis="Y", parent=root, bevel=0.002, segs=16)
        box(f"drl{s}", drl, (hx - 0.09, 3.258, 1.615), (hx + 0.09, 3.266, 1.626), root, bevel=0.002)
        box(f"hl_lens{s}", lens, (hx - 0.095, 3.264, 1.53), (hx + 0.095, 3.27, 1.635), root, bevel=0.004)
        box(f"indicator{s}", indic, (hx - 0.035 + s * 0.06, 3.255, 1.48), (hx + 0.035 + s * 0.06, 3.27, 1.51), root, bevel=0.004)

    # ---- fuel tank, battery box, steps
    tread = metal("tread", (0.25, 0.25, 0.26), 0.45)
    tank = box("fuel_tank", body, (0.38, 0.95, 0.62), (0.68, 1.7, 1.3), root, bevel=0.08, segs=5)
    cyl("filler", blackp, 0.05, 0.05, center=(0.6, 1.5, 1.32), parent=root, bevel=0.008)
    for yy in (1.1, 1.55):
        box(f"tank_strap{yy}", darkmetal, (0.37, yy - 0.025, 0.6), (0.69, yy + 0.025, 1.315), root, bevel=0.006)
    box("tank_step", tread, (0.62, 1.0, 0.86), (0.75, 1.65, 0.89), root, bevel=0.006)
    box("def_tank", blackp, (0.4, 1.72, 0.7), (0.62, 1.95, 1.08), root, bevel=0.05)
    box("battery_box", darkmetal, (-0.68, 1.05, 0.62), (-0.4, 1.6, 1.0), root, bevel=0.03)
    for k in range(4):
        box(f"step{k}", tread, (-0.82, 0.92, 0.48 + k * 0.27), (-0.6, 1.24, 0.52 + k * 0.27), root, bevel=0.008)
    for yy in (0.92, 1.24):
        box(f"step_rail{yy}", darkmetal, (-0.83, yy - 0.015, 0.44), (-0.8, yy + 0.015, 1.36), root, bevel=0.005)

    # ---- exhaust: stack at the right A-pillar with a perforated heat shield and a bent tip
    shield = plastic("heat_shield", (0.02, 0.02, 0.022), rough=0.45, mud=0.2, dust=0.5)
    ex, ey = 0.36, 1.04
    cyl("exhaust", steel, 0.055, 1.36, center=(ex, ey, 2.56), parent=root, bevel=0.006, segs=24)
    cyl("exhaust_boot", blackp, 0.09, 0.08, center=(ex, ey, 1.93), parent=root, bevel=0.02, segs=32)
    cyl("heat_shield", shield, 0.075, 0.75, center=(ex, ey, 2.4), parent=root, bevel=0.01, segs=32)
    bar("exhaust_tip", chrome, (ex, ey, 3.22), (ex, ey - 0.12, 3.33), 0.052, root, sides=24)
    for z in (2.15, 2.65):
        bar(f"exh_clamp{z}", steel, (ex, ey, z), (ex + 0.2, ey - 0.18, z), 0.012, root)

    # ---- cab: floor, four posts, glass, white roof, interior
    box("cab_base", body, (-0.8, -0.9, 1.38), (0.8, 0.84, 1.52), root, bevel=0.035)
    posts = [(-0.77, 0.8), (0.77, 0.8), (-0.77, -0.86), (0.77, -0.86)]
    for (px, py) in posts:
        lean = -0.05 if py > 0 else 0.0
        bar(f"post{px}{py}", body, (px, py, 1.5), (px * 0.985, py + lean, 2.99), 0.038, root, sides=12)
    for z in (1.52, 2.97):
        for (a, b) in ((posts[0], posts[1]), (posts[2], posts[3]), (posts[0], posts[2]), (posts[1], posts[3])):
            bar(f"rail{z}{a}{b}", body, (a[0], a[1] - (0.05 if z > 2 and a[1] > 0 else 0), z), (b[0], b[1] - (0.05 if z > 2 and b[1] > 0 else 0), z), 0.025, root, sides=10)
    # glass: front screen bowed slightly forward, sides and rear flat (6 mm panes)
    secs = []
    for i in range(9):
        u = i / 8
        x = lerp(-0.74, 0.74, u)
        bow = 0.035 * math.sin(math.pi * u)
        secs.append([Vector((x, 0.8 + bow, 1.55)), Vector((x, 0.75 + bow, 2.94))])
    front = loft("glass_front", secs, glass, root, subd=0)
    solid(front, 0.006, 0.0)
    for s in (-1, 1):
        g = box(f"glass_side{s}", glass, (s * 0.765 - 0.003, -0.83, 1.55), (s * 0.765 + 0.003, 0.77, 2.94), root, bevel=0.0)
    box("glass_rear", glass, (-0.74, -0.863, 1.6), (0.74, -0.857, 2.94), root, bevel=0.0)
    box("door_seal", blackp, (-0.775, -0.05, 1.55), (-0.765, -0.02, 2.94), root, bevel=0.002)
    box("door_handle", chrome, (-0.79, 0.05, 2.0), (-0.775, 0.2, 2.03), root, bevel=0.004)
    for z in (1.75, 2.7):
        box(f"door_hinge{z}", blackp, (-0.8, 0.7, z), (-0.77, 0.79, z + 0.08), root, bevel=0.006)
        box(f"rwin_hinge{z}", blackp, (0.77, -0.84, z), (0.8, -0.76, z + 0.08), root, bevel=0.006)
    for s_ in (-1, 1):
        box(f"grab_rail{s_}", steel, (s_ * 0.805 - 0.01, 0.62, 1.7), (s_ * 0.805 + 0.01, 0.65, 2.6), root, bevel=0.004)
    # roof: white, rounded, a visor with LED work lights; GPS dome; beacon; rear work lights
    roof_secs = []
    for t in (0.0, 0.08, 0.5, 0.92, 1.0):
        y = lerp(-1.0, 0.98, t)
        e = 0.0 if 0.05 < t < 0.95 else 0.05
        zt = 3.16 - e
        roof_secs.append([Vector((x, y, z)) for x, z in ((-0.86 + e, 2.97), (-0.88 + e, 3.06), (-0.8 + e, zt), (0, zt + 0.02), (0.8 - e, zt), (0.88 - e, 3.06), (0.86 - e, 2.97))])
    roof = loft("roof", roof_secs, white, root, subd=2)
    solid(roof, 0.03)
    for k, x in enumerate((-0.6, -0.2, 0.2, 0.6)):
        box(f"worklight{k}", blackp, (x - 0.09, 0.95, 2.96), (x + 0.09, 1.0, 3.04), root, bevel=0.01)
        box(f"worklight_led{k}", worklamp, (x - 0.075, 0.998, 2.972), (x + 0.075, 1.004, 3.028), root, bevel=0.004)
    for x in (-0.5, 0.5):
        box(f"rear_light{x}", blackp, (x - 0.08, -1.02, 2.97), (x + 0.08, -0.98, 3.04), root, bevel=0.01)
    domeb = cyl("gps_base", blackp, 0.15, 0.03, center=(0, 0.45, 3.19), parent=root, bevel=0.008, segs=40)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=0.14)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.001], context="VERTS")
    bmesh.ops.scale(bm, vec=(1, 1, 0.55), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0.45, 3.205), verts=bm.verts)
    finish("gps_dome", bm, white, root, 0)
    cyl("beacon_base", blackp, 0.06, 0.04, center=(-0.62, -0.78, 3.19), parent=root, bevel=0.008, segs=24)
    cyl("beacon", amber, 0.05, 0.1, center=(-0.62, -0.78, 3.26), parent=root, bevel=0.02, segs=24)
    # mirrors: tubular arms from the A-pillars, black housings, mirror glass
    for s in (-1, 1):
        bar(f"mirror_arm{s}", steel, (s * 0.78, 0.76, 2.78), (s * 1.12, 0.62, 2.7), 0.016, root)
        box(f"mirror_house{s}", blackp, (s * 1.12 - 0.05, 0.56, 2.38), (s * 1.12 + 0.05, 0.63, 2.78), root, bevel=0.025)
        box(f"mirror_glass{s}", chrome, (s * 1.12 - 0.042, 0.552, 2.4), (s * 1.12 + 0.042, 0.56, 2.76), root, bevel=0.006)
    # wipers parked at the bottom of the screen
    bar("wiper_arm", blackp, (0.05, 0.83, 1.6), (-0.45, 0.82, 1.68), 0.008, root)
    bar("wiper_blade", blackp, (-0.6, 0.835, 1.66), (-0.12, 0.835, 1.62), 0.006, root)
    # interior: seat, steering wheel on its column, dashboard, right-hand armrest console with joystick and screen
    box("cab_floor", trim, (-0.74, -0.82, 1.52), (0.74, 0.76, 1.56), root, bevel=0.01)
    box("seat_base", trim, (-0.2, -0.45, 1.56), (0.2, -0.1, 1.82), root, bevel=0.04)
    box("seat_cushion", seat, (-0.25, -0.5, 1.82), (0.25, 0.02, 1.93), root, bevel=0.045)
    back = box("seat_back", seat, (-0.25, -0.12, 0.0), (0.25, 0.0, 0.62), root, bevel=0.045)
    back.matrix_basis = Matrix.Translation((0, -0.45, 1.9)) @ Matrix.Rotation(rad(-12), 4, "X") @ Matrix.Translation((0, 0, 0))
    hr = box("headrest", seat, (-0.15, -0.1, 0.0), (0.15, 0.0, 0.2), root, bevel=0.04)
    hr.matrix_basis = Matrix.Translation((0, -0.6, 2.56)) @ Matrix.Rotation(rad(-12), 4, "X")
    box("console", trim, (0.27, -0.45, 1.56), (0.45, 0.25, 2.05), root, bevel=0.03)
    box("armrest", seat, (0.27, -0.45, 2.05), (0.43, 0.12, 2.1), root, bevel=0.025)
    bar("joystick", trim, (0.36, 0.14, 2.1), (0.36, 0.16, 2.22), 0.02, root)
    scr = box("terminal", screen, (-0.13, -0.004, -0.09), (0.13, 0.004, 0.09), root, bevel=0.003)
    scr.matrix_basis = Matrix.Translation((0.52, 0.45, 2.3)) @ Matrix.Rotation(rad(-35), 4, "Z") @ Matrix.Rotation(rad(-18), 4, "X")
    box("terminal_back", trim, (0.39, 0.32, 2.17), (0.62, 0.52, 2.42), root, bevel=0.02).scale = (1, 1, 1)
    box("dash", trim, (-0.5, 0.55, 1.56), (0.5, 0.76, 1.85), root, bevel=0.04)
    bar("steering_col", trim, (0, 0.62, 1.62), (0, 0.42, 2.06), 0.035, root)
    torus("steering_wheel", trim, 0.19, 0.018, root, Matrix.Translation((0, 0.42, 2.08)) @ Matrix.Rotation(rad(-58), 4, "X"))
    # ---- rear fenders: curved shells over the rear tyres with a flared lip, lights on their trailing ends
    for s in (-1, 1):
        secs = []
        for i in range(13):
            a = rad(lerp(-25, 165, i / 12))
            rr = 0.95
            cy, cz = math.cos(a) * rr, 0.848 + math.sin(a) * rr
            ox = s * (TRACK_X + 0.28)
            ix = s * (TRACK_X - 0.27)
            secs.append([Vector((ix, cy, cz)), Vector((lerp(ix, ox, 0.5), cy * 1.02, 0.848 + math.sin(a) * rr * 1.02)),
                         Vector((ox, cy * 1.0, cz)), Vector((ox + s * 0.02, cy * 0.98, 0.848 + math.sin(a) * rr * 0.96))])
        if s < 0:
            secs = [sec[::-1] for sec in secs]
        f = loft(f"fender{s}", secs, body, root, subd=2)
        solid(f, 0.012)
        box(f"tail{s}", tail, (s * (TRACK_X + 0.12) - 0.05, -0.95, 1.12), (s * (TRACK_X + 0.12) + 0.05, -0.9, 1.2), root, bevel=0.01)
        box(f"rear_ind{s}", indic, (s * (TRACK_X + 0.12) - 0.05, -0.95, 1.21), (s * (TRACK_X + 0.12) + 0.05, -0.9, 1.25), root, bevel=0.008)
    # front mudguards (follow the wheels' arc, fixed to the hubs' carriers)
    for s in (-1, 1):
        secs = []
        for i in range(9):
            a = rad(lerp(20, 160, i / 8))
            rr = 0.6
            cy, cz = 2.45 + math.cos(a) * rr, 0.508 + math.sin(a) * rr
            secs.append([Vector((s * (TRACK_X - 0.17), cy, cz)), Vector((s * TRACK_X, cy * 1.0 + (cy - 2.45) * 0.03, cz + 0.02)), Vector((s * (TRACK_X + 0.17), cy, cz))])
        if s < 0:
            secs = [sec[::-1] for sec in secs]
        f = loft(f"mudguard{s}", secs, blackp, root, subd=2)
        solid(f, 0.008)
        bar(f"mudguard_arm{s}", darkmetal, (s * 0.62, 2.45, 0.6), (s * (TRACK_X - 0.05), 2.45, 1.08), 0.02, root)

    # ---- three-point hitch and PTO at the rear
    for s in (-1, 1):
        bar(f"lower_link{s}", darkmetal, (s * 0.25, -0.45, 0.55), (s * 0.42, -1.25, 0.5), 0.035, root)
        bar(f"lift_arm{s}", darkmetal, (s * 0.3, -0.5, 1.22), (s * 0.34, -1.05, 1.08), 0.04, root)
        bar(f"lift_rod{s}", steel, (s * 0.34, -1.02, 1.08), (s * 0.4, -0.95, 0.55), 0.018, root)
        cyl(f"hitch_ball{s}", steel, 0.05, 0.07, center=(s * 0.42, -1.27, 0.5), axis="X", parent=root, bevel=0.01)
    bar("top_link", darkmetal, (0, -0.55, 1.22), (0, -1.15, 1.08), 0.035, root)
    cyl("top_link_turnbuckle", steel, 0.045, 0.2, center=(0, -0.85, 1.15), axis="Y", parent=root, bevel=0.008)
    cyl("pto_guard", blackp, 0.1, 0.18, center=(0, -0.62, 0.78), axis="Y", parent=root, bevel=0.01, segs=24)
    box("drawbar", darkmetal, (-0.06, -1.1, 0.38), (0.06, -0.4, 0.46), root, bevel=0.01)

    # ---- badges (generic model plate, no brand)
    for s in (-1, 1):
        cu = bpy.data.curves.new(f"badge{s}", "FONT")
        cu.body = "AX9"
        cu.size = 0.1
        cu.extrude = 0.0015
        cu.align_x = "CENTER"
        ob = bpy.data.objects.new(f"badge{s}", cu)
        ob.data.materials.append(chrome)
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = root
        w = lerp(0.47, 0.405, 0.42) + 0.006
        ob.matrix_basis = Matrix.Translation((s * w, lerp(0.86, 3.22, 0.42), 1.36)) @ Matrix.Rotation(rad(90), 4, "X") @ Matrix.Rotation(s * rad(90), 4, "Y")

    # ---- the boom: clamp on the roof corner, tube out over the rows, camera housing (real geometry: the film's
    #      CAMERA tag and field-of-view wedge are drawn from its lens)
    boomM = metal("boom", (0.06, 0.065, 0.075), 0.35, mud=0.0, dust=0.3)
    a, b = Vector((0.75, 0.6, 3.0)), BOOM + Vector((0, 0, 0.12))
    bar("boom_arm", boomM, a, b, 0.045, root, sides=24)
    box("boom_clamp", boomM, (0.66, 0.5, 2.94), (0.86, 0.72, 3.08), root, bevel=0.02)
    bar("boom_cable", hose_m, a + Vector((0, 0, 0.06)), b + Vector((0, -0.1, 0.06)), 0.009, root)
    camb = empty("boomcam", root)
    camb.matrix_basis = Matrix.Translation(BOOM) @ Matrix.Rotation(-BOOM_TILT, 4, "X")
    cambody = principled("cambody", (0.02, 0.02, 0.025), rough=0.35, coat=0.6)
    box("cam_body", cambody, (-0.13, -0.1, -0.08), (0.13, 0.12, 0.09), camb, bevel=0.025)
    box("cam_hood", cambody, (-0.12, 0.08, 0.06), (0.12, 0.2, 0.09), camb, bevel=0.01)
    cyl("cam_lens", glass_material("cam_glass", (0.6, 0.65, 0.75)), 0.055, 0.06, center=(0, 0.14, 0), axis="Y", parent=camb, bevel=0.01, segs=40)
    cyl("cam_ring", violet, 0.066, 0.015, center=(0, 0.125, 0), axis="Y", parent=camb, bevel=0.003, segs=40)
    box("cam_led", violet, (-0.1, -0.02, 0.09), (-0.06, 0.02, 0.1), camb, bevel=0.002)
    bar("cam_mount", boomM, (0, -0.05, 0.08), (0, -0.05, 0.16), 0.03, camb)

    # ---- the tractor's own lights (subtle in daylight): headlamps, roof work lights, the boom's flood
    for s in (-1, 1):
        for (loc, rot, e) in (((s * 0.27, 3.3, 1.58), (rad(84), 0, 0), 60), ((s * 0.4, 1.0, 3.0), (rad(60), 0, s * rad(-8)), 120)):
            ld = bpy.data.lights.new("lamp", "SPOT")
            ld.energy, ld.spot_size, ld.spot_blend, ld.color = e, rad(60), 0.6, (1.0, 0.95, 0.88)
            ld.shadow_soft_size = 0.05
            lo = bpy.data.objects.new("lamp", ld)
            bpy.context.scene.collection.objects.link(lo)
            lo.parent = root
            lo.location = loc
            lo.rotation_euler = rot
    return root, wheels, camb


# ---------------------------------------------------------------------------- the shot
ROOT_Z = -0.036            # the tractor sits 3.6 cm low: the lugs sink into the soft floor of the ruts


def cam_path(T, nfr, camb_basis):
    """Per frame: tractor y, camera eye, target, focus point and boom lens point (world). The move as before:
    a low 3/4 front tracking shot with a slow orbit, then from cTr + 0.1 a 0.9 s push that ends just behind and
    above the boom camera, looking where it looks (the cut to its feed)."""
    t0, cTr = T["t0"], T["cTr"]
    out = []
    for f in range(-1, nfr + 2):
        tau = f / FPS
        t = t0 + tau
        y = -2.0 + SPEED_M * tau
        Mr = Matrix.Translation((0.0, y, ROOT_Z))
        lens_w = Mr @ camb_basis @ Vector((0, 0.17, 0))
        p = clamp(tau / (cTr + 0.1 - t0))
        side = Vector((lerp(7.4, 5.2, ios(p)), y + lerp(7.8, 3.6, ios(p)), lerp(1.25, 2.3, ios(p))))
        look = Vector((lerp(0.2, 0.9, ios(p)), y + lerp(1.4, 2.4, ios(p)), lerp(1.45, 2.1, ios(p))))
        push = ioc(clamp((t - (cTr + 0.1)) / 0.9))
        Mc = Mr @ camb_basis
        fwd = (Mc.to_3x3() @ Vector((0, 1, 0))).normalized()
        near = lens_w - fwd * 0.75 + Vector((0.22, 0, 0.32))
        eye = side.lerp(near, push)
        tgt = look.lerp(lens_w + fwd * 3.0, push)
        focus = Vector((0.0, y + 1.0, 1.6)).lerp(lens_w, clamp(push * 1.3))
        out.append(dict(f=f, y=y, eye=eye, tgt=tgt, focus=focus, lens=lens_w))
    return out


def visible_filter(path, pts, rmax, margin=0.2):
    """Indices of points that any frame's camera can see (frustum + margin) within rmax of it. The set is fixed
    for the whole shot, so nothing appears or disappears; points near rmax are thinned with a smooth falloff."""
    import numpy as np
    P = np.asarray(pts, dtype=np.float64)
    best = np.full(len(P), 1e9)
    tx = math.tan(math.atan(960 / F_PX)) + margin
    ty = math.tan(math.atan(540 / F_PX)) + margin
    for c in path[::3]:
        e, t = np.array(c["eye"]), np.array(c["tgt"])
        fwd = t - e
        fwd /= np.linalg.norm(fwd)
        right = np.cross(fwd, [0, 0, 1.0])
        right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        v = P - e
        z = v @ fwd
        ok = (z > 0.1) & (np.abs(v @ right) < z * tx + 1.0) & (np.abs(v @ up) < z * ty + 1.0)
        d = np.linalg.norm(v, axis=1)
        best = np.where(ok, np.minimum(best, d), best)
    return best


def build_tractor(sc, a):
    import numpy as np
    T = IN["tractor"]
    plate = IN["plates"]["tractor"]
    nfr = plate["frames"]
    rnd = random.Random(5)
    sky_world(sc)
    sun_lamp(sc)
    camb_basis = Matrix.Translation(BOOM) @ Matrix.Rotation(-BOOM_TILT, 4, "X")
    path = cam_path(T, nfr, camb_basis)
    near = build_ground(sc)
    # ---- lettuce: every plant the camera can see within LETTUCE_R, as instances of 10 modelled variants
    variants = lettuce_variants(10)
    cand = []
    for r in range(int(math.floor(FMESH[0] / ROW_W)), int(math.floor(FMESH[1] / ROW_W)) - 1):
        x = (r + 0.5) * ROW_W
        for k in range(-148, 440):
            cand.append((x, k * PLANT_P))
    cand = np.array(cand)
    cand = cand[(cand[:, 1] > FMESH[2] + 1.2) & (cand[:, 1] < FMESH[3] - 2)]
    P3 = np.column_stack([cand, np.full(len(cand), 0.1)])
    best = visible_filter(path, P3, LETTUCE_R)
    keep = []
    for i, (x, y) in enumerate(cand):
        h = (math.sin(x * 12.9898 + y * 78.233) * 43758.5453) % 1.0      # a fixed per-plant hash
        fade = smoothstep(LETTUCE_R - 40, LETTUCE_R, best[i])            # thin out over the last 40 m
        if best[i] > LETTUCE_R or h < fade or h < 0.025:                 # (and a missing plant here and there)
            continue
        keep.append((x, y))
    lets = []
    for (x, y) in keep:
        x2 = x + rnd.uniform(-0.025, 0.025)
        y2 = y + rnd.uniform(-0.04, 0.04)
        s = 0.34 * rnd.uniform(0.82, 1.18)
        lets.append((x2, y2, field_z(x2, y2) - 0.012, rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), rnd.uniform(0, math.tau), s, s, s * rnd.uniform(0.85, 1.1), rnd.randrange(len(variants))))
    lobs = [bpy.data.objects.new(f"lv{i}", me) for i, me in enumerate(variants)]
    if not os.environ.get("AIV_NOLET"):
        instancer("lettuce", lobs, lets)
    print(f"{len(lets)} lettuce instances", flush=True)
    # ---- clods, stones, straw on the near soil (instances), only where the camera looks
    clod_objs = soil_bits()
    pts = []
    for _ in range(60000):
        x, y = rnd.uniform(-26.0, 14.0), rnd.uniform(-24.0, 34.0)
        pts.append((x, y))
    P3 = np.array([(x, y, 0.0) for x, y in pts])
    best = visible_filter(path, P3, 40.0, margin=0.1)
    bits = []
    for i, (x, y) in enumerate(pts):
        if best[i] > 40:
            continue
        dr = abs((x % ROW_W) - ROW_W * 0.5)
        if dr < 0.12 and rnd.random() < 0.8:
            continue                                         # the plants cover the bed tops
        rutw = rut_w(x) if abs(x) < 1.1 else 0
        if rutw > 0.5 and rnd.random() < 0.85:
            continue                                         # the tyres pressed the ruts flat
        kind = rnd.random()
        if kind < 0.86:
            s = rnd.uniform(0.012, 0.045)
            idx = rnd.randrange(5)
            bits.append((x, y, field_z(x, y) + s * 0.15, rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, math.tau), s, s * rnd.uniform(0.7, 1.2), s * rnd.uniform(0.5, 0.8), idx))
        elif kind < 0.93:
            s = rnd.uniform(0.01, 0.03)
            bits.append((x, y, field_z(x, y) + s * 0.2, 0, 0, rnd.uniform(0, math.tau), s, s * 0.8, s * 0.6, 5))
        else:
            L = rnd.uniform(0.08, 0.3)
            bits.append((x, y, field_z(x, y) + 0.008, rad(90) + rnd.uniform(-0.15, 0.15), 0, rnd.uniform(0, math.tau), 1, 1, L, 6))
    instancer("soil_bits", clod_objs, bits)
    print(f"{len(bits)} soil bits", flush=True)
    build_landscape(sc, rnd)
    if not os.environ.get("AIV_NOVEG"):
        build_vegetation(sc, rnd, [c["eye"] for c in path])
    # ---- the tractor
    root, wheels, camb = build_tractor_model()
    cam = camera(sc, f_px=F_PX, dof=a.fstop, clip_end=12000.0)
    cam.data.clip_start = 0.03
    focus = empty("focus")
    cam.data.dof.focus_object = focus
    K = Keyer()
    for c in path:
        f = c["f"]
        tau = f / FPS
        K.mat(root, Matrix.Translation((0.0, c["y"], ROOT_Z)), f)
        for hub, r, tyre_ob in wheels:
            ang = -(SPEED_M * tau) / r
            hub.rotation_euler = (ang, 0, 0)
            hub.keyframe_insert("rotation_euler", frame=f)
            ident = tyre_ob["bulge_angle_id"]
            sock = getattr(tyre_ob.modifiers["bulge"].properties.inputs, ident)
            sock.value = ang
            tyre_ob.keyframe_insert(data_path=sock.path_from_id() + ".value", frame=f)
        K.look(cam, c["eye"], c["tgt"], f)
        K.mat(focus, Matrix.Translation(c["focus"]), f)
    Keyer.linear()
    # true displacement is diced for the camera as it is on each frame
    sc.cycles.dicing_rate = 1.0
    sc.cycles.offscreen_dicing_scale = 6.0
    sc.cycles.max_subdivisions = 8

    def export(sc):
        W, H = plate["w"], plate["h"]
        lens, foot = [], []
        for f in range(nfr):
            sc.frame_set(f)
            M = camb.matrix_world
            o = M @ Vector((0, 0.17, 0))
            lens.append(list(project(sc, cam, o, W, H)[:2]))
            # the camera's footprint: four rays through its frustum corners, met with the ground (z = 0.04)
            corners = []
            for sx, sy in ((-1, 1), (1, 1), (1, -1), (-1, -1)):
                d = (M.to_3x3() @ Vector((sx * 0.55, 1.0, sy * 0.38))).normalized()
                s = (0.04 - o.z) / d.z if d.z < -1e-3 else 50
                corners.append(list(project(sc, cam, o + d * s, W, H)[:2]))
            foot.append(corners)
        return {"lens": lens, "foot": foot}

    return {"frames": nfr, "w": plate["w"], "h": plate["h"], "export": export}


def soil_bits():
    """Clods (5 shapes), a pale stone, a straw stalk: the instance sources for the near soil."""
    clod = principled("clod", (0.075, 0.055, 0.04), rough=0.92)
    n = Nodes(clod)
    tc = n.new("ShaderNodeTexCoord")
    nz = n.new("ShaderNodeTexNoise", Scale=6.0, Detail=8.0)
    n.link(tc.outputs["Object"], nz.inputs["Vector"])
    n.link(n.ramp(nz.outputs["Fac"], [(0.35, (0.05, 0.036, 0.027)), (0.65, (0.17, 0.13, 0.095))]), n.bsdf.inputs["Base Color"])
    bp = n.new("ShaderNodeBump", Strength=0.7, Distance=0.1)
    n.link(nz.outputs["Fac"], bp.inputs["Height"])
    n.link(bp.outputs["Normal"], n.bsdf.inputs["Normal"])
    stone = principled("stone", (0.2, 0.19, 0.17), rough=0.6)
    straw = principled("straw", (0.45, 0.36, 0.2), rough=0.7)
    obs = []
    for i in range(6):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        for v in bm.verts:
            v.co *= 1 + noise.noise(v.co * 2.2 + Vector((i * 1.7, 0, 0))) * 0.4 + noise.noise(v.co * 6 + Vector((0, i, 0))) * 0.08
        for f in bm.faces:
            f.smooth = True
        me = bpy.data.meshes.new(f"clod{i}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(clod if i < 5 else stone)
        obs.append(bpy.data.objects.new(f"clod{i}", me))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.004, radius2=0.003, depth=1.0)
    me = bpy.data.meshes.new("straw")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(straw)
    obs.append(bpy.data.objects.new("straw", me))
    return obs


# ---------------------------------------------------------------------------- main
def main():
    def extra(ap):
        ap.add_argument("--shot", choices=["tractor", "feed"], required=True)
        ap.add_argument("--sun-az", type=float, default=SUN["az"], help="sun azimuth, degrees counter-clockwise from +x")
        ap.add_argument("--sun-el", type=float, default=SUN["el"], help="sun elevation, degrees")
        ap.add_argument("--fstop", type=float, default=4.5)
        ap.add_argument("--clamp", type=float, default=10.0, help="indirect light clamp")
    a = args("tractor", extra)
    SUN["az"], SUN["el"] = a.sun_az, a.sun_el
    if a.out.endswith(os.path.join("plates", "tractor")) and a.shot != "tractor":
        a.out = a.out[: -len("tractor")] + a.shot
    sc = new_scene()
    info = build_tractor(sc, a) if a.shot == "tractor" else build_feed(sc, a)
    W, H = info["w"], info["h"]
    setup_render(sc, a.samples, a.res, W, H, adaptive=a.threshold or 0.01, device=a.device, min_samples=a.min_samples,
                 clamp_indirect=a.clamp, bounces=(10, 4, 6, 8), persistent=a.shot != "tractor", exr=a.exr)
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = a.exposure
    if info["export"] and not a.no_export:
        pts = info["export"](sc)
        write_shot(a.shot, {"fps": FPS, "frames": info["frames"], "w": W, "h": H, "pts": pts, "cam": []})
    if not a.export_only:
        render_frames(sc, a, info["frames"])


if __name__ == "__main__":
    main()
