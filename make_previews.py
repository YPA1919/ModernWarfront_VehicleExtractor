"""Render a preview PNG for every exported tank plus a contact sheet.

Usage: python make_previews.py [--root DIR] [--size 512] [--tris 60000]
"""
import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_obj as R


def render_one(path, size, max_tris):
    verts, faces = R.load_obj(path)
    if len(faces) == 0:
        return None
    if len(faces) > max_tris:
        step = len(faces) // max_tris + 1
        faces = faces[::step]
    v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n /= ln
    light = np.array([0.42, 0.78, 0.46])
    light /= np.linalg.norm(light)
    shade = np.abs(n @ light)
    centre = (verts.max(0) + verts.min(0)) / 2
    span = (verts.max(0) - verts.min(0)).max()
    a, b = np.radians(38), np.radians(22)
    ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    pts = (verts - centre) @ ry.T @ rx.T
    sc = (size * 0.44) / (span / 2)
    px, py, pz = pts[:, 0] * sc, -pts[:, 1] * sc, pts[:, 2]
    order = np.argsort(pz[faces].mean(axis=1))
    tri = np.stack([px[faces[:, 0]], py[faces[:, 0]],
                    px[faces[:, 1]], py[faces[:, 1]],
                    px[faces[:, 2]], py[faces[:, 2]]], axis=1)[order]
    img = Image.new("RGB", (size, size), (26, 28, 34))
    dr = ImageDraw.Draw(img)
    o = size / 2
    for t, s in zip(tri, shade[order]):
        c = int(45 + 195 * min(1.0, s))
        dr.polygon([(o + t[0], o + t[1]), (o + t[2], o + t[3]), (o + t[4], o + t[5])],
                   fill=(c, int(c * 0.95), int(c * 0.86)))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root",
                    default=os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "MW_Tanks"))
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--tris", type=int, default=60000)
    ap.add_argument("--cols", type=int, default=8)
    args = ap.parse_args()

    objs = []
    for dirpath, _dirs, files in os.walk(args.root):
        for f in files:
            if f.endswith(".obj"):
                objs.append(os.path.join(dirpath, f))
    objs.sort()
    print(f"{len(objs)} models", flush=True)

    thumbs = []
    t0 = time.time()
    for i, p in enumerate(objs, 1):
        out = os.path.join(os.path.dirname(p), "preview.png")
        if p.endswith("_Wreck.obj"):
            out = os.path.join(os.path.dirname(p), "preview_wreck.png")
        try:
            img = render_one(p, args.size, args.tris)
            if img is not None:
                img.save(out)
                thumbs.append((os.path.basename(os.path.dirname(p)), img, "_Wreck" in p))
                print(f"  [{i}/{len(objs)}] {os.path.basename(os.path.dirname(p)):28s} "
                      f"({time.time()-t0:.0f}s)", flush=True)
        except Exception as exc:
            print(f"  [{i}/{len(objs)}] {p}: {type(exc).__name__}: {exc}", flush=True)
        print("PROGRESS %d %d" % (i, len(objs)), flush=True)

    for label, want in (("", False), ("_wreck", True)):
        sel = [(n, im) for n, im, w in thumbs if w == want]
        if not sel:
            continue
        cols = args.cols
        rows = (len(sel) + cols - 1) // cols
        cell = args.size // 2
        sheet = Image.new("RGB", (cols * cell, rows * (cell + 16)), (18, 19, 24))
        dr = ImageDraw.Draw(sheet)
        for i, (name, img) in enumerate(sel):
            x, y = (i % cols) * cell, (i // cols) * (cell + 16)
            sheet.paste(img.resize((cell, cell)), (x, y))
            dr.text((x + 3, y + cell + 2), name[:22], fill=(230, 210, 130))
        out = os.path.join(args.root, f"_contact_sheet{label}.png")
        sheet.save(out)
        print("contact sheet:", out, f"({len(sel)} models)", flush=True)


if __name__ == "__main__":
    main()
