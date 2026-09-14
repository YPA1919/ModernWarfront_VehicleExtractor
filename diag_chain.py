# -*- coding: utf-8 -*-
"""Print the real parent chain (via m_Father) of every renderable of an aircraft,
plus its local/world AABB, to see how the game hangs the parts together."""
import os
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E

g = E.GameData()
E.set_kind("air")

TARGETS = sys.argv[1:] or ["Mi28NM_Helicopter"]
roots = g.root_candidates(E.tank_name_set())

for tank in TARGETS:
    if tank not in roots:
        print("missing", tank)
        continue
    g.clear_caches()
    root = roots[tank]
    print("=" * 78)
    print(tank, "root go:", root, "transform:", g.go2tr.get(root))
    # full name chain of the root itself
    tp = g.go2tr.get(root)
    chain = []
    while tp is not None and len(chain) < 40:
        go = g.tr_go.get(tp)
        chain.append(g.go_name.get(go, "?"))
        d = g.tr.get(tp)
        f = E.try_deref(d.m_Father) if d else None
        tp = g.go2tr.get(f) if f is not None else None
    print("root 的父链:", " <- ".join(chain) if chain else "(无)")

    order = E.ordered_gameobjects(g, root)
    print("%-40s %-5s %-4s %s" % ("部件", "src", "深度", "父链"))
    for go, wreck, camo, _blur in order[:200]:
        src = "MF" if go in g.mf else ("SMR" if go in g.smr else None)
        if src is None:
            continue
        tp = g.go2tr.get(go)
        names, depth = [], 0
        while tp is not None and depth < 40:
            d = g.tr.get(tp)
            if d is None:
                break
            f = E.try_deref(d.m_Father)
            if f is None:
                break
            fgo = g.tr_go.get(f)
            names.append(g.go_name.get(fgo, "?"))
            tp = g.go2tr.get(f)
            depth += 1
        print("%-40s %-5s %-4d %s" % (g.go_name.get(go, "")[:38], src, depth,
                                      " <- ".join(names[:4])))
    print()
