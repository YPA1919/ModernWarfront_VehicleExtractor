"""Try to read the game's own visual-slot mapping (LiveryMeshData / TankData)."""
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import UnityPy
import export_tanks as E

g = E.GameData()

targets = ("LiveryMeshes/Leopard2A8", "Data/UnitData/Leopard2A8",
           "LiveryMeshes/T90A", "Data/UnitData/T90A")

# how does the file store MonoBehaviours?
for sf in g.sfs:
    if sf.name != "resources.assets":
        continue
    print("serialized file:", sf.name, "version", getattr(sf, "version", None),
          "big_id", getattr(sf, "big_id_enabled", None))
    types = getattr(sf, "types", None)
    if types:
        mb = [t for t in types if getattr(t, "class_id", None) == 114]
        print("MonoBehaviour serialized types:", len(mb))
        for t in mb[:3]:
            nodes = getattr(t, "nodes", None) or getattr(t, "m_Nodes", None)
            print("   script", getattr(t, "script", None), "nodes",
                  len(nodes) if nodes else 0)

found = 0
for sf in g.sfs:
    for o in sf.objects.values():
        if o.type.name != "MonoBehaviour":
            continue
        try:
            c = o.container
        except Exception:
            c = None
        if c and any(c.endswith(t) or t in c for t in targets):
            print("=" * 70)
            print("container:", c, "path_id", o.path_id)
            try:
                tree = o.read_typetree()
                print("  typetree keys:", list(tree)[:20] if isinstance(tree, dict) else type(tree))
            except Exception as exc:
                print("  read_typetree failed:", type(exc).__name__, exc)
                raw = o.get_raw_data()
                print("  raw size:", len(raw))
                print("  head:", raw[:96].hex(" "))
            found += 1
            if found > 4:
                sys.exit()
