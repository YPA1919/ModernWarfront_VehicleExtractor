"""Survey two issues across every tank:
   1. materials whose albedo texture has non-default tiling/offset (UV bake needed)
   2. camo-net parts that end up outside the vehicle envelope
"""
import collections
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())

tiling = collections.Counter()
tiling_tanks = collections.defaultdict(set)
camo_bad = []
camo_ok = 0
mat_cache = {}

names = sorted(roots)
for i, tank in enumerate(names, 1):
    order = E.ordered_gameobjects(g, roots[tank])
    intact, wreck = E.build_plan(g, order, False)
    if not intact:
        continue

    # collect parts, split camo vs the rest
    prepared = []
    camo_parts = []
    for it in intact:
        go, mesh_reader, m, sub_idx, mats = it
        h = g.handler(mesh_reader)
        if h is None:
            continue
        tris = h.get_triangles()
        if sub_idx:
            flat = [t for k in sub_idx if k < len(tris) for t in tris[k]]
        else:
            flat = [t for group in tris for t in group]
        idx = sorted({j for t in flat for j in t})
        if not idx:
            continue
        V = h.m_Vertices
        pts = [E.xform_point(m, V[j]) for j in idx]
        mn = np.array([min(p[k] for p in pts) for k in range(3)])
        mx = np.array([max(p[k] for p in pts) for k in range(3)])
        rec = (g.go_name.get(go, ""), mn, mx, mats)
        if "camo" in rec[0].lower() or "cloth" in rec[0].lower():
            camo_parts.append(rec)
        else:
            prepared.append(rec)

    if prepared and camo_parts:
        lo = np.min([p[1] for p in prepared], axis=0)
        hi = np.max([p[2] for p in prepared], axis=0)
        size = float(np.linalg.norm(hi - lo))
        for name, mn, mx, mats in camo_parts:
            c = (mn + mx) / 2
            d = float(np.linalg.norm(c - (lo + hi) / 2))
            if d > 0.75 * size:
                camo_bad.append((tank, name, round(d, 2), round(size, 2)))
            else:
                camo_ok += 1

    for it in intact + wreck:
        for r in it[4]:
            if r in mat_cache:
                continue
            mat = g.material(r)
            if mat is None:
                mat_cache[r] = None
                continue
            props = getattr(mat, "m_SavedProperties", None)
            entry = {}
            for k, v in (getattr(props, "m_TexEnvs", None) or []):
                sc = getattr(v, "m_Scale", None)
                of = getattr(v, "m_Offset", None)
                if sc is not None:
                    entry[str(k)] = (round(sc.x, 4), round(sc.y, 4),
                                     round(of.x, 4), round(of.y, 4))
            mat_cache[r] = (getattr(mat, "m_Name", None), entry)
    if i % 40 == 0:
        print(f"  ...{i}/{len(names)}", flush=True)

for reader, val in mat_cache.items():
    if not val:
        continue
    name, entry = val
    for slot in ("_MainTex",):
        if slot in entry:
            t = entry[slot]
            tiling[t] += 1
            if t != (1.0, 1.0, 0.0, 0.0):
                tiling_tanks[t].add(name)

print()
print("total materials:", sum(1 for v in mat_cache.values() if v))
print("albedo tiling/offset distribution (scale.x, scale.y, off.x, off.y):")
for k, v in tiling.most_common(12):
    print(f"   {v:5d}  {k}")
nondefault = sum(v for k, v in tiling.items() if k != (1.0, 1.0, 0.0, 0.0))
print("materials with non-default albedo tiling/offset:", nondefault)

print()
print(f"camo nets placed sensibly: {camo_ok};  outside the vehicle: {len(camo_bad)}")
for b in camo_bad[:25]:
    print("   ", b)
