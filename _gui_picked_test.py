# -*- coding: utf-8 -*-
"""End-to-end: unpack (skipped, already present) -> index -> export ONLY the
picked vehicles, through the GUI pipeline, and check exactly those appear."""
import os
import shutil
import sys
import time

sys.path.insert(0, r"D:\DeepSeek Harness\mw")
sys.path.insert(0, r"D:\DeepSeek Harness\mw\pylibs")

import tank_gui as G

APK = ""
for root, _d, files in os.walk(os.path.join(os.path.expanduser("~"), ".dsh", "attachments")):
    for f in files:
        if f.lower().endswith(".apk"):
            APK = os.path.join(root, f)
            break
    if APK:
        break

OUT = r"D:\DeepSeek Harness\mw\_pick_out"
shutil.rmtree(OUT, ignore_errors=True)
PICK = ["T90A", "ZBD86", "M1A2SEPv2"]

app = G.App(r"D:\DeepSeek Harness\mw\sample")
app.update_idletasks()
app.update()
app.im_apk.set(APK)
app.im_work.set(r"D:\DeepSeek Harness\mw")
app.im_out.set(OUT)
app.im_index.set(True)
app.im_export.set(True)
app.im_preview.set(False)
app.im_validate.set(False)
app.im_scope.set("picked")
app.picker.set_names(G.list_tank_names(r"D:\DeepSeek Harness\mw", OUT))
for i, n in enumerate(app.picker.shown):
    if n in PICK:
        app.picker.lb.selection_set(i)
app.picker._on_select()
print("picked:", app.picker.selected())

app.run_import()
t0 = time.time()
while app._busy() and time.time() - t0 < 600:
    app.update()
    time.sleep(0.1)
for _ in range(20):          # let _pump_log drain the queue
    app.update()
    time.sleep(0.05)
log = app.log.get("1.0", "end")
print("phase:", app.prog_lbl.get())

objs = [f for r, _d, ff in os.walk(OUT) for f in ff if f.endswith(".obj")]
tanks = sorted({f[:-4] for f in objs if not f.endswith("_Wreck.obj")})
wrecks = [f for f in objs if f.endswith("_Wreck.obj")]
print("exported tanks:", tanks)
print("wreck objs:", len(wrecks), sorted(wrecks))
ok = tanks == sorted(PICK) and len(wrecks) == len(PICK) and "全部完成" in log
print("PICKED EXPORT OK" if ok else "PICKED EXPORT FAILED")
app.destroy()
