"""Investigate three reported problems:
   1. tracks (probably SkinnedMeshRenderer) never collected
   2. wreck ("Destructed") geometry and how it is stored
   3. whether intact and wreck meshes are shared / merged
"""
import collections
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E

g = E.GameData()

# ---- 1. how many renderer kinds exist ------------------------------------
kind = collections.Counter()
smr = {}
mr = {}
for sf in g.sfs:
    for o in sf.objects.values():
        tn = o.type.name
        if tn not in ("SkinnedMeshRenderer", "MeshRenderer"):
            continue
        try:
            d = o.read()
            go = E.try_deref(d.m_GameObject)
        except Exception:
            continue
        kind[tn] += 1
        if go is None:
            continue
        if tn == "SkinnedMeshRenderer":
            smr[go] = d
        else:
            mr[go] = d
print("renderer kinds:", dict(kind))
print("SkinnedMeshRenderer sample names:")
for go, d in list(smr.items())[:10]:
    print("   ", g.go_name.get(go), "| mesh:",
          getattr(E.try_deref(d.m_Mesh), "path_id", None),
          "| bones:", len(d.m_Bones or []))

roots = g.root_candidates(E.tank_name_set())

for tank in ["Leopard2A8", "T90A"]:
    print("=" * 84)
    print(tank)
    # full walk including everything
    start = g.go2tr[roots[tank]]
    stack = [(start, 0)]
    seen = set()
    rows = []
    while stack:
        tp, d = stack.pop()
        if tp in seen:
            continue
        seen.add(tp)
        go = g.tr_go.get(tp)
        if go is not None:
            name = g.go_name.get(go, "?")
            tag = []
            if go in g.mf:
                mesh = g.mesh(g.mf[go])
                tag.append(f"MF subs={len(getattr(mesh,'m_SubMeshes',()) or ())}")
            if go in mr:
                tag.append("MR")
            if go in smr:
                sd = smr[go]
                mref = E.try_deref(sd.m_Mesh)
                mesh = g.mesh(mref) if mref else None
                tag.append(f"SMR subs={len(getattr(mesh,'m_SubMeshes',()) or ())} "
                           f"bones={len(sd.m_Bones or [])} mesh={getattr(mesh,'m_Name',None)}")
            if tag:
                rows.append(("  " * min(d, 4), name, "; ".join(tag)))
        for c in reversed(g.tr_kids.get(tp, ())):
            stack.append((c, d + 1))
    for ind, name, tag in rows:
        print(f"  {ind}{name:38s} {tag}")
