"""Dump one tank's slot <-> submesh assignment with geometry, plus a render."""
import collections
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

tank = sys.argv[1] if len(sys.argv) > 1 else "ZBD86"
order = E.ordered_gameobjects(g, roots[tank])

mf_slots = collections.defaultdict(list)
for go, w, c, _blur in order:
    if go in g.mf:
        mf_slots[g.mf[go]].append((go, w, c))

print(f"===== {tank}: {len(order)} objects, {len(mf_slots)} meshes =====")
for mr, slots in sorted(mf_slots.items(), key=lambda kv: -len(kv[1])):
    mesh = g.mesh(mr)
    subs = len(mesh.m_SubMeshes)
    if subs < 2:
        continue
    h = g.handler(mr)
    centres = E.submesh_centres(h) if h else []
    tris = h.get_triangles() if h else []
    tag = "MATCH" if subs == len(slots) else "MISMATCH"
    print(f"-- mesh {mr.path_id} {mesh.m_Name!r} subs={subs} slots={len(slots)} {tag}")
    for i, (go, w, c) in enumerate(slots):
        m = g.world_matrix(g.go2tr.get(go))
        wp = np.array([m[12], m[13], m[14]])
        cen = centres[i] if i < len(centres) else None
        ntri = len(tris[i]) if i < len(tris) else 0
        d = float(np.linalg.norm(np.array(cen) - wp)) if cen else -1
        flag = "ok " if d < 0.12 else ("~  " if d < 0.3 else "BAD")
        print(f"   [{i:2d}] {g.go_name.get(go)[:34]:36s} w={'W' if w else '.'} "
              f"slotpos=({wp[0]:6.2f},{wp[1]:6.2f},{wp[2]:6.2f}) "
              f"sub{i:02d}c={None if cen is None else np.round(cen,2)} tris={ntri:5d} {flag}{d:.2f}")
