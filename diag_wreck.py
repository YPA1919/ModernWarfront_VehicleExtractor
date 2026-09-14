"""Full renderable inventory of one tank prefab, split by Default / Destructed,
including SkinnedMeshRenderers, with mesh identity and materials."""
import collections
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E

g = E.GameData()

smr = {}
for sf in g.sfs:
    for o in sf.objects.values():
        if o.type.name == "SkinnedMeshRenderer":
            try:
                d = o.read()
                go = E.try_deref(d.m_GameObject)
            except Exception:
                continue
            if go is not None:
                smr[go] = d

roots = g.root_candidates(E.tank_name_set())
tank = sys.argv[1] if len(sys.argv) > 1 else "Leopard2A8"

start = g.go2tr[roots[tank]]
stack = [(start, 0, "")]
seen = set()
rows = []
while stack:
    tp, depth, path = stack.pop()
    if tp in seen:
        continue
    seen.add(tp)
    go = g.tr_go.get(tp)
    if go is not None:
        name = g.go_name.get(go, "?")
        here = f"{path}/{name}" if path else name
        mesh_ref = None
        kind = None
        if go in g.mf:
            mesh_ref = g.mf[go]
            kind = "MF"
        elif go in smr:
            mesh_ref = E.try_deref(smr[go].m_Mesh)
            kind = "SMR"
        if mesh_ref is not None:
            mesh = g.mesh(mesh_ref)
            mats = [getattr(g.material(x), "m_Name", None) for x in g.mr.get(go, [])]
            rows.append((here, kind, mesh_ref, len(getattr(mesh, "m_SubMeshes", ()) or ()), mats))
        for c in reversed(g.tr_kids.get(tp, ())):
            stack.append((c, depth + 1, here))

groups = collections.Counter()
for here, kind, mref, subs, mats in rows:
    grp = "Destructed" if "_Destructed" in here else "Default"
    groups[grp] += 1
print("renderables:", len(rows), dict(groups))
print()
mesh_users = collections.defaultdict(set)
for here, kind, mref, subs, mats in rows:
    grp = "Destructed" if "_Destructed" in here else "Default"
    mesh_users[(mref.assets_file.name, mref.path_id)].add(grp)
shared = [k for k, v in mesh_users.items() if len(v) > 1]
print("meshes used by BOTH default and destructed groups:", len(shared), shared[:10])
print()
for here, kind, mref, subs, mats in rows:
    grp = "W" if "_Destructed" in here else " "
    leaf = here.split("/")[-1]
    if kind == "SMR" or "Track" in leaf or leaf in ("Hull_LOD0", "Hull_Destructed_LOD0"):
        print(f"  [{grp}] {leaf:34s} {kind} mesh={mref.path_id:6d} subs={subs:3d} mats={mats[:2]}")
