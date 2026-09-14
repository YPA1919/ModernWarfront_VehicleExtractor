"""Textured preview renderer for the exported OBJs.

Rasterises with a z-buffer and samples each material's map_Kd, which is the only
way to actually judge whether the UVs are right.

Usage: python render_textured.py <model.obj> <out.png> [size] [views]
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

LIGHT = np.array([0.42, 0.78, 0.46])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def load_obj(path):
    verts, uvs, normals, faces, mtls = [], [], [], [], []
    mat_of_face = []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                p = line.split()
                verts.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("vt "):
                p = line.split()
                uvs.append((float(p[1]), float(p[2])))
            elif line.startswith("vn "):
                p = line.split()
                normals.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("usemtl "):
                cur = line.split(None, 1)[1].strip()
                if cur not in mtls:
                    mtls.append(cur)
            elif line.startswith("f "):
                parts = line.split()[1:]
                idx = []
                for x in parts:
                    bits = x.split("/")
                    vi = int(bits[0]) - 1
                    ti = int(bits[1]) - 1 if len(bits) > 1 and bits[1] else -1
                    idx.append((vi, ti))
                for k in range(1, len(idx) - 1):
                    faces.append((idx[0], idx[k], idx[k + 1]))
                    mat_of_face.append(cur)
    return (np.asarray(verts, dtype=np.float64),
            np.asarray(uvs, dtype=np.float64) if uvs else None,
            np.asarray(faces), mat_of_face, mtls)


def load_mtl(path):
    out, cur = {}, None
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("newmtl "):
                cur = line.split(None, 1)[1].strip()
                out[cur] = None
            elif line.startswith("map_Kd ") and cur:
                out[cur] = line.split(None, 1)[1].strip()
    return out


VIEWS = {
    "iso": ((np.radians(35), np.radians(20)), (0, 1, 2)),
    "side": (None, (2, 1, 0)),
    "front": (None, (0, 1, 2)),
    "top": (None, (0, 2, 1)),
}


def project(verts, centre, span, size, view):
    rot, axes = VIEWS[view]
    if rot is not None:
        a, b = rot
        ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
        rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
        pts = (verts - centre) @ ry.T @ rx.T
    else:
        pts = verts - centre
    ax, ay, az = axes
    sc = (size * 0.46) / (span / 2)
    return pts[:, ax] * sc + size / 2, -pts[:, ay] * sc + size / 2, pts[:, az]


def render(path, size=800, views=("iso",)):
    verts, uvs, faces, mat_of_face, mtls = load_obj(path)
    if len(verts) == 0 or len(faces) == 0:
        return None
    mtl = load_mtl(os.path.splitext(path)[0] + ".mtl")
    texdir = os.path.join(os.path.dirname(path), "textures")
    tex_cache = {}

    def texture_for(mat):
        if mat in tex_cache:
            return tex_cache[mat]
        img = None
        rel = mtl.get(mat)
        if rel:
            p = os.path.join(os.path.dirname(path), rel.replace("\\", "/"))
            if os.path.exists(p):
                img = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)
        tex_cache[mat] = img
        return img

    centre = (verts.max(0) + verts.min(0)) / 2
    span = float((verts.max(0) - verts.min(0)).max())

    # face normals + shading, computed once
    v0, v1, v2 = verts[faces[:, 0, 0]], verts[faces[:, 1, 0]], verts[faces[:, 2, 0]]
    n = np.cross(v1 - v0, v2 - v0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    shade = np.abs((n / ln) @ LIGHT)

    out = Image.new("RGB", (size * len(views), size), (24, 26, 32))
    for vi, view in enumerate(views):
        px, py, pz = project(verts, centre, span, size, view)
        colour = np.zeros((size, size, 3), dtype=np.float32)
        colour[:] = (24, 26, 32)
        depth = np.full((size, size), -1e18, dtype=np.float64)
        for fi in range(len(faces)):
            (a, ta), (b, tb), (c, tc) = faces[fi]
            x0, y0, x1, y1, x2, y2 = px[a], py[a], px[b], py[b], px[c], py[c]
            lo_x = max(0, int(np.floor(min(x0, x1, x2))))
            hi_x = min(size - 1, int(np.ceil(max(x0, x1, x2))))
            lo_y = max(0, int(np.floor(min(y0, y1, y2))))
            hi_y = min(size - 1, int(np.ceil(max(y0, y1, y2))))
            if hi_x < lo_x or hi_y < lo_y:
                continue
            xs = np.arange(lo_x, hi_x + 1) + 0.5
            ys = np.arange(lo_y, hi_y + 1) + 0.5
            gx, gy = np.meshgrid(xs, ys)
            d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(d) < 1e-12:
                continue
            l0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / d
            l1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / d
            l2 = 1.0 - l0 - l1
            mask = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
            if not mask.any():
                continue
            z = l0 * pz[a] + l1 * pz[b] + l2 * pz[c]
            sub_depth = depth[lo_y:hi_y + 1, lo_x:hi_x + 1]
            better = mask & (z > sub_depth)
            if not better.any():
                continue
            sub_depth[better] = z[better]
            img = texture_for(mat_of_face[fi])
            sh = shade[fi]
            if img is not None and uvs is not None and ta >= 0 and tb >= 0 and tc >= 0:
                h, w = img.shape[:2]
                u = l0 * uvs[ta, 0] + l1 * uvs[tb, 0] + l2 * uvs[tc, 0]
                v = l0 * uvs[ta, 1] + l1 * uvs[tb, 1] + l2 * uvs[tc, 1]
                u = np.clip((u % 1.0) * (w - 1), 0, w - 1).astype(np.int32)
                v = np.clip((v % 1.0) * (h - 1), 0, h - 1).astype(np.int32)
                sample = img[v, u]
                target = colour[lo_y:hi_y + 1, lo_x:hi_x + 1]
                target[better] = sample[better] * (0.45 + 0.75 * sh)
            else:
                g = np.clip(45 + 195 * sh, 0, 255)
                target = colour[lo_y:hi_y + 1, lo_x:hi_x + 1]
                target[better] = (g, g * 0.95, g * 0.86)
        out.paste(Image.fromarray(np.clip(colour, 0, 255).astype(np.uint8)), (vi * size, 0))
        dr = ImageDraw.Draw(out)
        dr.text((vi * size + 8, 8), view, fill=(255, 220, 120))
    return out


if __name__ == "__main__":
    obj = sys.argv[1]
    out = sys.argv[2]
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 700
    views = tuple(sys.argv[4].split(",")) if len(sys.argv) > 4 else ("iso", "side")
    img = render(obj, size, views)
    if img is None:
        print("nothing to render")
        sys.exit(1)
    img.save(out)
    print("wrote", out, img.size)
