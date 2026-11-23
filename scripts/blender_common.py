"""
blender_common.py -- shared helpers for the Blender (Cycles) plates built in Python.

Used by render_field.py, render_packline.py, render_board.py and render_tracking.py (render_robot.py and
render_logo.py predate it and keep their own copies). Everything a shot needs that isn't the scene itself:

  - materials and meshes: principled(), box(), cyl(), area(), look_at()
  - a camera from a focal length in pixels (the film's convention: f px on a 1920-wide frame)
  - per-frame keying (one key per frame, LINEAR, so Cycles' motion blur sees the real motion)
  - Cycles settings shared by every plate (AgX, OIDN, adaptive sampling, motion blur)
  - inputs:  video/build/shots/inputs.json, written by video/tools/dump_shot_inputs.mjs from the film's own
             JS models (the field's plants, the pumpkins' spawn table, the story's slots...), so nothing is
             ported by hand from JS to Python
  - outputs: video/src/shots/<name>.js, per-frame camera + screen positions of tracked points, which the
             film's overlays read (video/src/lib/shot.js), so the labels sit on the rendered objects
  - main(): the resumable frame loop with --frames / --range / --step / --samples / --res / --export-only

Coordinates: Blender's own z-up world. Scripts that share 3D geometry with the film (render_tracking.py)
convert the film's y-up world with film_to_bl().
"""
import argparse
import json
import math
import os
import sys
import time

import bpy
import bmesh
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30
rad = math.radians


# ---------------------------------------------------------------------------- small maths
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, t):
    return a + (b - a) * t


def ios(t):  # inOutSine
    return -(math.cos(math.pi * clamp(t)) - 1) / 2


def ioc(t):  # inOutCubic
    t = clamp(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ocubic(t):  # outCubic
    return 1 - (1 - clamp(t)) ** 3


def film_to_bl(v):
    """The film's world (x right, y up, z forward) -> Blender (x right, y forward, z up)."""
    return Vector((v[0], v[2], v[1]))


def inputs():
    path = os.path.join(ROOT, "video", "build", "shots", "inputs.json")
    if not os.path.exists(path):
        sys.exit("missing video/build/shots/inputs.json: run  node video/tools/dump_shot_inputs.mjs  first")
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------- scene
def new_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def world_color(sc, rgb, strength=1.0):
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*rgb, 1)
    bg.inputs[1].default_value = strength
    sc.world = w
    return w


def principled(name, color, rough=0.4, metal=0.0, coat=0.0, emit=None, emit_strength=0.0, sss=0.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.08
    b.inputs["Specular IOR Level"].default_value = spec
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (0.4, 0.25, 0.12)
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_strength
    return m


class Nodes:
    """Tiny helper for writing shader graphs: n = Nodes(mat); a = n.new('ShaderNodeTexNoise', Scale=4)."""

    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        self.bsdf = self.nt.nodes.get("Principled BSDF")

    def new(self, kind, **inputs):
        node = self.nt.nodes.new(kind)
        for k, v in inputs.items():
            if k.startswith("_"):
                setattr(node, k[1:], v)
            else:
                node.inputs[k].default_value = v
        return node

    def link(self, a, b):
        self.nt.links.new(a, b)

    def math(self, op, a, b=None, clamp_=False):
        m = self.new("ShaderNodeMath", _operation=op, _use_clamp=clamp_)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                self.link(v, m.inputs[i])
        return m.outputs[0]

    def ramp(self, fac, stops):
        r = self.new("ShaderNodeValToRGB")
        el = r.color_ramp.elements
        el[0].position, el[0].color = stops[0][0], (*stops[0][1], 1)
        el[1].position, el[1].color = stops[-1][0], (*stops[-1][1], 1)
        for p, c in stops[1:-1]:
            e = el.new(p)
            e.color = (*c, 1)
        self.link(fac, r.inputs[0])
        return r.outputs[0]


def finish(name, bm, mat, parent=None, bevel=0.0, segs=3, smooth=True, angle=28):
    if bevel:
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > rad(angle)]
        if edges:
            bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type="OFFSET", segments=segs, profile=0.5, affect="EDGES")
    for f in bm.faces:
        f.smooth = smooth
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    if mat is not None:
        ob.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)
    if smooth:
        wn = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
        wn.keep_sharp = True
        wn.weight = 100
    if parent is not None:
        ob.parent = parent
    return ob


