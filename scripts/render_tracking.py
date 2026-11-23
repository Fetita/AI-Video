#!/usr/bin/env python3
"""
render_tracking.py -- the camera + wrist tracking plate (vision scene, "every camera and wrist, tracked in 3D").

The robot shot's black studio, with a real workbench in it: an oak top on steel legs, a parts box, hex nuts and a
screwdriver on the mat. Around it move the tracked devices: a head-mounted camera and two wrist bands with tracking
LEDs (sky blue left, coral right, as the film's legend). Every pose comes from the film's own model
(lib/tracking.js via inputs.json: per plate frame, the orbit camera, the head camera's frame and both wrists),
and the camera is the film's orbit camera itself, so the overlays (estimate vs ground truth, frustum, wrist trails)
are drawn by the film with no export at all.

    python scripts/render_tracking.py --res 0.25 --samples 8 --frames 0 30 55     # preview
    python scripts/render_tracking.py --res 0.5 --samples 10                      # final
    scripts/pack_plates.sh tracking
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from mathutils import Vector, Matrix  # noqa: E402
from blender_common import (  # noqa: E402
    FPS, Keyer, Nodes, area, args, box, camera, cyl, empty, film_to_bl, frame_matrix, inputs, new_scene,
    principled, render_frames, setup_render, wear,
)

IN = inputs()
TR = IN["tracking"]
PLATE = IN["plates"]["tracking"]
NF = PLATE["frames"]
W, H = PLATE["w"], PLATE["h"]


def V(p):
    return film_to_bl((p["x"], p["y"], p["z"]))


def floor_mat():
    m = bpy.data.materials.new("floor")
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    nz = n.new("ShaderNodeTexNoise", Scale=0.6, Detail=8.0)
    n.link(tc.outputs["Object"], nz.inputs["Vector"])
    n.link(n.ramp(nz.outputs["Fac"], [(0.3, (0.012, 0.012, 0.014)), (0.7, (0.028, 0.028, 0.032))]), n.bsdf.inputs["Base Color"])
    n.link(wear(n, 0.22, 0.2, 1.5, scratches=0.08), n.bsdf.inputs["Roughness"])
    return m


def oak():
    m = bpy.data.materials.new("oak")
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.12, 1.0, 1.0)
    n.link(tc.outputs["Object"], mp.inputs["Vector"])
    wv = n.new("ShaderNodeTexWave", Scale=4.0, Distortion=4.0, Detail=6.0)
    wv.wave_type = "RINGS"
    n.link(mp.outputs[0], wv.inputs["Vector"])
    n.link(n.ramp(wv.outputs["Fac"], [(0.2, (0.16, 0.09, 0.045)), (0.8, (0.36, 0.23, 0.12))]), n.bsdf.inputs["Base Color"])
    n.link(wear(n, 0.42, 0.2, 3.0, scratches=0.1), n.bsdf.inputs["Roughness"])
    n.bsdf.inputs["Coat Weight"].default_value = 0.25
    return m


def build(sc):
    steel = principled("steel", (0.5, 0.52, 0.55), rough=0.32, metal=1.0)
    black = principled("black", (0.02, 0.02, 0.022), rough=0.4, coat=0.5)
    mat_ = principled("mat", (0.03, 0.06, 0.05), rough=0.8)
    card = principled("card", (0.45, 0.32, 0.18), rough=0.85)
    nutm = principled("nut", (0.62, 0.6, 0.55), rough=0.25, metal=1.0)
    handle = principled("handle", (0.9, 0.35, 0.05), rough=0.35, coat=0.5)
    violet = principled("violet", (0.3, 0.1, 0.9), emit=(0.51, 0.2, 1.0), emit_strength=8.0)
    sky = principled("sky", (0.2, 0.6, 1.0), emit=(0.35, 0.75, 1.0), emit_strength=12.0)
    coral = principled("coral", (1.0, 0.4, 0.35), emit=(1.0, 0.45, 0.4), emit_strength=12.0)
    lensg = principled("lens", (0.01, 0.012, 0.02), rough=0.05, coat=1.0)

    box("floor", floor_mat(), (-30, -30, -0.05), (30, 30, 0), bevel=0)
    # the workbench, exactly on the film's bench block (x -0.9..0.9, height 0.9, depth -0.5..0.9 in film z)
    b = TR["bench"]
    lo, hi = film_to_bl(b["lo"]), film_to_bl(b["hi"])
    box("top", oak(), (lo.x, lo.y, hi.z - 0.05), (hi.x, hi.y, hi.z), bevel=0.012)
    for x in (lo.x + 0.06, hi.x - 0.06):
        for y in (lo.y + 0.06, hi.y - 0.06):
            box(f"leg{x}{y}", steel, (x - 0.03, y - 0.03, 0), (x + 0.03, y + 0.03, hi.z - 0.05), bevel=0.006)
    box("shelf", steel, (lo.x + 0.03, lo.y + 0.03, 0.18), (hi.x - 0.03, hi.y - 0.03, 0.2), bevel=0.004)
    box("mat", mat_, (-0.55, -0.15, hi.z), (0.45, 0.55, hi.z + 0.006), bevel=0.003)
    box("parts", card, (0.25, 0.05, hi.z), (0.6, 0.35, hi.z + 0.16), bevel=0.01)
    rnd = random.Random(4)
    for i in range(7):
        cyl(f"nut{i}", nutm, 0.022, 0.016, center=(rnd.uniform(-0.4, 0.1), rnd.uniform(0.0, 0.45), hi.z + 0.014), bevel=0.003, segs=6)
    sd = cyl("shaft", steel, 0.006, 0.2, center=(0, 0, 0), axis="X", bevel=0.001, segs=12)
    hd = cyl("handle", handle, 0.017, 0.11, center=(-0.15, 0, 0), axis="X", bevel=0.005, segs=16)
    for ob in (sd, hd):
        ob.location = (-0.15, 0.25, hi.z + 0.022)
        ob.rotation_euler = (0, 0, 0.5)

    # tracked devices (a little larger than life so they read at this distance)
    head = empty("head")
    box("cam_body", black, (-0.09, -0.07, -0.06), (0.09, 0.07, 0.06), parent=head, bevel=0.02)
    cyl("cam_lens", lensg, 0.045, 0.05, center=(0, 0.09, 0), axis="Y", parent=head, bevel=0.008)
    cyl("cam_ring", violet, 0.052, 0.012, center=(0, 0.075, 0), axis="Y", parent=head, bevel=0.002)
    box("cam_strap", black, (-0.025, -0.07, 0.06), (0.025, 0.02, 0.1), parent=head, bevel=0.01)
    wrists = []
    for side, led in ((-1, sky), (1, coral)):
        wr = empty(f"wrist{side}")
        cyl(f"band{side}", black, 0.055, 0.05, axis="Y", parent=wr, bevel=0.012)
        for k in range(3):
            a = k / 3 * math.tau
            box(f"led{side}{k}", led, (math.cos(a) * 0.056 - 0.012, -0.01, math.sin(a) * 0.056 - 0.012), (math.cos(a) * 0.056 + 0.012, 0.01, math.sin(a) * 0.056 + 0.012), parent=wr, bevel=0.004)
        wrists.append((wr, "wristL" if side < 0 else "wristR"))

    # light: the robot shot's studio
    area("key", (3.4, -3.6, 4.6), (0, 0.4, 0.8), 3.2, 520, (1.0, 0.97, 0.94))
    area("strip", (0.2, 0.6, 4.4), (0.2, 0.6, 0), 0.7, 260, (0.92, 0.95, 1.0), size_y=5.0)
    area("rim_violet", (3.6, 3.8, 1.5), (0, 0.3, 1.0), 1.6, 800, (0.42, 0.14, 1.0))
    area("rim_blue", (-4.4, 3.0, 1.4), (0, 0.3, 1.0), 1.8, 520, (0.30, 0.48, 1.0))
    area("fill", (-3.5, -4.5, 1.6), (0, 0.3, 0.8), 4.0, 70, (0.75, 0.80, 1.0))
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.0015, 0.0015, 0.0025, 1)
    sc.world = w

    fr = TR["frames"]
    cam = camera(sc, f_px=fr[0]["f"])
    K = Keyer()
    for f in range(-1, NF + 2):
        q = fr[max(0, min(len(fr) - 1, f))]
        if f >= len(fr):                       # extrapolate one frame past the end for the motion blur
            q2 = fr[-2]
            ext = lambda k: {a: 2 * q[k][a] - q2[k][a] for a in "xyz"}  # noqa: E731
            q = {**q, **{k: ext(k) for k in ("eye", "target", "c0", "wristL", "wristR")}}
        K.look(cam, V(q["eye"]), V(q["target"]), f)
        S = Matrix.Diagonal((1.8, 1.8, 1.8, 1))
        K.mat(head, frame_matrix(V(q["c0"]), V(q["rt"]), V(q["fw"])) @ S, f)
        for wr, key in wrists:
            fwd = V(q["fw"])
            K.mat(wr, frame_matrix(V(q[key]), fwd.cross(Vector((0, 0, 1))), fwd) @ S, f)
    Keyer.linear()


def main():
    a = args("tracking")
    sc = new_scene()
    build(sc)
    setup_render(sc, a.samples, a.res, W, H)
    sc.view_settings.exposure = a.exposure
    if not a.export_only:
        render_frames(sc, a, NF)


if __name__ == "__main__":
    main()
