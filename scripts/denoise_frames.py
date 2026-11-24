#!/usr/bin/env python3
"""
denoise_frames.py -- stage 2 of a two-stage plate render (stage 1: a render_*.py script run with --exr).

Stage 1 writes each frame's noisy, scene-referred image with its denoising albedo and normal passes to
<plate>/exr/NNNN.exr. This script, in its own Blender process, denoises each one with OpenImageDenoise (HDR,
accurate prefilter, high quality) in the compositor, applies the view transform (AgX + look + exposure) and writes
<plate>/NNNN.png (16-bit). On an 8 GB Mac the denoiser's working memory (~3 GB at 1080p) and a big scene can't be
resident together; split like this, each stage peaks on its own. Resumable: frames with a PNG are skipped.
Because exposure and look are applied here, they can be retuned without re-rendering.

    Blender -b --factory-startup -P scripts/denoise_frames.py -- video/build/plates/tractor --exposure -3.3
"""
import argparse
import glob
import os
import sys
import time

import bpy


def exr_size(path):
    """Width and height from an OpenEXR header (its dataWindow attribute)."""
    import struct
    with open(path, "rb") as f:
        f.read(8)                                # magic + version
        while True:
            name = b""
            while (c := f.read(1)) != b"\0":
                name += c
            if not name:
                break
            while f.read(1) != b"\0":
                pass
            size = struct.unpack("<i", f.read(4))[0]
            val = f.read(size)
            if name == b"dataWindow":
                x0, y0, x1, y1 = struct.unpack("<4i", val)
                return x1 - x0 + 1, y1 - y0 + 1
    raise ValueError(f"{path}: no dataWindow")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("plate", help="plate directory (EXRs in <plate>/exr)")
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--look", default="AgX - Medium High Contrast")
    ap.add_argument("--frames", type=int, nargs="*")
    ap.add_argument("--force", action="store_true", help="redo frames that already have a PNG")
    ap.add_argument("--prefilter", default="ACCURATE", choices=["NONE", "FAST", "ACCURATE"])
    a = ap.parse_args(argv)
    exrs = sorted(glob.glob(os.path.join(a.plate, "exr", "[0-9][0-9][0-9][0-9].exr")))
    if a.frames:
        exrs = [e for e in exrs if int(os.path.basename(e)[:4]) in a.frames]
    todo = [e for e in exrs if a.force or not os.path.exists(os.path.join(a.plate, os.path.basename(e)[:4] + ".png"))]
    print(f"{len(todo)} of {len(exrs)} frames to denoise", flush=True)
    if not todo:
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"       # renders nothing of note: the compositor produces the image
    sc.render.use_compositing = True
    sc.render.compositor_device = "CPU"
    sc.render.compositor_precision = "FULL"
    sc.render.compositor_denoise_final_quality = "HIGH"
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = a.look
    sc.view_settings.exposure = a.exposure
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "16"
    sc.render.image_settings.compression = 15
    g = bpy.data.node_groups.new("denoise", "CompositorNodeTree")
    g.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    sc.compositing_node_group = g
    img_node = g.nodes.new("CompositorNodeImage")
    dn = g.nodes.new("CompositorNodeDenoise")
    out = g.nodes.new("NodeGroupOutput")
    dn.inputs["HDR"].default_value = True
    dn.inputs["Prefilter"].default_value = a.prefilter.title()
    dn.inputs["Quality"].default_value = "High"
    g.links.new(dn.outputs["Image"], out.inputs[0])
    for e in todo:
        t0 = time.time()
        img = bpy.data.images.load(e)
        img_node.image = img
        sc.render.resolution_x, sc.render.resolution_y = exr_size(e)
        outs = {o.name: o for o in img_node.outputs if o.enabled}
        for k, sock in (("Combined", "Image"), ("Denoising Albedo", "Albedo"), ("Denoising Normal", "Normal")):
            if k not in outs:
                sys.exit(f"{e}: no '{k}' pass (render stage 1 with --exr); has {list(outs)}")
            g.links.new(outs[k], dn.inputs[sock])
        png = os.path.join(a.plate, os.path.basename(e)[:4] + ".png")
        tmp = png[:-4] + ".tmp.png"
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        os.replace(tmp, png)
        bpy.data.images.remove(img)
        print(f"denoised {os.path.basename(png)}  {time.time() - t0:5.1f}s", flush=True)


if __name__ == "__main__":
    main()
