
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
