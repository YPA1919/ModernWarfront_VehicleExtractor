import sys
import time

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import export_tanks as E

tank = sys.argv[1] if len(sys.argv) > 1 else "KW2Jupiter120"

g = E.GameData()
tn = {r["path"].split("/")[-1] for r in
      __import__("json").load(open(r"D:\DeepSeek Harness\mw\catalog_index.json", encoding="utf-8"))
      if r["path"].startswith("Tanks/")}
roots = g.root_candidates(tn)
print("tank in roots:", tank in roots)
root = roots[tank]
print("root go:", root, "name:", g.go_name.get(root))
print("children:", [g.go_name.get(g.tr[t].m_GameObject.path_id) for t in g.kids.get(root, ())
                    if t in g.tr and g.tr[t].m_GameObject])

t0 = time.time()
parts = E.collect_parts(g, root, False)
print(f"collect_parts: {len(parts)} parts in {time.time()-t0:.1f}s")

for go in parts[:20]:
    name = g.go_name.get(go)
    mp = g.mf.get(go)
    t = time.time()
    mesh = g.mesh(mp)
    t_read = time.time() - t
    vc = None
    if mesh is not None:
        try:
            vc = mesh.m_VertexData.m_VertexCount
        except Exception:
            pass
    print(f"   {name:34s} mesh={getattr(mesh,'m_Name',None)!r:44s} v={vc} read={t_read:.2f}s", flush=True)
    if mesh is not None:
        t = time.time()
        from UnityPy.helpers.MeshHelper import MeshHandler
        h = MeshHandler(mesh)
        h.process()
        tg = time.time() - t
        t = time.time()
        tris = h.get_triangles()
        tt = time.time() - t
        print(f"        process={tg:.2f}s tris={tt:.2f}s groups={len(tris)} "
              f"total={sum(len(x) for x in tris)} verts={len(h.m_Vertices)}", flush=True)
