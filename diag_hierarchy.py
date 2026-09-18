import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import export_tanks as E

g = E.GameData()
roots = g.root_candidates(E.tank_name_set())

for tank in ["Leopard2A8", "KW2Jupiter120"]:
    if tank not in roots:
        continue
    root = roots[tank]
    print("=" * 70)
    print(tank)
    start = g.go2tr[root]
    stack = [(start, 0)]
    seen = set()
    n = 0
    while stack and n < 120:
        tp, d = stack.pop(0)
        if tp in seen:
            continue
        seen.add(tp)
        go = g.tr_go.get(tp)
        name = g.go_name.get(go, "?")
        has_mf = "M" if g.mf.get(go) else " "
        has_mr = "R" if g.mr.get(go) else " "
        print("   " * d + f"[{has_mf}{has_mr}] {name}")
        n += 1
        for c in g.tr_kids.get(tp, ()):
            stack.append((c, d + 1))

# sub-system prefabs available
subs = sorted(n for n in set(g.go_name.values()) if n and "_" in n and
              any(k in n for k in ("120mm", "125mm", "105mm", "L55", "L44", "M256")))
print("\npossible subsystem names (sample):", subs[:15])
