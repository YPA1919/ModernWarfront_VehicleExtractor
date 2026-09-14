"""Structural validation of every assembled model.

Checks, per tank:
  A. vertical gaps - a floating hull shows up as an empty y band through the model
  B. hull/running-gear overlap - the hull must sit on the wheels and tracks
  C. proportions - height/length and width/length must be vehicle-like
  D. collider extents - the game's own collider mesh sets the expected footprint

Usage: python validate_models.py [--root DIR] [--tanks-only A,B] [--limit N]
"""
import argparse
import collections
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

HERE = os.path.dirname(os.path.abspath(__file__))
# 打包成 exe 后脚本在临时解包目录里，默认工作目录放到 exe 旁边；
# 源码运行时就是脚本自己所在目录（GUI 会把 --work 显式传进来，这里只是默认值）
if getattr(sys, "frozen", False):
    MW = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "work")
else:
    MW = HERE
BUNDLES = os.path.join(MW, "bundles")
GEAR_RE = re.compile(r"(wheel|track|tire|tyre|roadwheel|roller|sprocket|idler|suspension)", re.I)
HULL_RE = re.compile(r"(^|_)(hull|body|tub|chassis)", re.I)


def parse_obj_parts(path):
    """-> list of (name, aabb_min, aabb_max, nverts)"""
    parts = []
    cur = None
    mn = mx = None
    n = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("g "):
                if cur is not None and n:
                    parts.append((cur, mn, mx, n))
                cur = line[2:].strip()
                mn = np.array([1e18] * 3)
                mx = np.array([-1e18] * 3)
                n = 0
            elif line.startswith("v "):
                p = line.split()
                v = np.array([float(p[1]), float(p[2]), float(p[3])])
                mn = np.minimum(mn, v)
                mx = np.maximum(mx, v)
                n += 1
    if cur is not None and n:
        parts.append((cur, mn, mx, n))
    return parts


def model_scale(base):
    """导出时可能整体放大过（默认 ×7），比对前要还原回游戏单位。"""
    try:
        d = json.load(open(os.path.join(base, "manifest.json"), encoding="utf-8"))
        for k in ("intact", "wreck"):
            s = (d.get(k) or {}).get("scale")
            if s:
                return float(s)
    except Exception:
        pass
    return 1.0


def largest_gap(intervals):
    iv = sorted(intervals)
    gaps = []
    hi = iv[0][1]
    for lo, h in iv[1:]:
        if lo > hi:
            gaps.append((lo - hi, hi, lo))
        hi = max(hi, h)
    return max(gaps) if gaps else (0.0, 0.0, 0.0)


def collider_extents(tank, cache):
    """拿游戏里那张碰撞体网格算外廓，用来和导出模型比大小。

    工作目录里没有 catalog_index.json（比如没建过索引、或者 --work 指错了）时，
    以前会直接抛 FileNotFoundError 把整个校验打断 —— 表现就是「什么车都失败」。
    现在只提示一次，然后跳过这一项，其余检查照常跑。
    """
    if tank in cache:
        return cache[tank]
    idx = os.path.join(MW, "catalog_index.json")
    if not os.path.exists(idx):
        if not cache.get("__warned__"):
            print("[提示] 找不到 %s —— 跳过「与碰撞体外廓比对」这一项；" % idx, flush=True)
            print("       载具列表和这一项都要靠 catalog_index.json，"
                  "先用 build_index.py 建一次，或用 --work 指向正确的解包目录。", flush=True)
            cache["__warned__"] = True
        cache[tank] = None
        return None
    try:
        recs = json.load(open(idx, encoding="utf-8"))
    except Exception as exc:
        if not cache.get("__warned__"):
            print("[提示] 读不了 %s（%s）—— 跳过碰撞体比对。" % (idx, exc), flush=True)
            cache["__warned__"] = True
        cache[tank] = None
        return None
    pat = re.compile(r"Assets/Content/Mesh/[^/]+/([^/]+)/[^/]+/([^/]+)_Colliders\.asset$")
    key = tank.lower()
    bundle = None
    for r in recs:
        m = pat.match(r["path"])
        if not m or not r["bundle"]:
            continue
        d, f = m.group(1).lower(), m.group(2).lower()
        if key == d or key == f or key.startswith(d) or d.startswith(key):
            bundle = r["bundle"]
            break
    out = None
    if bundle:
        path = os.path.join(BUNDLES, bundle)
        if os.path.exists(path):
            try:
                import UnityPy
                from UnityPy.helpers import TypeTreeHelper as T
                from UnityPy.helpers.MeshHelper import MeshHandler
                T.read_typetree_boost = None
                env = UnityPy.load(path)
                best = None
                for o in env.objects:
                    if o.type.name != "Mesh":
                        continue
                    d = o.read()
                    h = MeshHandler(d)
                    h.process()
                    if not h.m_Vertices:
                        continue
                    V = np.array([v[:3] for v in h.m_Vertices])
                    if best is None or len(V) > len(best):
                        best = V
                if best is not None:
                    out = (best.min(0), best.max(0))
            except Exception:
                out = None
    cache[tank] = out
    return out


