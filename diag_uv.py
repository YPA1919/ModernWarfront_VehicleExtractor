"""Diagnose (a) UV problems on a given tank, (b) camo-net placement."""
import collections
import os
import sys

import numpy as np

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E
E.set_kind(os.environ.get('MW_KIND', 'tanks'))

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())

TANKS = sys.argv[1:] or ["Type86"]

for tank in TANKS:
    print("=" * 90)
    print(tank)
    order = E.ordered_gameobjects(g, roots[tank])
    intact, wreck = E.build_plan(g, order, False)
    print(f"  intact items {len(intact)}  wreck items {len(wreck)}")

    # --- UV analysis of the intact pieces
    chan = collections.Counter()
    weird = []
    for it in intact:
        go, mr, m, subs, mats = it
        mesh = g.mesh(mr)
        h = g.handler(mr)
        if h is None:
            continue
        uv0 = getattr(h, "m_UV0", None)
        uv1 = getattr(h, "m_UV1", None)
        chan[(bool(uv0), bool(uv1))] += 1
        for si in (subs or [None]):
            tris = h.get_triangles()
            t = tris[si] if si is not None and si < len(tris) else [x for gg in tris for x in gg]
            if not t:
                continue
            idx = sorted({j for tri in t for j in tri})
            if uv0:
                U = np.array([uv0[j] for j in idx])
                mn, mx = U.min(0), U.max(0)
                if mn.min() < -0.05 or mx.max() > 1.6:
                    weird.append((g.go_name.get(go), si, len(t),
                                  (round(float(mn[0]), 2), round(float(mn[1]), 2)),
                                  (round(float(mx[0]), 2), round(float(mx[1]), 2))))
    print("  (has UV0, has UV1) counts:", dict(chan))
    print("  parts with out-of-range UV0:")
    for w in weird[:14]:
        print("     ", w)

    # --- materials and their texture tiling/offset
    seen = set()
    print("  materials:")
    for it in intact + wreck:
        go, mr, m, subs, mats = it
        for r in mats:
            mat = g.material(r)
            if mat is None:
                continue
            name = getattr(mat, "m_Name", None)
            if name in seen:
                continue
            seen.add(name)
            props = getattr(mat, "m_SavedProperties", None)
            entries = []
            for k, v in (getattr(props, "m_TexEnvs", None) or []):
                sc = getattr(v, "m_Scale", None)
                of = getattr(v, "m_Offset", None)
                tex = E.try_deref(getattr(v, "m_Texture", None))
                tname = None
                if tex is not None:
                    tname = getattr(g.texture(tex), "m_Name", None)
                entries.append((str(k), tname,
                                None if sc is None else (round(sc.x, 3), round(sc.y, 3)),
                                None if of is None else (round(of.x, 3), round(of.y, 3))))
            print(f"     {name}:")
            for e in entries[:8]:
                print(f"        {e[0]:22s} tex={e[1]} scale={e[2]} offset={e[3]}")
