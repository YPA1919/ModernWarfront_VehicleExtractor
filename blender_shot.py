# -*- coding: utf-8 -*-
"""Blender 出图：把导出的 OBJ 渲染成带贴图的成品图。

思路沿用「最后一炮」那套：Blender 后台跑 Workbench 引擎，着色方式直接取 MTL 里的
贴图（color_type='TEXTURE'）+ 平光 + cavity 描形，速度快而且不用搭灯光。

    python blender_shot.py model.obj out.png [--yaw -35] [--pitch 22] [--zoom 1]
    python blender_shot.py --batch --root OUT [--only T90A,ZBD86] [--sample 4]
                           [--name render.png] [--size 1600x1000]

批量模式输出 "PROGRESS done total"，GUI 用它驱动进度条。
"""
import argparse
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

BLENDER_PY = r'''
import bpy, sys, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv[0], argv[1]
dx, dy, dz, dist_k, lens = (float(v) for v in argv[2:7])
size_x, size_y = (int(v) for v in argv[7:9])
transparent = (argv[9] == "1")
light_mode = argv[10] if len(argv) > 10 else "FLAT"

bpy.ops.wm.read_factory_settings(use_empty=True)

# Blender 4.x/5.x 用 wm.obj_import，3.x 用 import_scene.obj
try:
    bpy.ops.wm.obj_import(filepath=src)
except AttributeError:
    bpy.ops.import_scene.obj(filepath=src)

objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if not objs:
    raise SystemExit("no mesh in %s" % src)

pts = []
for o in objs:
    for c in o.bound_box:
        pts.append(o.matrix_world @ Vector(c))
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
centre = (lo + hi) / 2
radius = max((hi - lo).x, (hi - lo).y, (hi - lo).z) / 2 or 1.0

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
d = Vector((dx, dy, dz))
if d.length < 1e-6:
    d = Vector((0.85, -1.0, 0.45))
d = d.normalized()
cam.location = centre + d * radius * dist_k
cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
cam_data.lens = lens
bpy.context.scene.camera = cam

scn = bpy.context.scene
scn.render.resolution_x, scn.render.resolution_y = size_x, size_y
scn.render.resolution_percentage = 100
scn.render.film_transparent = bool(transparent)
scn.render.filepath = dst
scn.render.image_settings.file_format = 'PNG'
scn.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
scn.render.engine = 'BLENDER_WORKBENCH'

sh = scn.display.shading
def setopt(name, value):
    try:
        setattr(sh, name, value)
    except Exception as exc:
        print("shading.%s not set: %r" % (name, exc))

setopt("color_type", 'TEXTURE')     # 直接用 MTL 里的贴图
setopt("light", light_mode)         # FLAT：贴图颜色不被压暗，靠 cavity 交代形体
setopt("show_cavity", True)         # 凹陷阴影把形体交代清楚
setopt("cavity_type", 'SCREEN')
setopt("curvature_ridge_factor", 0.25)
setopt("curvature_valley_factor", 0.9)
setopt("cavity_ridge_factor", 0.4)
setopt("cavity_valley_factor", 1.0)
setopt("show_object_outline", True)
setopt("object_outline_color", (0.08, 0.08, 0.08))
setopt("show_shadows", False)
try:
    scn.display.render_aa = '8'
except Exception as exc:
    print("render_aa not set: %r" % (exc,))
try:
    scn.view_settings.view_transform = 'Standard'
except Exception:
    pass

bpy.ops.render.render(write_still=True)
print("rendered", dst)
'''


def find_blender():
    """BLENDER_EXE 环境变量优先，其次常见安装目录，最后 PATH。"""
    cands = [os.environ.get("BLENDER_EXE")]
    for root in (r"D:\Blender Foundation", r"C:\Program Files\Blender Foundation",
                 r"C:\Program Files\Blender", r"D:\Program Files\Blender Foundation"):
        if os.path.isdir(root):
            for d in sorted(os.listdir(root), reverse=True):
                exe = os.path.join(root, d, "blender.exe")
                if os.path.exists(exe):
                    cands.insert(0, exe)
    cands.append("blender")
    for c in cands:
        if not c:
            continue
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            from shutil import which
            p = which(c)
            if p:
                return p
    return None


def camera_dir(yaw, pitch):
    """预览里的 yaw/pitch -> OBJ 空间里"从模型指向相机"的方向。

    与 GUI 实时预览的旋转矩阵一致：R 的第三行就是视线方向，
    Blender 的 OBJ 导入按 (x, y, z)_obj -> (x, -z, y)_blender 换轴。
    """
    a, b = math.radians(yaw), math.radians(pitch)
    ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
    d_obj = (-cb * sa, sb, cb * ca)
    return (d_obj[0], -d_obj[2], d_obj[1])


