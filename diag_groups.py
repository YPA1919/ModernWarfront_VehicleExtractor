import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())
parts = E.collect_parts(g, roots["Leopard2A8"], False)

by_mesh = collections.defaultdict(list)
for go in parts:
    mr = g.mf[go]
    mesh = g.mesh(mr)
    by_mesh[(mr.path_id, getattr(mesh, "m_Name", None), len(mesh.m_SubMeshes))].append(go)

for (pid, name, subs), gos in sorted(by_mesh.items(), key=lambda kv: -len(kv[1])):
    print(f"mesh {pid} {name!r} submeshes={subs} users={len(gos)}")
    for go in gos:
        tr = g.go2tr.get(go)
        d = g.tr.get(tr)
        parent = E.try_deref(d.m_Father) if d else None
        pname = g.go_name.get(g.tr_go.get(parent)) if parent else None
        lp = d.m_LocalPosition if d else None
        lr = d.m_LocalRotation if d else None
        ls = d.m_LocalScale if d else None
        print(f"    {g.go_name.get(go):36s} parent={str(pname):24s} "
              f"localPos=({lp.x:6.3f},{lp.y:6.3f},{lp.z:6.3f}) "
              f"scale=({ls.x:5.2f},{ls.y:5.2f},{ls.z:5.2f})")
