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
    FPS, Keyer, Nodes, args, area, box, camera, clamp, cyl, empty, finish, haze, inputs, ioc, lerp, new_scene,
    physical_sky, principled, project, render_frames, setup_render, sun, wear, write_shot, ios, rad,
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
    col = n.ramp(fac, [(0.05, (0.62 + hue_shift, 0.78, 0.26)), (0.35, (0.30 + hue_shift, 0.60, 0.10)), (0.7, (0.09, 0.36 + hue_shift * 0.5, 0.05)), (1.1, (0.035, 0.16, 0.025))])
    n.link(col, n.bsdf.inputs["Base Color"])
    n.bsdf.inputs["Subsurface Weight"].default_value = 0.35
    n.bsdf.inputs["Subsurface Radius"].default_value = (0.25, 0.6, 0.12)
    n.bsdf.inputs["Subsurface Scale"].default_value = 0.02
    n.bsdf.inputs["Transmission Weight"].default_value = 0.08
    n.bsdf.inputs["Coat Weight"].default_value = 0.35
    n.bsdf.inputs["Coat Roughness"].default_value = 0.12
    # dew: tiny bright droplets as low-roughness specks
    dew = n.new("ShaderNodeTexVoronoi", Scale=90.0)
    n.link(tc.outputs["Object"], dew.inputs["Vector"])
    drop = n.math("LESS_THAN", dew.outputs["Distance"], 0.08)
    n.link(n.math("SUBTRACT", 0.45, n.math("MULTIPLY", drop, 0.38)), n.bsdf.inputs["Roughness"])
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
def build_feed(sc):
    F = IN["feed"]
    FR, SPEED, PITCH = F["FRAME"], F["SPEED"], F["PITCH"]
    U = 0.01  # world units per feed pixel
    t0 = F["t0"]
    plate = IN["plates"]["feed"]
    nfr = plate["frames"]

    variants = lettuce_variants(10)
    rows_x = [(F["ROW_X0"] - FR["x"] + r * F["ROW_DX"]) * U for r in range(F["ROWS"])]

    # ground: raised beds under each row, furrows between (field Y range covers every frame of the plate)
    y_lo = (FR["h"] * 0.5 + 120 + (t0 - 0.5) * SPEED - FR["h"]) * U - 2
    y_hi = (FR["h"] * 0.5 + 120 + (t0 + nfr / FPS + 0.5) * SPEED + FR["h"]) * U + 2
    bm = bmesh.new()
    nx, ny = 220, int((y_hi - y_lo) / 0.06)
    bmesh.ops.create_grid(bm, x_segments=nx, y_segments=ny, size=0.5)
    for v in bm.verts:
        x = (v.co.x + 0.5) * (FR["w"] * U + 2) - 1
        y = y_lo + (v.co.y + 0.5) * (y_hi - y_lo)
        d = min(abs(x - rx) for rx in rows_x)
        bed = 0.16 * (0.5 + 0.5 * math.cos(min(d / 1.22, 1.0) * math.pi))
        z = bed + noise.noise(Vector((x * 1.7, y * 1.7, 0.3))) * 0.05 + noise.noise(Vector((x * 6, y * 6, 1.3))) * 0.015
        v.co = Vector((x, y, z))
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new("ground")
    bm.to_mesh(me)
    bm.free()
    ground = bpy.data.objects.new("ground", me)
    sc.collection.objects.link(ground)
    ground.data.materials.append(soil_material(1.0))

    def bed_z(x, y):
        d = min(abs(x - rx) for rx in rows_x)
        return 0.16 * (0.5 + 0.5 * math.cos(min(d / 1.22, 1.0) * math.pi)) + noise.noise(Vector((x * 1.7, y * 1.7, 0.3))) * 0.05
    scatter_soil(random.Random(9), (-0.5, FR["w"] * U + 0.5, y_lo, y_hi, bed_z), 7000, scale=2.4)

    # plants, straight from the film's field model
    for p in F["plants"]:
        if p["missing"]:
            continue
        x = (F["ROW_X0"] - FR["x"] + p["r"] * F["ROW_DX"] + p["jx"]) * U
        y = (p["k"] * PITCH + p["jy"]) * U
        if y < y_lo + 1 or y > y_hi - 1:
            continue
        sz = 116 * p["s"] * U * 0.92          # same footprint as the film's sprite
        d = min(abs(x - rx) for rx in rows_x)
        z = 0.16 * (0.5 + 0.5 * math.cos(min(d / 1.22, 1.0) * math.pi)) - 0.01
        rnd = random.Random(p["r"] * 1000 + p["k"])
        instance(f"plant_{p['r']}_{p['k']}", variants[p["v"]], (x, y, z), rnd.random() * math.tau, sz)

    # light: the boom's flood light from above and slightly behind, a cool sky fill, a faint warm bounce
    # the boom's LED flood: a small hard source up and to one side (crisp leaf shadows), plus the dusk sky's blue
    ld = bpy.data.lights.new("flood", "SPOT")
    ld.energy, ld.spot_size, ld.spot_blend, ld.shadow_soft_size, ld.color = 6500, rad(140), 0.8, 0.35, (1.0, 0.95, 0.88)
    fl = bpy.data.objects.new("flood", ld)
    sc.collection.objects.link(fl)
    from blender_common import look_at
    look_at(fl, (5.0, -2.2, 7.5), (8.1, 0.4, 0))
    area("fill", (15, 2, 6.0), (8.1, 0, 0), 8.0, 90, (0.45, 0.55, 1.0))
    area("bounce", (8.1, 0, -3), (8.1, 0, 0), 14.0, 0, (1, 1, 1))
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.006, 0.008, 0.02, 1)
    sc.world = w
    # parent every light to the camera rig so the light travels with the boom
    rig = empty("rig")
    for ob in list(sc.collection.objects):
        if ob.type == "LIGHT":
            ob.parent = rig

    cam = camera(sc, ortho_scale=FR["w"] * U)
    K = Keyer()
    for f in range(-1, nfr + 2):
        t = t0 + f / FPS
        yc = (FR["h"] * 0.5 + 120 + t * SPEED) * U
        K.mat(cam, Matrix.Translation((FR["w"] * U * 0.5, yc, 20.0)), f)
        K.mat(rig, Matrix.Translation((0, yc, 0)), f)
    Keyer.linear()
    return {"frames": nfr, "w": plate["w"], "h": plate["h"], "export": None}


