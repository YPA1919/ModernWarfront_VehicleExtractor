"""Decide the selection rule for the canonical tank prefab root."""
import collections
import json
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import UnityPy
from UnityPy.helpers import TypeTreeHelper as _TTH

_TTH.read_typetree_boost = None

env = UnityPy.load(r"D:\DeepSeek Harness\mw\bundles\data.unity3d")
tank_names = {r["path"].split("/")[-1] for r in
              json.load(open(r"D:\DeepSeek Harness\mw\catalog_index.json", encoding="utf-8"))
              if r["path"].startswith("Tanks/")}

objs = {o.path_id: o for o in env.objects}
names = {}
for o in env.objects:
    if o.type.name == "GameObject":
        try:
            n = o.read().m_Name
        except Exception:
            continue
        names[o.path_id] = n
tr = {}
for o in env.objects:
    if o.type.name == "Transform":
        try:
            tr[o.path_id] = o.read()
        except Exception:
            pass
go2tr, kids = {}, collections.defaultdict(list)
for tp, d in tr.items():
    gid = d.m_GameObject.path_id if d.m_GameObject else None
    if gid:
        go2tr[gid] = tp
    kids[gid].append(tp)


def depth_of(go):
    tp = go2tr.get(go)
    d = 0
    while tp is not None and d < 500:
        f = tr[tp].m_Father
        if not f or not f.path_id or f.path_id not in tr:
            return d
        tp = f.path_id
        d += 1
    return d


def subtree(go, maxn=4000):
    out, stack = [], [go]
    while stack and len(out) < maxn:
        g = stack.pop()
        out.append(g)
        for t in kids.get(g, ()):
            cg = t.m_GameObject.path_id if t.m_GameObject else None
            if cg:
                stack.append(cg)
    return out


cand = collections.defaultdict(list)
for go, n in names.items():
    if n in tank_names:
        cand[n].append(go)

stats = collections.Counter()
problems = []
for n, gos in cand.items():
    ds = [depth_of(g) for g in gos]
    roots = [g for g, d in zip(gos, ds) if d == 0]
    stats[f"candidates={len(gos)}"] += 1
    if len(roots) == 1:
        stats["unique_root"] += 1
    elif len(roots) == 0:
        stats["no_root"] += 1
        problems.append((n, gos, ds))
    else:
        stats["multi_root"] += 1
        problems.append((n, gos, ds))

print("tanks:", len(cand))
for k, v in sorted(stats.items()):
    print(f"   {v:5d} {k}")
print("\nproblem samples:")
for n, gos, ds in problems[:12]:
    info = []
    for g, d in zip(gos, ds):
        sub = subtree(g)
        meshes = sum(1 for x in sub if any(
            c.component.deref() is not None and c.component.deref().type.name == "MeshFilter"
            for c in []) )
        child_names = [names.get(k.m_GameObject.path_id) for k in kids.get(g, ()) if k.m_GameObject]
        info.append((g, d, len(sub), child_names[:6]))
    print(f"  {n}:")
    for i in info:
        print("     ", i)

# verify subtree has hull/turret groups for the chosen root
print("\nchild-name signature check (unique roots):")
sig = collections.Counter()
for n, gos in cand.items():
    roots = [g for g in gos if depth_of(g) == 0]
    if len(roots) != 1:
        continue
    cn = tuple(sorted(names.get(k.m_GameObject.path_id, "") for k in kids.get(roots[0], ()) if k.m_GameObject))
    sig[cn] += 1
for k, v in sig.most_common(6):
    print(f"   {v:5d} {k}")
