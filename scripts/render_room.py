#!/usr/bin/env python3
"""
render_room.py -- the "ego camera" still for the face-detection beat of the vision chapter.

Three display mannequins sit behind a workbench in a daylit room: procedural geometry and materials,
Cycles on the CPU, shallow depth of field. They are mannequins on purpose -- the film shows face
detection and anonymisation without showing anyone's face. The script also prints each head's box in
the image (as fractions of its width and height), which video/src/scenes/vision.js uses for its overlays.

    python scripts/render_room.py            # -> video/assets/renders/room.jpg (1720×877, a little
                                             #    larger than the film's feed frame, for a slow push-in)
    python scripts/render_room.py --samples 24 --res 0.5 --out /tmp/room.jpg
"""
import argparse
import json
import math
import os
import sys

import bpy
import bmesh
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1720, 877
rad = math.radians


def material(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0, bump=0.0, bump_scale=200.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    if bump:
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = bump_scale
        n.inputs["Detail"].default_value = 4.0
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = bump
        nt.links.new(n.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def wood(name, a, b_):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.6, 9.0, 9.0)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 5.0
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Distortion"].default_value = 1.2
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*a, 1)
    ramp.color_ramp.elements[1].color = (*b_, 1)
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.3, 0.75
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.42
    return m


def add(name, bm, mat, smooth=True, bevel=0.0):
    if bevel:
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > rad(30)]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=3, profile=0.5, affect="EDGES")
    for f in bm.faces:
        f.smooth = smooth
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)
    if bevel:
        wn = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
        wn.keep_sharp = True
    return ob


def box(name, mat, lo, hi, bevel=0.006):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    lo, hi = Vector(lo), Vector(hi)
    bmesh.ops.transform(bm, matrix=Matrix.Translation((lo + hi) / 2) @ Matrix.Diagonal((*(hi - lo), 1.0)), verts=bm.verts)
    return add(name, bm, mat, bevel=bevel)


def ellipsoid(name, mat, center, scale, rot_z=0.0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=56, v_segments=36, radius=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ Matrix.Rotation(rot_z, 4, "Z") @ Matrix.Diagonal((*scale, 1.0)), verts=bm.verts)
    return add(name, bm, mat)


def cylinder(name, mat, r, depth, center, axis="Z", rot_z=0.0, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=r, radius2=r, depth=depth)
    rot = Matrix.Rotation(rad(90), 4, "Y") if axis == "X" else Matrix.Identity(4)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ Matrix.Rotation(rot_z, 4, "Z") @ rot, verts=bm.verts)
    return add(name, bm, mat, bevel=bevel)


def area(name, loc, target, size, power, color=(1, 1, 1), size_y=None):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.color, ld.size = power, color, size
    if size_y:
        ld.shape, ld.size_y = "RECTANGLE", size_y
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(loc)
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


PEOPLE = [
    # head centre, yaw towards the camera, clothes
    dict(p=(-0.62, 0.70, 1.235), yaw=rad(10), cloth=(0.035, 0.07, 0.13)),
    dict(p=(0.20, 1.95, 1.215), yaw=rad(-4), cloth=(0.16, 0.06, 0.035)),
    dict(p=(1.05, 1.22, 1.20), yaw=rad(-16), cloth=(0.05, 0.10, 0.06)),
]
HEAD = (0.092, 0.102, 0.126)


