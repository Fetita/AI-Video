#!/usr/bin/env python3
"""
render_robot.py -- the photoreal robot-arm plate for the vision chapter ("ready to teach a robot").

A six-second shot built entirely from code with Blender's Python module (bpy) and rendered with Cycles on
the CPU: the arm is primitives with bevels, the materials are procedural shader graphs, the light is four
area lamps in a black studio, and the camera dollies slowly around the cell with a shallow depth of field
that follows the gripper.  The arm descends, grips the part at the pick pad, carries it along the
demonstrated arc and releases it on the place pad.

The kinematics and the camera below are mirrored in video/src/lib/robot-shot.js, which draws the film's
overlays (trajectory, labels, keypoints) on top of the plate with the same camera, so the two line up.

Setup: the same Python 3.11 venv as render_locations.py (`pip install bpy==5.0.1`).

    python scripts/render_robot.py                      # all 180 frames -> video/build/plates/robot/
    python scripts/render_robot.py --frames 60 120      # a subset (frame numbers)
    python scripts/render_robot.py --samples 16 --res 0.5 --frames 90   # quick preview
    scripts/pack_plates.sh                              # frames -> video/assets/renders/robot.mp4
"""
import argparse
import math
import os
import sys
import time

import bpy
import bmesh
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30
DUR = 6.0
rad = math.radians

# ---------------------------------------------------------------------------- shared with robot-shot.js
# "Film world": x right, y up, z forward (metres-ish).  to_bl() maps it into Blender's z-up world.
H0, L1, L2, GRIP = 0.55, 0.95, 0.85, 0.28
PICK, PLACE = (-1.05, 0.10, 0.75), (1.05, 0.10, 0.55)


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, t):
    return a + (b - a) * t


def ios(t):  # inOutSine
    return -(math.cos(math.pi * t) - 1) / 2


def demo_path(u):
    e = ios(u)
    s = math.sin(math.pi * u)
    return (lerp(PICK[0], PLACE[0], e), PICK[1] + s * 0.9, lerp(PICK[2], PLACE[2], e) + s * 0.35)


def move_u(tau):
    return ios(clamp((tau - 1.5) / 2.8))


def hover(tau):  # height of the tool centre above the grasp point: descends to grip, lifts off after the release
    return 0.30 * (1 - ios(clamp((tau - 0.25) / 0.85))) + 0.30 * ios(clamp((tau - 4.65) / 0.9))


def finger_gap(tau):
    close = ios(clamp((tau - 1.05) / 0.35))
    reopen = ios(clamp((tau - 4.3) / 0.3))
    return lerp(0.165, 0.115, close * (1 - reopen))


def tip(tau):
    p = demo_path(move_u(tau))
    return (p[0], p[1] + hover(tau), p[2])


def ik(T):
    yaw = math.atan2(T[0], T[2])
    wy = T[1] + GRIP
    d = math.hypot(T[0], T[2])
    hgt = wy - H0
    L = min(math.hypot(d, hgt), L1 + L2 - 1e-3)
    a2 = math.acos(clamp((L1 ** 2 + L2 ** 2 - L ** 2) / (2 * L1 * L2), -1, 1))
    a1 = math.atan2(hgt, d) + math.acos(clamp((L1 ** 2 + L ** 2 - L2 ** 2) / (2 * L1 * L), -1, 1))
    dx, dz = math.sin(yaw), math.cos(yaw)
    sh = (0.0, H0, 0.0)
    el = (dx * math.cos(a1) * L1, H0 + math.sin(a1) * L1, dz * math.cos(a1) * L1)
    a3 = a1 - (math.pi - a2)
    wr = (el[0] + dx * math.cos(a3) * L2, el[1] + math.sin(a3) * L2, el[2] + dz * math.cos(a3) * L2)
    return {"yaw": yaw, "dir": (dx, 0.0, dz), "shoulder": sh, "elbow": el, "wrist": wr}


def cam(tau):
    p = clamp(tau / DUR)
    az = -0.62 + 0.22 * p
    R = 3.75 - 0.30 * p
    return (math.sin(az) * R, 1.95 - 0.12 * p, -math.cos(az) * R), (0.0, 0.50, 0.45)


F_PX = 1450.0  # focal length in pixels on a 1920-wide frame


def to_bl(v):
    return Vector((v[0], v[2], v[1]))


