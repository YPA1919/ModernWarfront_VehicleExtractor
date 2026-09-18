# -*- coding: utf-8 -*-
"""Measure the AABB gap of specific parts against the rest of the model, to
calibrate a parked-spare rule that keeps rotors/guns but drops parked spares."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E

g = E.GameData()

CASES = [
    ("tanks", "Cheonma2", ["Gun_LOD0", "Hull_LOD0", "Barrel_LOD0"]),
    ("tanks", "K21KNIFV", ["Hull_Capsule_L_LOD0", "Hull_Capsule_R_LOD0"]),
    ("tanks", "FH77BWL52Archer", ["Browning_m2_v2_gun_LOD0"]),
    ("tanks", "M3A3", ["BGM-71-TOW_Hull_LOD0", "BGM-71-TOW_Turret_LOD0"]),
    ("tanks", "Type89MLRS", ["Camo_net_Hull_LOD0", "Camo_net_ChargingPlatform_LOD0"]),
    ("air", "A10A_Fighter", ["A10_Gun_LOD0"]),
    ("air", "KA50_Helicopter", ["HelicopterBladeSmoothed (1)", "HelicopterBladeSmoothed (2)"]),
    ("air", "AH64E_Helicopter", ["HelicopterBladeSmoothed (1)"]),
    ("air", "F16_Fighter", ["F16_Chassis_Wheel_F_01_LOD0", "F16_Chassis_L_01_LOD0"]),
    ("air", "EF2000_Fighter", ["EF2000_Chassis_Front_04_LOD0", "EF2000_Hull_LOD0"]),
]


def aabb_gap(p, lo, hi):
    d = 0.0
    for k in range(3):
        if p["mx"][k] < lo[k]:
            d += (lo[k] - p["mx"][k]) ** 2
        elif p["mn"][k] > hi[k]:
            d += (p["mn"][k] - hi[k]) ** 2
    return d ** 0.5


for kind, tank, wanted in CASES:
    E.set_kind(kind)
    roots = g.root_candidates(E.tank_name_set())
    if tank not in roots:
        print("missing", tank)
        continue
    g.clear_caches()
    order = E.ordered_gameobjects(g, roots[tank])
    intact, _w = E.build_plan(g, order, False)
    prep = []
    for it in intact:
        go, mr, m, sub_idx, _mats = it
        h = g.handler(mr)
        if h is None:
            continue
        tris = h.get_triangles()
        flat = ([t for k in sub_idx if k < len(tris) for t in tris[k]] if sub_idx
                else [t for grp in tris for t in grp])
        if not flat:
            continue
        idx = sorted({j for t in flat for j in t})
        pts = [E.xform_point(m, h.m_Vertices[j]) for j in idx]
        mn = [min(p[i] for p in pts) for i in range(3)]
        mx = [max(p[i] for p in pts) for i in range(3)]
        prep.append({"name": g.go_name.get(go, ""), "mn": mn, "mx": mx,
                     "size": [mx[i] - mn[i] for i in range(3)]})
    print(f"=== {tank} ({kind}), {len(prep)} parts")
    for i, p in enumerate(prep):
        lo = [min(q["mn"][k] for j, q in enumerate(prep) if j != i) for k in range(3)]
        hi = [max(q["mx"][k] for j, q in enumerate(prep) if j != i) for k in range(3)]
        gap = aabb_gap(p, lo, hi)
        diag = sum((hi[k] - lo[k]) ** 2 for k in range(3)) ** 0.5
        ratio = gap / max(diag, 1e-6)
        mark = ""
        if any(w in p["name"] for w in wanted):
            mark = "  <<<"
        if mark or ratio > 0.15:
            print(f"   {p['name'][:34]:36s} gap={gap:6.2f} modelDiag={diag:5.2f} "
                  f"ratio={ratio:5.2f} size=({p['size'][0]:4.2f},{p['size'][1]:4.2f},{p['size'][2]:4.2f}){mark}")
    print()
