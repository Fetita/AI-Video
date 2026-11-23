#!/usr/bin/env python3
"""
render_board.py -- the story board plate (story scene, "physical to digital": pieces on a board -> a story).

A varnished walnut board with four engraved slots on an oak table, lit like a window-lit room with a warm lamp.
The character pieces are thick bevelled beech discs with the character printed on an inset face (the supplied
character art, assets/characters/*.png, UV-mapped exactly as lib/story-art.js lays it out). The shot opens close
on the sloth as it lands, pulls back and up to the whole board, and holds while the other three pieces drop into
their slots at the film's times (lib/board.js via inputs.json), with a small bounce and settle.

After the pull-back the camera holds still; the film adds the scene's slow residual zoom as a scale on the plate.
Per frame it exports every piece's screen centre and rim radius (video/src/shots/board.js) for the reticles,
labels and relation lines.

    python scripts/render_board.py --res 0.25 --samples 8 --frames 0 60 140 200     # preview
    python scripts/render_board.py --res 0.5 --samples 16                           # final
    scripts/pack_plates.sh board
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector, Matrix  # noqa: E402
from blender_common import (  # noqa: E402
    FPS, ROOT, Keyer, Nodes, area, args, box, camera, clamp, empty, finish, inputs, ioc, lerp, new_scene, ocubic,
    project, project_radius, render_frames, setup_render, wear, write_shot, rad,
)

IN = inputs()
B = IN["board"]
PLATE = IN["plates"]["board"]
NF = PLATE["frames"]
W, H = PLATE["w"], PLATE["h"]
U = 0.01                                  # world units per board pixel (zoom 1)
PR = B["PD"] / 2 * U                      # piece radius
PT = 0.34                                 # piece thickness
BT = 0.45                                 # board thickness
T_PULL0, T_PULL1 = 3.4, 4.6               # the pull-back (scene seconds), as the film's own camera keys


def slot_xy(s):
    return Vector((s["x"] * U, -s["y"] * U))


# ---------------------------------------------------------------------------- materials
def wood(name, light, dark, ring_scale=3.0, grain_dir="X", varnish=0.6, rough=0.32, stretch=8.0):
    """Long-grain wood: distorted growth rings stretched along the grain, pores, figure, and a varnish coat."""
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    s = (1.0 / stretch, 1.0, 1.0) if grain_dir == "X" else (1.0, 1.0 / stretch, 1.0)
    mp.inputs["Scale"].default_value = s
    n.link(tc.outputs["Object"], mp.inputs["Vector"])
    warp = n.new("ShaderNodeTexNoise", Scale=1.2, Detail=4.0)
    n.link(mp.outputs[0], warp.inputs["Vector"])
    vm = n.new("ShaderNodeVectorMath", _operation="ADD")
    n.link(mp.outputs[0], vm.inputs[0])
    n.link(warp.outputs["Color"], vm.inputs[1])
    rings = n.new("ShaderNodeTexWave", Scale=ring_scale, Distortion=2.5, Detail=6.0, **{"Detail Scale": 1.5})
    rings.wave_type = "RINGS"
    rings.rings_direction = "SPHERICAL"
    n.link(vm.outputs[0], rings.inputs["Vector"])
    pores = n.new("ShaderNodeTexNoise", Scale=180.0, Detail=2.0)
    n.link(mp.outputs[0], pores.inputs["Vector"])
    fig = n.new("ShaderNodeTexNoise", Scale=3.0, Detail=6.0)
    n.link(mp.outputs[0], fig.inputs["Vector"])
    fac = n.math("ADD", n.math("MULTIPLY", rings.outputs["Fac"], 0.42), n.math("MULTIPLY", fig.outputs["Fac"], 0.58))
    col = n.ramp(fac, [(0.2, dark), (0.55, tuple((a + b) / 2 for a, b in zip(dark, light))), (0.85, light)])
    pm = n.new("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    n.link(n.math("MULTIPLY", n.math("GREATER_THAN", pores.outputs["Fac"], 0.62), 0.5), pm.inputs["Factor"])
    n.link(col, pm.inputs[6])
    pm.inputs[7].default_value = (0.45, 0.4, 0.36, 1)
    n.link(pm.outputs[2], n.bsdf.inputs["Base Color"])
    n.link(wear(n, rough, 0.15, 5.0, scratches=0.05), n.bsdf.inputs["Roughness"])
    n.bsdf.inputs["Coat Weight"].default_value = varnish
    n.bsdf.inputs["Coat Roughness"].default_value = 0.08
    bump = n.new("ShaderNodeBump", Strength=0.12, Distance=0.01)
    n.link(n.math("ADD", rings.outputs["Fac"], pores.outputs["Fac"]), bump.inputs["Height"])
    n.link(bump.outputs["Normal"], n.bsdf.inputs["Normal"])
    return m


def print_material(kind):
    """The printed face: the character art over a cream ground, under a satin varnish."""
    f = B["face"][kind]
    path = os.path.join(ROOT, "video", "assets", "characters", f["src"])
    img = bpy.data.images.load(path, check_existing=True)
    m = bpy.data.materials.new(f"face_{kind}")
    n = Nodes(m)
    uv = n.new("ShaderNodeUVMap")
    tex = n.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "CLIP"
    tex.interpolation = "Cubic"
    n.link(uv.outputs[0], tex.inputs["Vector"])
    mix = n.new("ShaderNodeMix", _data_type="RGBA")
    n.link(tex.outputs["Alpha"], mix.inputs["Factor"])
    mix.inputs[6].default_value = (0.86, 0.76, 0.6, 1)
    n.link(tex.outputs["Color"], mix.inputs[7])
    n.link(mix.outputs[2], n.bsdf.inputs["Base Color"])
    n.bsdf.inputs["Roughness"].default_value = 0.42
    n.bsdf.inputs["Coat Weight"].default_value = 0.5
    n.bsdf.inputs["Coat Roughness"].default_value = 0.18
    return m, img.size


# ---------------------------------------------------------------------------- geometry
def disc(name, mat, r, h, bevel, segs=96, parent=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r, depth=h)
    bmesh.ops.translate(bm, vec=Vector((0, 0, h / 2)), verts=bm.verts)
    return finish(name, bm, mat, parent, bevel=bevel, segs=4, angle=30)


def face_cap(name, mat, kind, r_face, size, parent):
    """A thin disc with UVs that place the art exactly as story-art.js: the face circle is the CSS box,
    the image sits at left x%, top y%, width w% of it (height from the image's aspect)."""
    f = B["face"][kind]
    iw, ih = size
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, cap_tris=False, segments=96, radius=r_face)
    uvl = bm.loops.layers.uv.new("UVMap")
    for face in bm.faces:
        for lp in face.loops:
            x, y = lp.vert.co.x, lp.vert.co.y
            fx, fy = (x / r_face + 1) / 2, (1 - y / r_face) / 2           # 0..1, top-left origin (CSS)
            wbox = f["w"] / 100
            u = (fx - f["x"] / 100) / wbox
            v = (fy - f["y"] / 100) / (wbox * ih / iw)
            lp[uvl].uv = (u, 1 - v)
    ob = finish(name, bm, mat, parent, bevel=0, smooth=False)
    ob.location = (0, 0, PT + 0.0025)
    return ob