def box(name, mat, lo, hi, parent=None, bevel=0.01, segs=3):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    lo, hi = Vector(lo), Vector(hi)
    size, mid = hi - lo, (hi + lo) / 2
    bmesh.ops.transform(bm, matrix=Matrix.Translation(mid) @ Matrix.Diagonal((*size, 1.0)), verts=bm.verts)
    return finish(name, bm, mat, parent, bevel, segs)


def cyl(name, mat, r, depth, center=(0, 0, 0), axis="Z", parent=None, bevel=0.008, segs=48, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r if r2 is None else r2, depth=depth)
    rot = Matrix.Identity(4)
    if axis == "Y":
        rot = Matrix.Rotation(rad(90), 4, "X")
    elif axis == "X":
        rot = Matrix.Rotation(rad(90), 4, "Y")
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ rot, verts=bm.verts)
    return finish(name, bm, mat, parent, bevel)


def empty(name, parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    if parent is not None:
        e.parent = parent
    return e


def look_at(ob, loc, target, up="Y"):
    ob.location = Vector(loc)
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", up).to_euler()


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
    look_at(ob, loc, target)
    return ob


def sun(name, direction_target, power, color=(1, 1, 1), angle=2.0):
    ld = bpy.data.lights.new(name, "SUN")
    ld.energy = power
    ld.color = color
    ld.angle = rad(angle)
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    look_at(ob, (0, 0, 0), direction_target)
    return ob


# ---------------------------------------------------------------------------- realism helpers
def physical_sky(sc, elevation_deg, rotation_deg, strength=1.0, air=1.0, aerosol=1.6, ozone=1.0, sun_disc=True, sun_intensity=1.0):
    """Blender's physically based (multiple-scattering) sky: real dusk colours from the sun's elevation."""
    w = bpy.data.worlds.new("sky")
    w.use_nodes = True
    nt = w.node_tree
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = rad(elevation_deg)
    sky.sun_rotation = rad(rotation_deg)
    sky.air_density, sky.aerosol_density, sky.ozone_density = air, aerosol, ozone
    sky.sun_disc = sun_disc
    sky.sun_intensity = sun_intensity
    bg = nt.nodes["Background"]
    nt.links.new(sky.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = strength
    sc.world = w
    return sky


def haze(name, lo, hi, density=0.01, color=(0.9, 0.92, 1.0), anisotropy=0.6, height_falloff=None):
    """A box of participating medium: light shafts from lamps, depth haze. height_falloff (z0, z1) thins it upwards."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        if nd.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(nd)
    out = nt.nodes["Material Output"]
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (*color, 1)
    vol.inputs["Anisotropy"].default_value = anisotropy
    if height_falloff:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs[0])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -1.0, 1.0
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = density, density * height_falloff
        nt.links.new(sep.outputs[2], mr.inputs["Value"])
        nt.links.new(mr.outputs[0], vol.inputs["Density"])
    else:
        vol.inputs["Density"].default_value = density
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    ob = box(name, m, lo, hi, bevel=0)
    ob.visible_shadow = False
    return ob


def wear(n, base_rough=0.4, spread=0.25, scale=6.0, scratches=0.0, coord="Object"):
    """Roughness that varies like a used surface: smudges (noise) and optional fine scratches; returns the socket."""
    tc = n.new("ShaderNodeTexCoord")
    nz = n.new("ShaderNodeTexNoise", Scale=scale, Detail=10.0, Roughness=0.62)
    n.link(tc.outputs[coord], nz.inputs["Vector"])
    r = n.math("ADD", base_rough - spread * 0.5, n.math("MULTIPLY", nz.outputs["Fac"], spread))
    if scratches:
        sc = n.new("ShaderNodeTexWave", Scale=scale * 14, Distortion=22.0, Detail=2.0)
        sc.bands_direction = "DIAGONAL"
        n.link(tc.outputs[coord], sc.inputs["Vector"])
        line = n.math("GREATER_THAN", sc.outputs["Fac"], 0.985)
        r = n.math("SUBTRACT", r, n.math("MULTIPLY", line, scratches))
    return r


# ---------------------------------------------------------------------------- camera
def camera(sc, f_px=1450.0, frame_w=1920, ortho_scale=None, dof=None):
    """A camera whose focal length is given in pixels on a frame `frame_w` wide (sensor fit: horizontal)."""
    cd = bpy.data.cameras.new("cam")
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36.0
    if ortho_scale:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho_scale
    else:
        cd.lens = f_px / frame_w * 36.0
    cd.clip_start, cd.clip_end = 0.05, 400.0
    if dof:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = dof
    ob = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(ob)
    sc.camera = ob
    return ob


class Keyer:
    """One key per frame per object (quaternions kept continuous); call linear() once every key is in."""

    def __init__(self):
        self.prev = {}

    def mat(self, ob, m, f):
        loc, q, scale = m.decompose()
        if ob.name in self.prev:
            q.make_compatible(self.prev[ob.name])
        self.prev[ob.name] = q.copy()
        ob.rotation_mode = "QUATERNION"
        ob.location, ob.rotation_quaternion, ob.scale = loc, q, scale
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_quaternion", frame=f)
        ob.keyframe_insert("scale", frame=f)

    def look(self, ob, eye, target, f, up=Vector((0, 0, 1))):
        eye, target = Vector(eye), Vector(target)
        m = Matrix.Translation(eye) @ (target - eye).to_track_quat("-Z", "Y").to_matrix().to_4x4()
        self.mat(ob, m, f)

    @staticmethod
    def linear():
        for a in bpy.data.actions:
            for fc in getattr(a, "fcurves", []):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        # Blender 5 layered actions: walk the channelbags too
        for a in bpy.data.actions:
            for layer in getattr(a, "layers", []):
                for strip in layer.strips:
                    for bag in getattr(strip, "channelbags", []):
                        for fc in bag.fcurves:
                            for kp in fc.keyframe_points:
                                kp.interpolation = "LINEAR"


def frame_matrix(origin, x_axis, y_axis):
    x = Vector(x_axis).normalized()
    z = x.cross(Vector(y_axis)).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


# ---------------------------------------------------------------------------- render
def setup_render(sc, samples, res, width=1920, height=1080, transparent=False, adaptive=0.04, bounces=(8, 3, 4, 4)):
    sc.render.engine = "CYCLES"
    c = sc.cycles
    c.device = "CPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = adaptive
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces = bounces
    c.caustics_reflective = c.caustics_refractive = False
    c.sample_clamp_indirect = 8.0
    c.volume_step_rate = 4.0          # coarser volume marching: haze is soft anyway, and it is the slow part on a CPU
    c.volume_max_steps = 256
    c.use_light_tree = True
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.render.use_persistent_data = True
    sc.render.film_transparent = transparent
    sc.render.resolution_x, sc.render.resolution_y = int(round(width * res)), int(round(height * res))
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.render.image_settings.compression = 15


# ---------------------------------------------------------------------------- export for the film's overlays
def project(sc, cam, co, out_w, out_h):
    """World point -> plate pixel coordinates (x right, y down) on a plate shown at out_w × out_h."""
    p = world_to_camera_view(sc, cam, Vector(co))
    return p.x * out_w, (1 - p.y) * out_h, p.z


def project_radius(sc, cam, co, r, out_w, out_h):
    """Screen radius of a sphere of radius r at co (measured along the camera's right axis)."""
    right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
    x0, y0, _ = project(sc, cam, co, out_w, out_h)
    x1, y1, _ = project(sc, cam, Vector(co) + right * r, out_w, out_h)
    return math.hypot(x1 - x0, y1 - y0)


def write_shot(name, data):
    """video/src/shots/<name>.js: an ES module the film imports (numbers rounded to 0.1 px)."""
    def rnd(v):
        if isinstance(v, float):
            return round(v, 2)
        if isinstance(v, (list, tuple)):
            return [rnd(x) for x in v]
        if isinstance(v, dict):
            return {k: rnd(x) for k, x in v.items()}
        return v

    path = os.path.join(ROOT, "video", "src", "shots", f"{name}.js")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(f"// Generated by scripts/render_{name.split('-')[0]}.py — do not edit by hand.\n")
        f.write("// Per-frame camera and screen positions (plate pixels) of the tracked objects, for the film's overlays.\n")
        f.write("export default ")
        json.dump(rnd(data), f, separators=(",", ":"))
        f.write(";\n")
    print("wrote", os.path.relpath(path, ROOT))


# ---------------------------------------------------------------------------- the frame loop
def args(default_out, extra=None):
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, nargs="*")
    ap.add_argument("--range", type=int, nargs=2)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--res", type=float, default=0.6667)
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--export-only", action="store_true", help="write the overlay data, render nothing")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "video", "build", "plates", default_out))
    if extra:
        extra(ap)
    return ap.parse_args(argv)


def render_frames(sc, a, nframes):
    os.makedirs(a.out, exist_ok=True)
    frames = a.frames if a.frames else list(range(*(a.range or (0, nframes)), a.step))
    for f in frames:
        path = os.path.join(a.out, f"{f:04d}.png")
        if os.path.exists(path):
            continue
        t0 = time.time()
        sc.frame_set(f)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print(f"frame {f:4d}  {time.time() - t0:5.1f}s", flush=True)
