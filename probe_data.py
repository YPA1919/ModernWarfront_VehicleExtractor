"""Inspect the data.unity3d container (Resources paths) and whether the tank
prefab's MeshFilters reference meshes inside the same file."""
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import UnityPy
from UnityPy.helpers import TypeTreeHelper as _TTH

_TTH.read_typetree_boost = None

env = UnityPy.load(r"D:\DeepSeek Harness\mw\bundles\data.unity3d")

for name, cf in env.files.items():
    print("file:", type(cf).__name__, name)
    cont = getattr(cf, "container", None)
    print("  container:", "None" if cont is None else len(cont))
    if cont:
        tank_keys = [k for k in cont if k.lower().startswith("tanks/")]
        print("  Tanks/* keys:", len(tank_keys))
        for k in tank_keys[:5]:
            print("     ", k, "->", cont[k])
    inner = getattr(cf, "files", None)
    if inner:
        for n2, c2 in inner.items():
            print("   inner:", type(c2).__name__, n2, "objects",
                  len(getattr(c2, "objects", {})))
            c = getattr(c2, "container", None)
            print("     inner container:", "None" if c is None else len(c))
            if c:
                tk = [k for k in c if k.lower().startswith("tanks/")]
                print("     Tanks/* in inner:", len(tk), tk[:3])

# resolve sample prefab meshes
objs = {o.path_id: o for o in env.objects}
gos = {}
for o in env.objects:
    if o.type.name == "GameObject":
        try:
            d = o.read()
            if d.m_Name == "Hull_LOD0":
                gos[o.path_id] = d
        except Exception:
            pass
print("Hull_LOD0 GameObjects:", len(gos))
for pid, d in list(gos.items())[:2]:
    for comp in d.m_Component:
        try:
            c = comp.component if hasattr(comp, "component") else comp
            co = c.deref()
            if co is None:
                print("   unresolved component", c.path_id)
                continue
            cd = co.read()
            tn = co.type.name
            if tn == "MeshFilter":
                m = cd.m_Mesh
                print(f"   {tn}: mesh path_id={m.path_id} file={m.file if hasattr(m,'file') else '?'}")
                try:
                    md = m.deref().read()
                    print("      mesh name:", md.m_Name, "verts:", md.m_VertexData.m_VertexCount)
                except Exception as e:
                    print("      mesh unresolved:", type(e).__name__, e)
            elif tn == "MeshRenderer":
                ms = cd.m_Materials
                print(f"   {tn}: materials={[x.path_id for x in ms]}")
                for x in ms[:2]:
                    try:
                        mat = x.deref().read()
                        print("      mat:", mat.m_Name)
                    except Exception as e:
                        print("      mat unresolved:", type(e).__name__)
            else:
                print(f"   {tn}")
        except Exception as e:
            print("   component err", type(e).__name__, e)
