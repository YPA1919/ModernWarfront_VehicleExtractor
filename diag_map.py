"""Test the hypothesis: within a group mesh, slot i renders submesh i, assigned
in hierarchy order.  Check by comparing each slot's world position with the
matching submesh's centre."""
import collections
import sys

import numpy as np

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E
from UnityPy.helpers.MeshHelper import MeshHandler

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())


def slots_in_order(tank):
    start = g.go2tr[roots[tank]]
    stack = [(start, 0)]
    seen = set()
    out = []
    while stack:
        tp, d = stack.pop()
        if tp in seen:
            continue
        seen.add(tp)
        go = g.tr_go.get(tp)
        if go is not None:
            out.append(go)
        for c in reversed(g.tr_kids.get(tp, ())):
            stack.append((c, d + 1))
    return out


for tank in sys.argv[1:] or ["Leopard2A8"]:
    print("=" * 92)
    print(tank)
    order = slots_in_order(tank)
    by_mesh = collections.defaultdict(list)
    for go in order:
        if go in g.mf:
            by_mesh[g.mf[go]].append(go)

    for mr, gos in sorted(by_mesh.items(), key=lambda kv: -len(kv[1])):
        mesh = g.mesh(mr)
        subs = len(getattr(mesh, "m_SubMeshes", ()) or ())
        if subs < 2:
            continue
        h = MeshHandler(mesh)
        h.process()
        V = np.array([[p[0], p[1], p[2]] for p in h.m_Vertices])
        tris = h.get_triangles()
        print(f"-- mesh {mr.path_id} {mesh.m_Name!r} submeshes={subs} slots={len(gos)}"
              f"  {'MATCH' if subs == len(gos) else 'MISMATCH'}")
        for i, go in enumerate(gos):
            m = g.world_matrix(g.go2tr.get(go))
            wp = np.array([m[12], m[13], m[14]])
            if i < len(tris) and tris[i]:
                idx = sorted({j for t in tris[i] for j in t})
                c = V[idx].mean(0)
                dist = float(np.linalg.norm(c - wp))
                mark = "ok " if dist < 0.15 else "?? "
            else:
                c, dist, mark = None, -1, "?? "
            name = g.go_name.get(go, "?")
            # slot world matrix is the slot's own transform; submesh centre is in
            # mesh space, so a match means the slot transform is roughly identity
            # for that piece OR the piece sits at that offset.
            print(f"   [{i:2d}] {name[:34]:36s} slotpos=({wp[0]:6.2f},{wp[1]:6.2f},{wp[2]:6.2f})"
                  f"  sub{i:02d}centre={None if c is None else np.round(c,2)} {mark}{dist:.2f}")
