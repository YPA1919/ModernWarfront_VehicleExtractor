# -*- coding: utf-8 -*-
"""Benchmark the preview renderer paths so optimisation is data driven."""
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import tank_gui as G

OBJ = os.path.join(HERE, "sample/Russian/T90A/T90A.obj")
import os
if not os.path.exists(OBJ):
    OBJ = os.path.join(HERE, "sample/Canada/Leopard2A6MC2/Leopard2A6MC2.obj")

m = G.TankModel(OBJ)
print("model:", m.name, "verts", len(m.verts), "faces", len(m.faces))


def bench(fn, n=3):
    fn()
    t = time.time()
    for _ in range(n):
        fn()
    return (time.time() - t) / n


# current numpy path
for size, cap in ((900, 160000), (900, 14000), (640, 14000), (520, 12000)):
    dt = bench(lambda: m.render(35, 20, 1.0, [0, 0], size, mode="textured", max_tris=cap))
    print(f"numpy textured  size={size} cap={cap:6d} -> {dt*1000:7.1f} ms")
for size, cap in ((900, 160000), (900, 14000)):
    dt = bench(lambda: m.render(35, 20, 1.0, [0, 0], size, mode="solid", max_tris=cap))
    print(f"numpy solid     size={size} cap={cap:6d} -> {dt*1000:7.1f} ms")


# ---- candidate: PIL polygon painter's algorithm -------------------------
def pil_render(model, yaw, pitch, zoom, pan, size, cap, textured):
    import math
    w = h = size
    img = Image.new("RGB", (w, h), (26, 28, 34))
    dr = ImageDraw.Draw(img)
    fi = np.arange(len(model.faces))
    if cap and len(fi) > cap:
        fi = fi[:: max(1, len(fi) // cap)]
    f = model.faces[fi]
    a, b = math.radians(yaw), math.radians(pitch)
    ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
    pts = (model.verts - model.centre) @ ry.T @ rx.T
    sc = (size * 0.46) / max(model.span / 2, 1e-6) * zoom
    px = pts[:, 0] * sc + w / 2 + pan[0]
    py = -pts[:, 1] * sc + h / 2 + pan[1]
    pz = pts[:, 2]
    v0, v1, v2 = model.verts[f[:, 0, 0]], model.verts[f[:, 1, 0]], model.verts[f[:, 2, 0]]
    n = np.cross(v1 - v0, v2 - v0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    shade = np.abs((n / ln) @ G.LIGHT)
    order = np.argsort(pz[f[:, :, 0]].mean(axis=1))
    tri = np.stack([px[f[:, 0, 0]], py[f[:, 0, 0]], px[f[:, 1, 0]], py[f[:, 1, 0]],
                    px[f[:, 2, 0]], py[f[:, 2, 0]]], axis=1)[order]
    cols = None
    if textured:
        uv = model.uvs
        tu = (uv[f[:, 0, 1], 0] + uv[f[:, 1, 1], 0] + uv[f[:, 2, 1], 0]) / 3.0 % 1.0
        tv = (uv[f[:, 0, 1], 1] + uv[f[:, 1, 1], 1] + uv[f[:, 2, 1], 1]) / 3.0 % 1.0
        # one texture lookup per distinct material
        cols = np.zeros((len(f), 3))
        mats = np.array(model.mat_of_face, dtype=object)[fi]
        for name in set(mats.tolist()):
            tex = model.texture(name)
            if tex is None:
                continue
            sel = mats == name
            th, tw = tex.shape[:2]
            ui = np.clip((tu[sel] * (tw - 1)).astype(np.int32), 0, tw - 1)
            vi = np.clip((tv[sel] * (th - 1)).astype(np.int32), 0, th - 1)
            cols[sel] = tex[vi, ui]
        cols = cols[order]
    for i, t in enumerate(tri):
        s = shade[order][i]
        if cols is not None:
            c = cols[i] * (0.45 + 0.75 * s)
            col = (int(min(255, c[0])), int(min(255, c[1])), int(min(255, c[2])))
        else:
            g = int(np.clip(45 + 195 * s, 0, 255))
            col = (g, int(g * 0.95), int(g * 0.86))
        dr.polygon([(t[0], t[1]), (t[2], t[3]), (t[4], t[5])], fill=col)
    return img


for size, cap in ((900, 160000), (900, 14000), (520, 12000)):
    dt = bench(lambda: pil_render(m, 35, 20, 1.0, [0, 0], size, cap, False))
    print(f"PIL solid       size={size} cap={cap:6d} -> {dt*1000:7.1f} ms")
for size, cap in ((900, 14000), (520, 12000)):
    dt = bench(lambda: pil_render(m, 35, 20, 1.0, [0, 0], size, cap, True))
    print(f"PIL textured    size={size} cap={cap:6d} -> {dt*1000:7.1f} ms")
