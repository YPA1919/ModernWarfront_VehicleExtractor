import collections
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E
from UnityPy.helpers.MeshHelper import MeshHandler

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())

for tank in ["Leopard2A8", "KW2Jupiter120", "T90A"]:
    print("=" * 78)
    print(tank)
    parts = E.collect_parts(g, roots[tank], False)
    by_mesh = collections.defaultdict(list)
    for go in parts:
        by_mesh[g.mf[go]].append(go)
    for mr, gos in sorted(by_mesh.items(), key=lambda kv: -len(kv[1])):
        mesh = g.mesh(mr)
        subs = len(getattr(mesh, "m_SubMeshes", ()) or ())
        if subs <= 1:
            continue
        h = MeshHandler(mesh)
        h.process()
        V = np.array([[p[0], p[1], p[2]] for p in h.m_Vertices])
        mn, mx = V.min(0), V.max(0)
        print(f"  mesh {mr.path_id} {mesh.m_Name!r} submeshes={subs} users={len(gos)}")
        print(f"     local AABB ({mn[0]:6.2f},{mn[1]:6.2f},{mn[2]:6.2f})-({mx[0]:6.2f},{mx[1]:6.2f},{mx[2]:6.2f})")
        for go in gos[:5]:
            m = g.world_matrix(g.go2tr.get(go))
            print(f"       slot {g.go_name.get(go):34s} worldPos=({m[12]:6.3f},{m[13]:6.3f},{m[14]:6.3f})")