# ---------------------------------------------------------------------------- materials
def principled(name, color, rough=0.4, metal=0.0, coat=0.0, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.06
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_strength
    return m


def floor_material():
    """Dark polished floor with a faint tracking grid that fades out away from the cell."""
    m = bpy.data.materials.new("floor")
    m.use_nodes = True
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Object"], sep.inputs[0])

    def math_node(op, a, bval=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, bval)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                Lk.new(v, n.inputs[i])
        return n.outputs[0]

    def line(axis):
        f = math_node("FRACT", math_node("MULTIPLY", sep.outputs[axis], 2.0))
        return math_node("GREATER_THAN", math_node("ABSOLUTE", math_node("SUBTRACT", f, 0.5)), 0.4915)

    grid = math_node("MAXIMUM", line(0), line(1))
    ln = N.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    Lk.new(tc.outputs["Object"], ln.inputs[0])
    fall = N.new("ShaderNodeMapRange")
    fall.inputs["From Min"].default_value = 1.6
    fall.inputs["From Max"].default_value = 4.6
    fall.inputs["To Min"].default_value = 1.0
    fall.inputs["To Max"].default_value = 0.0
    Lk.new(ln.outputs["Value"], fall.inputs["Value"])
    mask = math_node("MULTIPLY", grid, fall.outputs[0])
    mix = N.new("ShaderNodeMixRGB")
    mix.inputs[1].default_value = (0.012, 0.012, 0.015, 1)
    mix.inputs[2].default_value = (0.035, 0.03, 0.06, 1)
    Lk.new(mask, mix.inputs[0])
    Lk.new(mix.outputs[0], b.inputs["Base Color"])
    b.inputs["Emission Color"].default_value = (0.42, 0.30, 1.0, 1)
    Lk.new(math_node("MULTIPLY", mask, 0.07), b.inputs["Emission Strength"])
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.4
    noise.inputs["Detail"].default_value = 3.0
    Lk.new(tc.outputs["Object"], noise.inputs["Vector"])
    rr = N.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.22
    rr.inputs["To Max"].default_value = 0.42
    Lk.new(noise.outputs["Fac"], rr.inputs["Value"])
    Lk.new(rr.outputs[0], b.inputs["Roughness"])
    return m


# ---------------------------------------------------------------------------- geometry helpers
def finish(name, bm, mat, parent=None, bevel=0.008, segs=3):
    if bevel:
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > rad(28)]
        if edges:
            bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type="OFFSET", segments=segs, profile=0.5, affect="EDGES")
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)
    wn = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
    wn.keep_sharp = True
    wn.weight = 100
    if parent is not None:
        ob.parent = parent
    return ob


def box(name, mat, lo, hi, parent=None, bevel=0.01):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    lo, hi = Vector(lo), Vector(hi)
    size, mid = hi - lo, (hi + lo) / 2
    bmesh.ops.transform(bm, matrix=Matrix.Translation(mid) @ Matrix.Diagonal((*size, 1.0)), verts=bm.verts)
    return finish(name, bm, mat, parent, bevel)


def cyl(name, mat, r, depth, center=(0, 0, 0), axis="Z", parent=None, bevel=0.008, segs=72, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r if r2 is None else r2, depth=depth)
    rot = Matrix.Identity(4)
    if axis == "Y":
        rot = Matrix.Rotation(rad(90), 4, "X")
    elif axis == "X":
        rot = Matrix.Rotation(rad(90), 4, "Y")
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ rot, verts=bm.verts)
    return finish(name, bm, mat, parent, bevel)


def empty(name):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    return e


def area(name, loc, target, size, power, color=(1, 1, 1), size_y=None, spread=None):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = power
    ld.color = color
    ld.size = size
    if size_y:
        ld.shape = "RECTANGLE"
        ld.size_y = size_y
    if spread:
        ld.spread = rad(spread)
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(loc)
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


def frame_matrix(origin, x_axis, y_axis):
    """4×4 with the given origin and orthonormalised x / y axes (z = x × y)."""
    x = Vector(x_axis).normalized()
    z = x.cross(Vector(y_axis)).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


