"""Decisive check: what exactly do the leaf slots carry (component list, full
material array, submesh index hints)?"""
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())

tank = sys.argv[1] if len(sys.argv) > 1 else "Leopard2A8"
start = g.go2tr[roots[tank]]
stack = [(start, 0)]
seen = set()
found = {}
while stack:
    tp, d = stack.pop()
    if tp in seen:
        continue
    seen.add(tp)
    go = g.tr_go.get(tp)
    if go is not None:
        found.setdefault(g.go_name.get(go), go)
        for c in reversed(g.tr_kids.get(tp, ())):
            stack.append((c, d + 1))

TARGETS = ["Hull_LOD0", "Hull_Destructed_LOD0", "Track_L_LOD0", "Track_L_LOD1",
           "Track_L_Destructed_LOD0", "Hull_NERA_Screen_Side_L_01_LOD0",
           "Turret_LOD0", "Turret_Destructed_LOD0", "Gun_LOD0"]

for name in TARGETS:
    go = found.get(name)
    if go is None:
        print(f"{name}: not in prefab")
        continue
    gd = go.read()
    print(f"== {name}  active={gd.m_IsActive}")
    for c in gd.m_Component:
        r = E.try_deref(c.component if hasattr(c, "component") else c)
        if r is None:
            print("     <unresolved>")
            continue
        tn = r.type.name
        d = r.read()
        if tn == "MeshFilter":
            print(f"     MeshFilter mesh={d.m_Mesh.m_PathID}")
        elif tn == "MeshRenderer":
            mats = [E.try_deref(m) for m in (d.m_Materials or [])]
            names = [getattr(g.material(x), "m_Name", None) for x in mats]
            print(f"     MeshRenderer enabled={getattr(d,'m_Enabled',None)} "
                  f"n_materials={len(mats)} materials={names[:6]}")
        elif tn == "SkinnedMeshRenderer":
            mats = [E.try_deref(m) for m in (d.m_Materials or [])]
            names = [getattr(g.material(x), "m_Name", None) for x in mats]
            print(f"     SkinnedMeshRenderer enabled={getattr(d,'m_Enabled',None)} "
                  f"n_materials={len(mats)} materials={names[:4]} bones={len(d.m_Bones or [])}")
        else:
            extra = ""
            if tn == "MonoBehaviour":
                try:
                    sc = E.try_deref(d.m_Script)
                    extra = f" script={sc.read().m_Name if sc else '?'}"
                except Exception:
                    extra = " script=?"
            print(f"     {tn}{extra}")