# ---------------------------------------------------------------------------- TRACTOR (dusk, perspective)
ROW_W, PLANT_P, SPEED_M = 0.76, 0.38, 2.2      # row spacing, plant pitch (m), tractor speed (m/s)
BOOM = Vector((1.55, 3.2, 2.55))               # camera housing, tractor-local (x right, y forward, z up)
BOOM_TILT = rad(62)                             # looking down-forward


def tire(name, mat, r, width, parent, lugs=30):
    """A real tyre: a rounded profile (bulging sidewalls, flat crown) revolved around the axle, with chevron lugs."""
    bm = bmesh.new()
    prof = []
    r_in = r * 0.62
    for i in range(25):                                   # profile in the (x across, z radial) plane
        a = i / 24 * math.pi
        x = -math.cos(a) * width * 0.5
        bulge = math.sin(a) ** 0.35
        prof.append(Vector((x, 0, r_in + (r - r_in) * bulge)))
    verts = [bm.verts.new(v) for v in prof]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(1, 0, 0), angle=math.tau, steps=72, use_merge=True)
    t = finish(name, bm, mat, parent, bevel=0)
    for i in range(lugs):
        side = 1 if i % 2 else -1
        lug = box(f"{name}_lug{i}", mat, (-width * 0.02, -0.04, -0.045), (width * 0.47, 0.04, 0.045), parent=t, bevel=0.015)
        lug.matrix_basis = Matrix.Rotation(i / lugs * math.tau, 4, "X") @ Matrix.Translation((0, 0, r - 0.01)) @ Matrix.Rotation(0.45 * side, 4, "Z") @ Matrix.Diagonal((side, 1, 1, 1))
    return t


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


