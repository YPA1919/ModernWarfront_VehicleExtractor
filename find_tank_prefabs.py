"""Locate tank prefab roots inside data.unity3d and inspect their hierarchy."""
import collections
import os
import json
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import UnityPy
from UnityPy.helpers import TypeTreeHelper as _TTH

_TTH.read_typetree_boost = None

DATA = os.path.join(HERE, "bundles/data.unity3d")

tank_names = set()
for r in json.load(open(os.path.join(HERE, "catalog_index.json"), encoding="utf-8")):
    p = r["path"]
    if p.startswith("Tanks/"):
        tank_names.add(p.split("/")[-1])
print("tank names:", len(tank_names))

env = UnityPy.load(DATA)
t0 = time.time()
gos = [o for o in env.objects if o.type.name == "GameObject"]
names = {}
for o in gos:
    try:
        names[o.path_id] = o.read().m_Name
    except Exception:
        pass
print(f"read {len(names)} GameObject names in {time.time()-t0:.1f}s")

hits = {pid: n for pid, n in names.items() if n in tank_names}
print("tank-named GameObjects:", len(hits))
missing = tank_names - set(hits.values())
print("tank names with no GameObject:", len(missing), sorted(missing)[:10])

# hierarchy: transforms
t0 = time.time()
trs = [o for o in env.objects if o.type.name == "Transform"]
tr = {}
for o in trs:
    try:
        d = o.read()
        tr[o.path_id] = d
    except Exception:
        pass
print(f"read {len(tr)} transforms in {time.time()-t0:.1f}s")

go2tr = {}
roots = []
for pid, d in tr.items():
    g = d.m_GameObject
    if g:
        try:
            go2tr[g.path_id] = pid
        except Exception:
            pass

sample = "KW2Jupiter120"
pid = next((p for p, n in hits.items() if n == sample), None)
print("sample GameObject path_id:", pid)

if pid is not None:
    # find its transform
    tpid = None
    for tp, d in tr.items():
        try:
            if d.m_GameObject.path_id == pid:
                tpid = tp
                break
        except Exception:
            continue
    print("transform:", tpid)
    root = tr[tpid]
    print("father:", root.m_Father.path_id if root.m_Father else None)
    print("children:", len(root.m_Children))

    # walk
    def walk(tpid, depth=0, limit=[0]):
        if limit[0] > 60:
            return
        limit[0] += 1
        d = tr[tpid]
        gid = d.m_GameObject.path_id
        print("  " * depth + f"- {names.get(gid, '?')} (go={gid})")
        for c in d.m_Children:
            walk(c.path_id, depth + 1, limit)

    walk(tpid)
