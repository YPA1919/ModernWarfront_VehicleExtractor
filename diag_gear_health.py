# -*- coding: utf-8 -*-
"""Health check: for every aircraft, does the landing gear actually attach to the
airframe, and does every part sit inside a sane envelope?"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E

GEAR = re.compile(r"(chassis|wheel|skid|strut|landing|gear)", re.I)
g = E.GameData()
E.set_kind("air")
roots = g.root_candidates(E.tank_name_set())

print("%-30s %6s %8s %9s %9s  %s" % ("载具", "部件", "机体底", "起落架顶", "起落架底", "判定"))
flagged = []
for tank in sorted(roots):
    g.clear_caches()
    order = E.ordered_gameobjects(g, roots[tank])
    intact, _w = E.build_plan(g, order, False)
    items = [p["it"] for p in E.drop_off_model(g, intact)[0]]
    gear_lo = gear_hi = None
    body_lo = body_hi = None
    gx = [1e9, -1e9]
    bx = [1e9, -1e9]
    for it in items:
        go, mr, m, sub, _m = it
        n = g.go_name.get(go, "")
        h = g.handler(mr)
        if h is None:
            continue
        h2 = None
        if go in g.mf:
            h2 = g.handler(g.mf[go])
        elif go in g.smr:
            h2 = g.handler(g.smr[go][0])
        if h2 is None:
            continue
        pts = [E.xform_point(m, v) for v in h2.m_Vertices]
        ylo = min(p[1] for p in pts)
        yhi = max(p[1] for p in pts)
        xlo = min(p[0] for p in pts)
        xhi = max(p[0] for p in pts)
        if GEAR.search(n):
            gear_lo = ylo if gear_lo is None else min(gear_lo, ylo)
            gear_hi = yhi if gear_hi is None else max(gear_hi, yhi)
            gx = [min(gx[0], xlo), max(gx[1], xhi)]
        else:
            body_lo = ylo if body_lo is None else min(body_lo, ylo)
            body_hi = yhi if body_hi is None else max(body_hi, yhi)
            bx = [min(bx[0], xlo), max(bx[1], xhi)]
    if gear_lo is None or body_lo is None:
        print("%-30s %6d  %s" % (tank[:30], len(items), "无起落架部件" if gear_lo is None else "无机体"))
        continue
    # 起落架顶必须高过机体底（否则悬在机腹下方）
    attach = gear_hi >= body_lo
    wide = gx[0] < bx[0] - 1e-6 or gx[1] > bx[1] + 1e-6
    verdict = "ok"
    if not attach:
        verdict = "悬空! 间隙 %.3f" % (body_lo - gear_hi)
    elif wide:
        verdict = "横向超出机体 (%.2f vs %.2f)" % (gx[1], bx[1])
    if verdict != "ok":
        flagged.append((tank, verdict))
    print("%-30s %6d %8.3f %9.3f %9.3f  %s" % (tank[:30], len(items), body_lo,
                                               gear_hi, gear_lo, verdict))
print()
print("有问题的:", len(flagged))
for t, v in flagged:
    print("   %-30s %s" % (t, v))
