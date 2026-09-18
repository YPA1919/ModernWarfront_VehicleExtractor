"""For one tank: per-part world AABB, mesh local AABB, and the transform used,
so a mis-placed group can be spotted."""
import collections
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E
E.set_kind(os.environ.get('MW_KIND', 'tanks'))

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())
tank = sys.argv[1] if len(sys.argv) > 1 else "ZBD86"

order = E.ordered_gameobjects(g, roots[tank])
intact, wreck = E.build_plan(g, order, False)

rows = []
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
    V = np.array([h.m_Vertices[j][:3] for j in idx])
    W = np.array([E.xform_point(m, v) for v in V])
    rows.append((g.go_name.get(go, ""), mr, m, V.min(0), V.max(0), W.min(0), W.max(0),
                 "SMR" if go in g.smr else "MF"))

body_lo = np.min([r[5] for r in rows], axis=0)
body_hi = np.max([r[6] for r in rows], axis=0)
c = (body_lo + body_hi) / 2
size = float(np.linalg.norm(body_hi - body_lo))
print(f"{tank}: {len(rows)} parts, whole-model aabb "
      f"{np.round(body_lo,2)}-{np.round(body_hi,2)}")
print()
print(f"{'part':34s} {'src':4s} {'local aabb':30s} {'world aabb':30s} off")
for name, mr, m, lmn, lmx, wmn, wmx, src in sorted(rows, key=lambda r: -np.linalg.norm(r[6] - r[5])):
    wc = (wmn + wmx) / 2
    dist = float(np.linalg.norm(wc - c))
    flag = "  <== far" if dist > 0.75 * size else ""
    print(f"{name[:33]:34s} {src:4s} "
          f"({lmn[0]:5.2f},{lmn[1]:5.2f},{lmn[2]:5.2f})-({lmx[0]:5.2f},{lmx[1]:5.2f},{lmx[2]:5.2f}) "
          f"({wmn[0]:5.2f},{wmn[1]:5.2f},{wmn[2]:5.2f})-({wmx[0]:5.2f},{wmx[1]:5.2f},{wmx[2]:5.2f}) "
          f"{dist:.2f}{flag}")
