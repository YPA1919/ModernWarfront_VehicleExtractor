# -*- coding: utf-8 -*-
"""把脚本 + 中英文 README + pylibs 依赖打成一个压缩包。

- 所有 .py 平铺在同一层：脚本之间是互相 import 的，tank_gui.py 也用自己所在目录
  拼出 export_tanks.py 的路径，拆到子目录就跑不起来。
- pylibs/ 原样带上（只去掉编译中间产物），这样解压就能直接跑，不用装任何东西。
"""
import os
import zipfile

SRC = r"D:\DeepSeek Harness\mw"
ROOT = "ModernWarfront_VehicleExtractor"
OUT = r"D:\DeepSeek Harness\ModernWarfront_VehicleExtractor源码.zip"
PYLIBS = os.path.join(SRC, "pylibs")

# 文档单独复制：源文件名 -> 包内文件名
DOCS = {"README.md": "README.md", "README_EN.md": "README_EN.md"}

# 依赖里这些是编译/调试中间产物，跑起来用不到
SKIP_EXT = (".iobj", ".pdb", ".lib", ".exp", ".obj", ".a", ".map")
SKIP_DIR = ("__pycache__",)


def dep_files():
    for r, ds, fs in os.walk(PYLIBS):
        ds[:] = [d for d in ds if d not in SKIP_DIR]
        for f in fs:
            if f.lower().endswith(SKIP_EXT):
                continue
            p = os.path.join(r, f)
            yield p, os.path.relpath(p, SRC).replace("\\", "/")


def main():
    scripts = sorted(f for f in os.listdir(SRC)
                     if f.endswith(".py") and os.path.isfile(os.path.join(SRC, f)))
    total = 0
    n_files = 0
    missing = []
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in scripts + list(DOCS):
            p = os.path.join(SRC, f)
            if not os.path.isfile(p):
                missing.append(f)
                continue
            z.write(p, "%s/%s" % (ROOT, DOCS.get(f, f)))
            total += os.path.getsize(p)
            n_files += 1
        n_dep = 0
        dep_bytes = 0
        for p, rel in dep_files():
            z.write(p, "%s/%s" % (ROOT, rel))
            dep_bytes += os.path.getsize(p)
            n_dep += 1

    size = os.path.getsize(OUT)
    print("打包 -> %s" % OUT)
    print("  脚本/文档 %d 个 (%.0f KB) + 依赖 %d 个 (%.1f MB)"
          % (n_files, total / 1024, n_dep, dep_bytes / 2 ** 20))
    print("  压缩后 %.1f MB" % (size / 2 ** 20))
    if missing:
        print("  !! 缺少:", missing)

    with zipfile.ZipFile(OUT) as z:
        tops = {}
        for n in z.namelist():
            k = n.split("/")[1] if n.count("/") > 1 else "(文件)"
            tops[k] = tops.get(k, 0) + 1
        print("  包内顶层条目:", ", ".join("%s(%d)" % (k, v)
                                        for k, v in sorted(tops.items())[:12]))


if __name__ == "__main__":
    main()
