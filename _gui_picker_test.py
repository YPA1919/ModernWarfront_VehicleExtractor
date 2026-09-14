# -*- coding: utf-8 -*-
"""Exercise the new vehicle picker: name list, search, multi-select, scope
switching, and the --only command it produces."""
import sys

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import tank_gui as G

app = G.App(r"D:\DeepSeek Harness\mw\sample")
app.update_idletasks()
app.update()

p = app.picker
print("names loaded:", len(p.names), "shown:", len(p.shown))
print("sample names:", p.names[:5])

# search
p.search.set("t90")
app.update_idletasks()
print("search 't90' ->", p.shown)

p.search.set("leopard2a")
app.update_idletasks()
print("search 'leopard2a' ->", len(p.shown), p.shown[:6])

# select two of the visible ones
p.search.set("")
app.update_idletasks()
for i, n in enumerate(p.shown):
    if n in ("T90A", "ZBD86", "M1A2SEPv2"):
        p.lb.selection_set(i)
p._on_select()
print("picked:", p.selected(), "|", p.count.get())

# filtered-out picks are remembered
p.search.set("t90")
app.update_idletasks()
print("after filtering to t90, picked still:", p.selected())

# scope switching
app.im_scope.set("picked")
app._sync_scope()
app.update_idletasks()
print("scope=picked  picker visible:", bool(app.pick_wrap.winfo_ismapped()))
app.im_scope.set("random")
app._sync_scope()
app.update_idletasks()
print("scope=random  picker visible:", bool(app.pick_wrap.winfo_ismapped()))
app.im_scope.set("picked")
app._sync_scope()
app.update_idletasks()

# command the pipeline would run
app.im_apk.set(G.__dict__.get("_", "") or app.im_apk.get())
app.im_export.set(True)
app.im_index.set(True)
steps = app._import_steps()
print("steps:", [s[0] for s in steps] if steps else None)
for label, cmd, env in steps or []:
    if label.startswith("导出模型"):
        print("export cmd:", " ".join(cmd[3:]))

# export tab picker
app.picker2.set_names(["T90A", "ZBD86"])
app.picker2.lb.selection_set(0, "end")
app.picker2._on_select()
app.fill_from_picker()
print("重导 tab 车辆框:", app.ex_only.get())

app.destroy()
print("PICKER TEST OK")