def piece(kind, beech, groove_mat, face_mat, size):
    root = empty(f"piece_{kind}")
    disc(f"{kind}_body", beech, PR, PT, bevel=0.06, parent=root)
    # the engraved ring between the wood and the printed face
    ring = disc(f"{kind}_groove", groove_mat, PR * 0.8, 0.02, bevel=0.004, parent=root)
    ring.location = (0, 0, PT - 0.019)          # its top sits 1 mm above the wood: a raised printed inlay
    face_cap(f"{kind}_face", face_mat, kind, PR * 0.74, size, root)
    return root


def board_mesh(walnut, felt):
    bw, bh = B["BW"] * U, B["BH"] * U
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Translation((0, 0, -BT / 2)) @ Matrix.Diagonal((bw, bh, BT, 1)), verts=bm.verts)
    ob = finish("board", bm, walnut, bevel=0.16, segs=8, smooth=False)    # flat faces: no smoothing streaks around the cut slots
    # engraved slots: a boolean cut per slot, with a darker, rougher floor
    for i, s in enumerate(B["slots"]):
        c = slot_xy(s)
        cutter = disc(f"slot_cut{i}", None, PR + 0.1, 0.2, bevel=0)
        cutter.location = (c.x, c.y, -0.06)
        cutter.hide_render = True
        mod = ob.modifiers.new(f"slot{i}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cutter
        floor = disc(f"slot_floor{i}", felt, PR + 0.095, 0.01, bevel=0)
        floor.location = (c.x, c.y, -0.065)
    return ob


# ---------------------------------------------------------------------------- shot
def build(sc):
    walnut = wood("walnut", (0.2, 0.11, 0.06), (0.055, 0.028, 0.015), ring_scale=2.5, varnish=0.7, rough=0.3)
    oak = wood("oak", (0.32, 0.22, 0.13), (0.12, 0.075, 0.045), ring_scale=1.6, varnish=0.3, rough=0.45, stretch=12.0)
    beech = wood("beech", (0.72, 0.5, 0.3), (0.45, 0.28, 0.15), ring_scale=6.0, varnish=0.5, rough=0.35, stretch=5.0)
    groove = wood("groove", (0.42, 0.27, 0.15), (0.3, 0.18, 0.1), ring_scale=6.0, varnish=0.2, rough=0.5)
    felt = bpy.data.materials.new("slotfloor")
    fn = Nodes(felt)
    fn.bsdf.inputs["Base Color"].default_value = (0.03, 0.018, 0.01, 1)
    fn.bsdf.inputs["Roughness"].default_value = 0.85

    box("table", oak, (-30, -20, -BT - 0.6), (30, 20, -BT), bevel=0.05)
    board_mesh(walnut, felt)

    pieces = []
    for i, s in enumerate(B["slots"]):
        fm, size = print_material(s["kind"])
        root = piece(s["kind"], beech, groove, fm, size)
        pieces.append((i, s, root))

    # light: a big soft window from the upper left, a warm lamp from the right, a cool bounce, dark room
    area("window", (-11, 7, 9), (0, 0, 0), 7.0, 2200, (0.85, 0.92, 1.0), size_y=4.0)
    area("lamp", (9, -4, 6), (-1, 0, 0), 1.4, 900, (1.0, 0.72, 0.42))
    area("bounce", (2, -14, 3), (0, 0, 0), 10.0, 120, (1.0, 0.85, 0.7))
    w = bpy.data.worlds.new("room")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.01, 0.008, 0.007, 1)
    sc.world = w

    cam = camera(sc, f_px=1800.0, dof=2.8)
    focus = empty("focus")
    cam.data.dof.focus_object = focus
    K = Keyer()
    hero = slot_xy(B["slots"][0])
    t0 = B["t0"]
    drops = B["drops"]
    for f in range(-1, NF + 2):
        t = t0 + f / FPS
        # camera: close on the sloth, slowly orbiting in; then up and back to the whole board, then still
        pull = ioc(clamp((t - T_PULL0) / (T_PULL1 - T_PULL0)))
        near = clamp((t - t0) / (T_PULL0 - t0))
        tgt = Vector((hero.x, hero.y + 0.05, PT * 0.6)).lerp(Vector((0.0, -0.05, 0.0)), pull)
        dist = lerp(lerp(11.2, 10.2, near), 19.6, pull)
        elev = rad(lerp(lerp(40, 44, near), 74, pull))
        az = rad(lerp(lerp(-16, -9, near), 0, pull))
        eye = tgt + Vector((math.sin(az) * math.cos(elev), -math.cos(az) * math.cos(elev), math.sin(elev))) * dist
        K.look(cam, eye, tgt, f)
        K.mat(focus, Matrix.Translation(tgt), f)
        cam.data.dof.aperture_fstop = lerp(2.8, 6.0, pull)
        cam.data.dof.keyframe_insert("aperture_fstop", frame=f)
        # pieces: fall (accelerating), land, a small hop, settle; a little spin and tilt while falling
        for i, s, root in pieces:
            c = slot_xy(s)
            u = (t - drops[i]) / B["DROP"]
            z, tilt, spin = 0.0, 0.0, 0.0
            if u < 1:
                uu = clamp(u)
                z = 3.2 * (1 - uu * uu)
                tilt = (1 - uu) * 0.25
                spin = (1 - uu) * 0.6 * (1 if i % 2 else -1)
            else:
                tb = (t - drops[i] - B["DROP"])
                if tb < 0.22:
                    z = 0.12 * math.sin(tb / 0.22 * math.pi)
                tilt = 0.05 * math.exp(-tb * 9) * math.sin(tb * 40)
            if u < -0.02:
                z = 60.0                                  # not yet dropped: out of shot, high above
            M = Matrix.Translation((c.x, c.y, z - 0.06)) @ Matrix.Rotation(spin, 4, "Z") @ Matrix.Rotation(tilt, 4, "X")
            K.mat(root, M, f)
    Keyer.linear()

    def export(sc):
        rows = []
        for f in range(NF):
            sc.frame_set(f)
            row = []
            for i, s, root in pieces:
                ctr = root.matrix_world @ Vector((0, 0, PT))
                x, y, _ = project(sc, cam, ctr, W, H)
                row.append([x, y, project_radius(sc, cam, ctr, PR, W, H)])
            rows.append(row)
        return {"piece": rows}

    return export


def main():
    a = args("board")
    sc = new_scene()
    export = build(sc)
    setup_render(sc, a.samples, a.res, W, H)
    sc.view_settings.exposure = a.exposure
    if not a.no_export:
        write_shot("board", {"fps": FPS, "frames": NF, "w": W, "h": H, "pts": export(sc), "cam": []})
    if not a.export_only:
        render_frames(sc, a, NF)


if __name__ == "__main__":
    main()
