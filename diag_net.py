"""Look closely at a camo net: net alone, hull alone, and both, from several
views, plus the Cloth component state."""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E
E.set_kind(os.environ.get('MW_KIND', 'tanks'))

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())


def collect(tank, want_camo):
    order = E.ordered_gameobjects(g, roots[tank])
    intact, wreck = E.build_plan(g, order, False, skip_camo=False)
    V, F = [], []
    for it in intact:
        go, mr, m, sub_idx, mats = it
        name = g.go_name.get(go, "")
        is_camo = bool(E.CAMO_RE.search(name))
        if is_camo != want_camo:
            continue
        h = g.handler(mr)
        if h is None:
            continue
        tris = h.get_triangles()
        flat = ([t for k in sub_idx if k < len(tris) for t in tris[k]] if sub_idx
                else [t for grp in tris for t in grp])
        if not flat:
            continue
        idx = sorted({j for t in flat for j in t})
        remap = {o: i for i, o in enumerate(idx)}
        base = len(V)
        V.extend(E.xform_point(m, h.m_Vertices[j]) for j in idx)
        F.extend([remap[a] + base, remap[b] + base, remap[c] + base] for a, b, c in flat)
    return np.array(V, dtype=np.float64), np.array(F, dtype=np.int64)


def draw(img, dr, verts, faces, centre, span, size, view, tint):
    if len(faces) == 0:
        return
    if view == "side":
        axes = (2, 1, 0)
        pts = verts - centre
    elif view == "top":
        axes = (0, 2, 1)
        pts = verts - centre
    else:
        a, b = np.radians(35), np.radians(20)
        ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
        rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
        pts = (verts - centre) @ ry.T @ rx.T
        axes = (0, 1, 2)
    ax, ay, az = axes
    sc = (size * 0.45) / (span / 2)
    px = pts[:, ax] * sc + size / 2
    py = -pts[:, ay] * sc + size / 2
    pz = pts[:, az]
    n = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]], verts[faces[:, 2]] - verts[faces[:, 0]])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    light = np.array([0.42, 0.78, 0.46])
    light /= np.linalg.norm(light)
    sh = np.abs((n / ln) @ light)
    order = np.argsort(pz[faces].mean(axis=1))
    tri = np.stack([px[faces[:, 0]], py[faces[:, 0]], px[faces[:, 1]], py[faces[:, 1]],
                    px[faces[:, 2]], py[faces[:, 2]]], axis=1)[order]
    for t, s in zip(tri, sh[order]):
        if tint is None:
            v = int(45 + 195 * min(1.0, s))
            col = (v, int(v * .95), int(v * .86))
        else:
            col = tuple(int(c * (0.4 + 0.8 * min(1.0, s))) for c in tint)
        dr.polygon([(t[0], t[1]), (t[2], t[3]), (t[4], t[5])], fill=col)


tank = sys.argv[1] if len(sys.argv) > 1 else "Type86"
v_all, f_all = collect(tank, True)
v_net, f_net = collect(tank, False)
v_body, f_body = collect(tank, False) if False else (None, None)

order = E.ordered_gameobjects(g, roots[tank])
intact, wreck = E.build_plan(g, order, False, skip_camo=False)

# split properly
def split():
    net_v, net_f, body_v, body_f = [], [], [], []
    for it in intact:
        go, mr, m, sub_idx, mats = it
        is_camo = bool(E.CAMO_RE.search(g.go_name.get(go, "")))
        h = g.handler(mr)
        if h is None:
            continue
        tris = h.get_triangles()
        flat = ([t for k in sub_idx if k < len(tris) for t in tris[k]] if sub_idx
                else [t for grp in tris for t in grp])
        if not flat:
            continue
        idx = sorted({j for t in flat for j in t})
        remap = {o: i for i, o in enumerate(idx)}
        dst_v, dst_f = (net_v, net_f) if is_camo else (body_v, body_f)
        base = len(dst_v)
        dst_v.extend(E.xform_point(m, h.m_Vertices[j]) for j in idx)
        dst_f.extend([remap[a] + base, remap[b] + base, remap[c] + base] for a, b, c in flat)
    return (np.array(net_v), np.array(net_f, dtype=np.int64),
            np.array(body_v), np.array(body_f, dtype=np.int64))


net_v, net_f, body_v, body_f = split()
centre = (body_v.max(0) + body_v.min(0)) / 2
span = float((body_v.max(0) - body_v.min(0)).max())
print(f"{tank}: net verts={len(net_v)} tris={len(net_f)}  aabb={np.round(net_v.min(0),2)}-{np.round(net_v.max(0),2)}")
print(f"   body aabb={np.round(body_v.min(0),2)}-{np.round(body_v.max(0),2)}")

S = 430
sheet = Image.new("RGB", (S * 3, S * 2), (18, 19, 24))
for col, view in enumerate(("side", "top", "iso")):
    img = Image.new("RGB", (S, S), (26, 28, 34))
    dr = ImageDraw.Draw(img)
    draw(img, dr, body_v, body_f, centre, span, S, view, (150, 150, 150))
    draw(img, dr, net_v, net_f, centre, span, S, view, (250, 190, 60))
    sheet.paste(img, (col * S, 0))
    img2 = Image.new("RGB", (S, S), (26, 28, 34))
    dr2 = ImageDraw.Draw(img2)
    draw(img2, dr2, net_v, net_f, centre, span, S, view, None)
    sheet.paste(img2, (col * S, S))
out = os.path.join(HERE, "_net_%s.png" % E.safe_name(tank))
sheet.save(out)
print("wrote", out)

# cloth component info
for go, is_w, is_c, _blur in order:
    if E.CAMO_RE.search(g.go_name.get(go, "")) and go in g.mf:
        print("slot", g.go_name.get(go))
        break

