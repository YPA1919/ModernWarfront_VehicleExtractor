"""Validate the slot<->submesh mapping across every tank, and check how
SkinnedMeshRenderer parts (tracks) are positioned."""
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


def ordered_gos(root):
    start = g.go2tr[root]
    stack = [start]
    seen = set()
    out = []
    while stack:
        tp = stack.pop()
        if tp in seen:
            continue
        seen.add(tp)
        go = g.tr_go.get(tp)
        if go is not None:
            out.append(go)
        for c in reversed(g.tr_kids.get(tp, ())):
            stack.append(c)
    return out


mismatch = collections.Counter()
ok_meshes = 0
smr_info = []
tanks_with_smr = 0
for tank in sorted(roots):
    order = ordered_gos(roots[tank])
    by_mesh = collections.defaultdict(list)
    has_smr = False
    for go in order:
        if go in g.mf:
            by_mesh[g.mf[go]].append(go)
        if go in smr:
            has_smr = True
            d = smr[go]
            mr = E.try_deref(d.m_Mesh)
            if mr is not None and len(smr_info) < 12:
                m = g.mesh(mr)
                h = MeshHandler(m)
                h.process()
                V = np.array([[p[0], p[1], p[2]] for p in h.m_Vertices])
                wm = g.world_matrix(g.go2tr.get(go))
                smr_info.append((tank, g.go_name.get(go), mr.path_id,
                                 np.round(V.min(0), 2), np.round(V.max(0), 2),
                                 np.round([wm[12], wm[13], wm[14]], 2),
                                 len(d.m_Bones or [])))
    tanks_with_smr += int(has_smr)
    for mr, gos in by_mesh.items():
        mesh = g.mesh(mr)
        subs = len(getattr(mesh, "m_SubMeshes", ()) or ())
        if subs < 2:
            continue
        if subs == len(gos):
            ok_meshes += 1
        else:
            mismatch[(subs, len(gos))] += 1

print(f"group meshes with submeshes == slots: {ok_meshes}")
print(f"mismatches: {sum(mismatch.values())}  detail (subs,slots)->count: {mismatch.most_common(10)}")
print(f"tanks with SkinnedMeshRenderer parts: {tanks_with_smr}/{len(roots)}")
print()
print("SkinnedMeshRenderer samples (mesh AABB vs renderer world pos):")
for t, n, mid, mn, mx, wp, bones in smr_info:
    print(f"   {t:16s} {n[:22]:24s} mesh={mid:6d} aabb={mn}-{mx} worldpos={wp} bones={bones}")
