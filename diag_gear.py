# -*- coding: utf-8 -*-
"""Dump the landing-gear parts of an aircraft: parent chain, local TRS of the
part and of its parents, plus the resulting world AABB of the mesh."""
import os
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E

g = E.GameData()
E.set_kind("air")
roots = g.root_candidates(E.tank_name_set())
tank = sys.argv[1] if len(sys.argv) > 1 else "F16_Fighter"
g.clear_caches()
root = roots[tank]

# transform tRNS of the whole chain for the hull, for reference
print("=" * 100)
print(tank)


def chain_trs(go):
    out = []
    tp = g.go2tr.get(go)
    while tp is not None and len(out) < 8:
        d = g.tr.get(tp)
        if d is None:
            break
        nm = g.go_name.get(g.tr_go.get(tp), "?")
        lp, lr, ls = d.m_LocalPosition, d.m_LocalRotation, d.m_LocalScale
        out.append((nm, (lp.x, lp.y, lp.z), (lr.x, lr.y, lr.z, lr.w), (ls.x, ls.y, ls.z)))
        f = E.try_deref(d.m_Father)
        tp = g.go2tr.get(f) if f is not None else None
    return out


def aabb(go):
    if go in g.mf:
        mr = g.mf[go]
    elif go in g.smr:
        mr = g.smr[go][0]
    else:
        return None, 0
    h = g.handler(mr)
    if h is None:
        return None, 0
    m = g.world_matrix(g.go2tr.get(go))
    pts = [E.xform_point(m, v) for v in h.m_Vertices]
    mn = [min(p[i] for p in pts) for i in range(3)]
    mx = [max(p[i] for p in pts) for i in range(3)]
    return (mn, mx), len(h.m_Vertices)


PAT = __import__("re").compile(r"(wheel|chassis|gear|strut|landing|tyre|tire)",
                               __import__("re").I)

rows = []
for go, wreck, camo, blur in E.ordered_gameobjects(g, root):
    if go not in g.mf and go not in g.smr:
        continue
    n = g.go_name.get(go, "")
    if not PAT.search(n):
        continue
    box, nv = aabb(go)
    if box is None:
        continue
    ch = chain_trs(go)
    rows.append((n, box, nv, ch))

rows.sort(key=lambda r: r[1][0][1])
for n, (mn, mx), nv, ch in rows:
    print(f"\n{n}   v={nv}")
    print(f"   世界 AABB  y[{mn[1]:6.2f},{mx[1]:6.2f}]  z[{mn[2]:6.2f},{mx[2]:6.2f}]"
          f"  x[{mn[0]:6.2f},{mx[0]:6.2f}]")
    for i, (nm, lp, lr, ls) in enumerate(ch):
        print(f"   {'自己' if i == 0 else '父%-2d' % i} {nm[:38]:40s} "
              f"pos({lp[0]:6.2f},{lp[1]:6.2f},{lp[2]:6.2f}) "
              f"rot({lr[0]:5.2f},{lr[1]:5.2f},{lr[2]:5.2f},{lr[3]:5.2f}) "
              f"scale({ls[0]:5.2f},{ls[1]:5.2f},{ls[2]:5.2f})")
