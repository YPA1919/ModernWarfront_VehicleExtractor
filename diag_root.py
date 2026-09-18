# -*- coding: utf-8 -*-
"""Test the hypothesis: parked spares are prefab-root GameObjects (no parent),
while real parts hang under group nodes."""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E

g = E.GameData()


def depth(g, go):
    tp = g.go2tr.get(go)
    d = 0
    while tp is not None and d < 200:
        f = E.try_deref(g.tr[tp].m_Father)
        if f is None:
            return d
        tp = g.go2tr.get(f)
        if tp is None:
            return d
        d += 1
    return d


for kind in ("tanks", "air"):
    E.set_kind(kind)
    roots = g.root_candidates(E.tank_name_set())
    depths = collections.Counter()
    root_parts = collections.Counter()
    for t in sorted(roots):
        g.clear_caches()
        order = E.ordered_gameobjects(g, roots[t])
        for go, w, c, _blur in order:
            if go not in g.mf and go not in g.smr:
                continue
            d = depth(g, go)
            depths[d] += 1
            if d == 0:
                root_parts[g.go_name.get(go, "")] += 1
    print(f"=== {kind}: 可渲染部件的层级深度分布 ===")
    for d, n in sorted(depths.items())[:8]:
        print(f"    depth {d}: {n}")
    print(f"    根级部件名（前 20）:")
    for k, v in root_parts.most_common(20):
        print(f"       {v:4d} {k}")
    print()
