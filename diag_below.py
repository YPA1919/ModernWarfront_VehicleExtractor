"""Inspect specific parts: mesh local AABB vs slot transform, and the ancestor
chain, to tell a parked part from a double-offset one."""
import sys

import numpy as np

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())

TARGETS = {
    "M3A3": ["BGM-71-TOW_Turret_LOD0", "BGM-71-TOW_Hull_LOD0"],
    "PantsirSM": ["Support_02_LOD0"],
    "Strv2000": ["KSP39C_Gun_LOD0"],
    "K30Biho": None,
    "M3Bradley": ["BGM-71-TOW_Turret_LOD0", "BGM-71-TOW_Hull_LOD0"],
}

for tank, names in TARGETS.items():
    order = E.ordered_gameobjects(g, roots[tank])
    print("=" * 88)
    print(tank)
    for go, is_w, is_c, _blur in order:
        n = g.go_name.get(go, "")
        if names is not None and n not in names:
            continue
        if names is None and not (go in g.mf or go in g.smr):
            continue
        if names is None:
            h = g.handler(g.mf[go]) if go in g.mf else None
            if h is None:
                continue
            tris = h.get_triangles()
            flat = [t for grp in tris for t in grp]
            idx = sorted({j for t in flat for j in t})
            V = np.array([h.m_Vertices[j][:3] for j in idx])
        else:
            mr = g.mf.get(go) or (g.smr.get(go) or (None,))[0]
            h = g.handler(mr)
            if h is None:
                continue
            tris = h.get_triangles()
            flat = [t for grp in tris for t in grp]
            idx = sorted({j for t in flat for j in t})
            V = np.array([h.m_Vertices[j][:3] for j in idx])
        m = g.world_matrix(g.go2tr.get(go))
        W = np.array([E.xform_point(m, v) for v in V])
        chain = []
        tp = g.go2tr.get(go)
        while tp is not None:
            chain.append(g.go_name.get(g.tr_go.get(tp), "?"))
            f = E.try_deref(g.tr[tp].m_Father)
            tp = g.go2tr.get(f) if f else None
        print(f"  {n}")
        print(f"     mesh local aabb {np.round(V.min(0),3)} - {np.round(V.max(0),3)}")
        print(f"     slot world      {np.round([m[12],m[13],m[14]],3)}  "
              f"scale=({np.linalg.norm(m[0:3]):.2f},{np.linalg.norm(m[4:7]):.2f},{np.linalg.norm(m[8:11]):.2f})")
        print(f"     placed aabb     {np.round(W.min(0),3)} - {np.round(W.max(0),3)}")
        print(f"     chain           {' < '.join(chain[:5])}")
