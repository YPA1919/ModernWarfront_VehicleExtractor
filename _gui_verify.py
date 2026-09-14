# -*- coding: utf-8 -*-
"""Exercise the GUI's non-visual parts: model loading, part isolation, wreck
switch, texture gallery, and the export command builder."""
import os
import sys

import numpy as np

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import tank_gui as G

app = G.App(G.TANKS_DEFAULT)
app.update_idletasks()
app.update()
print("countries:", len(app.lib), "tanks:", sum(len(v) for v in app.lib.values()))

allt = sorted([t for v in app.lib.values() for t in v], key=lambda x: x[0])
# a tank with a wreck
target = next((t for t in allt if os.path.exists(t[1].replace(".obj", "_Wreck.obj"))), allt[0])
app.load_tank(target[1])
app.update_idletasks()
m = app.model
print("loaded:", m.name, "verts", len(m.verts), "faces", len(m.faces), "groups", len(m.groups))
print("materials:", len(m.mtl), "textures:", len(m.texture_files()))
man = m.manifest()
print("manifest keys:", list(man.keys()))
if "intact" in man:
    print("manifest parts:", len(man["intact"].get("parts", [])),
          "skipped:", man["intact"].get("skipped_off_model"))

full = np.asarray(m.render(35, 20, 1.0, [0, 0], 500, mode="textured"))
nb = int((np.abs(full - full[0, 0]).sum(axis=2) > 12).sum())
print("full render non-bg pixels:", nb)

# isolate the biggest group
counts = {}
for g in m.group_of_face:
    counts[g] = counts.get(g, 0) + 1
big = max(counts, key=counts.get)
iso = np.asarray(m.render(35, 20, 1.0, [0, 0], 500, mode="textured", only_group=big))
ni = int((np.abs(iso - iso[0, 0]).sum(axis=2) > 12).sum())
print("isolated group %r: %d faces -> non-bg pixels %d (%s)" %
      (big, counts[big], ni, "ok" if 0 < ni < nb else "UNEXPECTED"))

# solid is the default mode now
solid = np.asarray(m.render(35, 20, 1.0, [0, 0], 500, mode="solid"))
ns = int((np.abs(solid - solid[0, 0]).sum(axis=2) > 12).sum())
print("solid render non-bg pixels:", ns, "ok" if ns > 0 else "UNEXPECTED")

# wireframe mode
wire = np.asarray(m.render(35, 20, 1.0, [0, 0], 400, mode="wire"))
nw = int((wire.sum(axis=2) > 60).sum())
print("wireframe pixels:", nw, "ok" if nw > 0 else "UNEXPECTED")

# wreck toggle
app.wreck.set(True)
app.load_tank(target[1])
print("wreck model:", app.model.name, "faces", len(app.model.faces))
app.wreck.set(False)
app.load_tank(target[1])

# part table + texture gallery populated
print("part rows:", len(app.part_tv.get_children()))
print("texture thumbs:", len(app.tex_thumbs))

# export command builder
cmd, env = app._cmd(["--out", r"D:\tmp", "--sample", "4", "--seed", "7"])
print("export cmd ok:", cmd[2].endswith("export_tanks.py"), "PYTHONPATH set:", "pylibs" in env.get("PYTHONPATH", ""))
app.destroy()
print("ALL OK")
