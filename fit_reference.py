# -*- coding: utf-8 -*-
"""Match our assembled model against the game's own preview sprite.

Renders a grid of yaw/pitch, keeps the silhouette, and reports the best IoU plus
a difference image — so "is the model wrong and where" becomes measurable.
"""
import glob
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import tank_gui as G

REF = os.path.join(HERE, "_preview_ref")
OUT = os.path.join(HERE, "_fit")
os.makedirs(OUT, exist_ok=True)

PAIRS = [("F16", "F16_Fighter"), ("A10A", "A10A_Fighter"),
         ("AH64E", "AH64E_Helicopter"), ("KA50", "KA50_Helicopter")]


def silhouette(img, thr=28):
    a = np.asarray(img.convert("RGB")).astype(int)
    return a.sum(axis=2) > thr * 3


def ref_silhouette(path):
    """The preview sprites carry an alpha channel: opaque = vehicle."""
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)
    alpha = a[..., 3] > 128
    if alpha.sum() > 200:
        return alpha
    return silhouette(im)


def norm_mask(mask, size=256, box=220):
    """Crop to the bbox, scale UNIFORMLY into a common frame, centre it.
    (Scaling x and y independently would destroy the aspect ratio and make the
    IoU meaningless.)"""
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return np.zeros((size, size), bool)
    sub = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = sub.shape
    k = box / max(h, w)
    nh, nw = max(1, int(round(h * k))), max(1, int(round(w * k)))
    im = Image.fromarray((sub * 255).astype(np.uint8)).resize((nw, nh), Image.BILINEAR)
    out = np.zeros((size, size), bool)
    y0, x0 = (size - nh) // 2, (size - nw) // 2
    out[y0:y0 + nh, x0:x0 + nw] = np.asarray(im) > 127
    return out


for ref_name, tank in PAIRS:
    rp = os.path.join(REF, ref_name + ".png")
    obj = glob.glob(os.path.join(HERE, "_gear/**/%s.obj") % tank, recursive=True)
    if not os.path.exists(rp) or not obj:
        print("skip", ref_name, " (no ref or no obj)")
        continue
    ref = norm_mask(ref_silhouette(rp))
    m = G.TankModel(obj[0])
    best = (-1, None, None)
    for yaw in range(-180, 180, 10):
        for pitch in (3, 8, 14, 20, 28, 38):
            im = m.render(yaw, pitch, 1.0, [0, 0], 256, mode="solid", max_tris=60000)
            mask = silhouette(im)
            if mask.sum() < 50:
                continue
            cand = norm_mask(mask)
            iou = (cand & ref).sum() / max(1, (cand | ref).sum())
            if iou > best[0]:
                best = (iou, (yaw, pitch), cand)
    iou, ang, cand = best
    print("%-8s %-20s 最佳 IoU = %.3f  角度 %s" % (ref_name, tank, iou, ang))
    if cand is not None:
        rgb = np.zeros((256, 256, 3), np.uint8)
        rgb[..., 0] = ref * 255          # 红 = 游戏预览
        rgb[..., 1] = cand * 255         # 绿 = 我们导出，黄 = 重合
        Image.fromarray(rgb).resize((512, 512), Image.NEAREST).save(
            os.path.join(OUT, ref_name + "_diff.png"))
