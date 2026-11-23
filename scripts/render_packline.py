#!/usr/bin/env python3
"""
render_packline.py -- the packing-line plate (agri scene, beat D: "every pumpkin gets an ID, a track and a count").

A packhouse conveyor at night under strip lights: a cleated rubber belt between steel guide rails, crates at the far
end, a concrete floor. Pumpkins (orange, deep orange, pale and green, ribbed, with stems) ride the belt on the
lanes and spawn times of the film's own model (lib/pack.js via inputs.json). The shot opens low and oblique,
then the camera rises to the overhead line-camera view before the IDs appear and holds there.

The plate is shown inside the feed frame (1620×826). Per frame it exports every visible pumpkin's centre and radius
in plate pixels (video/src/shots/packline.js), which the film's boxes, IDs, trails and diameters follow.

    python scripts/render_packline.py --res 0.25 --samples 8 --frames 0 20 45 120     # preview
    python scripts/render_packline.py --samples 16                                    # final (res 0.6667)
    scripts/pack_plates.sh packline
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
    FPS, Keyer, Nodes, area, args, box, camera, clamp, cyl, empty, inputs, ioc, lerp, new_scene, wear,
    principled, project, project_radius, render_frames, setup_render, write_shot, rad,
)

IN = inputs()
P = IN["packline"]
PLATE = IN["plates"]["packline"]
FR = P["FRAME"]
U = 0.01                      # world units per feed pixel (at the overhead view)
NF = PLATE["frames"]
W, H = PLATE["w"], PLATE["h"]


def px_to_world(x, y):
    """Feed coordinates (film px, FRAME space) -> world (x right, y up the plate)."""
    return Vector(((x - FR["x"]) * U, (FR["h"] - (y - FR["y"])) * U, 0))


BELT_Y0 = px_to_world(0, P["by0"] + P["bh"]).y     # near edge (bottom of the plate)
BELT_Y1 = px_to_world(0, P["by0"]).y               # far edge
X_LO, X_HI = -40.0, FR["w"] * U + 8.0


# ---------------------------------------------------------------------------- materials
def belt_material(offset_socket_cb):
    m = bpy.data.materials.new("belt")
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    n.link(tc.outputs["Object"], mp.inputs["Vector"])
    offset_socket_cb(mp.inputs["Location"])
    sep = n.new("ShaderNodeSeparateXYZ")
    n.link(mp.outputs[0], sep.inputs[0])
    # cleats every 1.2 units across the belt
    cle = n.math("PINGPONG", sep.outputs[0], 0.6)
    ridge = n.math("LESS_THAN", cle, 0.05)
    grain = n.new("ShaderNodeTexNoise", Scale=60.0, Detail=4.0)
    n.link(mp.outputs[0], grain.inputs["Vector"])
    base = n.ramp(grain.outputs["Fac"], [(0.35, (0.018, 0.019, 0.021)), (0.65, (0.04, 0.041, 0.044))])
    # soil dust collects against the cleats; the middle of the belt is polished by the produce
    dust = n.math("MULTIPLY", n.math("LESS_THAN", cle, 0.12), n.math("ADD", 0.3, grain.outputs["Fac"]))
    mixd = n.new("ShaderNodeMix", _data_type="RGBA")
    n.link(n.math("MULTIPLY", dust, 0.7, clamp_=True), mixd.inputs["Factor"])
    n.link(base, mixd.inputs[6])
    mixd.inputs[7].default_value = (0.11, 0.085, 0.06, 1)
    n.link(mixd.outputs[2], n.bsdf.inputs["Base Color"])
    n.link(n.math("ADD", wear(n, 0.62, 0.3, 3.0, scratches=0.2), n.math("MULTIPLY", dust, 0.25)), n.bsdf.inputs["Roughness"])
    bump = n.new("ShaderNodeBump", Strength=0.6, Distance=0.05)
    n.link(n.math("ADD", ridge, n.math("MULTIPLY", grain.outputs["Fac"], 0.08)), bump.inputs["Height"])
    n.link(bump.outputs["Normal"], n.bsdf.inputs["Normal"])
    return m


def concrete():
    m = bpy.data.materials.new("concrete")
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    nz = n.new("ShaderNodeTexNoise", Scale=0.9, Detail=8.0, Roughness=0.65)
    n.link(tc.outputs["Object"], nz.inputs["Vector"])
    n.link(n.ramp(nz.outputs["Fac"], [(0.35, (0.012, 0.013, 0.015)), (0.7, (0.03, 0.031, 0.034))]), n.bsdf.inputs["Base Color"])
    n.bsdf.inputs["Roughness"].default_value = 0.35            # sealed epoxy floor: soft reflections of the fixtures
    return m


def pumpkin_material(kind, seed):
    pal = {"orange": ((0.9, 0.3, 0.03), (0.42, 0.09, 0.01)), "deep": ((0.75, 0.2, 0.02), (0.3, 0.05, 0.008)),
           "pale": ((0.78, 0.72, 0.58), (0.45, 0.38, 0.27)), "green": ((0.2, 0.3, 0.1), (0.06, 0.1, 0.03))}[kind]
    m = bpy.data.materials.new(f"pumpkin_{kind}_{seed}")
    n = Nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    nz = n.new("ShaderNodeTexNoise", Scale=4.0 + seed % 3, Detail=6.0)
    n.link(tc.outputs["Object"], nz.inputs["Vector"])
    # darker in the creases between lobes: the mesh stores the crease amount in its vertex colours
    attr = n.new("ShaderNodeVertexColor", _layer_name="crease")
    fac = n.math("ADD", n.math("MULTIPLY", attr.outputs["Color"], 0.8), n.math("MULTIPLY", nz.outputs["Fac"], 0.35))
    n.link(n.ramp(fac, [(0.25, pal[0]), (0.95, pal[1])]), n.bsdf.inputs["Base Color"])
    n.link(wear(n, 0.42, 0.25, 7.0), n.bsdf.inputs["Roughness"])
    n.bsdf.inputs["Coat Weight"].default_value = 0.35
    n.bsdf.inputs["Coat Roughness"].default_value = 0.2
    n.bsdf.inputs["Subsurface Weight"].default_value = 0.15
    n.bsdf.inputs["Subsurface Radius"].default_value = (0.8, 0.35, 0.1)
    n.bsdf.inputs["Subsurface Scale"].default_value = 0.03
    # pale speckles and blemishes
    spk = n.new("ShaderNodeTexVoronoi", Scale=70.0)
    n.link(tc.outputs["Object"], spk.inputs["Vector"])
    bump = n.new("ShaderNodeBump", Strength=0.3, Distance=0.02)
    fine = n.new("ShaderNodeTexNoise", Scale=40.0, Detail=3.0)
    n.link(tc.outputs["Object"], fine.inputs["Vector"])
    n.link(fine.outputs["Fac"], bump.inputs["Height"])
    n.link(bump.outputs["Normal"], n.bsdf.inputs["Normal"])
    return m


def pumpkin_mesh(seed, kind, mat, stem_mat):
    rnd = random.Random(seed)
    lobes = 9 + rnd.randint(0, 3)
    bm = bmesh.new()
    g = bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=1.0)
    col = bm.loops.layers.color.new("crease")
    fl = bm.verts.layers.float.new("c")
    squash = 0.72 + rnd.random() * 0.1 if kind != "pale" else 0.66
    for v in bm.verts:
        x, y, z = v.co
        lon = math.atan2(y, x)
        lat = math.asin(max(-1, min(1, z)))
        c = abs(math.cos(lon * lobes / 2)) ** 0.5           # 1 on a lobe, 0 in a crease
        r = 1 - 0.07 * (1 - c) * math.cos(lat) ** 0.5
        r *= 1 + noise.noise(Vector((x * 2 + seed, y * 2, z * 2))) * 0.03
        zz = z * squash
        if z > 0.85:                                          # the dimple around the stem
            zz -= (z - 0.85) * 0.9
        v.co = Vector((x * r, y * r, zz))
        v[fl] = 1 - c
    for f in bm.faces:
        f.smooth = True
        for lp in f.loops:
            k = lp.vert[fl]
            lp[col] = (k, k, k, 1)
    me = bpy.data.meshes.new(f"pumpkin{seed}")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(f"pumpkin{seed}", me)
    bpy.context.scene.collection.objects.link(ob)
    # stem
    st = cyl(f"stem{seed}", stem_mat, 0.08, 0.22, center=(0, 0, squash - 0.05 + 0.1), parent=ob, bevel=0.02, segs=10, r2=0.06)
    st.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 0)
    return ob, squash


# ---------------------------------------------------------------------------- scene
def build(sc):
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.004, 0.007, 1)
    sc.world = w
    steel = bpy.data.materials.new("steel")
    sn = Nodes(steel)
    sn.bsdf.inputs["Base Color"].default_value = (0.6, 0.62, 0.65, 1)
    sn.bsdf.inputs["Metallic"].default_value = 1.0
    sn.bsdf.inputs["Anisotropic"].default_value = 0.3
    sn.link(wear(sn, 0.3, 0.08, 2.0, scratches=0.06), sn.bsdf.inputs["Roughness"])
    dark = principled("frame", (0.05, 0.055, 0.06), rough=0.45, metal=0.7)
    stem_mat = principled("stem", (0.22, 0.2, 0.09), rough=0.8)
    card = principled("card", (0.42, 0.29, 0.16), rough=0.85)

    # floor and conveyor
    floor = box("floor", concrete(), (-30, -30, -1.6), (50, 40, -1.55), bevel=0)
    keys_holder = {}
    belt = box("belt", belt_material(lambda sock: keys_holder.setdefault("sock", sock)), (X_LO, BELT_Y0, -0.12), (X_HI, BELT_Y1, 0.0), bevel=0.01)
    for name, (y0, y1) in {"rail_near": (BELT_Y0 - 0.4, BELT_Y0), "rail_far": (BELT_Y1, BELT_Y1 + 0.4)}.items():
        box(name, steel, (X_LO, y0, -0.3), (X_HI, y1, 0.45), bevel=0.03)
        for i in range(int((X_HI - X_LO) / 1.6)):
            x = X_LO + 0.4 + i * 1.6
            cyl(f"{name}_bolt{i}", dark, 0.05, 0.03, center=(x, (y0 + y1) / 2, 0.46), bevel=0.006, segs=12)
    for x in range(int(X_LO) + 1, int(X_HI), 4):
        for y in (BELT_Y0 - 0.3, BELT_Y1 + 0.3):
            box(f"leg{x}{y}", dark, (x - 0.12, y - 0.12, -1.55), (x + 0.12, y + 0.12, -0.3), bevel=0.02)
    # crates stacked beyond the end of the line
    rnd = random.Random(3)
    for i in range(8):
        x = X_HI + 0.4 + (i % 2) * 2.3
        y = BELT_Y0 - 1.5 + (i // 2) * 2.2
        h = 1.4 + rnd.random() * 0.4
        box(f"crate{i}", card, (x, y, -1.55), (x + 2.0, y + 1.9, -1.55 + h), bevel=0.03)

    # light: two long strips over the belt, a warm fill, a cool rim from the far side
    cx = FR["w"] * U * 0.5
    # hanging LED fixtures over the line: a housing with a glowing diffuser, each a real area light (pools of light)
    housing = principled("housing", (0.08, 0.085, 0.09), rough=0.4, metal=0.8)
    glow = principled("diffuser", (1, 1, 1), emit=(1.0, 0.97, 0.92), emit_strength=18.0)
    # two rows, either side of the line and outside the overhead camera's view, angled in over the belt
    yl = (BELT_Y0 + BELT_Y1) / 2
    for side, yf in ((-1, BELT_Y0 - 3.4), (1, BELT_Y1 + 3.4)):
        for i in range(7):
            x = -14 + i * 6.0 + side * 1.5
            box(f"fixture{side}{i}", housing, (x - 1.6, yf - 0.22, 6.0), (x + 1.6, yf + 0.22, 6.18), bevel=0.02)
            box(f"diffuser{side}{i}", glow, (x - 1.5, yf - 0.16, 5.97), (x + 1.5, yf + 0.16, 6.0), bevel=0)
            cyl(f"cable{side}{i}a", housing, 0.01, 4.0, center=(x - 1.2, yf, 8.1), bevel=0, segs=6)
            cyl(f"cable{side}{i}b", housing, 0.01, 4.0, center=(x + 1.2, yf, 8.1), bevel=0, segs=6)
            L = area(f"led{side}{i}", (x, yf, 5.95), (x, yl, 0), 1.0, 650 if side < 0 else 170, (1.0, 0.97, 0.92), size_y=3.0, spread=120)
    area("warm", (-4, -8, 3), (cx, 3, 0), 6.0, 120, (1.0, 0.72, 0.45))
    area("rim", (cx + 6, 14, 3), (cx, 3, 0), 6.0, 160, (0.45, 0.35, 1.0))

    # pumpkins (one mesh per pumpkin, its own material variation)
    mats = {}
    objs = []
    for pk in P["pumpkins"]:
        kind = pk["kind"]
        key = (kind, pk["k"] % 3)
        if key not in mats:
            mats[key] = pumpkin_material(kind, pk["k"] % 3)
        ob, squash = pumpkin_mesh(1000 + pk["k"], kind, mats[key], stem_mat)
        R = pk["R"] * U
        objs.append((pk, ob, R, squash))

    # camera: low and oblique to begin with, then up to the overhead line camera, settled before the IDs appear
    cam = camera(sc, f_px=1100.0, frame_w=W)
    over_eye = Vector((FR["w"] * U * 0.5, FR["h"] * U * 0.5, 24.0))
    over_tgt = Vector((FR["w"] * U * 0.5, FR["h"] * U * 0.5, 0.0))
    over_f = 100.0 * (over_eye.z - 0.8)            # 100 px per unit at the pumpkins' centre height
    obl_eye = Vector((FR["w"] * U * 0.18, BELT_Y0 - 7.5, 3.2))
    obl_tgt = Vector((FR["w"] * U * 0.62, (BELT_Y0 + BELT_Y1) / 2, 0.2))
    settle = (P["cID"] + 0.1) - P["t0"] - 0.35       # plate seconds: settled 0.25 s before the overlays fade in
    K = Keyer()
    for f in range(-1, NF + 2):
        tau = f / FPS
        rel = P["t0"] + tau                          # seconds relative to the "a3" cue
        u = ioc(clamp(tau / settle))
        e = obl_eye.lerp(over_eye, u)
        e.z = lerp(obl_eye.z, over_eye.z, u ** 1.6)
        tg = obl_tgt.lerp(over_tgt, u)
        K.look(cam, e, tg, f)
        cam.data.lens = lerp(1100.0, over_f, u ** 2) / W * 36.0
        cam.data.keyframe_insert("lens", frame=f)
        keys_holder["sock"].default_value = (-(rel * P["BV"] * U), 0, 0)
        keys_holder["sock"].keyframe_insert("default_value", frame=f)
        for pk, ob, R, squash in objs:
            x = FR["x"] - 110 + (rel - pk["spawn"]) * P["BV"]
            pos = px_to_world(x, pk["y"])
            pos.z = R * squash
            if pos.x < X_LO + 1 or pos.x > X_HI - 0.5:       # off the belt: parked out of sight
                pos = Vector((pos.x, -60, -20))
            yaw = pk["rot0"] + (rel - pk["spawn"]) * 0.15
            K.mat(ob, Matrix.Translation(pos) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Diagonal((R, R, R, 1)), f)
    Keyer.linear()

    def export(sc):
        rows = []
        for f in range(NF):
            sc.frame_set(f)
            row = {}
            for pk, ob, R, squash in objs:
                c = ob.matrix_world.translation
                x, y, z = project(sc, cam, c, W, H)
                if -200 < x < W + 200 and -200 < y < H + 200 and z > 0:
                    row[str(pk["k"])] = [x, y, project_radius(sc, cam, c, R, W, H)]
            rows.append(row)
        return {"pumpkin": rows}

    return cam, export


def main():
    a = args("packline")
    sc = new_scene()
    cam, export = build(sc)
    setup_render(sc, a.samples, a.res, W, H)
    sc.view_settings.exposure = a.exposure
    if not a.no_export:
        write_shot("packline", {"fps": FPS, "frames": NF, "w": W, "h": H, "pts": export(sc), "cam": []})
    if not a.export_only:
        render_frames(sc, a, NF)


if __name__ == "__main__":
    main()
