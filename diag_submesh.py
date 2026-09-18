"""Classify every submesh of a group mesh by geometry and UV footprint, to
separate intact parts from wreck parts."""
import sys
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E
from UnityPy.helpers.MeshHelper import MeshHandler

g = E.GameData()

MESH_IDS = [int(x) for x in (sys.argv[1:] or ["19193"])]
for mid in MESH_IDS:
    reader = None
    for sf in g.sfs:
        if sf.name == "resources.assets" and mid in sf.objects:
            reader = sf.objects[mid]
            break
    mesh = reader.read()
    h = MeshHandler(mesh)
    h.process()
    V = np.array([[p[0], p[1], p[2]] for p in h.m_Vertices])
    UV = np.array([[p[0], p[1]] for p in h.m_UV0]) if h.m_UV0 else None
    tris = h.get_triangles()
    print(f"== mesh {mid} {mesh.m_Name!r} verts={len(V)} submeshes={len(tris)} "
          f"uv={'yes' if UV is not None else 'no'}")
    for i, t in enumerate(tris):
        idx = sorted({j for tri in t for j in tri})
        P = V[idx]
        mn, mx = P.min(0), P.max(0)
        line = (f"  sub{i:2d} tris={len(t):6d} "
                f"xyz=({mn[0]:6.2f},{mn[1]:6.2f},{mn[2]:6.2f})-({mx[0]:6.2f},{mx[1]:6.2f},{mx[2]:6.2f})")
        if UV is not None:
            U = UV[idx]
            line += f" uv=({U[:,0].min():5.2f},{U[:,1].min():5.2f})-({U[:,0].max():5.2f},{U[:,1].max():5.2f})"
        print(line)