def paint(name, color, mud=0.8):
    """Two-coat paint: metallic-flake base under a clearcoat, smudged roughness, and dried mud splashed up from the
    wheels (matte, brown) that kills the clearcoat where it sits."""
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    b = n.bsdf
    mask = n.math("MULTIPLY", mud_mask(n), mud)
    mix = n.new("ShaderNodeMix", _data_type="RGBA")
    n.link(mask, mix.inputs["Factor"])
    mix.inputs[6].default_value = (*color, 1)
    mix.inputs[7].default_value = (0.16, 0.12, 0.085, 1)
    n.link(mix.outputs[2], b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = 0.25
    n.link(n.math("ADD", wear(n, 0.28, 0.2, 4.0, scratches=0.1), n.math("MULTIPLY", mask, 0.6)), b.inputs["Roughness"])
    n.link(n.math("SUBTRACT", 1.0, mask), b.inputs["Coat Weight"])
    b.inputs["Coat Roughness"].default_value = 0.04
    return m


def tyre_rubber():
    m = bpy.data.materials.new("tyre")
    n = Nodes(m)
    dust = mud_mask(n, 0.0, 1.6)
    mix = n.new("ShaderNodeMix", _data_type="RGBA")
    n.link(n.math("MULTIPLY", dust, 0.85), mix.inputs["Factor"])
    mix.inputs[6].default_value = (0.016, 0.016, 0.018, 1)
    mix.inputs[7].default_value = (0.13, 0.1, 0.075, 1)
    n.link(mix.outputs[2], n.bsdf.inputs["Base Color"])
    n.link(n.math("ADD", wear(n, 0.62, 0.2, 12.0), n.math("MULTIPLY", dust, 0.25)), n.bsdf.inputs["Roughness"])
    return m


def build_tractor_model():
    body = paint("graphite", (0.032, 0.034, 0.04), mud=0.9)
    white = paint("white", (0.78, 0.79, 0.8), mud=0.35)
    rubber = tyre_rubber()
    rim = paint("rim", (0.52, 0.53, 0.55), mud=0.7)
    chrome = principled("chrome", (0.8, 0.8, 0.82), rough=0.12, metal=1.0)
    glass = principled("glass", (0.02, 0.025, 0.035), rough=0.05, coat=1.0)
    glass.node_tree.nodes["Principled BSDF"].inputs["Transmission Weight"].default_value = 0.6
    violet = principled("violet", (0.3, 0.1, 0.9), rough=0.3, emit=(0.51, 0.2, 1.0), emit_strength=6.0)
    lamp = principled("lamp", (1, 1, 1), emit=(1.0, 0.95, 0.85), emit_strength=40.0)

    root = empty("tractor")
    # wheels (each on its own empty so it can spin)
    wheels = []
    for (x, y, r, w) in [(-0.76, 0, 0.86, 0.4), (0.76, 0, 0.86, 0.4), (-0.76, 2.45, 0.52, 0.3), (0.76, 2.45, 0.52, 0.3)]:
        hub = empty(f"hub{x}{y}", root)
        hub.location = (x, y, r)
        t = tire(f"tire{x}{y}", rubber, r, w, hub)
        cyl(f"rim{x}{y}", rim, r * 0.6, w * 0.78, axis="X", parent=hub, bevel=0.03)          # recessed dish
        cyl(f"rimlip{x}{y}", rim, r * 0.64, w * 0.9, axis="X", parent=hub, bevel=0.012, r2=r * 0.64)
        for k in range(8):                                                                    # wheel nuts
            a = k / 8 * math.tau
            cyl(f"nut{x}{y}{k}", chrome, 0.025, w * 0.84, center=(0, math.cos(a) * r * 0.22, math.sin(a) * r * 0.22), axis="X", parent=hub, bevel=0.004, segs=6)
        cyl(f"cap{x}{y}", chrome, r * 0.13, w * 0.86, axis="X", parent=hub, bevel=0.01)
        wheels.append((hub, r))
    # chassis, hood, grille, cab
    box("chassis", body, (-0.42, -0.9, 0.55), (0.42, 3.0, 1.0), root, bevel=0.04)
    box("hood", body, (-0.5, 0.55, 0.95), (0.5, 3.15, 1.78), root, bevel=0.09)
    box("hood_top", white, (-0.46, 0.6, 1.74), (0.46, 3.05, 1.86), root, bevel=0.05)
    box("stripe", violet, (-0.505, 0.7, 1.52), (0.505, 3.05, 1.56), root, bevel=0.005)
    box("grille", principled("grille", (0.01, 0.01, 0.012), rough=0.6), (-0.42, 3.13, 1.0), (0.42, 3.2, 1.7), root, bevel=0.02)
    for s in (-1, 1):
        box(f"head{s}", lamp, (s * 0.38 - 0.08, 3.17, 1.42), (s * 0.38 + 0.08, 3.22, 1.5), root, bevel=0.01)
        box(f"fender{s}", body, (s * 0.7 - 0.36 * (s < 0), -1.0, 1.55), (s * 0.7 + 0.36 * (s > 0), 1.0, 1.66), root, bevel=0.03)
    cyl("exhaust", chrome, 0.06, 1.2, center=(-0.36, 2.6, 2.3), parent=root, bevel=0.01)
    box("cab_floor", body, (-0.75, -0.85, 1.4), (0.75, 0.8, 1.6), root, bevel=0.04)
    for x in (-0.72, 0.72):
        for y in (-0.8, 0.75):
            box(f"post{x}{y}", body, (x - 0.045, y - 0.045, 1.55), (x + 0.045, y + 0.045, 3.0), root, bevel=0.015)
    box("glass_front", glass, (-0.68, 0.72, 1.62), (0.68, 0.76, 2.95), root, bevel=0.0)
    box("glass_l", glass, (-0.74, -0.78, 1.62), (-0.7, 0.72, 2.95), root, bevel=0.0)
    box("glass_r", glass, (0.7, -0.78, 1.62), (0.74, 0.72, 2.95), root, bevel=0.0)
    box("glass_back", glass, (-0.68, -0.82, 1.62), (0.68, -0.78, 2.95), root, bevel=0.0)
    box("seat", principled("seat", (0.05, 0.05, 0.055), rough=0.8), (-0.25, -0.5, 1.6), (0.25, 0.0, 2.15), root, bevel=0.06)
    box("roof", white, (-0.86, -1.0, 2.95), (0.86, 0.95, 3.12), root, bevel=0.06)
    amber = principled("beacon", (1.0, 0.5, 0.05), rough=0.2, emit=(1.0, 0.45, 0.05), emit_strength=25.0)
    cyl("beacon", amber, 0.07, 0.12, center=(-0.6, -0.7, 3.2), parent=root, bevel=0.02, segs=24)
    for s in (-1, 1):
        box(f"mirror_arm{s}", body, (s * 0.85, 0.62, 2.55), (s * 1.12, 0.66, 2.58), root, bevel=0.005)
        box(f"mirror{s}", glass, (s * 1.1 - 0.04, 0.58, 2.3), (s * 1.1 + 0.04, 0.7, 2.62), root, bevel=0.01)
        for k in range(3):
            box(f"step{s}{k}", principled("tread", (0.2, 0.2, 0.21), rough=0.5, metal=1.0), (s * 0.78 - 0.12, -0.35, 0.55 + k * 0.32), (s * 0.78 + 0.12, 0.05, 0.58 + k * 0.32), root, bevel=0.01)
    for x in (-0.6, -0.2, 0.2, 0.6):
        box(f"worklamp{x}", lamp, (x - 0.07, 0.93, 3.0), (x + 0.07, 0.98, 3.08), root, bevel=0.01)
    # the boom: from the cab roof forward and out over the rows, ending in the camera housing
    boomM = principled("boom", (0.06, 0.065, 0.075), rough=0.35, metal=0.6)
    a, b = Vector((0.75, 0.6, 3.0)), BOOM + Vector((0, 0, 0.12))
    mid = (a + b) / 2
    d = b - a
    arm = cyl("boom_arm", boomM, 0.045, d.length, center=(0, 0, 0), parent=root, bevel=0.01)
    arm.matrix_basis = Matrix.Translation(mid) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    camb = empty("boomcam", root)
    camb.matrix_basis = Matrix.Translation(BOOM) @ Matrix.Rotation(-BOOM_TILT, 4, "X")
    box("cam_body", principled("cambody", (0.02, 0.02, 0.025), rough=0.4, coat=0.6), (-0.13, -0.1, -0.08), (0.13, 0.12, 0.09), camb, bevel=0.025)
    cyl("cam_lens", glass, 0.055, 0.06, center=(0, 0.14, 0), axis="Y", parent=camb, bevel=0.01)
    cyl("cam_ring", violet, 0.066, 0.015, center=(0, 0.125, 0), axis="Y", parent=camb, bevel=0.003)
    box("cam_led", violet, (-0.1, -0.02, 0.09), (-0.06, 0.02, 0.1), camb, bevel=0.002)
    # lights the tractor carries: two cab work lights forward, the boom's flood down at its footprint
    lights = []
    for s in (-1, 1):
        ld = bpy.data.lights.new(f"work{s}", "SPOT")
        ld.energy, ld.spot_size, ld.spot_blend, ld.color = 900, rad(70), 0.5, (1.0, 0.94, 0.84)
        lo = bpy.data.objects.new(f"work{s}", ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.parent = root
        lo.location = (s * 0.5, 1.0, 3.05)
        lo.rotation_euler = (rad(58), 0, s * rad(-8))   # -Z tipped forward (+y) and down
        lights.append(lo)
    ld = bpy.data.lights.new("flood", "SPOT")
    ld.energy, ld.spot_size, ld.spot_blend, ld.color = 700, rad(75), 0.6, (0.92, 0.9, 1.0)
    fl = bpy.data.objects.new("flood", ld)
    bpy.context.scene.collection.objects.link(fl)
    fl.parent = root
    fl.location = BOOM + Vector((0, -0.05, 0.12))
    fl.rotation_euler = (rad(26), 0, 0)
    # lights that ride with the tractor so its shape reads against the dusk: a violet rim from behind, a cool key
    for name, loc, tgt, size, power, col in [("rim", (-3.5, -3.0, 4.2), (0, 1.0, 1.4), 2.5, 900, (0.55, 0.25, 1.0)),
                                             ("rim2", (3.0, -3.5, 3.0), (0, 1.0, 1.2), 2.0, 500, (0.35, 0.45, 1.0)),
                                             ("key", (5.5, 6.5, 3.2), (0, 1.2, 1.3), 3.5, 380, (0.85, 0.9, 1.0))]:
        area(name, loc, tgt, size, power, col).parent = root
    return root, wheels, camb


def sky_world(sc):
    w = bpy.data.worlds.new("dusk")
    n = Nodes(w)
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    n.link(tc.outputs["Generated"], sep.inputs[0])
    z = n.math("MULTIPLY", n.math("ADD", sep.outputs[2], 0.02), 3.0, clamp_=True)
    col = n.ramp(z, [(0.0, (0.30, 0.13, 0.20)), (0.08, (0.17, 0.09, 0.22)), (0.3, (0.04, 0.035, 0.11)), (1.0, (0.006, 0.008, 0.025))])
    n.link(col, bg.inputs[0])
    bg.inputs[1].default_value = 1.0
    sc.world = w


def build_tractor(sc):
    T = IN["tractor"]
    plate = IN["plates"]["tractor"]
    nfr = plate["frames"]
    t0, cTr = T["t0"], T["cTr"]
    # last light: the physical sky with the sun a degree above the horizon, behind the tractor as the camera sees
    # it (a warm backlight that rims the machine and rakes across the rows), and low haze for depth and light shafts
    EL, ROT = 4.5, 233.0
    physical_sky(sc, EL, ROT, strength=0.16, aerosol=0.7, sun_disc=True, sun_intensity=0.4)
    d = Vector((math.sin(rad(ROT)) * math.cos(rad(EL)), math.cos(rad(ROT)) * math.cos(rad(EL)), math.sin(rad(EL))))
    sun("sun", -d, 3.2, (1.0, 0.55, 0.28), angle=0.6)

    variants = lettuce_variants(10)
    ground = bpy.data.objects.new("field", bpy.data.meshes.new("field"))
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=240, y_segments=400, size=0.5)
    for v in bm.verts:
        x = v.co.x * 34
        y = (v.co.y + 0.5) * 140 - 30
        d = abs(((x + ROW_W * 0.5) % ROW_W) - ROW_W * 0.5)
        z = 0.07 * (0.5 + 0.5 * math.cos(min(d / (ROW_W * 0.5), 1) * math.pi)) + noise.noise(Vector((x * 0.6, y * 0.6, 0))) * 0.04
        v.co = Vector((x, y, z))
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(ground.data)
    bm.free()
    sc.collection.objects.link(ground)
    ground.data.materials.append(soil_material(2.2))
    meadow = bpy.data.materials.new("meadow")
    mn = Nodes(meadow)
    mtc = mn.new("ShaderNodeTexCoord")
    mnz = mn.new("ShaderNodeTexNoise", Scale=0.02, Detail=8.0)
    mn.link(mtc.outputs["Object"], mnz.inputs["Vector"])
    mn.link(mn.ramp(mnz.outputs["Fac"], [(0.35, (0.05, 0.06, 0.025)), (0.65, (0.11, 0.1, 0.05))]), mn.bsdf.inputs["Base Color"])
    mn.bsdf.inputs["Roughness"].default_value = 0.95
    far = box("far_ground", meadow, (-1500, -1500, -0.08), (1500, 1500, -0.03), bevel=0)   # meadows out to the horizon
    # a tree line and a farm shed on the far edge of the field, softened by distance haze (aerial perspective)
    foliage = principled("foliage", (0.03, 0.045, 0.025), rough=0.85)
    trunk = principled("trunk", (0.04, 0.03, 0.025), rough=0.9)
    trnd = random.Random(12)
    crowns = []
    for i in range(12):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        for v in bm.verts:
            v.co *= 1 + noise.noise(v.co * 2.3 + Vector((i * 3.1, 0, 0))) * 0.28 + noise.noise(v.co * 7 + Vector((0, i, 0))) * 0.06
        me = bpy.data.meshes.new(f"crown{i}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(foliage)
        crowns.append(me)
    for i in range(1600):                                  # a continuous ring of woodland around the field, far off
        ang = trnd.uniform(0, math.tau)
        rr = 400 + trnd.uniform(0, 110) + 40 * math.sin(ang * 5)
        x, y = math.cos(ang) * rr, 20 + math.sin(ang) * rr
        hgt = trnd.uniform(12, 26)
        for k in range(3):                                 # each tree is a clump of crowns
            ob = bpy.data.objects.new(f"tree{i}_{k}", crowns[trnd.randrange(12)])
            sc.collection.objects.link(ob)
            sz = hgt * (0.36 - 0.07 * k)
            ob.location = (x + trnd.uniform(-3, 3), y + trnd.uniform(-3, 3), sz * 0.55 + hgt * 0.28 * k)
            ob.scale = (sz, sz, sz * 1.1)
    shed = principled("shed", (0.32, 0.3, 0.28), rough=0.6, metal=0.4)
    box("shed", shed, (-250, -150, 0), (-218, -128, 9), bevel=0.2)
    box("shed_roof", shed, (-252, -152, 9), (-216, -126, 11.5), bevel=0.2)
    # four slabs around a clear core, so rays near the camera never march through a volume (it is the slow part)
    for i, (lo, hi) in enumerate([((-1400, -1400), (1400, -60)), ((-1400, 100), (1400, 1400)), ((-1400, -60), (-80, 100)), ((80, -60), (1400, 100))]):
        haze(f"haze_far{i}", (lo[0], lo[1], -1), (hi[0], hi[1], 120), density=0.0015, color=(1.0, 0.84, 0.72), anisotropy=0.55, height_falloff=0.05)
    rnd = random.Random(5)
    for r in range(-12, 13):
        x = r * ROW_W + ROW_W * 0.5
        for k in range(-50, 300):
            y = k * PLANT_P + (rnd.random() - 0.5) * 0.06
            if y > 95 or rnd.random() < 0.03:
                continue
            s = 0.32 * (0.8 + rnd.random() * 0.4)
            instance(f"l{r}_{k}", variants[rnd.randrange(10)], (x + (rnd.random() - 0.5) * 0.04, y, 0.06), rnd.random() * math.tau, s)

    def field_z(x, y):
        dd = abs(((x + ROW_W * 0.5) % ROW_W) - ROW_W * 0.5)
        return 0.07 * (0.5 + 0.5 * math.cos(min(dd / (ROW_W * 0.5), 1) * math.pi)) + noise.noise(Vector((x * 0.6, y * 0.6, 0))) * 0.04
    scatter_soil(random.Random(4), (-7, 9, -6, 22, field_z), 9000, scale=1.0)
    root, wheels, camb = build_tractor_model()
    cam = camera(sc, f_px=1600.0, dof=2.8)
    focus = empty("focus")
    cam.data.dof.focus_object = focus
    K = Keyer()
    # the tractor straddles the rows between x = -0.38 .. 0.38 and drives forward (+y)
    for f in range(-1, nfr + 2):
        tau = f / FPS
        t = t0 + tau
        y = -2.0 + SPEED_M * tau
        K.mat(root, Matrix.Translation((0.0, y, 0.0)), f)
        for hub, r in wheels:
            hub.rotation_euler = (-(SPEED_M * tau) / r, 0, 0)
            hub.keyframe_insert("rotation_euler", frame=f)
        lens_w = Matrix.Translation((0, y, 0)) @ camb.matrix_basis @ Vector((0, 0.17, 0))
        # camera: low 3/4 front view tracking with the tractor, slow orbit, then a push into the boom camera
        p = clamp(tau / (cTr + 0.1 - t0))
        side = Vector((lerp(7.4, 5.2, ios(p)), y + lerp(7.8, 3.6, ios(p)), lerp(1.25, 2.3, ios(p))))
        look = Vector((lerp(0.2, 0.9, ios(p)), y + lerp(1.4, 2.4, ios(p)), lerp(1.45, 2.1, ios(p))))
        # the push ends just behind and above the boom camera, looking where it looks: the cut to its feed
        push = ioc(clamp((t - (cTr + 0.1)) / 0.9))
        Mc = Matrix.Translation((0, y, 0)) @ camb.matrix_basis
        fwd = (Mc.to_3x3() @ Vector((0, 1, 0))).normalized()
        near = lens_w - fwd * 0.75 + Vector((0.22, 0, 0.32))
        eye = side.lerp(near, push)
        tgt = look.lerp(lens_w + fwd * 3.0, push)
        K.look(cam, eye, tgt, f)
        K.mat(focus, Matrix.Translation(Vector((0.0, y + 1.0, 1.6)).lerp(lens_w, clamp(push * 1.3))), f)
    Keyer.linear()

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


# ---------------------------------------------------------------------------- main
def main():
    a = args("tractor", lambda ap: ap.add_argument("--shot", choices=["tractor", "feed"], required=True))
    if a.out.endswith(os.path.join("plates", "tractor")) and a.shot != "tractor":
        a.out = a.out[: -len("tractor")] + a.shot
    sc = new_scene()
    info = build_tractor(sc) if a.shot == "tractor" else build_feed(sc)
    W, H = info["w"], info["h"]
    setup_render(sc, a.samples, a.res, W, H)
    sc.view_settings.exposure = a.exposure
    if info["export"] and not a.no_export:
        pts = info["export"](sc)
        write_shot(a.shot, {"fps": FPS, "frames": info["frames"], "w": W, "h": H, "pts": pts, "cam": []})
    if not a.export_only:
        render_frames(sc, a, info["frames"])


if __name__ == "__main__":
    main()