def _use_work(work):
    """切换工作目录（catalog_index.json / bundles 都在那儿）。"""
    global MW, BUNDLES
    MW = work
    BUNDLES = os.path.join(work, "bundles")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(os.path.dirname(MW), "MW_Tanks"))
    ap.add_argument("--work", default=MW,
                    help="workspace holding catalog_index.json (for collider lookup)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    _use_work(args.work)

    summary = json.load(open(os.path.join(args.root, "_summary.json"), encoding="utf-8"))
    rows = summary["tanks"]
    if args.only:
        want = {x.strip() for x in args.only.split(",")}
        rows = [r for r in rows if r["tank"] in want]
    if args.limit:
        rows = rows[:args.limit]

    cache = {}
    flags = collections.defaultdict(list)
    for i, r in enumerate(rows, 1):
        tank, country = r["tank"], r["country"]
        base = os.path.join(args.root, E_dir(country), E_name(tank))
        path = os.path.join(base, E_name(tank) + ".obj")
        if not os.path.exists(path):
            flags["missing_obj"].append(tank)
            continue
        parts = parse_obj_parts(path)
        if not parts:
            flags["empty"].append(tank)
            continue
        sc = model_scale(base)
        if sc and sc != 1.0:            # 还原成游戏单位，后面所有阈值才有意义
            parts = [(n, lo / sc, hi / sc, nv) for (n, lo, hi, nv) in parts]
        lo = np.min([p[1] for p in parts], axis=0)
        hi = np.max([p[2] for p in parts], axis=0)
        size = hi - lo

        gap, g0, g1 = largest_gap([(p[1][1], p[2][1]) for p in parts])
        if gap > 0.05 and gap > 0.14 * size[1]:
            flags["vertical_gap"].append((tank, round(gap, 3), round(g0, 2), round(g1, 2)))

        gear = [p for p in parts if GEAR_RE.search(p[0])]
        hulls = [p for p in parts if HULL_RE.search(p[0])]
        if gear:
            gear_top = max(p[2][1] for p in gear)
            # the biggest hull-ish part should reach down into the running gear
            cand = hulls or [max(parts, key=lambda p: p[3])]
            hull_bottom = min(p[1][1] for p in cand)
            if hull_bottom > gear_top + 0.02:
                flags["hull_floats"].append((tank, round(hull_bottom - gear_top, 3)))

        hl = size[1] / max(size[2], 1e-6)
        wl = size[0] / max(size[2], 1e-6)
        if not (0.08 <= hl <= 0.80) or not (0.15 <= wl <= 1.30):
            flags["proportions"].append((tank, round(hl, 3), round(wl, 3)))

        ref = collider_extents(tank, cache)
        if ref is not None:
            csize = ref[1] - ref[0]
            dx = abs(size[0] - csize[0]) / max(csize[0], 1e-6)
            dz = abs(size[2] - csize[2]) / max(csize[2], 1e-6)
            if dx > 0.45 or dz > 0.35:
                flags["collider_extent"].append((tank, round(dx, 2), round(dz, 2)))
        print("PROGRESS %d %d" % (i, len(rows)), flush=True)
        if i % 40 == 0:
            print(f"  ...{i}/{len(rows)}", flush=True)

    print()
    print(f"checked {len(rows)} tanks")
    for k in sorted(flags):
        print(f"== {k}: {len(flags[k])}")
        for v in flags[k][:25]:
            print("     ", v)


def E_name(s):
    import export_tanks as E
    return E.safe_name(s)


def E_dir(s):
    return E_name(s)


if __name__ == "__main__":
    main()
