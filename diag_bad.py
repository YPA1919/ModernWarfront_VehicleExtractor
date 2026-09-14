import sys

import numpy as np

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E
from UnityPy.helpers.MeshHelper import MeshHandler

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())

for tank in sys.argv[1:] or ["FH77BWL52Archer", "K21KNIFV"]:
    print("=" * 90)
    print(tank)
    parts = E.collect_parts(g, roots[tank], False)
    plan = E.plan_parts(g, parts)
    for go, mr, m, is_group in plan:
        mesh = g.mesh(mr)
        h = MeshHandler(mesh)
        h.process()
        V = np.array([[p[0], p[1], p[2]] for p in h.m_Vertices])
        mn, mx = V.min(0), V.max(0)
        sc = (np.linalg.norm(m[0:3]), np.linalg.norm(m[4:7]), np.linalg.norm(m[8:11]))
        # world aabb
        pts = V @ np.array([m[0:3], m[4:7], m[8:11]]) + np.array([m[12], m[13], m[14]])
        wmn, wmx = pts.min(0), pts.max(0)
        print(f"  {g.go_name.get(go)[:30]:32s} grp={int(is_group)} subs={len(mesh.m_SubMeshes):3d} "
              f"scale=({sc[0]:6.2f},{sc[1]:6.2f},{sc[2]:6.2f}) "
              f"meshAABB=({mn[0]:7.2f},{mn[1]:7.2f},{mn[2]:7.2f})-({mx[0]:7.2f},{mx[1]:7.2f},{mx[2]:7.2f}) "
              f"world=({wmn[0]:7.2f},{wmn[1]:7.2f},{wmn[2]:7.2f})-({wmx[0]:7.2f},{wmx[1]:7.2f},{wmx[2]:7.2f})")
