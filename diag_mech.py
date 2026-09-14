"""How are slots mapped to submeshes?  Look at components of the group nodes,
active state of intact vs wreck slots, and mesh sharing across several tanks."""
import collections
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())


def comps(go):
    d = go.read()
    out = []
    for c in d.m_Component:
        r = E.try_deref(c.component if hasattr(c, "component") else c)
        if r is None:
            continue
        tn = r.type.name
        if tn == "MonoBehaviour":
            try:
                md = r.read()
                sc = E.try_deref(md.m_Script)
                tn += "(" + (sc.read().m_Name if sc else "?") + ")"
            except Exception:
                tn += "(?)"
        out.append(tn)
    return out


tank = "Leopard2A8"
start = g.go2tr[roots[tank]]
stack = [(start, 0)]
seen = set()
defs = {}
while stack:
    tp, d = stack.pop()
    if tp in seen:
        continue
    seen.add(tp)
    go = g.tr_go.get(tp)
    if go is not None:
        defs[g.go_name.get(go)] = go
        for c in reversed(g.tr_kids.get(tp, ())):
            stack.append((c, d + 1))

print("== components of group nodes ==")
for n in ["HullGroup_Default", "HullGroup_Destructed", "Track_L_LOD0", "Track_L_LOD1",
          "Hull_NERA_Screen_Side_L_01_Default", "Hull_NERA_Screen_Side_L_01_LOD0",
          "TurretGroup_Default", "GunGroup"]:
    go = defs.get(n)
    print(f"   {n:36s} {comps(go) if go else 'NOT FOUND'}")

print()
print("== active state: intact vs wreck slots ==")
cnt = collections.Counter()
for name, go in defs.items():
    if not (name.endswith("_LOD0") and (go in g.mf or go in g.mr)):
        continue
    try:
        act = go.read().m_IsActive
    except Exception:
        act = None
    grp = "wreck" if "_Destructed" in name else "intact"
    cnt[(grp, act)] += 1
print("  ", dict(cnt))

# renderer enabled flag
cnt2 = collections.Counter()
for sf in g.sfs:
    for o in sf.objects.values():
        if o.type.name != "MeshRenderer":
            continue
        d = o.read()
        go = E.try_deref(d.m_GameObject)
        if go is None:
            continue
        nm = g.go_name.get(go)
        if nm not in defs:
            continue
        cnt2[("wreck" if "_Destructed" in nm else "intact", getattr(d, "m_Enabled", None))] += 1
print("   meshrenderer enabled:", dict(cnt2))

print()
print("== sharing between Hull and Hull_Destructed across tanks ==")
share = same = 0
for t in sorted(roots)[:25]:
    st = g.go2tr[roots[t]]
    stk = [(st, 0)]
    sn = set()
    names = {}
    while stk:
        tp, dd = stk.pop()
        if tp in sn:
            continue
        sn.add(tp)
        go = g.tr_go.get(tp)
        if go is not None:
            nm = g.go_name.get(go, "")
            if nm in ("Hull_LOD0", "Hull_Destructed_LOD0"):
                names[nm] = go
            for c in reversed(g.tr_kids.get(tp, ())):
                stk.append((c, dd + 1))
    a, b = names.get("Hull_LOD0"), names.get("Hull_Destructed_LOD0")
    if a and b and a in g.mf and b in g.mf:
        shared = g.mf[a].path_id == g.mf[b].path_id and \
            g.mf[a].assets_file.name == g.mf[b].assets_file.name
        share += 1
        same += int(shared)
        print(f"   {t:22s} same_mesh={shared} "
              f"intact={g.mf[a].path_id} wreck={g.mf[b].path_id}")
print(f"   -> {same}/{share} tanks share the hull mesh between intact and wreck")
