"""Replicate drop_off_model step by step and report which rule drops what."""
import os
import sys

import numpy as np

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E
E.set_kind(os.environ.get('MW_KIND', 'tanks'))
from UnityPy.helpers.MeshHelper import MeshHandler

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())


def prepare(items):
    out = []
    for it in items:
        go, mr, m, sub_idx, mats = it
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
        out.append({"it": it, "name": g.go_name.get(go, ""), "mn": mn, "mx": mx,
                    "centre": [(mn[i] + mx[i]) / 2 for i in range(3)],
                    "diag": sum((mx[i] - mn[i]) ** 2 for i in range(3)) ** 0.5})
    return out


for tank, which in [(a.split(":")[0], a.split(":")[1]) for a in sys.argv[1:]]:
    g.clear_caches()
    order = E.ordered_gameobjects(g, roots[tank])
    intact, wreck = E.build_plan(g, order, False)
    items = intact if which == "intact" else wreck
    prepared = prepare(items)
    print("=" * 78)
    print(f"{tank} {which}: {len(prepared)} parts")

    diags = sorted((p["diag"] for p in prepared), reverse=True)
    ref = E.median(diags[:5])
    med = [E.median([p["centre"][i] for p in prepared]) for i in range(3)]
    med_diag = E.median([p["diag"] for p in prepared])
    print(f"   ref(top5 median)={ref:.3f} med_diag={med_diag:.3f} threshold=2.5*ref={2.5*ref:.3f}")

    kept, dropped = [], []
    for p in prepared:
        dist = sum((p["centre"][i] - med[i]) ** 2 for i in range(3)) ** 0.5
        if dist > 2.5 * ref or p["diag"] > 20.0 * med_diag:
            dropped.append((p, f"distance({dist:.2f})"))
        else:
            kept.append(p)

    if len(kept) >= 4:
        big = max(kept, key=lambda p: p["diag"])
        w = max(big["mx"][0] - big["mn"][0], 1e-6)
        l = max(big["mx"][2] - big["mn"][2], 1e-6)
        print(f"   envelope ref = {big['name']} x[{big['mn'][0]:.2f},{big['mx'][0]:.2f}] "
              f"z[{big['mn'][2]:.2f},{big['mx'][2]:.2f}] margin x={0.5*w:.2f} z={1.2*l:.2f}")
        keep2 = []
        for p in kept:
            if (p["mx"][0] < big["mn"][0] - 0.5 * w or p["mn"][0] > big["mx"][0] + 0.5 * w
                    or p["mx"][2] < big["mn"][2] - 1.2 * l or p["mn"][2] > big["mx"][2] + 1.2 * l):
                dropped.append((p, "envelope"))
            else:
                keep2.append(p)
        kept = keep2

    gear = [p for p in kept if E.GEAR_RE.search(p["name"])]
    if gear and kept:
        floor = min(p["mn"][1] for p in gear)
        print(f"   floor={floor:.3f} from {len(gear)} gear parts")
        keep2 = []
        for p in kept:
            if p["mx"][1] < floor - 0.02:
                dropped.append((p, f"below floor (ymax={p['mx'][1]:.3f})"))
            else:
                keep2.append(p)
        kept = keep2

    print(f"   kept {len(kept)}  dropped {len(dropped)}")
    for p, why in dropped:
        print(f"      DROP {p['name'][:36]:38s} {why}")
