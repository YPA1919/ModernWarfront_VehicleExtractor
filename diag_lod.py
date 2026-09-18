# -*- coding: utf-8 -*-
"""Internal consistency check: the same logical part at LOD0/LOD1/LOD2 must land
at the same world position.  Disagreement means one of them is placed wrong."""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E

g = E.GameData()
E.set_kind("air")
roots = g.root_candidates(E.tank_name_set())
tank = sys.argv[1] if len(sys.argv) > 1 else "F16_Fighter"
g.clear_caches()
root = roots[tank]

info = {}
for go, wreck, camo, blur in E.ordered_gameobjects(g, root):
    if go not in g.mf and go not in g.smr:
        continue
    n = g.go_name.get(go, "")
    if "Collider" in n:
        continue
    mr = g.mf.get(go) or g.smr.get(go)[0]
    h = g.handler(mr)
    if h is None:
        continue
    m = g.world_matrix(g.go2tr.get(go))
    pts = [E.xform_point(m, v) for v in h.m_Vertices]
    mn = [min(p[i] for p in pts) for i in range(3)]
    mx = [max(p[i] for p in pts) for i in range(3)]
    key = E.LOD_RE.sub("", n)          # 去掉 LODn
    key = key.rstrip("_")
    info.setdefault(key, []).append((n, mn, mx))

print("=== %s：同名部件跨 LOD 的世界包围盒对比 ===" % tank)
bad = 0
for key in sorted(info):
    variants = info[key]
    if len(variants) < 2:
        continue
    base_n, base_mn, base_mx = variants[0]
    for n, mn, mx in variants[1:]:
        d = max(abs(mn[i] - base_mn[i]) for i in range(3))
        d = max(d, max(abs(mx[i] - base_mx[i]) for i in range(3)))
        flag = "  <<< 不一致" if d > 0.03 else ""
        if flag:
            bad += 1
        print("  %-34s vs %-34s 偏差 %.3f%s" % (base_n[:34], n[:34], d, flag))
print("不一致的对数:", bad)

# 顺便列出所有"位置可疑"的部件：中心离机体中轴很远的小件
hull = None
for go, wreck, camo, blur in E.ordered_gameobjects(g, root):
    n = g.go_name.get(go, "")
    if re.search(r"(^|_)hull", n, re.I) and go in g.mf:
        mr = g.mf[go]
        h = g.handler(mr)
        m = g.world_matrix(g.go2tr.get(go))
        pts = [E.xform_point(m, v) for v in h.m_Vertices]
        hull = ([min(p[i] for p in pts) for i in range(3)],
                [max(p[i] for p in pts) for i in range(3)])
        break
print("\n机体 AABB:", hull)
