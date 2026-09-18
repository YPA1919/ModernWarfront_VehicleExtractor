"""Render individual submeshes of a group mesh side by side, to tell intact
geometry apart from wreck geometry."""
import sys
import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E
from UnityPy.helpers.MeshHelper import MeshHandler

g = E.GameData()


def submesh_arrays(mid, subs):
    reader = None
    for sf in g.sfs:
        if sf.name == "resources.assets" and mid in sf.objects:
            reader = sf.objects[mid]
            break
    mesh = reader.read()
    h = MeshHandler(mesh)
    h.process()
    tris = h.get_triangles()
    V = np.array([[p[0], p[1], p[2]] for p in h.m_Vertices])
    out = []
    for si in subs:
        if si >= len(tris):
            continue
        t = np.array(tris[si], dtype=np.int64)
        if len(t) == 0:
            continue
        out.append((si, len(t), V, t))
    return mesh.m_Name, out


def draw(canvas, box, verts, faces, title, size=420):
    if len(faces) == 0:
        return
    v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    shade = np.abs((n / ln) @ (np.array([0.42, 0.78, 0.46]) / np.linalg.norm([0.42, 0.78, 0.46])))
    c = (verts.max(0) + verts.min(0)) / 2
    span = max((verts.max(0) - verts.min(0)).max(), 1e-6)
    a, b = np.radians(35), np.radians(20)
    ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    pts = (verts - c) @ ry.T @ rx.T
    sc = (size * 0.44) / (span / 2)
    px, py, pz = pts[:, 0] * sc, -pts[:, 1] * sc, pts[:, 2]
    order = np.argsort(pz[faces].mean(axis=1))
    tri = np.stack([px[faces[:, 0]], py[faces[:, 0]], px[faces[:, 1]], py[faces[:, 1]],
                    px[faces[:, 2]], py[faces[:, 2]]], axis=1)[order]
    img = Image.new("RGB", (size, size), (26, 28, 34))
    dr = ImageDraw.Draw(img)
    o = size / 2
    for t, s in zip(tri, shade[order]):
        v = int(45 + 195 * min(1.0, s))
        dr.polygon([(o + t[0], o + t[1]), (o + t[2], o + t[3]), (o + t[4], o + t[5])],
                   fill=(v, int(v * .95), int(v * .86)))
    dr.text((8, 8), title, fill=(255, 215, 120))
    canvas.paste(img, box)


groups = [(19193, [26, 27, 28, 33, 34]), (24013, [2, 5, 7])]
for mid, subs in groups:
    name, items = submesh_arrays(mid, subs)
    cell = 420
    cols = len(items)
    canvas = Image.new("RGB", (cell * cols, cell), (18, 19, 24))
    for i, (si, ntri, V, t) in enumerate(items):
        draw(canvas, (i * cell, 0), V, t, f"mesh {mid} sub{si}  ({ntri} tris)")
    canvas.save(os.path.join(HERE, "_subs_%s.png" % mid))
    print("wrote", os.path.join(HERE, "_subs_%s.png" % mid),
          "subs", [i[0] for i in items])
