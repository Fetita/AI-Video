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

    def sock(self, v, node_input):
        if isinstance(v, (int, float)):
            node_input.default_value = v
        elif isinstance(v, tuple):
            node_input.default_value = v
        elif v is not None:
            self.link(v, node_input)

    def vmath(self, op, a, b=None, c=None):
        """Vector math; returns the Vector output (or the Value output for DOT_PRODUCT / LENGTH / DISTANCE)."""
        m = self.new("ShaderNodeVectorMath", _operation=op)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                if op == "SCALE" and i == 1:
                    m.inputs[3].default_value = v
                else:
                    m.inputs[i].default_value = (v, v, v)
            elif isinstance(v, tuple):
                m.inputs[i].default_value = v
            else:
                if op == "SCALE" and i == 1:
                    self.link(v, m.inputs[3])
                else:
                    self.link(v, m.inputs[i])
        return m.outputs[1] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else m.outputs[0]

    def sep(self, v):
        s = self.new("ShaderNodeSeparateXYZ")
        self.link(v, s.inputs[0])
        return s.outputs

    def comb(self, x, y, z):
        c = self.new("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.sock(v, c.inputs[i])
        return c.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        """Colour mix; a, b sockets or RGB tuples."""
        m = self.new("ShaderNodeMix", _data_type="RGBA", _blend_type=blend)
        self.sock(fac, m.inputs["Factor"])
        for i, v in ((6, a), (7, b)):
            if isinstance(v, tuple):
                m.inputs[i].default_value = (*v[:3], 1)
            else:
                self.link(v, m.inputs[i])
        return m.outputs[2]

    def fmix(self, fac, a, b):
        """Float lerp."""
        m = self.new("ShaderNodeMix", _data_type="FLOAT")
        self.sock(fac, m.inputs["Factor"])
        self.sock(a, m.inputs[2])
        self.sock(b, m.inputs[3])
        return m.outputs[0]

    def smooth(self, e0, e1, x):
        """smoothstep(e0, e1, x) (e0 > e1 gives the falling step)."""
        mr = self.new("ShaderNodeMapRange", _interpolation_type="SMOOTHSTEP")
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = e0, e1
        self.link(x, mr.inputs["Value"])
        return mr.outputs[0]

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


def mesh_object(name, verts, faces, mats=None, mat_index=None, smooth=True, link=True):
    """A mesh object from flat python lists (fast path for big procedural meshes)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    if mats:
        for m in mats:
            me.materials.append(m)
        if mat_index is not None:
            me.polygons.foreach_set("material_index", mat_index)
    me.shade_smooth() if smooth else me.shade_flat()
    me.validate(clean_customdata=False)
    ob = bpy.data.objects.new(name, me)
    if link:
        bpy.context.scene.collection.objects.link(ob)
    return ob


def instancer(name, sources, pts):
    """Geometry Nodes Instance on Points: thousands of copies of a few source objects as true Cycles instances
    (one object in the scene, not one per copy). sources: objects (left unlinked from the scene, at the origin);
    pts: iterable of (x, y, z, rx, ry, rz, sx, sy, sz, index)."""
    src = bpy.data.collections.new(f"{name}_src")
    for i, ob in enumerate(sources):
        ob.name = f"{name}_{i:03d}"               # Collection Info's separate children come in name order
        src.objects.link(ob)
    import numpy as np
    a = np.asarray(list(pts), dtype=np.float32).reshape(-1, 10)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(a))
    me.vertices.foreach_set("co", a[:, 0:3].ravel())
    for key, cols, kind in (("rot", slice(3, 6), "FLOAT_VECTOR"), ("scl", slice(6, 9), "FLOAT_VECTOR")):
        at = me.attributes.new(key, kind, "POINT")
        at.data.foreach_set("vector", a[:, cols].ravel())
    at = me.attributes.new("idx", "INT", "POINT")
    at.data.foreach_set("value", a[:, 9].astype(np.int32))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    g = bpy.data.node_groups.new(name, "GeometryNodeTree")
    g.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N = g.nodes
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    iop = N.new("GeometryNodeInstanceOnPoints")
    ci = N.new("GeometryNodeCollectionInfo")
    ci.transform_space = "ORIGINAL"
    ci.inputs["Collection"].default_value = src
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    def attr(key, kind):
        n = N.new("GeometryNodeInputNamedAttribute")
        n.data_type = kind
        n.inputs["Name"].default_value = key
        return n.outputs["Attribute"]
    e2r = N.new("FunctionNodeEulerToRotation")
    g.links.new(attr("rot", "FLOAT_VECTOR"), e2r.inputs[0])
    g.links.new(gi.outputs[0], iop.inputs["Points"])
    g.links.new(ci.outputs[0], iop.inputs["Instance"])
    iop.inputs["Pick Instance"].default_value = True
    g.links.new(attr("idx", "INT"), iop.inputs["Instance Index"])
    g.links.new(e2r.outputs[0], iop.inputs["Rotation"])
    g.links.new(attr("scl", "FLOAT_VECTOR"), iop.inputs["Scale"])
    g.links.new(iop.outputs[0], go.inputs[0])
    mod = ob.modifiers.new(name, "NODES")
    mod.node_group = g
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
def camera(sc, f_px=1450.0, frame_w=1920, ortho_scale=None, dof=None, clip_end=400.0):
    """A camera whose focal length is given in pixels on a frame `frame_w` wide (sensor fit: horizontal).
    clip_end must reach past everything the shot can see, or distant objects pop in and out as the camera moves."""
    cd = bpy.data.cameras.new("cam")
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36.0
    if ortho_scale:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho_scale
    else:
        cd.lens = f_px / frame_w * 36.0
    cd.clip_start, cd.clip_end = 0.05, clip_end
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
def use_device(sc, device="CPU"):
    """Cycles compute device: CPU, METAL (Apple GPU) or METAL+CPU (GPU and CPU together). Returns the devices in use.
    Exits if a GPU was asked for and none is there (the pip bpy module may ship without Metal: use Blender.app)."""
    device = device.upper()
    if device == "CPU":
        sc.cycles.device = "CPU"
        return ["CPU"]
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.refresh_devices()
    used = []
    for d in prefs.devices:
        d.use = d.type == "METAL" or (d.type == "CPU" and device == "METAL+CPU")
        if d.use:
            used.append(f"{d.name} [{d.type}]")
    if not any(d.use and d.type == "METAL" for d in prefs.devices):
        sys.exit(f"no Metal device available ({[(d.name, d.type) for d in prefs.devices]}): run with Blender.app")
    sc.cycles.device = "GPU"
    print("cycles devices:", ", ".join(used), flush=True)
    return used


def setup_render(sc, samples, res, width=1920, height=1080, transparent=False, adaptive=0.04, bounces=(8, 3, 4, 4),
                 device="CPU", min_samples=0, clamp_indirect=8.0, persistent=True, transparent_bounces=8, exr=False):
    """exr=True: render the noisy, scene-referred image with its denoising albedo and normal passes to a
    multilayer EXR, and leave denoising and the view transform to scripts/denoise_frames.py in a separate process
    (on an 8 GB Mac the denoiser and a big scene must not be in memory at the same time)."""
    sc.render.engine = "CYCLES"
    c = sc.cycles
    use_device(sc, device)
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = adaptive
    c.adaptive_min_samples = min_samples
    c.use_animated_seed = True        # a fresh noise pattern every frame: the denoiser's residue never sticks to the image
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    c.denoising_prefilter = "ACCURATE"
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces = bounces
    c.transparent_max_bounces = transparent_bounces
    c.caustics_reflective = c.caustics_refractive = False
    c.sample_clamp_indirect = clamp_indirect
    c.volume_step_rate = 4.0          # coarser volume marching: haze is soft anyway, and it is the slow part on a CPU
    c.volume_max_steps = 256
    c.use_light_tree = True
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.render.use_persistent_data = persistent
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
    if exr:
        c.use_denoising = False
        sc.view_layers[0].cycles.denoising_store_passes = True
        if hasattr(sc.render.image_settings, "media_type"):     # Blender 5: multilayer is a media type
            sc.render.image_settings.media_type = "MULTI_LAYER_IMAGE"
            sc.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
        else:
            sc.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
        sc.render.image_settings.color_depth = "16"
        sc.render.image_settings.exr_codec = "ZIP"


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
    ap.add_argument("--device", default="CPU", type=str.upper, choices=["CPU", "METAL", "METAL+CPU"],
                    help="Cycles device: CPU, METAL (Apple GPU) or METAL+CPU")
    ap.add_argument("--threshold", type=float, default=None, help="adaptive sampling noise threshold")
    ap.add_argument("--min-samples", type=int, default=0, help="adaptive sampling minimum samples")
    ap.add_argument("--exr", action="store_true", help="render noisy EXRs (+albedo/normal) for scripts/denoise_frames.py")
    ap.add_argument("--export-only", action="store_true", help="write the overlay data, render nothing")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "video", "build", "plates", default_out))
    if extra:
        extra(ap)
    return ap.parse_args(argv)


def render_frames(sc, a, nframes):
    os.makedirs(a.out, exist_ok=True)
    frames = a.frames if a.frames else list(range(*(a.range or (0, nframes)), a.step))
    stats = {"last": ""}

    def on_stats(s):                      # Cycles' status line ("... Mem:..., Peak:...") as it renders
        stats["last"] = s if isinstance(s, str) else str(s)
    bpy.app.handlers.render_stats.append(on_stats)
    exr = sc.render.image_settings.file_format in ("OPEN_EXR", "OPEN_EXR_MULTILAYER")
    if exr:
        os.makedirs(os.path.join(a.out, "exr"), exist_ok=True)
    for f in frames:
        path = os.path.join(a.out, f"{f:04d}.png")
        if exr:
            if os.path.exists(path):
                continue
            path = os.path.join(a.out, "exr", f"{f:04d}.exr")
        if os.path.exists(path):
            continue
        t0 = time.time()
        sc.frame_set(f)
        sc.render.filepath = path
        tmp = path[:-4] + ".tmp" + path[-4:]   # written under a temporary name, so an interrupted frame is never kept
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        os.replace(tmp, path)
        peak = ""
        for part in stats["last"].split("|"):
            if "Peak" in part or "Mem" in part:
                peak += part.strip() + " "
        if not peak and os.environ.get("STATS_DEBUG"):
            peak = repr(stats["last"])[:300]
        print(f"frame {f:4d}  {time.time() - t0:6.1f}s  {peak.strip()}", flush=True)
