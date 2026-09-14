"""Quick OBJ preview renderer: 4 orthographic views with flat shading.

Usage: python render_obj.py <file.obj> <out.png> [max_tris]
"""
import sys

import numpy as np
from PIL import Image, ImageDraw

VIEWS = [
    ("side", (2, 1)),    # Z-Y  (right side)
    ("front", (0, 1)),   # X-Y
    ("top", (0, 2)),     # X-Z
    ("iso", None),       # 3/4 view
]


def load_obj(path):
    verts = []
    faces = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                p = line.split()
                verts.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("f "):
                p = line.split()[1:]
                idx = [int(x.split("/")[0]) - 1 for x in p]
                for k in range(1, len(idx) - 1):
                    faces.append((idx[0], idx[k], idx[k + 1]))
    return np.asarray(verts, dtype=np.float64), np.asarray(faces, dtype=np.int64)


def render(verts, faces, size=900, max_tris=400000):
    if len(faces) > max_tris:
        step = len(faces) // max_tris + 1
        faces = faces[::step]
    v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n = n / ln
    light = np.array([0.4, 0.8, 0.45])
    light = light / np.linalg.norm(light)
    shade = np.abs(n @ light)
    centre = (verts.max(0) + verts.min(0)) / 2
    span = (verts.max(0) - verts.min(0)).max()

    canvas = Image.new("RGB", (size * 2, size * 2), (24, 26, 32))
    for vi, (name, axes) in enumerate(VIEWS):
        if axes is None:
            # isometric: rotate 35 deg around Y then 25 around X
            a, b = np.radians(35), np.radians(25)
            ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
            rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
            pts = (verts - centre) @ ry.T @ rx.T
            ax, ay, az = 0, 1, 2
        else:
            pts = verts - centre
            ax, ay = axes
            az = 3 - ax - ay
        sc = (size * 0.45) / (span / 2)
        px = pts[:, ax] * sc
        py = -pts[:, ay] * sc
        pz = pts[:, az]
        order = np.argsort(pz[faces].mean(axis=1))
        img = Image.new("RGB", (size, size), (24, 26, 32))
        dr = ImageDraw.Draw(img)
        tri2 = np.stack([px[faces[:, 0]], py[faces[:, 0]],
                         px[faces[:, 1]], py[faces[:, 1]],
                         px[faces[:, 2]], py[faces[:, 2]]], axis=1)
        tri2 = tri2[order]
        shade_o = shade[order]
        ox, oy = size / 2, size / 2
        for t, s in zip(tri2, shade_o):
            c = int(40 + 200 * min(1.0, s))
            dr.polygon([(ox + t[0], oy + t[1]), (ox + t[2], oy + t[3]),
                        (ox + t[4], oy + t[5])],
                       fill=(c, int(c * 0.96), int(c * 0.88)))
        canvas.paste(img, ((vi % 2) * size, (vi // 2) * size))
        dr2 = ImageDraw.Draw(canvas)
        dr2.text(((vi % 2) * size + 8, (vi // 2) * size + 8), name, fill=(255, 220, 120))
    return canvas


if __name__ == "__main__":
    obj = sys.argv[1]
    out = sys.argv[2]
    v, f = load_obj(obj)
    print(f"{len(v)} verts, {len(f)} tris")
    img = render(v, f)
    img.save(out)
    print("wrote", out)
