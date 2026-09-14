# -*- coding: utf-8 -*-
"""Build the catalog index: asset path <-> guid <-> bundle.

    python build_index.py --catalog mw\\catalog.json --out mw

Also prints a short summary of the tank assets found.  Emits "PROGRESS done total"
lines for the GUI.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from aacatalog import Catalog

TANK_RE = "Assets/Content/Mesh/Tanks/"


def progress(done, total):
    print("PROGRESS %d %d" % (done, total), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=os.path.join(HERE, "catalog.json"))
    ap.add_argument("--out", default=HERE, help="where catalog_index.json is written")
    args = ap.parse_args()

    if not os.path.exists(args.catalog):
        print("catalog not found: %s" % args.catalog, flush=True)
        return 2
    print("catalog: %s (%.1f MB)" % (args.catalog, os.path.getsize(args.catalog) / 2 ** 20))
    cat = Catalog(args.catalog)

    def bundle_of(entry):
        dk = entry["dependencyKey"]
        if 0 <= dk < len(cat.keys):
            k = cat.keys[dk]
            if isinstance(k, str) and k.endswith(".bundle"):
                return k.rsplit("_", 1)[-1]
        return None

    def cls_of(entry):
        rt = cat.resource_types[entry["resourceTypeIndex"]]
        return rt.get("m_ClassName") if isinstance(rt, dict) else str(rt)

    index = collections.defaultdict(list)
    by_bundle = collections.defaultdict(set)
    records = []
    total = len(cat.buckets)
    progress(0, total)
    for n, (key_off, eis) in enumerate(cat.buckets, 1):
        ki = cat._by_offset.get(key_off)
        if ki is None:
            continue
        key = cat.keys[ki]
        if not isinstance(key, str):
            continue
        for ei in eis:
            e = cat.entries[ei]
            iid = cat.internal_ids[e["internalId"]]
            b = bundle_of(e)
            rec = {"path": key, "cls": cls_of(e), "bundle": b, "guid": iid}
            records.append(rec)
            if len(iid) == 32 and "/" not in iid:
                index[iid].append(rec)
                if b:
                    by_bundle[b].add(iid)
        if n % 2000 == 0:
            progress(n, total)
    progress(total, total)

    out = os.path.join(args.out, "catalog_index.json")
    os.makedirs(args.out, exist_ok=True)
    json.dump(records, open(out, "w", encoding="utf-8"))
    print("wrote %s (%d records, %.1f MB)"
          % (out, len(records), os.path.getsize(out) / 2 ** 20), flush=True)

    tank_bundles = collections.defaultdict(set)
    for r in records:
        if r["path"].startswith(TANK_RE) and r["bundle"]:
            parts = r["path"][len(TANK_RE):].split("/")
            if len(parts) >= 3:
                tank_bundles[(parts[0], parts[1])].add(r["bundle"])
    print("tanks in catalog: %d, distinct bundles: %d"
          % (len(tank_bundles), len({b for v in tank_bundles.values() for b in v})))
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
