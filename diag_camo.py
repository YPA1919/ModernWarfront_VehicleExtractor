"""Render camo-net submeshes in isolation (world space) next to the rest of the
vehicle, to judge whether the stored cloth state is usable."""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E
E.set_kind(os.environ.get('MW_KIND', 'tanks'))
import render_obj as R

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())

TANKS = sys.argv[1:] or ["Type86", "Leopard2A8", "T90A", "M1A2SEPv2"]

for tank in TANKS:
    order = E.ordered_gameobjects(g, roots[tank])
    intact, wreck = E.build_plan(g, order, False)
    camo_v, camo_f, rest_v, rest_f = [], [], [], []
    for it in intact:
        go, mr, m, sub_idx, mats = it
        h = g.handler(mr)
        if h is None:
            continue
        tris = h.get_triangles()
        flat = ([t for k in sub_idx if k < len(tris) for t in tris[k]] if sub_idx
                else [t for grp in tris for t in grp])
        if not flat:
            continue
        idx = sorted({j for t in flat for j in t})
        pts = np.array([E.xform_point(m, h.m_Vertices[j]) for j in idx])
        remap = {old: i for i, old in enumerate(idx)}
        faces = np.array([[remap[a], remap[b], remap[c]] for a, b, c in flat], dtype=np.int64)
        name = g.go_name.get(go, "")
        if "camo" in name.lower() or "cloth" in name.lower():
            base = len(camo_v)
            camo_v.extend(pts.tolist())
            camo_f.extend((faces + base).tolist())
        else:
            base = len(rest_v)
            rest_v.extend(pts.tolist())
            rest_f.extend((faces + base).tolist())

    if not camo_v:
        print(f"{tank}: no camo net")
        continue
    cv, cf = np.array(camo_v), np.array(camo_f)
    rv, rf = np.array(rest_v), np.array(rest_f)
    # put both in a shared frame using the vehicle centre/scale
    centre = (rv.max(0) + rv.min(0)) / 2
    span = float((rv.max(0) - rv.min(0)).max())
    print(f"{tank}: camo verts={len(cv)} aabb={np.round(cv.min(0),2)}-{np.round(cv.max(0),2)}")
    print(f"   vehicle aabb={np.round(rv.min(0),2)}-{np.round(rv.max(0),2)}")

    def shot(verts, faces, colour):
        if len(faces) == 0:
            return Image.new("RGB", (460, 460), (26, 28, 34))
        n = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]],
                     verts[faces[:, 2]] - verts[faces[:, 0]])
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        ln[ln == 0] = 1
        light = np.array([0.42, 0.78, 0.46])
        light /= np.linalg.norm(light)
        shade = np.abs((n / ln) @ light)
        a, b = np.radians(35), np.radians(20)
        ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
        rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
        pts = (verts - centre) @ ry.T @ rx.T
        sc = (460 * 0.44) / (span / 2)
        px, py, pz = pts[:, 0] * sc, -pts[:, 1] * sc, pts[:, 2]
        order_i = np.argsort(pz[faces].mean(axis=1))
        from PIL import ImageDraw
        img = Image.new("RGB", (460, 460), (26, 28, 34))
        dr = ImageDraw.Draw(img)
        o = 230
        tri = np.stack([px[faces[:, 0]], py[faces[:, 0]], px[faces[:, 1]], py[faces[:, 1]],
                        px[faces[:, 2]], py[faces[:, 2]]], axis=1)[order_i]
        for t, s in zip(tri, shade[order_i]):
            v = int(45 + 195 * min(1.0, s))
            dr.polygon([(o + t[0], o + t[1]), (o + t[2], o + t[3]), (o + t[4], o + t[5])],
                       fill=(v, int(v * .95), int(v * .86)))
        return img

    a = shot(rv, rf, None)
    b = shot(cv, cf, None)
    c = shot(np.vstack([rv, cv]), np.vstack([rf, cf + len(rv)]), None)
    sheet = Image.new("RGB", (1380, 460), (18, 19, 24))
    sheet.paste(a, (0, 0))
    sheet.paste(b, (460, 0))
    sheet.paste(c, (920, 0))
    out = rf"D:\DeepSeek Harness\mw\_camo_{E.safe_name(tank)}.png"
    sheet.save(out)
    print("   wrote", out)