def person(i, d, skin):
    """A display mannequin: egg-shaped head with the hint of a nose, neck, and a soft block of a torso."""
    x, y, z = d["p"]
    yaw = d["yaw"]
    f = Vector((math.sin(yaw), -math.cos(yaw), 0))          # facing direction (towards the camera)
    cloth = material(f"cloth{i}", d["cloth"], rough=0.85, bump=0.1, bump_scale=900)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=40, radius=1.0)
    for v in bm.verts:                                       # taper towards the chin
        if v.co.z < 0:
            k = 1 - 0.30 * (-v.co.z) ** 1.6
            v.co.x *= k
            v.co.y *= k
    bmesh.ops.transform(bm, matrix=Matrix.Translation((x, y, z)) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Diagonal((*HEAD, 1.0)), verts=bm.verts)
    add(f"head{i}", bm, skin)
    c = Vector((x, y, z))
    ellipsoid(f"nose{i}", skin, c + f * 0.088 + Vector((0, 0, -0.018)), (0.013, 0.022, 0.028), yaw)
    cylinder(f"neck{i}", skin, 0.043, 0.16, (x, y + 0.012, z - 0.15))
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Translation((x, y + 0.02, z - 0.52)) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Diagonal((0.47, 0.23, 0.62, 1.0)), verts=bm.verts)
    add(f"torso{i}", bm, cloth, bevel=0.092)


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    wall = material("wall", (0.075, 0.073, 0.072), rough=0.9, bump=0.05, bump_scale=60)
    box("back", wall, (-4, 3.6, 0), (4, 3.8, 3.2), bevel=0)
    box("left", wall, (-3.4, -3, 0), (-3.2, 3.8, 3.2), bevel=0)
    box("right", wall, (3.2, -3, 0), (3.4, 3.8, 3.2), bevel=0)
    box("ceiling", wall, (-4, -3, 3.0), (4, 3.8, 3.2), bevel=0)
    box("floor", material("floor", (0.10, 0.09, 0.08), rough=0.6), (-4, -3, -0.1), (4, 3.8, 0), bevel=0)
    # window on the back wall (right): bright pane, dark frame
    box("pane", material("pane", (1, 1, 1), emit=(0.80, 0.90, 1.0), strength=4.0), (1.15, 3.55, 1.0), (2.75, 3.6, 2.45), bevel=0)
    frame = material("frame", (0.03, 0.03, 0.035), rough=0.4)
    for lo, hi in (((1.08, 3.5, 0.93), (2.82, 3.58, 1.0)), ((1.08, 3.5, 2.45), (2.82, 3.58, 2.52)), ((1.08, 3.5, 0.93), (1.15, 3.58, 2.52)),
                   ((2.75, 3.5, 0.93), (2.82, 3.58, 2.52)), ((1.925, 3.5, 1.0), (1.975, 3.58, 2.45)), ((1.15, 3.5, 1.70), (2.75, 3.58, 1.74))):
        box("fr", frame, lo, hi, bevel=0.004)
    # shelves on the back wall (left) with a few boxes and binders
    shelf = wood("shelf", (0.11, 0.07, 0.04), (0.24, 0.15, 0.09))
    for z in (1.38, 1.86):
        box("shelf", shelf, (-2.5, 3.28, z), (-0.7, 3.6, z + 0.035))
    props = [(-2.35, 1.415, 0.22, 0.26, (0.20, 0.33, 0.42)), (-2.05, 1.415, 0.16, 0.34, (0.42, 0.25, 0.17)), (-1.6, 1.415, 0.3, 0.2, (0.16, 0.25, 0.15)),
             (-1.15, 1.415, 0.2, 0.3, (0.36, 0.33, 0.26)), (-2.3, 1.895, 0.3, 0.22, (0.34, 0.2, 0.2)), (-1.8, 1.895, 0.2, 0.3, (0.2, 0.22, 0.3)), (-1.2, 1.895, 0.34, 0.18, (0.3, 0.28, 0.2))]
    for k, (x, z, w, h, col) in enumerate(props):
        box(f"prop{k}", material(f"prop{k}", col, rough=0.7), (x, 3.34, z), (x + w, 3.56, z + h), bevel=0.008)
    # workbench across the foreground with a few things on it
    table = wood("table", (0.13, 0.075, 0.04), (0.30, 0.18, 0.10))
    box("table", table, (-2.6, -1.6, 0.70), (2.6, 0.42, 0.75), bevel=0.01)
    box("notebook", material("notebook", (0.06, 0.07, 0.09), rough=0.5), (-0.5, -0.2, 0.75), (-0.1, 0.1, 0.775), bevel=0.004)
    cylinder("mug", material("mug", (0.75, 0.74, 0.72), rough=0.25), 0.045, 0.1, (0.55, 0.05, 0.80), bevel=0.006)
    box("tablet", material("tablet", (0.02, 0.02, 0.025), rough=0.2), (0.95, -0.25, 0.75), (1.4, 0.08, 0.765), bevel=0.004)
    skin = material("mannequin", (0.52, 0.47, 0.43), rough=0.38)
    for i, d in enumerate(PEOPLE):
        person(i, d, skin)

    cd = bpy.data.cameras.new("cam")
    cd.sensor_fit, cd.sensor_width = "HORIZONTAL", 36.0
    cd.lens = 38.0
    cd.dof.use_dof = True
    cd.dof.focus_distance = 2.75
    cd.dof.aperture_fstop = 1.4
    cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam)
    cam.location = (0.12, -1.95, 1.27)
    cam.rotation_euler = (Vector((0.14, 1.2, 1.10)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam

    area("window", (2.2, 3.2, 1.9), (0.0, 0.9, 1.15), 1.6, 620, (0.80, 0.89, 1.0), size_y=1.4)
    area("key", (-2.6, -1.2, 2.2), (0.1, 1.1, 1.15), 1.6, 95, (1.0, 0.86, 0.72))
    area("top", (0.0, 1.0, 2.9), (0.0, 1.0, 0.0), 2.5, 28, (1.0, 0.96, 0.9))
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.006, 0.007, 0.009, 1)
    sc.world = w
    return sc, cam


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--res", type=float, default=1.0)
    ap.add_argument("--out", default=os.path.join(ROOT, "video", "assets", "renders", "room.jpg"))
    a = ap.parse_args(argv)
    sc, cam = build()
    sc.render.engine = "CYCLES"
    c = sc.cycles
    c.device, c.samples, c.use_adaptive_sampling, c.adaptive_threshold = "CPU", a.samples, True, 0.02
    c.use_denoising, c.denoiser = True, "OPENIMAGEDENOISE"
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 6, 4, 4
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = int(W * a.res), int(H * a.res), 100
    sc.view_settings.view_transform, sc.view_settings.look = "AgX", "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 92
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    sc.render.filepath = a.out
    bpy.context.view_layer.update()
    faces = []
    for d in PEOPLE:
        ctr = Vector(d["p"])
        pts = [world_to_camera_view(sc, cam, ctr + Vector((sx * HEAD[0], 0, sz * HEAD[2]))) for sx in (-1, 1) for sz in (-1, 1)]
        xs, ys = [p.x for p in pts], [1 - p.y for p in pts]
        faces.append([round(v, 4) for v in (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))])
    print("FACES (x, y, w, h as fractions of the image):", json.dumps(faces))
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
