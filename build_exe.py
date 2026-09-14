# -*- coding: utf-8 -*-
"""用 PyInstaller 把 tank_gui.py 打成 exe（onedir）。

为什么用 onedir 而不是 onefile：
    界面是用子进程调用同级脚本的（解包 / 建索引 / 导出 / 校验 / 出图），
    打包后走 `<exe> --run <script>` 分发。onefile 每次启动都要把整包解到临时目录，
    子进程也一样 —— 一次导出要解好几遍，慢得离谱。onedir 只解一次（其实是直接就绪）。

脚本本身以**数据文件**形式打进包里，所以 `--run` 还能跑任意子脚本。
"""
import os
import shutil
import sys

MW = r"D:\DeepSeek Harness\mw"
PYLIBS = os.path.join(MW, "pylibs")
DIST = r"D:\DeepSeek Harness\exe"
WORK = r"D:\DeepSeek Harness\tmp\pyi"
NAME = "ModernWarfront_VehicleExtractor"

sys.path.insert(0, PYLIBS)

EXCLUDES = [
    "matplotlib", "scipy", "pandas", "PyQt5", "PyQt6", "PySide2", "PySide6",
    "IPython", "jupyter", "notebook", "pytest", "setuptools", "pip",
    "sqlite3", "pydoc_data", "lib2to3", "distutils", "test", "unittest",
]


def main():
    from PyInstaller.__main__ import run

    for d in (DIST, WORK):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(DIST, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)

    args = [
        "--noconfirm", "--clean",
        "--console",                       # 子进程要 stdio；界面自己会把控制台窗口藏起来
        "--name", NAME,
        "--distpath", DIST,
        "--workpath", WORK,
        "--specpath", WORK,
        "--paths", MW,
        "--paths", PYLIBS,
        # 子脚本以数据形式带上，--run 才能在包里找到它们
        "--add-data", os.path.join(MW, "*.py") + ";.",
        "--add-data", os.path.join(MW, "README.md") + ";.",
        "--add-data", os.path.join(MW, "README_EN.md") + ";.",
        # 贴图解码相关（UnityPy 会按需 import）
        "--collect-all", "UnityPy",
        "--collect-all", "texture2ddecoder",
        "--collect-all", "etcpak",
        "--collect-all", "astc_encoder",
        # UnityPy.helpers 会间接 import 它；它的 fmod.dll 必须一起带上，
        # 否则打包后贴图解码会抛 PyInstallerImportError
        "--collect-all", "fmod_toolkit",
        "--collect-all", "pyfmodex",
        # etcpak / astc_encoder 会 import archspec，它要读自带的 json 数据
        "--collect-all", "archspec",
        "--collect-all", "lz4",
        "--hidden-import", "PIL._tkinter_finder",
    ]
    for m in EXCLUDES:
        args += ["--exclude-module", m]
    args.append(os.path.join(MW, "tank_gui.py"))

    print("PyInstaller:", " ".join(args[:10]), "...")
    run(args)

    exe = os.path.join(DIST, NAME, NAME + ".exe")
    print()
    if os.path.exists(exe):
        total = sum(os.path.getsize(os.path.join(r, f))
                    for r, _d, fs in os.walk(os.path.join(DIST, NAME)) for f in fs)
        print("完成 -> %s" % exe)
        print("目录体积 %.0f MB" % (total / 2 ** 20))
    else:
        print("!! 没有生成 exe")


if __name__ == "__main__":
    main()
