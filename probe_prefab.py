"""Work out how to pick the canonical tank prefab GameObject, and test texture
export from a tank material."""
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
        if n in tank_names:
            names[o.path_id] = (n, getattr(o.assets_file, "name", "?"))

by_file = collections.Counter(f for _, f in names.values())
print("tank-named GameObjects by file:", by_file.most_common())
dupes = collections.Counter(n for n, _ in names.values())
print("names appearing more than once:", sum(1 for v in dupes.values() if v > 1))

# transforms
tr = {}
for o in env.objects:
    if o.type.name == "Transform":
        try:
            tr[o.path_id] = o.read()
        except Exception:
            pass
print("transforms:", len(tr))
go2tr = {}
for tp, d in tr.items():
    if d.m_GameObject:
        go2tr[d.m_GameObject.path_id] = tp

# for each tank-named go, get root ancestor and child names
def root_of(go):
    tp = go2tr.get(go)
    if tp is None:
        return None, 0
    depth = 0
    while True:
        d = tr[tp]
        f = d.m_Father
        if not f or f.path_id == 0:
            return tp, depth
        nxt = f.path_id
        if nxt not in tr or depth > 200:
            return tp, depth
        tp = nxt
        depth += 1

kids = {}
for tp, d in tr.items():
    gid = d.m_GameObject.path_id if d.m_GameObject else None
    kids.setdefault(gid, []).append(d)

sample = [go for go, (n, f) in names.items() if n == "Leopard2A8"]
print("Leopard2A8 candidates:", sample)
for go in sample:
    n, f = names[go]
    r, depth = root_of(go)
    rn = None
    if r is not None:
        rg = tr[r].m_GameObject
        rn = None
        if rg:
            try:
                rn = objs[rg.path_id].read().m_Name
            except Exception:
                pass
    ch = [objs[c.m_GameObject.path_id].read().m_Name for c in kids.get(go, []) if c.m_GameObject]
    print(f"  go={go} file={f} depth={depth} root={rn!r} children={ch[:12]}")

# texture check on a tank material
print()
for o in env.objects:
    if o.type.name == "Material":
        try:
            d = o.read()
        except Exception:
            continue
        if d.m_Name != "Leopard2A8":
            continue
        print("material", d.m_Name, "file", o.assets_file.name)
        props = d.m_SavedProperties
        texenvs = getattr(props, "m_TexEnvs", [])
        print("  texenvs:", len(texenvs))
        for k, v in texenvs:
            p = v.m_Texture
            nm = None
            fmt = None
            if p and p.path_id:
                try:
                    t = p.deref().read()
                    nm, fmt = t.m_Name, t.m_TextureFormat
                    w, h = t.m_Width, t.m_Height
                except Exception as e:
                    nm, fmt, w, h = f"<unresolved {type(e).__name__}>", None, 0, 0
            else:
                w = h = 0
            print(f"    {k}: {nm} fmt={fmt} {w}x{h}")
        floats = getattr(props, "m_Floats", [])
        print("  float props:", [k for k, _ in floats][:14])
        break
