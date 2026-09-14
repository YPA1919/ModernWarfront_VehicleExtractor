# -*- coding: utf-8 -*-
"""Unpack an APK's Unity payload: Addressables catalog + bundles + player data.

    python extract_bundles.py --apk game.apk --work D:\\work
    python extract_bundles.py --apk game.apk --list-only

Emits machine readable progress lines ("PROGRESS done total") so a GUI can drive
a progress bar; everything else on stdout is ordinary logging.
"""
import argparse
import os
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
# 打包成 exe 后脚本在临时解包目录里，默认工作目录放到 exe 旁边；
# 源码运行时就是脚本自己所在目录（GUI 会把 --work 显式传进来，这里只是默认值）
if getattr(sys, "frozen", False):
    MW = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "work")
else:
    MW = HERE
DEFAULT_APK = r"E:\modern_warfront_0.23.2.12034397.apk"
# 换过几次位置，留几个候选，找不到再让用户手选
APK_CANDIDATES = (
    DEFAULT_APK,
    r"D:\modern_warfront_0.23.2.12034397.apk",
    r"C:\modern_warfront_0.23.2.12034397.apk",
)


def say(msg):
    print(msg, flush=True)


def progress(done, total):
    print("PROGRESS %d %d" % (done, total), flush=True)


def pick_targets(infos, want_data=True):
    out = []
    for i in infos:
        n = i.filename
        if n.startswith("assets/aa/") and n.endswith(".bundle"):
            out.append(("bundle", i))
        elif n in ("assets/aa/catalog.json", "assets/aa/settings.json"):
            out.append(("catalog", i))
        elif want_data and n == "assets/bin/Data/data.unity3d":
            out.append(("data", i))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", default=DEFAULT_APK)
    ap.add_argument("--work", default=MW,
                    help="workspace holding bundles/ and catalog.json (default: mw)")
    ap.add_argument("--out", default="", help="bundle output dir (default <work>/bundles)")
    ap.add_argument("--catalog-out", default="", help="where to write catalog.json")
    ap.add_argument("--skip-data", action="store_true", help="do not extract data.unity3d")
    ap.add_argument("--list-only", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.apk):
        say("APK not found: %s" % args.apk)
        return 2
    outdir = args.out or os.path.join(args.work, "bundles")
    cat_out = args.catalog_out or os.path.join(args.work, "catalog.json")
    os.makedirs(outdir, exist_ok=True)

    size = os.path.getsize(args.apk)
    say("APK    : %s (%.2f GB)" % (args.apk, size / 2 ** 30))
    say("bundles: %s" % outdir)
    say("catalog: %s" % cat_out)

    t0 = time.time()
    say("reading zip index ...")
    z = zipfile.ZipFile(args.apk)
    targets = pick_targets(z.infolist(), want_data=not args.skip_data)
    nb = sum(1 for k, _ in targets if k == "bundle")
    nmeta = sum(1 for k, _ in targets if k == "catalog")
    total_bytes = sum(i.file_size for _, i in targets)
    say("indexed %d zip entries in %.1fs" % (len(z.infolist()), time.time() - t0))
    say("%d bundles + %d metadata files + player data, %.2f GB uncompressed"
        % (nb, nmeta, total_bytes / 2 ** 30))
    if nmeta == 0:
        say("NOTE: no assets/aa/catalog.json in this APK - it may not use Addressables")
    if args.list_only:
        progress(0, 0)
        return 0

    total = len(targets)
    progress(0, total)
    done = copied = skipped = 0
    written = 0
    t1 = time.time()
    for kind, info in targets:
        name = os.path.basename(info.filename)
        if kind == "catalog":
            # catalog.json goes to the workspace root, settings.json next to it;
            # both used to land on the same path and clobbered the catalog.
            dest = cat_out if name == "catalog.json" else os.path.join(
                os.path.dirname(cat_out) or ".", name)
        else:
            dest = os.path.join(outdir, name)
        if os.path.exists(dest) and os.path.getsize(dest) == info.file_size:
            skipped += 1
            done += 1
            if done % 50 == 0 or done == total:
                progress(done, total)
            continue
        tmp = dest + ".part"
        with z.open(info) as src, open(tmp, "wb") as dst:
            while True:
                chunk = src.read(1 << 22)
                if not chunk:
                    break
                dst.write(chunk)
        if os.path.exists(dest):
            os.remove(dest)
        os.replace(tmp, dest)
        written += info.file_size
        copied += 1
        done += 1
        if done % 25 == 0 or done == total:
            progress(done, total)
    say("done: %d extracted, %d already present, %.2f GB written in %.1fs"
        % (copied, skipped, written / 2 ** 30, time.time() - t1))
    if not os.path.exists(cat_out):
        say("WARNING: catalog.json missing - the index step will not work")
    return 0


if __name__ == "__main__":
    sys.exit(main())