def blender_render(obj_path, png_path, yaw=-35.0, pitch=22.0, zoom=1.0,
                   size=(1400, 900), transparent=False, blender=None,
                   log=print, timeout=900, script_path=None, light="FLAT"):
    blender = blender or find_blender()
    if not blender:
        log("没找到 blender.exe（可设环境变量 BLENDER_EXE 指定路径）")
        return None
    obj_path = os.path.abspath(obj_path)
    png_path = os.path.abspath(png_path)
    if not os.path.exists(obj_path):
        log("模型不存在: %s" % obj_path)
        return None
    script = script_path or os.path.join(HERE, "_blender_shot.py")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(BLENDER_PY)
    d = camera_dir(yaw, pitch)
    dist_k = 3.1 / max(0.35, min(2.0, zoom))
    lens = 55.0 * max(0.5, min(1.6, zoom))
    cmd = [blender, "-b", "--factory-startup", "--python", script, "--",
           obj_path, png_path,
           "%.4f" % d[0], "%.4f" % d[1], "%.4f" % d[2],
           "%.3f" % dist_k, "%.2f" % lens,
           str(int(size[0])), str(int(size[1])), "1" if transparent else "0",
           light]
    log("Blender: %s" % os.path.basename(blender))
    log("  视角 水平 %.0f° 俯仰 %.0f° 缩放 %.2f  %dx%d" %
        (yaw, pitch, zoom, size[0], size[1]))
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             timeout=timeout)
        text = out.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        log("Blender 超时（%ds）" % timeout)
        return None
    except Exception as exc:
        log("Blender 启动失败: %r" % (exc,))
        return None
    for line in text.strip().splitlines()[-6:]:
        log("  " + line)
    if out.returncode != 0 and not os.path.exists(png_path):
        log("Blender 退出码 %s" % out.returncode)
        return None
    if not os.path.exists(png_path):
        alt = png_path + ".png"
        if os.path.exists(alt):
            png_path = alt
        else:
            log("Blender 没有输出图片")
            return None
    log("出图: %s" % png_path)
    return png_path


def batch_targets(root, only=None, sample=0, seed=7):
    import random
    items = []
    if not os.path.isdir(root):
        return items
    for country in sorted(os.listdir(root)):
        d = os.path.join(root, country)
        if not os.path.isdir(d):
            continue
        for tank in sorted(os.listdir(d)):
            obj = os.path.join(d, tank, tank + ".obj")
            if os.path.exists(obj):
                items.append((tank, obj))
    if only:
        want = {x.strip() for x in only.split(",") if x.strip()}
        items = [x for x in items if x[0] in want]
    if sample:
        items = random.Random(seed).sample(items, min(sample, len(items)))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("obj", nargs="?", help="单个模型")
    ap.add_argument("out", nargs="?", help="输出 PNG")
    ap.add_argument("--batch", action="store_true")
    ap.add_argument("--root",
                    default=os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "MW_Tanks"))
    ap.add_argument("--only", default="")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--name", default="render.png", help="批量模式的文件名")
    ap.add_argument("--wreck", action="store_true", help="批量模式渲染残骸模型")
    ap.add_argument("--yaw", type=float, default=-35.0)
    ap.add_argument("--pitch", type=float, default=22.0)
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--size", default="1400x900")
    ap.add_argument("--transparent", action="store_true")
    args = ap.parse_args()
    size = tuple(int(v) for v in args.size.lower().split("x"))

    if args.batch:
        items = batch_targets(args.root, args.only, args.sample, args.seed)
        if not items:
            print("没有找到模型（root=%s）" % args.root)
            return 1
        print("%d 个模型" % len(items), flush=True)
        print("PROGRESS 0 %d" % len(items), flush=True)
        ok = 0
        for i, (tank, obj) in enumerate(items, 1):
            if args.wreck:
                w = os.path.join(os.path.dirname(obj), tank + "_Wreck.obj")
                if os.path.exists(w):
                    obj = w
            png = os.path.join(os.path.dirname(obj), args.name)
            if blender_render(obj, png, args.yaw, args.pitch, args.zoom, size,
                              args.transparent) is not None:
                ok += 1
            print("PROGRESS %d %d" % (i, len(items)), flush=True)
        print("完成 %d/%d" % (ok, len(items)), flush=True)
        return 0

    if not args.obj or not args.out:
        ap.print_help()
        return 1
    got = blender_render(args.obj, args.out, args.yaw, args.pitch, args.zoom, size,
                         args.transparent)
    return 0 if got else 1


if __name__ == "__main__":
    sys.exit(main())
