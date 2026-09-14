# -*- coding: utf-8 -*-
"""End-to-end test of the GUI's APK import pipeline (list mode, then a real
extract + index + 2-tank export) while watching the progress bar."""
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
print("APK:", APK)
assert APK and os.path.exists(APK)

OUT = r"D:\DeepSeek Harness\mw\_pipe_out"
shutil.rmtree(OUT, ignore_errors=True)

app = G.App(G.TANKS_DEFAULT)
app.update_idletasks()
app.update()
app.im_apk.set(APK)
app.im_work.set(r"D:\DeepSeek Harness\mw")        # bundles already there
app.im_out.set(OUT)
app.im_index.set(True)
app.im_export.set(True)
app.im_preview.set(False)
app.im_validate.set(False)
app.im_scope.set("sample")
app.im_n.set("2")
app.im_seed.set("11")


def wait(limit=600):
    t0 = time.time()
    seen = []
    while app._busy() and time.time() - t0 < limit:
        app.update()
        seen.append((app.progress["value"], app.progress["maximum"], app.prog_lbl.get()))
        time.sleep(0.1)
    app.update()
    return seen


print("\n--- step 1: list only ---")
app.run_import_list()
seen = wait(120)
print("progress samples:", seen[len(seen) // 2] if seen else None)
print("final:", app.prog_lbl.get(), app.progress["value"], "/", app.progress["maximum"])
log = app.log.get("1.0", "end")
print("log mentions bundles:", "bundles +" in log or "bundles" in log)

print("\n--- step 2: full pipeline (extract + index + export 2) ---")
app.log.delete("1.0", "end")
app.run_import()
seen = wait(900)
print("progress samples:", seen[len(seen) // 2] if seen else None)
print("final:", app.prog_lbl.get(), app.progress["value"], "/", app.progress["maximum"])
log = app.log.get("1.0", "end")
for marker in ("解包 APK", "解析 catalog", "导出模型", "全部完成"):
    print("  %-14s in log: %s" % (marker, marker in log))
objs = []
for r, _d, ff in os.walk(OUT):
    objs += [f for f in ff if f.endswith(".obj")]
print("exported obj files:", len(objs), objs[:4])
app.destroy()
print("PIPELINE TEST OK" if objs and "全部完成" in log else "PIPELINE TEST FAILED")
