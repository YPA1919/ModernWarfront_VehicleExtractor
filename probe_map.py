import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
from aacatalog import Catalog

cat = Catalog()
key_to_idx = {k: i for i, k in enumerate(cat.keys)}

target = "Assets/Content/Mesh/Tanks/USA/HSTVL/Meshes/HSTVL_Colliders.asset"
print("target key present:", target in key_to_idx)
print("key index:", key_to_idx.get(target))

# find entries whose key set contains the target
buckets_for_key = {}
for key_off, eis in cat.buckets:
    ki = cat._by_offset.get(key_off)
    buckets_for_key.setdefault(ki, []).extend(eis)

ei_list = buckets_for_key.get(key_to_idx.get(target), [])
print("entries:", ei_list)
for ei in ei_list:
    e = cat.entries[ei]
    print("  entry", ei, {k: v for k, v in e.items()})
    print("    internalId ->", cat.internal_ids[e["internalId"]])
    pk = e["primaryKey"]
    print("    primaryKey idx", pk, "->", repr(cat.keys[pk])[:120] if 0 <= pk < len(cat.keys) else None)
    rt = cat.resource_types[e["resourceTypeIndex"]]
    print("    resourceType:", str(rt)[:160])
    dk = e["dependencyKey"]
    print("    dependencyKey idx", dk, "->", repr(cat.keys[dk])[:160] if 0 <= dk < len(cat.keys) else None)

# For the bundle found, list the guid_bundle keys that reference it
print()
for ei in ei_list:
    bundle = cat.internal_ids[cat.entries[ei]["internalId"]]
    bname = bundle.rsplit("/", 1)[-1]
    matches = [k for k in cat.keys if isinstance(k, str) and k.endswith("_" + bname)]
    print("bundle", bname, "guid keys:", len(matches))
    for m in matches[:5]:
        print("   ", m)
