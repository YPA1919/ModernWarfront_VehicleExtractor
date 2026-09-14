import collections
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())
root = roots["Leopard2A8"]
parts = E.collect_parts(g, root, False)
print("parts:", len(parts))

mesh_ids = collections.Counter()
rows = []
for go in parts:
    mr = g.mf.get(go)
    name = g.go_name.get(go)
    tr = g.go2tr.get(go)
    d = g.tr.get(tr)
    m = g.mesh(mr) if mr else None
    lp = d.m_LocalPosition if d else None
    ls = d.m_LocalScale if d else None
    mesh_ids[(mr.assets_file.name if mr else None, mr.path_id if mr else None)] += 1
    rows.append((name,
                 f"{mr.assets_file.name}:{mr.path_id}" if mr else "?",
                 getattr(m, "m_Name", None),
                 (m.m_VertexData.m_VertexCount if m is not None else None),
                 (round(lp.x, 2), round(lp.y, 2), round(lp.z, 2)) if lp else None,
                 (round(ls.x, 3), round(ls.y, 3), round(ls.z, 3)) if ls else None))

print("distinct mesh refs:", len(mesh_ids))
print("most reused mesh refs:", mesh_ids.most_common(4))
print()
for r in sorted(rows, key=lambda x: -(x[3] or 0))[:20]:
    print(f"  {r[0]:36s} {r[1]:28s} v={r[3]} pos={r[4]} scale={r[5]}")

# active state of parts
inactive = 0
for go in parts:
    try:
        if not go.read().m_IsActive:
            inactive += 1
    except Exception:
        pass
print("inactive parts:", inactive, "of", len(parts))

# compare with KW2 for reference
root2 = roots["KW2Jupiter120"]
p2 = E.collect_parts(g, root2, False)
print("\nKW2 parts:", len(p2), "distinct mesh refs:",
      len({(g.mf[go].assets_file.name, g.mf[go].path_id) for go in p2 if g.mf.get(go)}))