# ---------------------------------------------------------------------------- the scene
def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    except Exception:
        pass

    shell = principled("shell", (0.62, 0.63, 0.66), rough=0.32, coat=0.7)
    dark = principled("dark", (0.022, 0.023, 0.027), rough=0.34, metal=1.0)
    steel = principled("steel", (0.62, 0.63, 0.66), rough=0.22, metal=1.0)
    rubber = principled("rubber", (0.015, 0.015, 0.017), rough=0.75)
    led = principled("led", (0.05, 0.02, 0.1), rough=0.3, emit=(0.38, 0.12, 1.0), emit_strength=22.0)
    led_soft = principled("led_soft", (0.05, 0.05, 0.06), rough=0.3, emit=(0.75, 0.80, 1.0), emit_strength=5.0)
    amber = principled("amber", (1.0, 0.50, 0.09), rough=0.26, coat=1.0)

    # floor + pads
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40)
    fl = finish("floor", bm, floor_material(), bevel=0)
    for name, P, ring in (("pick", PICK, led_soft), ("place", PLACE, led)):
        c = to_bl((P[0], 0, P[2]))
        cyl(f"{name}_pad", dark, 0.27, 0.014, center=(c.x, c.y, 0.007), bevel=0.003)
        cyl(f"{name}_ring", ring, 0.285, 0.006, center=(c.x, c.y, 0.003), bevel=0)
        cyl(f"{name}_ring_mask", dark, 0.272, 0.0075, center=(c.x, c.y, 0.00375), bevel=0)

    # base (static)
    cyl("flange", dark, 0.37, 0.06, center=(0, 0, 0.03), bevel=0.012)
    for i in range(10):
        a = i / 10 * math.tau
        cyl(f"bolt{i}", steel, 0.022, 0.022, center=(math.cos(a) * 0.315, math.sin(a) * 0.315, 0.068), bevel=0.004, segs=6)
    cyl("base_ring", led, 0.262, 0.016, center=(0, 0, 0.085), bevel=0)

    # turret: local x = reach direction, y = joint axis, z = up
    turret = empty("turret")
    cyl("column", shell, 0.25, 0.34, center=(0, 0, 0.25), parent=turret, bevel=0.03, r2=0.21)
    cyl("shoulder", shell, 0.195, 0.40, center=(0, 0, H0), axis="Y", parent=turret, bevel=0.022)
    for s in (-1, 1):
        cyl(f"sh_cap{s}", dark, 0.15, 0.02, center=(0, s * 0.205, H0), axis="Y", parent=turret, bevel=0.006)
        cyl(f"sh_hub{s}", steel, 0.055, 0.016, center=(0, s * 0.218, H0), axis="Y", parent=turret, bevel=0.004)

    # upper arm: local x from shoulder to elbow
    upper = empty("upper")
    box("upper_link", shell, (0.0, -0.088, -0.105), (L1, 0.088, 0.105), parent=upper, bevel=0.03)
    for s in (-1, 1):
        box(f"upper_inlay{s}", dark, (0.24, s * 0.089 - 0.004, -0.04), (L1 - 0.24, s * 0.089 + 0.004, 0.04), parent=upper, bevel=0.003)
    box("upper_strip", led, (0.30, -0.010, 0.1045), (0.62, 0.010, 0.1075), parent=upper, bevel=0)

    # forearm: local x from elbow to wrist (carries the elbow and wrist joints)
    fore = empty("fore")
    cyl("elbow", shell, 0.155, 0.34, axis="Y", parent=fore, bevel=0.02)
    for s in (-1, 1):
        cyl(f"el_cap{s}", dark, 0.118, 0.02, center=(0, s * 0.175, 0), axis="Y", parent=fore, bevel=0.006)
        cyl(f"el_ring{s}", led, 0.158, 0.012, center=(0, s * 0.125, 0), axis="Y", parent=fore, bevel=0)
    box("fore_link", shell, (0.0, -0.07, -0.082), (L2, 0.07, 0.082), parent=fore, bevel=0.026)
    for s in (-1, 1):
        box(f"fore_inlay{s}", dark, (0.22, s * 0.071 - 0.004, -0.03), (L2 - 0.2, s * 0.071 + 0.004, 0.03), parent=fore, bevel=0.003)
    cyl("wrist", shell, 0.108, 0.26, center=(L2, 0, 0), axis="Y", parent=fore, bevel=0.016)
    for s in (-1, 1):
        cyl(f"wr_cap{s}", dark, 0.08, 0.016, center=(L2, s * 0.134, 0), axis="Y", parent=fore, bevel=0.005)

    # tool: at the wrist, always vertical; local y = finger axis
    tool = empty("tool")
    cyl("tool_neck", dark, 0.058, 0.13, center=(0, 0, -0.065), parent=tool, bevel=0.008)
    cyl("tool_flange", steel, 0.092, 0.022, center=(0, 0, -0.128), parent=tool, bevel=0.005)
    box("palm", dark, (-0.055, -0.215, -0.176), (0.055, 0.215, -0.138), parent=tool, bevel=0.01)
    box("palm_led", led, (0.0555, -0.06, -0.162), (0.0575, 0.06, -0.152), parent=tool, bevel=0)
    fingers = []
    for s in (-1, 1):
        f = empty(f"finger{s}")
        f.parent = tool
        box(f"finger_body{s}", steel, (-0.04, -0.014, -0.345), (0.04, 0.014, -0.17), parent=f, bevel=0.006)
        box(f"finger_pad{s}", rubber, (-0.034, -s * 0.014 - 0.004, -0.34), (0.034, -s * 0.014 + 0.004, -0.20), parent=f, bevel=0.002)
        fingers.append((s, f))

    part = box("part", amber, (-0.10, -0.10, -0.10), (0.10, 0.10, 0.10), bevel=0.016)

    # camera
    cd = bpy.data.cameras.new("cam")
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36.0
    cd.lens = F_PX / 1920.0 * 36.0
    cd.clip_start, cd.clip_end = 0.05, 200
    cd.dof.use_dof = True
    cd.dof.focus_object = tool
    cd.dof.aperture_fstop = 1.1
    cd.dof.aperture_blades = 9
    camo = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(camo)
    sc.camera = camo

    # light: black studio, one soft key, an overhead strip for the long highlights, violet and blue rims
    area("key", (3.4, -3.6, 4.6), (0, 0.4, 0.8), 3.2, 520, (1.0, 0.97, 0.94))
    area("strip", (0.2, 0.6, 4.4), (0.2, 0.6, 0), 0.7, 260, (0.92, 0.95, 1.0), size_y=5.0)
    area("rim_violet", (3.6, 3.8, 1.5), (0, 0.3, 1.0), 1.6, 800, (0.42, 0.14, 1.0))
    area("rim_blue", (-4.4, 3.0, 1.4), (0, 0.3, 1.0), 1.8, 520, (0.30, 0.48, 1.0))
    area("fill", (-3.5, -4.5, 1.6), (0, 0.3, 0.8), 4.0, 70, (0.75, 0.80, 1.0))
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.0015, 0.0015, 0.0025, 1)
    sc.world = w

    # ---- animation: one key per frame on every moving empty (Cycles interpolates for motion blur)
    nframes = int(DUR * FPS)
    up = Vector((0, 0, 1))
    prev = {}

    def key(ob, m, f):
        loc, q, _ = m.decompose()
        if ob.name in prev:
            q.make_compatible(prev[ob.name])
        prev[ob.name] = q.copy()
        ob.rotation_mode = "QUATERNION"
        ob.location, ob.rotation_quaternion = loc, q
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_quaternion", frame=f)

    for f in range(-1, nframes + 2):
        tau = f / FPS
        T = tip(tau)
        k = ik(T)
        d = to_bl(k["dir"])
        ax = up.cross(d)
        S, E, Wr = to_bl(k["shoulder"]), to_bl(k["elbow"]), to_bl(k["wrist"])
        key(turret, frame_matrix((0, 0, 0), d, ax), f)
        key(upper, frame_matrix(S, E - S, ax), f)
        key(fore, frame_matrix(E, Wr - E, ax), f)
        key(tool, frame_matrix(Wr, d, ax), f)
        gap = finger_gap(tau)
        for s, fo in fingers:
            fo.location = (0, s * gap, 0)
            fo.keyframe_insert("location", frame=f)
        pp = demo_path(move_u(tau))
        pd = to_bl((math.sin(math.atan2(pp[0], pp[2])), 0, math.cos(math.atan2(pp[0], pp[2]))))
        key(part, frame_matrix(to_bl(pp), pd, up.cross(pd)), f)
        eye, tgt = cam(tau)
        cm = Matrix.Translation(to_bl(eye)) @ (to_bl(tgt) - to_bl(eye)).to_track_quat("-Z", "Y").to_matrix().to_4x4()
        key(camo, cm, f)
    return sc


def setup_render(sc, samples, res):
    sc.render.engine = "CYCLES"
    c = sc.cycles
    c.device = "CPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.05
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces = 5, 2, 4, 2
    c.caustics_reflective = c.caustics_refractive = False
    c.sample_clamp_indirect = 6.0
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = int(1920 * res), int(1080 * res)
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.compression = 15


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, nargs="*", help="frame numbers, or a range as: --range A B")
    ap.add_argument("--range", type=int, nargs=2)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--res", type=float, default=1.0)
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--out", default=os.path.join(ROOT, "video", "build", "plates", "robot"))
    a = ap.parse_args(argv)
    sc = build()
    setup_render(sc, a.samples, a.res)
    sc.view_settings.exposure = a.exposure
    os.makedirs(a.out, exist_ok=True)
    frames = a.frames if a.frames else list(range(*(a.range or (0, int(DUR * FPS))), a.step))
    for f in frames:
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
