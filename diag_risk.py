"""Report group meshes whose slot<->submesh mapping and mount cannot be verified
positionally (few or no slots carrying an offset) - the residual risk set."""
import collections
import os
import sys

import numpy as np

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E
E.set_kind(os.environ.get('MW_KIND', 'tanks'))

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())

unverified = []       # meshes with < 3 significant slots -> mapping assumed
mount_fallback = []   # meshes whose mount came from the closest-to-identity rule
mismatch_geo = []
total = 0
for tank in sorted(roots):
    g.clear_caches()
    order = E.ordered_gameobjects(g, roots[tank])
    by = collections.defaultdict(list)
    for go, w, c, _blur in order:
        if go in g.mf:
            by[g.mf[go]].append(go)
    for mr, slots in by.items():
        mesh = g.mesh(mr)
        if mesh is None:
            continue
        subs = len(getattr(mesh, "m_SubMeshes", ()) or ())
        if subs < 2:
            continue
        total += 1
        h = g.handler(mr)
        if h is None:
            continue
        centres = E.submesh_centres(h)
        if len(centres) != len(slots):
            mismatch_geo.append((tank, mesh.m_Name, subs, len(slots)))
            continue
        sig, dists = 0, []
        for s, c in zip(slots, centres):
            if c is None:
                continue
            m = g.world_matrix(g.go2tr.get(s))
            p = (m[12], m[13], m[14])
            if (p[0] ** 2 + p[1] ** 2 + p[2] ** 2) ** 0.5 <= 0.02:
                continue
            sig += 1
            dists.append(sum((c[k] - p[k]) ** 2 for k in range(3)) ** 0.5)
        if sig < 3:
            unverified.append((tank, mesh.m_Name, subs, len(slots), sig))
        elif sum(dists) / len(dists) >= 0.08:
            mount_fallback.append((tank, mesh.m_Name, subs, round(sum(dists) / len(dists), 3)))

print(f"group meshes: {total}")
print(f"meshes with <3 offset-carrying slots (mapping assumed by order): {len(unverified)}")
for u in unverified[:20]:
    print("   ", u)
print(f"meshes placed with a non-identity mount (subassembly space): {len(mount_fallback)}")
for u in mount_fallback[:25]:
    print("   ", u)
print(f"meshes whose submesh/slot counts disagree (positional pairing): {len(mismatch_geo)}")
for u in mismatch_geo[:15]:
    print("   ", u)
