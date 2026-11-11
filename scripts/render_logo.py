#!/usr/bin/env python3
"""
render_logo.py -- the 3D logo sting for the finale.

The Eagerworks icon (the supplied vector artwork, video/assets/logo/eagerworks-logo.svg) is extruded into
a slab of black glass whose three "E" strokes are cut clean through it. Violet light tubes sit inside the
cut-outs and ignite one after another while the camera starts close on them; strip lights streak across the
glass as the camera orbits and pulls back, and the slab turns white-hot as it comes exactly frontal -- the
frame the film dissolves into the flat white lockup.

Rendered with Cycles on the CPU over a transparent film, so the object is composited into the film's own
atmosphere (video/src/scenes/finale.js). Timing constants are mirrored there (LOGO3D).

    python scripts/render_logo.py                         # 90 frames -> video/build/plates/logo/
    python scripts/render_logo.py --samples 16 --res 0.5 --frames 0 45 89
    scripts/pack_plates.sh                                # frames -> video/assets/renders/logo*.mp4
"""
import argparse
import math
import os
import re
import sys
import time

import bpy
from mathutils import Vector, Matrix, Euler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30
DUR = 3.0
MOVE = 2.5          # the camera move ends here; the rest is a hold on the frontal icon
F_PX = 4500.0       # focal length in pixels on a 1920-wide frame (a long lens: the final frame is nearly flat)
END_DIST = 30.0     # icon height is 2 units -> 2 * F_PX / END_DIST = 300 px tall in the final frame
rad = math.radians


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, t):
    return a + (b - a) * t


def io_cubic(t):
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def io_sine(t):
    return -(math.cos(math.pi * t) - 1) / 2


# ---------------------------------------------------------------------------- the artwork
def icon_subpaths():
    svg = open(os.path.join(ROOT, "video", "assets", "logo", "eagerworks-logo.svg")).read()
    d = re.search(r'<path[^>]*\sd="([^"]+)"', svg).group(1)
    toks = re.findall(r"[MLCZ]|-?\d*\.?\d+(?:e-?\d+)?", d)
    subs, cur, i, cmd = [], None, 0, None
    while i < len(toks):
        if toks[i] in "MLCZ":
            cmd = toks[i]
            i += 1
            if cmd == "Z":
                subs.append(cur)
                cur = None
            continue
        n = {"M": 2, "L": 2, "C": 6}[cmd]
        v = [float(x) for x in toks[i:i + n]]
        i += n
        if cmd == "M":
            cur = [("M", v)]
            cmd = "L"
        else:
            cur.append((cmd, v))
    return subs


S = 2.0 / 70.0


def P(x, y):  # artwork units -> object space (x right, y up), centred on the icon
    return Vector(((x - 31.36) * S, (35.0 - y) * S, 0.0))


def add_spline(curve, sub):
    pts = []  # [co, handle_left, handle_right, left_is_vector, right_is_vector]
    for cmd, v in sub:
        if cmd == "M":
            pts.append([P(*v), None, None, True, True])
        elif cmd == "L":
            pts.append([P(*v), None, None, True, True])
        else:
            pts[-1][2], pts[-1][4] = P(v[0], v[1]), False
            pts.append([P(v[4], v[5]), P(v[2], v[3]), None, False, True])
    # a closing point that repeats the first one only carries its incoming handle
    if (pts[-1][0] - pts[0][0]).length < 1e-6:
        last = pts.pop()
        pts[0][1], pts[0][3] = last[1], last[3]
    sp = curve.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, (co, hl, hr, lv, rv) in zip(sp.bezier_points, pts):
        bp.co = co
        bp.handle_left_type = "VECTOR" if lv else "FREE"
        bp.handle_right_type = "VECTOR" if rv else "FREE"
        if not lv:
            bp.handle_left = hl
        if not rv:
            bp.handle_right = hr
    sp.use_cyclic_u = True


def curve_object(name, subs, extrude, bevel, mat, offset=0.0):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.resolution_u = 24
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 6
    cu.offset = offset
    for s in subs:
        add_spline(cu, s)
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler = Euler((rad(90), 0, 0))  # face towards -Y, up = +Z
    return ob


