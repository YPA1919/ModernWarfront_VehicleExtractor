# -*- coding: utf-8 -*-
"""Extract the game's own vehicle preview sprites (Sprites/<Name>) so we can
compare our assembled models against the artist's reference."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import UnityPy

HERE = os.path.dirname(os.path.abspath(__file__))
# 打包成 exe 后脚本在临时解包目录里，默认工作目录放到 exe 旁边；
# 源码运行时就是脚本自己所在目录（GUI 会把 --work 显式传进来，这里只是默认值）
if getattr(sys, "frozen", False):
    MW = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "work")
else:
    MW = HERE
OUT = os.path.join(HERE, "_preview_ref")
os.makedirs(OUT, exist_ok=True)

WANT = sys.argv[1:] or ["F16", "A10A", "KA50", "AH64E"]
recs = json.load(open(os.path.join(MW, "catalog_index.json"), encoding="utf-8"))
by_path = {}
for r in recs:
    by_path.setdefault(r["path"], []).append(r)

for name in WANT:
    key = "Sprites/" + name
    cands = [r for r in by_path.get(key, []) if r["cls"] == "UnityEngine.Texture2D"]
    if not cands:
        print("no texture record for", key)
        continue
    b = cands[0]["bundle"]
    path = os.path.join(MW, "bundles", b)
    if not os.path.exists(path):
        print("missing bundle", b)
        continue
    env = UnityPy.load(path)
    got = 0
    for obj in env.objects:
        if obj.type.name not in ("Texture2D", "Sprite"):
            continue
        try:
            d = obj.read()
        except Exception:
            continue
        nm = getattr(d, "m_Name", "") or ""
        if obj.type.name == "Texture2D" and nm == name:
            img = d.image
            out = os.path.join(OUT, name + ".png")
            img.save(out)
            print("saved %s  %dx%d  (%s)" % (out, img.width, img.height, b))
            got += 1
    if not got:
        print("not found inside", b)
