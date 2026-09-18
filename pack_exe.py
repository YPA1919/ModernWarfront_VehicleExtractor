# -*- coding: utf-8 -*-
"""把 PyInstaller 的 onedir 产物整理成一个可直接分发的压缩包。

- 把中英 README 和使用说明放进 exe 同级目录
- 整目录打成 zip（保留目录结构，解压即用）
"""
import io
import os
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
MW = HERE
DIST = os.path.join(os.path.dirname(HERE), "exe")
NAME = "ModernWarfront_VehicleExtractor"
APP = os.path.join(DIST, NAME)
OUT = os.path.join(os.path.dirname(HERE), "ModernWarfront_VehicleExtractor_exe.zip")

NOTE = """Modern Warfront 载具模型提取工具  V1.2 2026.9.18 — 免安装版
====================================================================

双击 ModernWarfront_VehicleExtractor.exe 就能用，不用装 Python，也不用装依赖。
（会有一个黑色控制台窗口一闪，被程序自己藏掉了；界面在「日志」页看输出。）

这个包不用装任何东西
--------------------
exe 里已经带了 UnityPy / Pillow / numpy / texture2ddecoder 等依赖，
目标机器不需要装 Python。（源码包才需要先装依赖，见 README。）

第一次用怎么走
--------------
界面默认停在「提取模型」页，两步：

  第一步  选一个**空的文件夹**当「解包工作目录」；
          选 APK 文件 —— 但如果这个工作目录里已经有解包结果
          （catalog.json + bundles/data.unity3d），APK 可以留空，会跳过解包；
          点「解包 APK」。会解出 catalog.json、4809 个 bundle 和 data.unity3d，
          解完工作目录里才有东西，下面的载具列表也才会出现。
  第二步  选「模型输出目录」；
          勾「载具类别」（坦克 / 固定翼 / 直升机）；
          选「导出范围」——默认「指定载具」，在搜索框输名字、在列表里勾选；
          点「提取模型」。

三处路径都没有默认值，留空点按钮会提示，不会偷偷用某个写死的路径。

命令行（一般用不上）
--------------------
exe 内置了脚本分发，所以命令行也能跑单个工具：

    ModernWarfront_VehicleExtractor.exe --run export_tanks.py --work <工作目录> ^
        --out <输出目录> --kind air
    ModernWarfront_VehicleExtractor.exe --run extract_bundles.py --apk game.apk --work D:\\work
    ModernWarfront_VehicleExtractor.exe --run build_index.py --catalog D:\\work\\catalog.json --out D:\\work
    ModernWarfront_VehicleExtractor.exe --run export_tanks.py --out D:\\out --only T90A --turret 0,0.05,-0.1
    ModernWarfront_VehicleExtractor.exe --run blender_shot.py model.obj out.png

`--run` 后面跟的就是包内脚本名，其余参数和脚本本身一致。
不带 `--run` 就直接开界面。

炮塔 / 炮管微调
---------------
某辆车的炮塔或炮管位置不对，就打开「微调」页：炮塔和炮管各有前后(Z) /
左右(X) / 上下(Y) 三对 ± 按钮，步长 0.01~0.5，改一下中间的预览实时跟着动。
数值单位就是导出的 OBJ 单位（已经 ×7，约等于米）。

外观和残骸共用同一套偏移量。

数值按车名存在 exe 旁边的 tweaks.json 里，以后全量导出会自动带上。
「炮塔」= 名字里含 Turret 的部件，「炮管」= Barrel / Gun，机枪不算在内；
默认炮管跟着炮塔一起动（炮是装在炮塔上的）。

LOD
---
游戏按远近切换简化模型，LOD0 最精细。提取页和重导页都有「LOD ○0 ○1 ○2」三个
单选：**选哪档就只导哪档**，各自一个 OBJ。LOD0 是 <名字>.obj，LOD1/2 带 _LODn
后缀（<名字>_LOD1.obj 等），残骸在对应名字后加 _Wreck。三档各自都是完整的一台车，
不是拼接关系。

Blender 出图
------------
可选功能。「Blender 出图」按钮会去找本机的 Blender
（D:\\Blender Foundation\\*、C:\\Program Files\\Blender Foundation\\* 或 PATH），
也可以用环境变量 BLENDER_EXE 指定。没装 Blender 只影响出图，其它功能照常。

详细说明
--------
README.md（中文）/ README_EN.md（英文）—— 用法在前，原理在后，
含引擎内部拼装规则和踩过的坑。
"""