def principled(name, color, rough=0.4, metal=0.0, coat=0.0, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.08
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_strength
    return m


def area(name, loc, target, size, power, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.color, ld.size = power, color, size
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(loc)
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


# ---------------------------------------------------------------------------- camera move
def cam_pose(tau):
    s = clamp(tau / MOVE)
    k = io_cubic(s)
    az = rad(54) * (1 - k)
    el = rad(-13) * (1 - k)
    roll = rad(9) * (1 - k)
    dist = 4.3 * (END_DIST / 4.3) ** io_sine(s)
    tgt = Vector((0.39, 0.0, -0.20)) * (1 - k)
    eye = tgt + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
    return eye, tgt, roll, dist


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    except Exception:
        pass
    subs = icon_subpaths()
    strokes, hexagon = subs[:3], subs[3]
    # black glass that turns white-hot at the end (the frame that dissolves into the flat white icon)
    body_mat = principled("glass", (0.012, 0.012, 0.018), rough=0.085, coat=1.0, emit=(1.0, 1.0, 1.0), emit_strength=0.0)
    body_mat.node_tree.nodes["Principled BSDF"].inputs["Coat Roughness"].default_value = 0.03
    body_emit = body_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    # the bevel grows the outline (and narrows the cut-outs) by its depth: offset the curve back by the same amount
    curve_object("icon", [hexagon] + strokes, extrude=0.12, bevel=0.028, mat=body_mat, offset=-0.028)
    bars = []
    for i, st in enumerate(strokes):
        m = principled(f"tube{i}", (0.03, 0.01, 0.08), rough=0.3, emit=(0.27, 0.05, 1.0), emit_strength=0.0)
        ob = curve_object(f"tube{i}", [st], extrude=0.03, bevel=0.0, mat=m, offset=-0.004)
        ob.location = (0, 0.085, 0)
        bars.append(m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"])

    cd = bpy.data.cameras.new("cam")
    cd.sensor_fit, cd.sensor_width = "HORIZONTAL", 36.0
    cd.lens = F_PX / 1920.0 * 36.0
    cd.clip_start, cd.clip_end = 0.1, 500
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = 1.8
    cd.dof.aperture_blades = 9
    camo = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(camo)
    sc.camera = camo

    # strip lights along the arc the camera's mirror image travels: their reflections sweep across the
    # glass one after another as the camera orbits to the front
    for i, (az, el, power) in enumerate(((50, 12, 620), (31, 7, 520), (13, 3, 440))):
        d = Vector((-math.sin(rad(az)) * math.cos(rad(el)), -math.cos(rad(az)) * math.cos(rad(el)), math.sin(rad(el)))) * 9.0
        ld = bpy.data.lights.new(f"strip{i}", "AREA")
        ld.shape, ld.size, ld.size_y, ld.energy, ld.color = "RECTANGLE", 0.4, 7.0, power, (0.93, 0.95, 1.0)
        ob = bpy.data.objects.new(f"strip{i}", ld)
        sc.collection.objects.link(ob)
        ob.location = d
        ob.rotation_euler = (-d).to_track_quat("-Z", "Z").to_euler()
    area("rim_violet", (6.0, 3.0, 1.0), (0, 0, 0), 2.0, 2600, (0.36, 0.10, 1.0))
    area("rim_blue", (-5.5, 4.0, -1.5), (0, 0, 0), 2.5, 1800, (0.25, 0.42, 1.0))
    area("under", (2.0, -3.0, -5.0), (0, 0, 0), 3.0, 300, (0.45, 0.35, 1.0))
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.0015, 0.0015, 0.003, 1)
    sc.world = w

    for f in range(-1, int(DUR * FPS) + 2):
        tau = f / FPS
        eye, tgt, roll, dist = cam_pose(tau)
        q = (tgt - eye).to_track_quat("-Z", "Y")
        camo.rotation_mode = "QUATERNION"
        camo.location = eye
        camo.rotation_quaternion = q @ Euler((0, 0, roll)).to_quaternion()
        camo.keyframe_insert("location", frame=f)
        camo.keyframe_insert("rotation_quaternion", frame=f)
        cd.dof.focus_distance = dist
        cd.dof.keyframe_insert("focus_distance", frame=f)
        # the tubes ignite one after another, then settle as the face lights up
        for i, inp in enumerate(bars):
            on = io_sine(clamp((tau - 0.08 - i * 0.16) / 0.3))
            settle = io_sine(clamp((tau - 1.7) / 0.8))
            inp.default_value = lerp(0.0, 34.0, on) * lerp(1.0, 0.05, settle)
            inp.keyframe_insert("default_value", frame=f)
        body_emit.default_value = 6.0 * io_sine(clamp((tau - 1.5) / 0.95)) ** 2
        body_emit.keyframe_insert("default_value", frame=f)
    return sc


def setup_render(sc, samples, res):
    sc.render.engine = "CYCLES"
    c = sc.cycles
    c.device = "CPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.04
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 5, 3, 4
    c.caustics_reflective = c.caustics_refractive = False
    c.sample_clamp_indirect = 8.0
    sc.render.film_transparent = True
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = int(1920 * res), int(1080 * res)
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.compression = 15


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, nargs="*")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--res", type=float, default=1.0)
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--out", default=os.path.join(ROOT, "video", "build", "plates", "logo"))
    a = ap.parse_args(argv)
    sc = build()
    setup_render(sc, a.samples, a.res)
    sc.view_settings.exposure = a.exposure
    os.makedirs(a.out, exist_ok=True)
    for f in (a.frames if a.frames else range(int(DUR * FPS))):
        path = os.path.join(a.out, f"{f:04d}.png")
        if os.path.exists(path):
            continue
        t0 = time.time()
        sc.frame_set(f)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print(f"frame {f:4d}  {time.time() - t0:5.1f}s", flush=True)


if __name__ == "__main__":
    main()
