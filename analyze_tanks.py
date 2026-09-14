import collections
import re
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
from aacatalog import Catalog

cat = Catalog()

# key index -> key string
# entry -> bundle file derived from dependencyKey (key ends with .bundle)
def bundle_of(entry):
    dk = entry["dependencyKey"]
    if 0 <= dk < len(cat.keys):
        k = cat.keys[dk]
        if isinstance(k, str) and k.endswith(".bundle"):
            return k.rsplit("_", 1)[-1]
    return None


rows = []
for key_off, eis in cat.buckets:
    ki = cat._by_offset.get(key_off)
    if ki is None:
        continue
    key = cat.keys[ki]
    if not isinstance(key, str):
        continue
    for ei in eis:
        e = cat.entries[ei]
        rows.append((key, e, bundle_of(e)))

print("total locations:", len(rows))

tank_rows = [r for r in rows if "/Tanks/" in r[0] or "/tanks/" in r[0]]
print("tank-ish locations:", len(tank_rows))

# path shapes
shapes = collections.Counter()
for key, e, b in tank_rows:
    shapes[re.sub(r"/[^/]+$", "/*", key)] += 1
for s, n in shapes.most_common(20):
    print(f"  {n:5d}  {s}")

# resource classes
cls = collections.Counter()
for key, e, b in tank_rows:
    rt = cat.resource_types[e["resourceTypeIndex"]]
    cls[rt.get("m_ClassName") if isinstance(rt, dict) else str(rt)] += 1
print("classes:", cls.most_common())

print()
print("distinct tank dirs (Assets/Content/Mesh/Tanks/<country>/<tank>/...):")
tanks = collections.defaultdict(set)
for key, e, b in tank_rows:
    m = re.match(r"Assets/Content/Mesh/Tanks/([^/]+)/([^/]+)/", key)
    if m:
        tanks[m.group(1)].add(m.group(2))
for country in sorted(tanks):
    print(f"  {country:16s} {len(tanks[country]):3d}  {sorted(tanks[country])[:12]}")
print("total tanks:", sum(len(v) for v in tanks.values()))

# bundles involved
tb = {b for _, _, b in tank_rows if b}
print("bundles containing tank assets:", len(tb))