NOTE_EN = """Modern Warfront Vehicle Extractor - portable build
==================================================

Double-click ModernWarfront_VehicleExtractor.exe. No Python and no dependencies
need to be installed. (A black console window flashes up and is hidden by the
program itself; the same output is available on the Log tab.)

Nothing to install
------------------
The exe already bundles UnityPy / Pillow / numpy / texture2ddecoder, so the
target machine needs no Python at all. (Only the source package requires
installing dependencies first - see the README.)

First run, step by step
-----------------------
The UI opens on the Extract tab and works in two steps:

  Step 1  Pick an EMPTY folder as the "work dir".
          Pick the APK file - UNLESS the work dir already holds unpacked
          data (catalog.json + bundles/data.unity3d), in which case the APK
          may be left blank and unpacking is skipped.
          Click "Unpack APK". This writes catalog.json, 4809 bundles and
          data.unity3d into that folder - only after this does the vehicle list
          below have anything to show.
  Step 2  Pick the "model output dir".
          Tick the vehicle kinds (Tanks / Jets / Helicopters).
          Pick the export scope - it defaults to "Picked": type a name in the
          search box and tick vehicles in the list.
          Click "Extract".

None of the three paths has a default value. Clicking a button with a field
empty shows a prompt instead of silently using some hard-coded path.

Models are exported scaled x7 by default, which turns game units into roughly
real-world metres (one game unit is about 1/7 m). Untick "Scale x7" in the UI, or
pass --scale 1 on the command line, to keep the raw game units.

Command line (rarely needed)
----------------------------
The exe has a built-in script dispatcher, so single tools can be run as well:

    ModernWarfront_VehicleExtractor.exe --run export_tanks.py --work <work dir> ^
        --out <output dir> --kind air
    ModernWarfront_VehicleExtractor.exe --run extract_bundles.py --apk game.apk --work D:\\work
    ModernWarfront_VehicleExtractor.exe --run build_index.py --catalog D:\\work\\catalog.json --out D:\\work
    ModernWarfront_VehicleExtractor.exe --run export_tanks.py --out D:\\out --only T90A --turret 0,0.05,-0.1
    ModernWarfront_VehicleExtractor.exe --run blender_shot.py model.obj out.png

The name after --run is simply a script bundled inside the exe; every other
argument is the same as for that script. Run the exe with no arguments to open
the UI.

Tweaking the turret / gun barrel
--------------------------------
If a vehicle's turret or gun barrel comes out misplaced, open the "Tweak" tab:
each of turret and gun has a +/- pair for front-back (Z), left-right (X) and
up-down (Y), with a 0.01-0.5 step, and the preview in the middle updates live.
Units are the exported OBJ units (already x7, so roughly metres).

Intact and wreck models share the same offsets.

Values are stored per vehicle in tweaks.json next to the exe, so later full
exports pick them up automatically. "Turret" means parts whose name contains
Turret; "gun" means Barrel / Gun, with machine guns excluded. By default the gun
follows the turret, since the gun is mounted in the turret.

LOD
---
The game swaps to simpler models with distance; LOD0 is the most detailed. Both
the extract tab and the re-export tab have a "LOD 0 / 1 / 2" radio group: the
chosen level is the only one exported, into its own OBJ. LOD0 is <name>.obj,
LOD1/2 carry a _LODn suffix (<name>_LOD1.obj and so on), and the wreck adds
_Wreck to the same name. Each level is a complete vehicle, not a slice.

Blender renders
---------------
Optional. The "Blender render" button looks for a local Blender install
(D:\\Blender Foundation\\*, C:\\Program Files\\Blender Foundation\\* or PATH);
you can also point at it with the BLENDER_EXE environment variable. Without
Blender only the rendering feature is unavailable - everything else still works.

More detail
-----------
README.md (Chinese) / README_EN.md (English) - usage first, internals after,
including the engine's assembly rules and every pitfall hit along the way.
"""


def main():
    if not os.path.isdir(APP):
        raise SystemExit("没有找到构建产物：%s（先跑 build_exe.py）" % APP)
    for f in ("README.md", "README_EN.md", "VERSION.txt"):
        src = os.path.join(MW, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(APP, f))
    io.open(os.path.join(APP, "使用说明.txt"), "w", encoding="utf-8").write(NOTE)
    io.open(os.path.join(APP, "Instructions_EN.txt"), "w",
            encoding="utf-8").write(NOTE_EN)
    # 清掉旧版本留下的名字，免得打包目录里堆残留
    for stale in ("使用说明_EN.txt", "Instructions.txt"):
        p = os.path.join(APP, stale)
        if os.path.exists(p):
            try:
                os.remove(p)
                print("清掉旧文件:", stale)
            except OSError:
                pass

    try:
        if os.path.exists(OUT):
            os.remove(OUT)
    except PermissionError:
        # Windows 上资源管理器/杀软可能正占着这个 zip，换个名字继续
        alt = OUT[:-4] + "_new.zip"
        if os.path.exists(alt):
            try:
                os.remove(alt)
            except PermissionError:
                pass
        print("原压缩包被占用，改写到 %s" % alt)
        globals()["OUT"] = alt
    n = 0
    total = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for r, _d, fs in os.walk(APP):
            for f in fs:
                p = os.path.join(r, f)
                z.write(p, os.path.join(NAME, os.path.relpath(p, APP)))
                n += 1
                total += os.path.getsize(p)
    print("打包 -> %s" % OUT)
    print("  %d 个文件, 原始 %.0f MB, 压缩后 %.0f MB"
          % (n, total / 2 ** 20, os.path.getsize(OUT) / 2 ** 20))
    print("  入口: %s\\%s.exe" % (NAME, NAME))


if __name__ == "__main__":
    main()
