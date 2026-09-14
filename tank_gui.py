# -*- coding: utf-8 -*-
"""Modern Warfront 载具模型提取工具箱（GUI）。

一个窗口里做完浏览 → 检查 → 重导：

  1. 浏览   左侧按国家/车名列出全部 223 辆，双击载入。
  2. 三维预览  带贴图软件渲染，左键旋转、滚轮缩放、右键平移；
             可切外观/残骸、可只看某个部件（排查错位特别有用）。
  3. 贴图   右侧贴图墙，双击放大看原图。
  4. 部件    manifest 里的部件表（网格名/子网格号/顶点/面数/材质/UV 变换），
             点一行即单独渲染该部件。
  5. 重导    勾选车辆或用「随机 N 辆」，选 LOD / 去伪装网，后台跑 export_tanks.py，
             输出实时打印；单车的炮塔 / 炮管位置可以在「微调」页推一下。

usage:  python tank_gui.py                打开窗口
        python tank_gui.py --selftest     建好窗口后立刻退出（自检）
        python tank_gui.py --shot out.png 载入首辆车渲染一张图后退出
"""
from __future__ import print_function

import json
import math
import os
import queue
import random
import subprocess
import sys
import threading
import traceback

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import numpy as np
from PIL import Image, ImageDraw, ImageTk

import part_groups as PG          # 炮塔/炮管部件判定（导出脚本共用同一份）

FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    # PyInstaller：脚本/资源被解到 _MEIPASS，用户可见的目录是 exe 所在处
    HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = HERE
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

MW = HERE
# 默认的模型输出目录：打包成 exe 时在 exe 旁边，源码运行时在脚本目录的上一级
_OUT_BASE = APP_DIR if FROZEN else os.path.dirname(APP_DIR)
TANKS_DEFAULT = os.path.join(_OUT_BASE, "MW_Tanks")
PY = sys.executable

# 子进程要用的第三方库（模块名, pip 包名）。缺了就明确报出来 ——
# 否则日志里只有一句 "No module named 'UnityPy'"，看不出该干什么。
DEPS = (("UnityPy", "UnityPy"), ("PIL", "Pillow"), ("numpy", "numpy"),
        ("texture2ddecoder", "texture2ddecoder"))


def missing_deps():
    miss = []
    for mod, pkg in DEPS:
        try:
            __import__(mod)
        except Exception:
            miss.append((mod, pkg))
    return miss


# APK 待过的几个位置，找不到再让用户手选
APK_HINTS = (
    r"E:\modern_warfront_0.23.2.12034397.apk",
    r"D:\modern_warfront_0.23.2.12034397.apk",
)

# 逐车的炮塔/炮管微调值存这儿（按车名），全量导出时由 --tweaks 带进去
TWEAK_FILE = os.path.join(APP_DIR, "tweaks.json")


def load_tweaks():
    try:
        # utf-8-sig：记事本存盘默认带 BOM，普通 utf-8 会读不了
        d = json.load(open(TWEAK_FILE, encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_tweaks(data):
    try:
        with open(TWEAK_FILE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
        return True
    except OSError:
        return False


def work_dir_state(work):
    """看工作目录里是不是已经有解包好的东西。

    返回 (是否就绪, 说明)。就绪 = catalog.json + bundles/data.unity3d 都在，
    这时**不需要再选 APK**，直接建索引 / 导出即可。
    """
    if not work:
        return False, "未设置"
    data = os.path.join(work, "bundles", "data.unity3d")
    cat = os.path.join(work, "catalog.json")
    if not os.path.exists(data):
        return False, "缺 bundles/data.unity3d"
    if not os.path.exists(cat):
        return False, "缺 catalog.json"
    return True, "已解包"



# ------------------------------------------------------------------ 多语言
# 界面文案用中文当键：tr("中文") 在英文模式下查表，查不到就原样返回。
# 好处是不用给每句话起 key，漏翻也只是显示中文，不会崩。
LANG = "zh"
EN = {
    "Modern Warfront 载具模型提取工具箱": "Modern Warfront Vehicle Extractor",
    "提取模型": "Extract",
    "部件": "Parts",
    "贴图": "Textures",
    "重导": "Re-export",
    "日志": "Log",
    "车辆库": "Library",
    "随机一辆": "Random",
    "重扫输出目录": "Rescan output dir",
    "（左侧选一辆车）": "(pick a vehicle on the left)",
    "实体": "Solid",
    "带光照的实体模型": "Shaded solid model",
    "线框": "Wire",
    "残骸": "Wreck",
    "复位视角": "Reset view",
    "Blender 出图": "Blender render",
    "只看整机": "Whole vehicle",
    "停止当前任务": "Stop task",
    "日志见「日志」页": "see the Log tab",
    "空闲": "idle",
    "准备中…": "preparing…",
    "全部完成": "all done",
    "完成": "done",
    "启动中": "starting",
    "已停止": "stopped",
    "当前没有在跑的任务": "no task is running",
    "开始导出": "Export",
    "微调": "Tweak",
    "炮塔微调": "Turret",
    "炮管微调": "Gun barrel",
    "前后": "Front/back",
    "左右": "Left/right",
    "上下": "Up/down",
    "Z 轴": "Z axis",
    "X 轴": "X axis",
    "Y 轴": "Y axis",
    "步长": "Step",
    "炮管跟随炮塔": "Gun follows turret",
    "不跟随": "not following",
    "归零": "Reset",
    "导出此车": "Export this one",
    "当前载具：%s": "Current vehicle: %s",
    "当前载具：%s（%s）": "Current vehicle: %s (%s)",
    "外观": "intact",
    "单位就是导出的 OBJ 单位（已 ×7，约等于米）。\n"
    "前后 = Z 轴，左右 = X 轴，上下 = Y 轴；改一下中间预览就会跟着动。\n"
    "炮塔 = 名字里含 Turret 的部件；炮管 = Barrel / Gun，"
    "机枪（Machinegun）不算在内。\n"
    "外观和残骸共用同一套偏移量：切到残骸时也按这套走。\n"
    "微调值按车名记在脚本目录的 tweaks.json，"
    "以后全量导出会自动带上。":
        "Units are the exported OBJ units (already x7, so roughly metres).\n"
        "Front/back = Z, left/right = X, up/down = Y; the preview updates as you "
        "change them.\n"
        "Turret = parts whose name contains Turret; gun = Barrel / Gun, with "
        "machine guns excluded.\n"
        "The numbers are how far to move **on top of the current OBJ**: once you "
        "export, the offset is written into the file and these reset to 0 without "
        "the model moving.\n"
        "Intact and wreck share the same values; stored per vehicle in "
        "tweaks.json, so later full exports pick them up automatically.",
    "（在左侧车辆库里选一辆）": "(pick one in the library on the left)",
    "受影响的部件：炮塔 %d 个，炮管 %d 个（共 %d 个部件）":
        "Parts affected: %d turret, %d gun (of %d parts)",
    "；这个 OBJ 里已烘入 炮塔(%.2f, %.2f, %.2f) 炮管(%.2f, %.2f, %.2f)，"
    "上面的数值是在它基础上再挪":
        "; this OBJ already has turret(%.2f, %.2f, %.2f) gun(%.2f, %.2f, %.2f) baked "
        "in - the numbers above are applied on top of that",
    "导出 %s（带微调）": "Export %s (with tweaks)",
    "微调后导出": "Export with tweaks",
    "导出完成 —— 偏移已经写进 OBJ，预览按实际文件显示":
        "export done - the offsets are baked into the OBJ; the preview now shows "
        "the file as-is",
    "[警告] 写不了 %s，微调值这次不保存。\n":
        "[warning] cannot write %s - tweaks will not be saved this time.\n",
    "出预览图": "Make previews",
    "预览图": "Previews",
    "重新导出": "Re-export",
    "Blender 批量出图": "Blender batch render",
    "生成预览图": "Previews",
    "全部": "All",
    "随机": "Random",
    "指定载具": "Picked",
    "导出范围": "Scope",
    "载具类别": "Vehicle kind",
    "坦克": "Tanks",
    "固定翼": "Jets",
    "直升机": "Helicopters",
    "含 LOD1/2": "Include LOD1/2",
    "缩放到 7 倍": "Scale x7",
    "缩放到 7 倍：1 游戏单位 ≈ 1/7 米，×7 后≈米制"
    "（豹2A6MC2 得 11.01 m，真车 10.97 m）；取消则保持原始单位。":
        "Scale x7: one game unit is about 1/7 m, so x7 gives metres "
        "(Leopard2A6MC2 -> 11.01 m, real tank 10.97 m). Untick to keep raw units.",
    "种子：同一数字抽到同一批。含 LOD1/2：LOD1/2 与 LOD0 重叠，一般不用。":
        "Seed: same number, same batch. Include LOD1/2: they overlap LOD0, rarely useful.",
    "缩放到 7 倍：游戏里 1 单位 ≈ 1/7 米，×7 之后基本就是米制尺寸。":
        "Scale x7: one game unit is about 1/7 metre, so x7 gives roughly "
        "real-world metres.",
    "不要伪装网": "No camo net",
    "提取时顺带做": "Also do",
    "解析 catalog 建立索引（解包时做，列表要靠它）":
        "Build catalog index (during unpack; the list needs it)",
    "导出模型": "Export models",
    "出预览图（较慢）": "Make previews (slow)",
    "辆  种子": "veh.  seed",
    "进度与停止在右下角；日志见「日志」页":
        "Progress and Stop are at the bottom right; see the Log tab",
    "APK 文件（必选）": "APK file (required)",
    "APK 文件（工作目录已就绪，可留空）": "APK file (work dir ready - may be blank)",
    "· 还没解包（要先选 APK）": "\u00b7 not unpacked yet (pick an APK)",
    "[跳过解包] 工作目录里已经有解包结果，直接用；APK 可以不填。\n":
        "[skip unpack] the work dir already holds unpacked data; APK can be blank.\n",
    "[跳过解包] %s 里已经有解包结果和索引。\n":
        "[skip unpack] %s already holds unpacked data and an index.\n",
    "这个工作目录已经解包过了，不用再解 —— 直接去第二步提取模型":
        "this work dir is already unpacked - go straight to step 2",
    "缺少工作目录": "No work dir",
    "工作目录里还没有解包结果（缺 catalog.json 或 bundles/data.unity3d），"
    "所以必须先选一个 APK 解包。\n\n"
    "如果已经解包过，把「解包工作目录」指向那个目录就行，APK 可以留空。":
        "The work dir has no unpacked data yet (catalog.json or "
        "bundles/data.unity3d is missing), so an APK is required to unpack first."
        "\n\nIf you already unpacked somewhere, just point the work dir at that "
        "folder - the APK can stay blank.",
    "浏览": "Browse",
    "解包工作目录（必选，建议用空文件夹）":
        "Work dir (required, use an empty folder)",
    "选目录": "Choose dir",
    "第一步：解包 APK（只解包，不导出）":
        "Step 1: unpack the APK (no export)",
    "解包 APK": "Unpack APK",
    "只看 APK 里有什么": "List APK contents",
    "第二步：提取模型": "Step 2: extract models",
    "模型输出目录（必选）": "Model output dir (required)",
    "搜索载具名": "Search",
    "刷新": "Refresh",
    "全选可见": "Select shown",
    "清空": "Clear",
    "已选 0": "0 selected",
    "先解包 APK": "unpack the APK first",
    "已选 %d / 共 %d": "%d / %d selected",
    "部件 / 网格": "Part / mesh",
    "子网格": "Sub",
    "顶点": "Verts",
    "面": "Tris",
    "材质": "Material",
    "UV 变换": "UV xform",
    "选中一行 = 只渲染该部件（再点「只看整机」恢复）":
        "Pick a row to render that part alone (then \"Whole vehicle\")",
    "双击贴图查看原图": "Double-click a texture to open it",
    "车辆（逗号分隔，留空=全部）": "Vehicles (comma separated, blank = all)",
    "解包工作目录（含 catalog_index.json）": "Work dir (holds catalog_index.json)",
    "用提取页的": "Use Extract tab's",
    "用左侧选中": "Use left selection",
    "按名字搜索载具（可多选）": "Search by name (multi-select)",
    "把勾选的车辆填入上面的框": "Put picked vehicles into the box above",
    "Blender 出图（上面填的车）": "Blender render (vehicles above)",
    "提示": "Notice",
    "缺少依赖": "Missing dependencies",
    "[缺少依赖] 没找到：": "[missing dependencies] not found: ",
    "解包 / 导出 / 校验这几步是在子进程里跑的，子进程需要这些 Python 库。":
        "Unpacking / exporting / validating run in child processes, which need "
        "these Python packages.",
    "两条任选其一（在本目录执行）：": "Pick either one (run it in this directory):",
    "不想折腾的话，直接用打包好的 exe（release 里），什么都不用装。":
        "Or simply use the prebuilt exe from the releases - nothing to install.",
    "装好后重启本程序。": "Restart this program afterwards.",
    "缺少依赖：%s（详见日志页）": "missing dependencies: %s (see the Log tab)",
    "解包 / 导出 / 校验要在子进程里跑，需要它们。两条任选其一：":
        "Unpacking / exporting / validating run in child processes and need them. "
        "Pick either one:",
    "参数错误": "Bad parameter",
    "缺少 APK": "No APK",
    "缺少工作目录": "No work dir",
    "缺少输出目录": "No output dir",
    "没有选类别": "No kind selected",
    "没有选择车辆": "No vehicle picked",
    "载入失败": "Load failed",
    "打开失败": "Open failed",
    "关闭": "Close",
    "另存为…": "Save as…",
    "选择 APK": "Select APK",
    "Android 包": "Android package",
    "所有文件": "All files",
    "整机": "whole",
    "无": "none",
    "先选一辆车": "Pick a vehicle first",
    "先在左侧选车（可多选）": "Select vehicles on the left first",
    "先在下面的列表里勾选车辆（可按名字搜索）":
        "Tick vehicles in the list below first",
    "这辆没有残骸模型": "This vehicle has no wreck model",
    "当前没有在跑的任务": "No task is running",
    "还有任务在跑，先点停止或等它结束":
        "A task is still running - stop it or wait",
    "还没设置模型输出目录": "no model output dir set",
    "车辆库为空": "library is empty",
    "只渲染：%s": "showing: %s",
    "显示整机": "showing whole vehicle",
    "扫描：%s": "scanning: %s",
    "车辆库：%d 个载具": "library: %d vehicles",
    "车辆库为空 —— %s": "library is empty - %s",
    "%s   %d 顶点 / %d 面 / %d 组": "%s   %d verts / %d tris / %d groups",
    "出图：%s": "rendered: %s",
    "另存为 %s": "saved as %s",
    "已保存 %s": "saved %s",
    "没有产出图片：%s": "no image produced: %s",
    "解包 APK（不导出模型）": "unpack APK (no export)",
    "提取模型：解包 APK": "Extract: unpack APK",
    "查看 APK 内容": "APK contents",
    "解析 catalog 建立索引": "Build catalog index",
    "导出模型（%s）": "Export models (%s)",
    "%d 辆指定": "%d picked",
    "先选一个存在的 APK 文件": "Pick an existing APK file first",
    "先填「解包工作目录」—— 解出来的 catalog 和 bundle 会放这里，载具列表也从这里读。\n建议选一个空文件夹。":
        "Fill in the work dir first - the unpacked catalog and bundles go there, "
        "and the vehicle list is read from there.\nAn empty folder is recommended.",
    "先填「模型输出目录」—— 提取出来的 OBJ / 贴图会写到这里，左侧车辆库也扫这里。":
        "Fill in the model output dir first - the OBJ and textures are written "
        "there, and the library scans it.",
    "先填「模型输出目录」—— 导出/校验/出图都按这个目录来。":
        "Fill in the model output dir first - export/render both use it.",
    "「载具类别」一个都没勾：坦克 / 固定翼 / 直升机。":
        "No vehicle kind is ticked: Tanks / Jets / Helicopters.",
    "随机数量 / seed 必须是整数": "Random count / seed must be integers",
    "导出范围选了「指定载具」，但一辆都没勾选。\n\n· 在「搜索车名」框里输名字，从下面列表勾选要导出的车\n· 或者改成「随机 N 辆」/「全部」\n· 或者取消勾选「导出模型」只解包不导出":
        "Scope is \u300cPicked\u300d but nothing is ticked.\n\n"
        "\u00b7 type a name in the search box and tick vehicles below\n"
        "\u00b7 or switch to \u300cRandom\u300d / \u300cAll\u300d\n"
        "\u00b7 or untick \u300cExport models\u300d to only unpack",
    "· 还没选工作目录": "\u00b7 no work dir yet",
    "· 还没解包": "\u00b7 not unpacked yet",
    "· 已解包，但缺索引（勾上建索引再点一次）":
        "\u00b7 unpacked, but no index (tick the index option and run again)",
    "· 已就绪（工作目录共 %d 个载具）": "\u00b7 ready (%d vehicles in the work dir)",
    "· 已就绪": "\u00b7 ready",
    "解包完成：工作目录已就绪，可提取 %d 个载具":
        "unpacked: work dir ready, %d vehicles available",
    "解包完成，但没有索引 —— 勾上「解析 catalog 建立索引」再解一次":
        "unpacked, but there is no index - tick \u300cBuild catalog index\u300d and run again",
    "这个目录里没有模型：": "no models in this directory:",
    "但解包结果还在（%s\\bundles），可以直接提取：":
        "but the unpacked data is still at (%s\\bundles), you can extract directly:",
    "  · 「提取模型」页 → 选好类别和范围 → 点「提取模型」":
        "  \u00b7 Extract tab \u2192 pick kind and scope \u2192 click Extract",
    "  · 或「重导」页 → 输出目录填 %s → 点开始导出":
        "  \u00b7 or Re-export tab \u2192 set output dir to %s \u2192 click Export",
    "也找不到解包结果（%s\\bundles\\data.unity3d）。":
        "and no unpacked data was found at (%s\\bundles\\data.unity3d).",
    "到「提取模型」页选 APK，点上面的「解包 APK」。":
        "Open the Extract tab, pick the APK and click \u300cUnpack APK\u300d.",
    "「提取模型」页还没填解包工作目录。":
        "The work dir is not set on the Extract tab.",
    "选一个空文件夹当工作目录，再点「解包 APK」，模型提取好之后这里就会列出来。":
        "Pick an empty folder as the work dir and click \u300cUnpack APK\u300d; "
        "vehicles will show up here after extraction.",
    "还没选「模型输出目录」。\n\n到「提取模型」页选一个文件夹（模型会写到这里），\n提取完成或点左侧「重扫输出目录」之后，这里就会列出载具。":
        "No model output dir selected.\n\n"
        "Pick a folder on the Extract tab (models are written there);\n"
        "vehicles will be listed here after extraction, or click "
        "\u300cRescan output dir\u300d.",
    "种子：同一数字每次抽到同一批（复现抽样用）。含 LOD1/2：LOD0 最精细，勾上会把 LOD1/LOD2 也写进同一个 OBJ 并和 LOD0 重叠，一般不用。":
        "Seed: the same number always picks the same batch (reproducible). "
        "Include LOD1/2: LOD0 is the most detailed; ticking it also writes "
        "LOD1/LOD2 into the same OBJ where they overlap LOD0 - rarely useful.",
    "含 LOD1/2：LOD 是游戏按远近切换的简化模型，LOD0 最精细；勾上会把 LOD1/LOD2 一起写进同一个 OBJ，它们和 LOD0 重叠，一般不用。":
        "Include LOD1/2: LODs are the game's distance-based simplified models; "
        "LOD0 is the most detailed. Ticking it writes LOD1/LOD2 into the same "
        "OBJ where they overlap LOD0 - rarely useful.",
    "随机种子：同一个数字每次抽到同一批，换个数字换一批（用来复现抽样）。":
        "Seed: the same number always picks the same batch (reproducible).",
    "载具列表读的是工作目录里的 catalog_index.json —— 先解包（并勾建索引）才会列出来，解包一次后一直可用。":
        "The vehicle list comes from catalog_index.json in the work dir - "
        "unpack first (with the index option) and it stays available.",
    "说明：导出用 mw\\export_tanks.py；随机抽样只会覆盖抽样到的车，不会动其它目录。\nBlender 出图走 Workbench + MTL 贴图，单张约 5–15 秒，输出到每辆车目录下的 render.png。":
        "Export uses mw\\export_tanks.py; random sampling only overwrites the "
        "sampled vehicles.\nBlender render uses Workbench + MTL textures, "
        "about 5-15 s each, written to render.png in each vehicle folder.",
    "语言 / Language": "语言 / Language",
    "界面语言": "Interface language",
    "切换后整个界面会重建，已填的路径和选择会保留。":
        "The whole UI is rebuilt on switch; filled paths and selections are kept.",
    "本页只切换界面语言。脚本自身的输出（控制台 / 日志页）仍是中文。":
        "This page only switches the UI language. Script output (console / Log tab) stays Chinese.",
}


def tr(s):
    """界面文案翻译：中文模式下原样返回。"""
    if LANG == "zh":
        return s
    return EN.get(s, s)


BG = "#20242a"
BG2 = "#282d35"
FG = "#d8dde4"
ACC = "#ffd45e"
LIGHT = np.array([0.42, 0.78, 0.46])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
# 实体预览是否剔除背面（测试时可关掉对比）。省掉约一半多边形，且模型是闭合的话
# 看不出来 —— 实测轮廓只差 0.23%。
CULL_BACKFACE = True
PROG_RE = __import__("re").compile(r"PROGRESS\s+(\d+)\s+(\d+)")


# ---------------------------------------------------------------- 模型载入
class TankModel(object):
    """One exported tank: geometry, per-face group + material, textures."""

    def __init__(self, obj_path):
        self.obj_path = obj_path
        self.dir = os.path.dirname(obj_path)
        self.name = os.path.splitext(os.path.basename(obj_path))[0]
        self.verts = np.zeros((0, 3))
        self.uvs = None
        self.faces = np.zeros((0, 3, 2), dtype=np.int64)   # (vi, ti) per corner
        self.group_of_face = []
        self.mat_of_face = []
        self.groups = []            # ordered group names
        self.mtl = {}
        self._tex = {}
        self.load()

    # -- geometry
    def load(self):
        verts, uvs, faces, groups, mats = [], [], [], [], []
        cur_g, cur_m = "?", None
        with open(self.obj_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("v "):
                    p = line.split()
                    verts.append((float(p[1]), float(p[2]), float(p[3])))
                elif line.startswith("vt "):
                    p = line.split()
                    uvs.append((float(p[1]), float(p[2])))
                elif line.startswith("g ") or line.startswith("o "):
                    cur_g = line.split(None, 1)[1].strip()
                elif line.startswith("usemtl "):
                    cur_m = line.split(None, 1)[1].strip()
                elif line.startswith("f "):
                    idx = []
                    for tok in line.split()[1:]:
                        b = tok.split("/")
                        vi = int(b[0]) - 1
                        ti = int(b[1]) - 1 if len(b) > 1 and b[1] else -1
                        idx.append((vi, ti))
                    for k in range(1, len(idx) - 1):
                        faces.append((idx[0], idx[k], idx[k + 1]))
                        groups.append(cur_g)
                        mats.append(cur_m)
        self.verts = np.asarray(verts, dtype=np.float64)
        self.base_verts = self.verts            # 原始顶点，微调时在它上面加偏移
        # 炮塔/炮管偏移的当前值（set_tweaks 会更新；预览缓存键要用到）
        self.tweak = {"turret": (0.0, 0.0, 0.0), "gun": (0.0, 0.0, 0.0), "follow": True}
        self.tweak_total = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), True)
        self._baked = self._read_baked()        # 文件里已经烘进去的偏移
        self.uvs = np.asarray(uvs, dtype=np.float64) if uvs else None
        self.faces = np.asarray(faces, dtype=np.int64) if faces else np.zeros((0, 3, 2), np.int64)
        self.group_of_face = groups
        self.mat_of_face = mats
        seen = []
        for g in groups:
            if g not in seen:
                seen.append(g)
        self.groups = seen
        self.mtl = self._load_mtl()
        if len(self.verts):
            self.centre = (self.verts.max(0) + self.verts.min(0)) / 2
            self.span = float((self.verts.max(0) - self.verts.min(0)).max())
        else:
            self.centre = np.zeros(3)
            self.span = 1.0
        self._prepare_render()

    def _prepare_render(self):
        """Per-model arrays and caches used by the rasteriser."""
        n = len(self.faces)
        self._all_idx = np.arange(n, dtype=np.int64)
        self._empty_idx = np.zeros(0, dtype=np.int64)
        self._fi_cache = {}
        self._group_idx = {}
        by_group = {}
        for i, g in enumerate(self.group_of_face):
            by_group.setdefault(g, []).append(i)
        for g, v in by_group.items():
            self._group_idx[g] = np.asarray(v, dtype=np.int64)

    # -- 炮塔 / 炮管微调（实时预览用；导出走 export_tanks 的同一套判定）
    def baked_tweaks(self):
        """这个 OBJ 里**已经烘进去**的炮塔/炮管偏移（导出时写进 manifest 的）。

        导出过的模型顶点本来就带着偏移了，预览再按 tweaks.json 叠一次就成双倍 ——
        双击预览时炮塔炮管会「在已经对的位置上又挪一遍」。所以预览要叠的是
        「想要的总量 − 已经烘进去的量」。
        """
        return self._baked

    def set_tweaks(self, turret=(0.0, 0.0, 0.0), gun=(0.0, 0.0, 0.0), follow=True,
                   total=None):
        """把偏移量叠到炮塔/炮管部件的顶点上。传全 0 就还原。

        turret/gun 是**这次要额外叠上去的增量**；total 是界面上显示的总量
        （默认和增量相同）。
        """
        self.tweak = {"turret": tuple(turret), "gun": tuple(gun), "follow": bool(follow)}
        self.tweak_total = total or (tuple(turret), tuple(gun), bool(follow))
        if not len(self.base_verts):
            return
        if not any(self.tweak["turret"]) and not any(self.tweak["gun"]):
            self.verts = self.base_verts
            return
        # 每个 group 一个偏移 -> 每个面一个偏移 -> 摊到面的三个顶点上
        table = {}
        for g in self.groups:
            table[g] = np.asarray(PG.offset_for(g, self.tweak["turret"],
                                               self.tweak["gun"], self.tweak["follow"]))
        zero = np.zeros(3)
        per_face = np.asarray([table.get(g, zero) for g in self.group_of_face])
        disp = np.zeros_like(self.base_verts)
        vi = self.faces[:, :, 0].reshape(-1)
        disp[vi] = np.repeat(per_face, 3, axis=0)
        self.verts = self.base_verts + disp

    def _load_mtl(self):
        out = {}
        p = os.path.splitext(self.obj_path)[0] + ".mtl"
        if not os.path.exists(p):
            return out
        cur = None
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("newmtl "):
                    cur = line.split(None, 1)[1].strip()
                    out[cur] = None
                elif line.startswith("map_Kd ") and cur:
                    out[cur] = line.split(None, 1)[1].strip()
        return out

    def texture(self, mat):
        if mat in self._tex:
            return self._tex[mat]
        img = None
        rel = self.mtl.get(mat)
        if rel:
            p = os.path.join(self.dir, rel.replace("\\", "/"))
            if os.path.exists(p):
                img = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)
        self._tex[mat] = img
        return img

    def texture_files(self):
        d = os.path.join(self.dir, "textures")
        if not os.path.isdir(d):
            return []
        return sorted(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(".png"))

    def manifest(self):
        p = os.path.join(self.dir, "manifest.json")
        if not os.path.exists(p):
            return {}
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return {}

    def _read_baked(self):
        """从 manifest 读「这个 OBJ 已经烘进去的偏移」。没记录就当 0。"""
        rec = (self.manifest().get("wreck" if self.name.endswith("_Wreck")
                                   else "intact") or {})
        return (tuple(rec.get("turret_offset") or (0.0, 0.0, 0.0)),
                tuple(rec.get("gun_offset") or (0.0, 0.0, 0.0)),
                bool(rec.get("gun_follows_turret", True)))

    # -- render
    #  Painter's-algorithm rasteriser built on PIL polygon fills.  The previous
    #  per-pixel numpy loop cost ~2.5 s per full-detail frame (and ~1.3 s even
    #  decimated while dragging); PIL costs ~20 us per polygon, so the polygon
    #  budget - not the resolution - is the dial that matters.
    def _face_index(self, only_group):
        key = only_group
        hit = self._fi_cache.get(key)
        if hit is not None:
            return hit
        idx = self._all_idx
        if only_group is not None:
            idx = self._group_idx.get(only_group, self._empty_idx)
        self._fi_cache[key] = idx
        return idx

    def render(self, yaw, pitch, zoom, pan, size, mode="solid", only_group=None,
               max_tris=0, bg_colour=(26, 28, 34)):
        # size 可以是整数（正方形）或 (w, h) —— 中间画布是长方形的，填满才够大
        if isinstance(size, (tuple, list)):
            w, h = int(size[0]), int(size[1])
        else:
            w = h = int(size)
        w, h = max(64, w), max(64, h)
        img = Image.new("RGB", (w, h), bg_colour)
        if len(self.faces) == 0:
            return img
        # 注意：这里**不再按面数抽稀**。以前拖动时只画 1/N 的面，等于把模型
        # 打个稀烂（就是「破面」）；面多的时候靠背面剔除和分辨率来省，不丢面。
        fi = self._face_index(only_group)
        if len(fi) == 0:
            return img

        a, b = math.radians(yaw), math.radians(pitch)
        ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
        ry = np.array([[ca, 0, sa], [0, 1, 0], [-sa, 0, ca]])
        rx = np.array([[1, 0, 0], [0, cb, -sb], [0, sb, cb]])
        pts = (self.verts - self.centre) @ (ry.T @ rx.T)
        ref = min(w, h)                      # 按短边算缩放，长边自然留白
        sc = (ref * 0.62) / max(self.span / 2, 1e-6) * zoom
        px = pts[:, 0] * sc + w / 2 + pan[0]
        py = -pts[:, 1] * sc + h / 2 + pan[1]

        f = self.faces[fi]
        ia, ib, ic = f[:, 0, 0], f[:, 1, 0], f[:, 2, 0]
        x0, y0 = px[ia], py[ia]
        x1, y1 = px[ib], py[ib]
        x2, y2 = px[ic], py[ic]

        v0, v1, v2 = pts[ia], pts[ib], pts[ic]
        nrm = np.cross(v1 - v0, v2 - v0)
        ln = np.linalg.norm(nrm, axis=1, keepdims=True)
        ln[ln == 0] = 1
        shade = np.abs((nrm / ln) @ LIGHT)

        # 有向面积：负的一侧朝向镜头。实体模式把背面剔掉 —— 能省掉将近一半
        # 多边形（实测轮廓只差 0.23%），顺带也少一半画家算法的排序错位。
        # 线框模式不剔，否则背面线条都没了。
        signed = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        minx = np.minimum(np.minimum(x0, x1), x2)
        maxx = np.maximum(np.maximum(x0, x1), x2)
        miny = np.minimum(np.minimum(y0, y1), y2)
        maxy = np.maximum(np.maximum(y0, y1), y2)
        onscreen = (maxx >= 0) & (minx <= w) & (maxy >= 0) & (miny <= h)
        keep = onscreen & (signed <= 0) if (mode != "wire" and CULL_BACKFACE) else onscreen
        # 万一某辆车的绕向是反的，剔除后剩不下东西 —— 那就这一帧不剔，别把模型剃光
        if mode != "wire" and CULL_BACKFACE and keep.sum() < 0.25 * len(signed):
            keep = onscreen
        keep = keep & (np.abs(signed) >= 1.0)   # 亚像素三角形不值得付一次 PIL 调用
        if not keep.all():
            k = np.nonzero(keep)[0]
            if len(k) == 0:
                return img
            x0, y0, x1, y1, x2, y2 = x0[k], y0[k], x1[k], y1[k], x2[k], y2[k]
            shade = shade[k]
            f = f[k]

        zc = pts[f[:, :, 0], 2].mean(axis=1)
        order = np.argsort(zc)            # far to near
        tri = np.stack([x0[order], y0[order], x1[order], y1[order],
                        x2[order], y2[order]], axis=1).tolist()
        sh = shade[order]
        dr = ImageDraw.Draw(img)
        if mode == "wire":
            line = dr.line
            grey = (205, 205, 205)
            for t in tri:
                line([(t[0], t[1]), (t[2], t[3])], fill=grey)
                line([(t[2], t[3]), (t[4], t[5])], fill=grey)
                line([(t[4], t[5]), (t[0], t[1])], fill=grey)
            return img

        # 贴图不在这里渲染（实时预览只有实体/线框），带贴图的成品图走 Blender
        g = np.clip(30 + 210 * np.power(sh, 1.3), 0, 255).astype(np.uint8)
        rgb = np.stack([g, (g * 0.95).astype(np.uint8), (g * 0.86).astype(np.uint8)],
                       axis=1)
        # PIL 的 fill 必须是 tuple，tolist() 出来的是 list —— 先转好，
        # 比在循环里现搭 (c[0], c[1], c[2]) 便宜
        colours = [tuple(c) for c in rgb.tolist()]
        poly = dr.polygon
        # t 是扁平的 [x0,y0,x1,y1,x2,y2]，PIL 直接收这种序列 ——
        # 比在循环里现搭三个元组快一成
        for i, t in enumerate(tri):
            poly(t, fill=colours[i])
        return img


# Resources/<前缀>/<名> 就是预制体；和 export_tanks.KINDS 保持一致（这里不 import
# export_tanks，因为它会拉起 UnityPy，启动要多花十几秒）
KIND_PREFIX = {"tanks": "Tanks/", "fighters": "Fighters/",
               "helicopters": "Helicopters/"}


def kind_of(name):
    """名字属于哪一类（看后缀，够用了）。"""
    low = name.lower()
    if low.endswith("_fighter") or low.endswith("_fighterter"):
        return "fighters"
    if low.endswith("_helicopter"):
        return "helicopters"
    return "tanks"


def list_tank_names(work, out, kinds=None):
    """按类别列出可提取的载具名：来自 catalog 索引，加上已经导出的。

    kinds=None 表示全部类别（坦克 + 固定翼 + 直升机）。
    """
    prefixes = [KIND_PREFIX[k] for k in (kinds or KIND_PREFIX) if k in KIND_PREFIX]
    if not prefixes:
        prefixes = list(KIND_PREFIX.values())
    names = set()
    ci = os.path.join(work, "catalog_index.json")
    if os.path.exists(ci):
        try:
            for r in json.load(open(ci, encoding="utf-8")):
                p = r.get("path", "")
                if any(p.startswith(pr) for pr in prefixes):
                    names.add(p.split("/")[-1])
        except Exception:
            pass
    if os.path.isdir(out):
        for country in os.listdir(out):
            d = os.path.join(out, country)
            if not os.path.isdir(d):
                continue
            for tank in os.listdir(d):
                if os.path.exists(os.path.join(d, tank, tank + ".obj")) or \
                        os.path.exists(os.path.join(d, tank, "manifest.json")):
                    if not kinds or kind_of(tank) in kinds:
                        names.add(tank)
    return sorted(names)


class TankPicker(tk.Frame):
    """搜索框 + 多选列表：坦克 / 固定翼 / 直升机都能按名字挑。

    extra 是 [(文字, 回调)]，追加到底部那一排（全选可见 / 清空 之后）。
    这样调用方不用再单独占一行按钮，腾出来的高度可以留给列表。
    """

    def __init__(self, master, height=7, kinds_of=None, work_of=None, out_of=None,
                 extra=()):
        tk.Frame.__init__(self, master, bg=BG)
        self.names = []
        self.shown = []
        self.picked = set()
        self._kinds_of = kinds_of        # () -> ["tanks", ...] 或 None=全部
        self._work_of = work_of
        self._out_of = out_of

        row = tk.Frame(self, bg=BG)
        row.pack(fill="x")
        tk.Label(row, text=tr("搜索载具名"), bg=BG, fg=FG).pack(side="left")
        self.search = tk.StringVar()
        tk.Entry(row, textvariable=self.search, bg=BG2, fg=FG, insertbackground=FG,
                 width=16).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(row, text=tr("刷新"), width=5, command=self.refresh).pack(side="left")
        self.search.trace_add("write", lambda *_a: self.refilter())

        body = tk.Frame(self, bg=BG)
        body.pack(fill="x", pady=2)
        self.lb = tk.Listbox(body, height=height, selectmode="extended", exportselection=False,
                             bg=BG2, fg=FG, selectbackground="#4a6b8a",
                             highlightthickness=0, activestyle="none")
        sb = ttk.Scrollbar(body, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        self.lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.lb.bind("<<ListboxSelect>>", self._on_select)

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x")
        ttk.Button(foot, text=tr("全选可见"), command=self.select_all_shown).pack(side="left")
        ttk.Button(foot, text=tr("清空"), command=self.clear).pack(side="left", padx=4)
        for text, cmd in (extra or ()):
            ttk.Button(foot, text=text, command=cmd).pack(side="left", padx=(4, 0))
        self.count = tk.StringVar(value=tr("已选 0"))
        tk.Label(foot, textvariable=self.count, bg=BG, fg="#8fa6c0").pack(side="right")

    # -- data
    def set_names(self, names):
        self.names = list(names)
        self.picked &= set(self.names)
        self.refilter()

    def refresh(self):
        self.set_names(list_tank_names(self._work(), self._out(), self._kinds()))

    def _kinds(self):
        return self._kinds_of() if self._kinds_of else None

    def _work(self):
        if self._work_of:
            return self._work_of()
        app = self.winfo_toplevel()
        return getattr(app, "im_work", tk.StringVar(value="")).get().strip()

    def _out(self):
        if self._out_of:
            return self._out_of()
        app = self.winfo_toplevel()
        return getattr(app, "im_out", tk.StringVar(value="")).get().strip()

    def refilter(self):
        key = self.search.get().strip().lower()
        self.shown = [n for n in self.names if not key or key in n.lower()]
        self.lb.delete(0, "end")
        for n in self.shown:
            self.lb.insert("end", n)
        for i, n in enumerate(self.shown):
            if n in self.picked:
                self.lb.selection_set(i)
        self._update()

    def _on_select(self, _e=None):
        for i, n in enumerate(self.shown):
            if self.lb.selection_includes(i):
                self.picked.add(n)
            else:
                self.picked.discard(n)
        self._update()

    def select_all_shown(self):
        for i, n in enumerate(self.shown):
            self.picked.add(n)
            self.lb.selection_set(i)
        self._update()

    def clear(self):
        self.picked.clear()
        self.lb.selection_clear(0, "end")
        self._update()

    def _update(self):
        # 这一排左侧是「全选可见/清空/…」按钮，右侧只剩一点宽度，文字要短
        if not self.names:
            self.count.set(tr("先解包 APK"))
        else:
            self.count.set(tr("已选 %d / 共 %d") % (len(self.picked), len(self.names)))

    def selected(self):
        return sorted(self.picked)


# ---------------------------------------------------------------- 主窗口
class App(tk.Tk):
    #  预览画质：成本几乎全在 PIL 每次 polygon 调用的固定开销上（约 1.5 us/个），
    #  和分辨率、填充面积基本无关 —— 实测 0.72 分辨率并不比全分辨率快。
    #  所以拖动和静止都用**全分辨率 + 全部面**（丢面就是破面），
    #  只靠背面剔除省掉看不见的那一半。
    SETTLE_MS = 260                  # 停手多久之后重画一次（保险用）

    def __init__(self, root_dir=""):
        tk.Tk.__init__(self)
        self.title(tr("Modern Warfront 载具模型提取工具箱"))
        self.geometry("1560x1000")
        self.minsize(1180, 720)     # 再小右栏就会被挤扁
        self.configure(bg=BG)
        self.root_dir = root_dir
        self.model = None
        self.wreck = tk.BooleanVar(value=False)
        self.mode = tk.StringVar(value="solid")
        self.status = tk.StringVar(value="")
        self.yaw, self.pitch, self.zoom = 35.0, 20.0, 1.0
        self.pan = [0.0, 0.0]
        self._drag = None
        self._after = None
        self._settle = None
        self.only_group = None
        self._photo = None
        self._last_key = None
        self._on_done = None
        self.blend_size = "1600x1000"
        self.logq = queue.Queue()
        self.worker = None
        self._proc = None
        self.phase = tr("空闲")
        self.tex_thumbs = []
        self.im_scope = tk.StringVar(value="picked")
        self.tweaks = load_tweaks()          # 逐车的炮塔/炮管微调（tweaks.json）
        self._build()
        self.scan_library()
        self._refresh_pickers()
        self._sync_scope()
        self._check_deps()
        self.after(120, self._pump_log)

    # ------------------------------------------------------------ 依赖自检
    def _check_deps(self):
        """缺第三方库时给出能照着做的提示，而不是让日志里只剩一句 import 报错。"""
        miss = missing_deps()
        if not miss:
            return
        mods = ", ".join(m for m, _p in miss)
        pkgs = " ".join(sorted({p for _m, p in miss}))
        text = "\n".join([
            "",
            "=" * 66,
            tr("[缺少依赖] 没找到：") + mods,
            "",
            tr("解包 / 导出 / 校验这几步是在子进程里跑的，子进程需要这些 Python 库。"),
            tr("两条任选其一（在本目录执行）："),
            "    python fetch_wheels.py pylibs " + pkgs,
            "    pip install " + pkgs,
            "",
            tr("不想折腾的话，直接用打包好的 exe（release 里），什么都不用装。"),
            tr("装好后重启本程序。"),
            "=" * 66,
            "",
        ])
        self.logq.put(("log", text))
        self.status.set(tr("缺少依赖：%s（详见日志页）") % mods)
        messagebox.showwarning(
            tr("缺少依赖"),
            tr("[缺少依赖] 没找到：") + mods + "\n\n" +
            tr("解包 / 导出 / 校验要在子进程里跑，需要它们。两条任选其一：") + "\n" +
            "    python fetch_wheels.py pylibs " + pkgs + "\n" +
            "    pip install " + pkgs + "\n\n" +
            tr("或者直接用打包好的 exe（release 里），不用装任何东西。"))

    # ------------------------------------------------------------ 布局
    def _build(self):
        self.title(tr("Modern Warfront 载具模型提取工具箱"))
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("TButton", padding=4)
        st.configure("Treeview", background=BG2, fieldbackground=BG2, foreground=FG)

        left = tk.Frame(self, bg=BG, width=290)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text=tr("车辆库"), bg=BG, fg=ACC, anchor="w").pack(fill="x", padx=8, pady=(8, 2))
        self.filter = tk.StringVar()
        e = tk.Entry(left, textvariable=self.filter, bg=BG2, fg=FG, insertbackground=FG)
        e.pack(fill="x", padx=8)
        e.bind("<KeyRelease>", lambda _e: self.refill_tree())
        self.tree = ttk.Treeview(left, show="tree")
        self.tree.pack(fill="both", expand=True, padx=8, pady=6)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_pick)
        bar = tk.Frame(left, bg=BG)
        bar.pack(fill="x", padx=8, pady=(0, 2))
        ttk.Button(bar, text=tr("随机一辆"), command=self.pick_random).pack(side="left")
        ttk.Button(bar, text=tr("重扫输出目录"), command=self.scan_library).pack(side="left", padx=6)
        self.lib_root_lbl = tk.StringVar(value="")
        tk.Label(left, textvariable=self.lib_root_lbl, bg=BG, fg="#8fa6c0", anchor="w",
                 wraplength=270, justify="left").pack(fill="x", padx=8, pady=(0, 8))

        mid = tk.Frame(self, bg=BG)
        # 注意：mid 要等 right 先 pack（见下），否则窗口变窄时右侧面板会被挤扁
        head = tk.Frame(mid, bg=BG)
        head.pack(fill="x", padx=8, pady=(8, 2))
        self.title_lbl = tk.Label(head, text=tr("（左侧选一辆车）"), bg=BG, fg=ACC, anchor="w")
        self.title_lbl.pack(side="left")
        self.canvas = tk.Canvas(mid, bg="#1a1c22", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8)
        self.canvas.bind("<ButtonPress-1>", lambda e: self.begin_drag(e, "orbit"))
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<ButtonPress-3>", lambda e: self.begin_drag(e, "pan"))
        self.canvas.bind("<B3-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-3>", self.end_drag)
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Configure>", lambda _e: self.schedule(delay=10))

        opt = tk.Frame(mid, bg=BG)
        opt.pack(fill="x", padx=8, pady=6)
        for text, val, tip in ((tr("实体"), "solid", tr("带光照的实体模型")), (tr("线框"), "wire", tr("线框"))):
            tk.Radiobutton(opt, text=text, variable=self.mode, value=val, bg=BG, fg=FG,
                           selectcolor=BG2, activebackground=BG,
                           command=self.schedule).pack(side="left")
        tk.Checkbutton(opt, text=tr("残骸"), variable=self.wreck, bg=BG, fg=FG, selectcolor=BG2,
                       activebackground=BG, command=self.load_current).pack(side="left", padx=8)
        ttk.Button(opt, text=tr("复位视角"), command=self.reset_view).pack(side="left", padx=6)
        ttk.Button(opt, text=tr("Blender 出图"), command=self.blender_shot).pack(side="left")
        ttk.Button(opt, text=tr("只看整机"), command=lambda: self.isolate(None)).pack(side="left", padx=6)
        tk.Label(opt, textvariable=self.status, bg=BG, fg="#8fa6c0").pack(side="right")

        right = tk.Frame(self, bg=BG, width=560)
        right.pack(side="right", fill="y")      # 先占住右侧固定宽度
        mid.pack(side="left", fill="both", expand=True)
        right.pack_propagate(False)

        # 全局状态栏：进度条 + 停止。放在 notebook 外面，切到任何一页都看得见，
        # 也免得各页自己塞一套把内容挤出去。
        bar = tk.Frame(right, bg=BG)
        bar.pack(side="bottom", fill="x", padx=6, pady=(0, 8))
        self.prog_lbl = tk.StringVar(value=tr("空闲"))
        tk.Label(bar, textvariable=self.prog_lbl, bg=BG, fg="#cfe0d0",
                 anchor="w").pack(fill="x")
        self.progress = ttk.Progressbar(bar, orient="horizontal", mode="determinate",
                                        maximum=100, value=0)
        self.progress.pack(fill="x", pady=(2, 4))
        brow = tk.Frame(bar, bg=BG)
        brow.pack(fill="x")
        ttk.Button(brow, text=tr("停止当前任务"), command=self.stop_worker).pack(side="left")
        tk.Label(brow, text=tr("日志见「日志」页"), bg=BG, fg="#8fa6c0").pack(side="right")

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True, padx=6, pady=8)
        self.nb = nb
        # 提取模型放在最前面，默认就是选中页
        self.import_tab = self._tab_import(nb)
        self.parts = self._tab_parts(nb)
        self.textab = self._tab_textures(nb)
        self.tweaktab = self._tab_tweak(nb)
        self._tab_export(nb)
        self.log_tab = self._tab_log(nb)
        self.lang_tab = self._tab_lang(nb)
        nb.select(self.import_tab)

    # -- 提取模型页
    def _tab_import(self, nb):
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text=tr("提取模型"))

        self.apk_lbl = tk.StringVar(value=tr("APK 文件（必选）"))
        tk.Label(f, textvariable=self.apk_lbl, bg=BG, fg=ACC,
                 anchor="w").pack(fill="x", padx=6, pady=(8, 0))
        r = tk.Frame(f, bg=BG)
        r.pack(fill="x", padx=6)
        self.im_apk = tk.StringVar(value="")
        tk.Entry(r, textvariable=self.im_apk, bg=BG2, fg=FG,
                 insertbackground=FG).pack(side="left", fill="x", expand=True)
        ttk.Button(r, text=tr("浏览"), command=self.pick_apk).pack(side="left", padx=4)

        tk.Label(f, text=tr("解包工作目录（必选，建议用空文件夹）"), bg=BG, fg=ACC,
                 anchor="w").pack(fill="x", padx=6, pady=(8, 0))
        r = tk.Frame(f, bg=BG)
        r.pack(fill="x", padx=6)
        self.im_work = tk.StringVar(value="")
        we = tk.Entry(r, textvariable=self.im_work, bg=BG2, fg=FG, insertbackground=FG)
        we.pack(side="left", fill="x", expand=True)
        we.bind("<FocusOut>", lambda _e: self._on_work_changed())
        we.bind("<Return>", lambda _e: self._on_work_changed())
        ttk.Button(r, text=tr("选目录"), command=lambda: self.pick_dir(self.im_work)).pack(side="left", padx=4)
        self.im_work.trace_add("write", lambda *_a: self._update_unpack_state())

        # ---- 第一步：只解包 APK（不导出模型） -------------------------------
        tk.Label(f, text=tr("第一步：解包 APK（只解包，不导出）"), bg=BG, fg=ACC,
                 anchor="w").pack(fill="x", padx=6, pady=(10, 0))
        r = tk.Frame(f, bg=BG)
        r.pack(fill="x", padx=6)
        ttk.Button(r, text=tr("解包 APK"), command=self.run_unpack).pack(side="left")
        ttk.Button(r, text=tr("只看 APK 里有什么"),
                   command=self.run_import_list).pack(side="left", padx=6)
        self.unpack_state = tk.StringVar(value="")
        tk.Label(r, textvariable=self.unpack_state, bg=BG, fg="#8fd08f").pack(side="left")
        tk.Label(f, bg=BG, fg="#8fa6c0", justify="left", anchor="w", wraplength=520,
                 text=tr("载具列表读的是工作目录里的 catalog_index.json —— 先解包（并勾建索引）"
                       "才会列出来，解包一次后一直可用。")).pack(fill="x", padx=10, pady=(2, 0))
        # ---- 第二步：提取模型 ---------------------------------------------
        tk.Label(f, text=tr("第二步：提取模型"), bg=BG, fg=ACC,
                 anchor="w").pack(fill="x", padx=6, pady=(10, 0))
        tk.Label(f, text=tr("模型输出目录（必选）"), bg=BG, fg=FG,
                 anchor="w").pack(fill="x", padx=6)
        r = tk.Frame(f, bg=BG)
        r.pack(fill="x", padx=6)
        self.im_out = tk.StringVar(value="")
        tk.Entry(r, textvariable=self.im_out, bg=BG2, fg=FG,
                 insertbackground=FG).pack(side="left", fill="x", expand=True)
        ttk.Button(r, text=tr("选目录"), command=lambda: self.pick_dir(self.im_out)).pack(side="left", padx=4)

        self.im_index = tk.BooleanVar(value=True)
        self.im_export = tk.BooleanVar(value=True)
        self.im_preview = tk.BooleanVar(value=False)
        tk.Label(f, text=tr("提取时顺带做"), bg=BG, fg=FG, anchor="w").pack(fill="x", padx=6,
                                                                   pady=(6, 0))
        for text, var in ((tr("解析 catalog 建立索引（解包时做，列表要靠它）"), self.im_index),
                          (tr("导出模型"), self.im_export),
                          (tr("出预览图（较慢）"), self.im_preview)):
            tk.Checkbutton(f, text=text, variable=var, bg=BG, fg=FG, selectcolor=BG2,
                           activebackground=BG, anchor="w").pack(fill="x", padx=10)

        tk.Label(f, text=tr("载具类别"), bg=BG, fg=ACC, anchor="w").pack(fill="x", padx=6,
                                                                  pady=(8, 0))
        self.im_kind_tanks = tk.BooleanVar(value=True)
        self.im_kind_fighters = tk.BooleanVar(value=False)
        self.im_kind_helicopters = tk.BooleanVar(value=False)
        kr = tk.Frame(f, bg=BG)
        kr.pack(fill="x", padx=8)
        for text, var in ((tr("坦克"), self.im_kind_tanks), (tr("固定翼"), self.im_kind_fighters),
                          (tr("直升机"), self.im_kind_helicopters)):
            tk.Checkbutton(kr, text=text, variable=var, bg=BG, fg=FG, selectcolor=BG2,
                           activebackground=BG,
                           command=self._refresh_pickers).pack(side="left", padx=(0, 8))

        # 选项集中在 opt 里，方便按「导出范围」显示/隐藏车辆搜索框
        opt = tk.Frame(f, bg=BG)
        opt.pack(fill="x")

        r = tk.Frame(opt, bg=BG)
        r.pack(fill="x", padx=10, pady=(4, 0))
        tk.Label(r, text=tr("导出范围"), bg=BG, fg=FG).pack(side="left")
        tk.Radiobutton(r, text=tr("指定载具"), variable=self.im_scope, value="picked", bg=BG, fg=FG,
                       selectcolor=BG2, activebackground=BG,
                       command=self._sync_scope).pack(side="left", padx=(4, 0))
        tk.Radiobutton(r, text=tr("随机"), variable=self.im_scope, value="sample", bg=BG, fg=FG,
                       selectcolor=BG2, activebackground=BG,
                       command=self._sync_scope).pack(side="left")
        self.im_n = tk.StringVar(value="4")
        tk.Entry(r, textvariable=self.im_n, width=4, bg=BG2, fg=FG,
                 insertbackground=FG).pack(side="left", padx=3)
        tk.Label(r, text=tr("辆  种子"), bg=BG, fg=FG).pack(side="left")
        self.im_seed = tk.StringVar(value="7")
        tk.Entry(r, textvariable=self.im_seed, width=5, bg=BG2, fg=FG,
                 insertbackground=FG).pack(side="left", padx=3)
        tk.Radiobutton(r, text=tr("全部"), variable=self.im_scope, value="all", bg=BG, fg=FG,
                       selectcolor=BG2, activebackground=BG,
                       command=self._sync_scope).pack(side="left", padx=(6, 0))

        self.im_scale = tk.BooleanVar(value=True)
        self.im_lods = tk.BooleanVar(value=False)
        self.im_nocamo = tk.BooleanVar(value=False)
        r2 = tk.Frame(opt, bg=BG)
        r2.pack(fill="x", padx=8)
        tk.Checkbutton(r2, text=tr("缩放到 7 倍"), variable=self.im_scale, bg=BG, fg=FG,
                       selectcolor=BG2, activebackground=BG).pack(side="left")
        tk.Checkbutton(r2, text=tr("含 LOD1/2"), variable=self.im_lods, bg=BG, fg=FG,
                       selectcolor=BG2, activebackground=BG).pack(side="left", padx=8)
        tk.Checkbutton(r2, text=tr("不要伪装网"), variable=self.im_nocamo, bg=BG, fg=FG,
                       selectcolor=BG2, activebackground=BG).pack(side="left")
        tk.Label(opt, bg=BG, fg="#8fa6c0", justify="left", anchor="w", wraplength=520,
                 text=tr("缩放到 7 倍：1 游戏单位 ≈ 1/7 米，×7 后≈米制"
                         "（豹2A6MC2 得 11.01 m，真车 10.97 m）；取消则保持原始单位。")
                 ).pack(fill="x", padx=10, pady=(2, 0))
        tk.Label(opt, bg=BG, fg="#8fa6c0", justify="left", anchor="w", wraplength=520,
                 text=tr("种子：同一数字抽到同一批。含 LOD1/2：LOD1/2 与 LOD0 重叠，一般不用。")
                 ).pack(fill="x", padx=10, pady=(2, 0))

        self.pick_wrap = tk.Frame(opt, bg=BG)
        self.picker = TankPicker(self.pick_wrap, height=6, kinds_of=self._im_kinds,
                                 work_of=lambda: self.im_work.get().strip(),
                                 out_of=lambda: self.im_out.get().strip())
        self.picker.pack(fill="x")

        # 提取按钮必须放在 pick_wrap 外面：选「随机 / 全部」时整个列表会被隐藏，
        # 之前把它塞进列表底部那一排，按钮就跟着消失了。
        b = tk.Frame(f, bg=BG)
        b.pack(fill="x", padx=6, pady=(2, 2))
        ttk.Button(b, text=tr("提取模型"), command=self.run_import).pack(side="left")
        tk.Label(b, text=tr("进度与停止在右下角；日志见「日志」页"), bg=BG,
                 fg="#8fa6c0").pack(side="left", padx=8)
        self._sync_scope()
        self._update_unpack_state()
        return f

    def _update_unpack_state(self):
        """把「工作目录是否已解包」直接显示在第一步旁边，并据此决定 APK 还要不要填。

        只做文件存在性判断（便宜）—— 载具数量直接取列表现有的，避免每敲一个字
        都去读一遍 17 MB 的 catalog_index.json。"""
        work = self.im_work.get().strip()
        ready, _why = work_dir_state(work)
        idx = os.path.join(work, "catalog_index.json") if work else ""
        if not work:
            self.unpack_state.set(tr("· 还没选工作目录"))
        elif not ready:
            self.unpack_state.set(tr("· 还没解包（要先选 APK）"))
        elif not os.path.exists(idx):
            self.unpack_state.set(tr("· 已解包，但缺索引（勾上建索引再点一次）"))
        else:
            n = len(self.picker.names) if getattr(self, "picker", None) else 0
            self.unpack_state.set(tr("· 已就绪（工作目录共 %d 个载具）") % n if n else tr("· 已就绪"))
        # 工作目录里已经有解包结果 -> APK 可以不填
        if hasattr(self, "apk_lbl"):
            self.apk_lbl.set(tr("APK 文件（工作目录已就绪，可留空）") if ready
                             else tr("APK 文件（必选）"))

    def _on_work_changed(self):
        """离开工作目录输入框时刷新列表（切目录后列表要跟着换）。"""
        self._refresh_pickers()
        self._update_unpack_state()

    def _sync_scope(self):
        """Only show the vehicle picker when it is the active export scope."""
        if self.im_scope.get() == "picked":
            self.pick_wrap.pack(fill="x", padx=8, pady=(4, 0))
        else:
            self.pick_wrap.pack_forget()

    # -- 部件页
    def _tab_parts(self, nb):
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text=tr("部件"))
        cols = ("mesh", "sub", "verts", "tris", "mat", "uv")
        tv = ttk.Treeview(f, columns=cols, show="headings", height=22)
        for c, w in zip(cols, (150, 46, 60, 60, 110, 90)):
            tv.heading(c, text={"mesh": tr("部件 / 网格"), "sub": tr("子网格"), "verts": tr("顶点"),
                                "tris": tr("面"), "mat": tr("材质"), "uv": tr("UV 变换")}[c])
            tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=4, pady=4)
        tv.bind("<<TreeviewSelect>>", self.on_part_pick)
        self.part_tv = tv
        tk.Label(f, text=tr("选中一行 = 只渲染该部件（再点「只看整机」恢复）"),
                 bg=BG, fg="#8fa6c0", anchor="w").pack(fill="x", padx=6, pady=(0, 6))
        return f

    # -- 微调页（炮塔 / 炮管平移）
    def _tab_tweak(self, nb):
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text=tr("微调"))

        self.tw_which = tk.StringVar(value=tr("当前载具：%s") % tr("（在左侧车辆库里选一辆）"))
        tk.Label(f, textvariable=self.tw_which, bg=BG, fg="#8fa6c0",
                 anchor="w").pack(fill="x", padx=6, pady=(8, 2))

        self.tw_vars = {}
        self.tw_turret = (0.0, 0.0, 0.0)
        self.tw_gun = (0.0, 0.0, 0.0)
        self.tw_follow = tk.BooleanVar(value=True)
        self.tw_step = tk.StringVar(value="0.05")

        for key, title in (("turret", tr("炮塔微调")), ("gun", tr("炮管微调"))):
            box = tk.LabelFrame(f, text=title, bg=BG, fg=FG, bd=1, relief="groove")
            box.pack(fill="x", padx=6, pady=(6, 0))
            for axis, albl in (("z", tr("前后")), ("x", tr("左右")), ("y", tr("上下"))):
                row = tk.Frame(box, bg=BG)
                row.pack(fill="x", padx=4, pady=1)
                tk.Label(row, text=albl, bg=BG, fg=FG, width=5, anchor="w").pack(side="left")
                ttk.Button(row, text="−", width=3,
                           command=lambda k=key, a=axis: self.tw_nudge(k, a, -1)
                           ).pack(side="left")
                var = tk.StringVar(value="0.00")
                tk.Entry(row, textvariable=var, bg=BG2, fg=FG, width=8, justify="center",
                         insertbackground=FG).pack(side="left", padx=3)
                ttk.Button(row, text="+", width=3,
                           command=lambda k=key, a=axis: self.tw_nudge(k, a, +1)
                           ).pack(side="left")
                tk.Label(row, text={"z": tr("Z 轴"), "x": tr("X 轴"), "y": tr("Y 轴")}[axis],
                         bg=BG, fg="#8fa6c0").pack(side="left", padx=6)
                self.tw_vars[(key, axis)] = var
                var.trace_add("write", lambda *_a: self._tw_from_entries())

        opt = tk.Frame(f, bg=BG)
        opt.pack(fill="x", padx=6, pady=(6, 0))
        tk.Label(opt, text=tr("步长"), bg=BG, fg=FG).pack(side="left")
        for s in ("0.01", "0.05", "0.1", "0.5"):
            tk.Radiobutton(opt, text=s, variable=self.tw_step, value=s, bg=BG, fg=FG,
                           selectcolor=BG2, activebackground=BG).pack(side="left", padx=2)
        tk.Checkbutton(opt, text=tr("炮管跟随炮塔"), variable=self.tw_follow, bg=BG, fg=FG,
                       selectcolor=BG2, activebackground=BG,
                       command=self._tw_from_entries).pack(side="left", padx=8)

        btns = tk.Frame(f, bg=BG)
        btns.pack(fill="x", padx=6, pady=6)
        ttk.Button(btns, text=tr("归零"), command=self.tw_reset).pack(side="left")
        ttk.Button(btns, text=tr("导出此车"), command=self.tw_export).pack(side="left", padx=6)

        self.tw_info = tk.StringVar(value="")
        tk.Label(f, textvariable=self.tw_info, bg=BG, fg="#8fa6c0", justify="left",
                 anchor="w", wraplength=520).pack(fill="x", padx=6)
        tk.Label(f, bg=BG, fg="#8fa6c0", justify="left", anchor="w", wraplength=520,
                 text=tr("单位就是导出的 OBJ 单位（已 ×7，约等于米）。\n"
                         "前后 = Z 轴，左右 = X 轴，上下 = Y 轴；改一下中间预览就会跟着动。\n"
                         "炮塔 = 名字里含 Turret 的部件；炮管 = Barrel / Gun，"
                         "机枪（Machinegun）不算在内。\n"
                         "数值是**在当前 OBJ 基础上再挪多少**：导出后偏移写进了文件，"
                         "这里会自动归零，模型位置不变。\n"
                         "外观和残骸共用同一套值；按车名记在脚本目录的 tweaks.json，"
                         "以后全量导出会自动带上。")
                 ).pack(fill="x", padx=6, pady=(2, 6))
        self._tw_refresh_info()
        return f

    def tw_nudge(self, kind, axis, sign):
        idx = {"x": 0, "y": 1, "z": 2}[axis]
        try:
            step = float(self.tw_step.get())
        except ValueError:
            step = 0.05
        cur = list(self.tw_turret if kind == "turret" else self.tw_gun)
        cur[idx] = round(cur[idx] + sign * step, 4)
        if kind == "turret":
            self.tw_turret = tuple(cur)
        else:
            self.tw_gun = tuple(cur)
        self._tw_to_entries()
        self._tw_apply()

    def _tw_to_entries(self):
        """把内部状态写到输入框。写的时候要屏蔽回读，否则 set() 触发的回调
        会拿着还没更新的其他框把刚改的值覆盖回去（归零就失效了）。"""
        self._tw_updating = True
        try:
            for (kind, axis), var in self.tw_vars.items():
                idx = {"x": 0, "y": 1, "z": 2}[axis]
                val = (self.tw_turret if kind == "turret" else self.tw_gun)[idx]
                if var.get() != "%.2f" % val:
                    var.set("%.2f" % val)
        finally:
            self._tw_updating = False

    def _tw_from_entries(self):
        """输入框被手改 / 勾选框变化时同步到内部状态并重画预览。"""
        if getattr(self, "_tw_updating", False):
            return
        for kind, attr in (("turret", "tw_turret"), ("gun", "tw_gun")):
            vals = list(getattr(self, attr))
            for axis in ("x", "y", "z"):
                idx = {"x": 0, "y": 1, "z": 2}[axis]
                try:
                    vals[idx] = float(self.tw_vars[(kind, axis)].get())
                except ValueError:
                    continue
            setattr(self, attr, tuple(vals))
        self._tw_apply()

    def _tw_apply(self):
        """界面上的数值就是**在文件基础上再挪多少**，直接套到预览模型上。

        （文件里已经烘进去的部分不用管 —— 顶点本来就带着它，模型看着就是对的。）
        """
        if self.model:
            self.model.set_tweaks(self.tw_turret, self.tw_gun, self.tw_follow.get())
            self.redraw()
            # 每次改动都落盘：算绝对总量要用「文件已烘入 + 界面增量」，
            # 换辆车再导出时才不会漏掉刚才那辆的值。
            self.save_tweaks()
        self._tw_refresh_info()

    def _tw_refresh_info(self):
        if not self.model:
            self.tw_which.set(tr("当前载具：%s") % tr("（在左侧车辆库里选一辆）"))
            self.tw_info.set("")
            return
        base = self._tw_key(self.model.name)
        self.tw_which.set(tr("当前载具：%s") % base)
        nt, ng = PG.count_kinds(self.model.groups)
        info = tr("受影响的部件：炮塔 %d 个，炮管 %d 个（共 %d 个部件）") \
            % (nt, ng, len(self.model.groups))
        # 文件里已经烘进去的偏移也报一下 —— 上面那几个框是「在这基础上再挪多少」，
        # 刚导出完框里就是 0，不说清楚会以为没生效
        bt, bg, _bf = self.model.baked_tweaks()
        if any(bt) or any(bg):
            info += tr("；这个 OBJ 里已烘入 炮塔(%.2f, %.2f, %.2f) 炮管(%.2f, %.2f, %.2f)，"
                       "上面的数值是在它基础上再挪") \
                % (bt[0], bt[1], bt[2], bg[0], bg[1], bg[2])
        self.tw_info.set(info)

    def tw_reset(self):
        self.tw_turret = (0.0, 0.0, 0.0)
        self.tw_gun = (0.0, 0.0, 0.0)
        self.tw_follow.set(True)
        self._tw_to_entries()
        self._tw_apply()

    def tw_export(self):
        """按当前微调值重导这一辆车。"""
        out = self.im_out.get().strip() or self.ex_out.get().strip()
        if not out:
            messagebox.showerror(tr("缺少输出目录"),
                                 tr("先填「模型输出目录」（提取模型页或重导页都行）。"))
            return
        if not self.model:
            messagebox.showinfo(tr("提示"), tr("先选一辆车"))
            return
        name = self.model.name
        if name.endswith("_Wreck"):
            name = name[:-6]
        work = self.im_work.get().strip() or self.ex_work.get().strip()
        self.save_tweaks()
        extra = ["--out", out, "--only", name, "--scale", "7",
                 "--tweaks", TWEAK_FILE]
        if work:
            extra += ["--work", work]
        self._start_pipeline([(tr("导出 %s（带微调）") % name,
                               self._tool_cmd("export_tanks.py", extra), self._env())],
                             tr("微调后导出"), on_done=self._after_tw_export)

    def _after_tw_export(self):
        """导出完重新读一次模型：偏移已经烘进新文件，内存里那份记录得刷新，
        否则接着微调会按旧的「已烘值」算增量。"""
        self.load_current()
        self.status.set(tr("导出完成 —— 偏移已经写进 OBJ，预览按实际文件显示"))

    # -- 贴图页
    def _tab_textures(self, nb):
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text=tr("贴图"))
        # the canvas lives in its own frame, otherwise it eats the bottom hint's width
        wrap = tk.Frame(f, bg=BG2)
        wrap.pack(side="top", fill="both", expand=True)
        self.tex_canvas = tk.Canvas(wrap, bg=BG2, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tex_canvas.yview)
        inner = tk.Frame(self.tex_canvas, bg=BG2)
        self.tex_canvas.create_window((0, 0), window=inner, anchor="nw")
        self.tex_canvas.configure(yscrollcommand=sb.set)
        self.tex_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        inner.bind("<Configure>",
                   lambda _e: self.tex_canvas.configure(scrollregion=self.tex_canvas.bbox("all")))
        self.tex_inner = inner
        tk.Label(f, text=tr("双击贴图查看原图"), bg=BG, fg="#8fa6c0").pack(side="bottom", fill="x")
        return f

    # -- 重导页
    def _tab_export(self, nb):
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text=tr("重导"))
        # 重导同样要工作目录：导出要读 bundles/data.unity3d，校验要读 catalog_index.json。
        # （打包成 exe 后脚本的默认工作目录是 <exe>/work，不填就会找不到东西。）
        tk.Label(f, text=tr("解包工作目录（含 catalog_index.json）"), bg=BG, fg=ACC,
                 anchor="w").pack(fill="x", padx=6, pady=(8, 0))
        wr = tk.Frame(f, bg=BG)
        wr.pack(fill="x", padx=6)
        self.ex_work = tk.StringVar(value="")
        tk.Entry(wr, textvariable=self.ex_work, bg=BG2, fg=FG,
                 insertbackground=FG).pack(side="left", fill="x", expand=True)
        ttk.Button(wr, text=tr("选目录"),
                   command=lambda: self.pick_dir(self.ex_work)).pack(side="left", padx=4)
        ttk.Button(wr, text=tr("用提取页的"),
                   command=lambda: self.ex_work.set(self.im_work.get().strip())
                   ).pack(side="left")
        tk.Label(f, text=tr("车辆（逗号分隔，留空=全部）"), bg=BG, fg=FG, anchor="w").pack(fill="x", padx=6, pady=(6, 0))
        self.ex_only = tk.StringVar(value="")
        tk.Entry(f, textvariable=self.ex_only, bg=BG2, fg=FG, insertbackground=FG).pack(fill="x", padx=6)
        row = tk.Frame(f, bg=BG)
        row.pack(fill="x", padx=6, pady=6)
        tk.Label(row, text=tr("随机"), bg=BG, fg=FG).pack(side="left")
        self.ex_n = tk.StringVar(value="4")
        tk.Entry(row, textvariable=self.ex_n, width=5, bg=BG2, fg=FG,
                 insertbackground=FG).pack(side="left", padx=4)
        tk.Label(row, text=tr("辆  种子"), bg=BG, fg=FG).pack(side="left")
        self.ex_seed = tk.StringVar(value="7")
        tk.Entry(row, textvariable=self.ex_seed, width=7, bg=BG2, fg=FG,
                 insertbackground=FG).pack(side="left", padx=4)
        ttk.Button(row, text=tr("用左侧选中"), command=self.use_selection).pack(side="left", padx=6)
        tk.Label(f, bg=BG, fg="#8fa6c0", justify="left", anchor="w", wraplength=520,
                 text=tr("随机种子：同一个数字每次抽到同一批，换个数字换一批（用来复现抽样）。")
                 ).pack(fill="x", padx=6)

        tk.Label(f, text=tr("按名字搜索载具（可多选）"), bg=BG, fg=ACC, anchor="w").pack(
            fill="x", padx=6, pady=(6, 0))
        self.picker2 = TankPicker(f, height=6, kinds_of=self._ex_kinds,
                                  work_of=lambda: MW,
                                  out_of=lambda: self.ex_out.get().strip())
        self.picker2.pack(fill="x", padx=6)
        ttk.Button(f, text=tr("把勾选的车辆填入上面的框"),
                   command=self.fill_from_picker).pack(fill="x", padx=6, pady=4)

        self.ex_out = tk.StringVar(value="")
        row2 = tk.Frame(f, bg=BG)
        row2.pack(fill="x", padx=6)
        tk.Entry(row2, textvariable=self.ex_out, bg=BG2, fg=FG,
                 insertbackground=FG).pack(side="left", fill="x", expand=True)
        ttk.Button(row2, text=tr("选目录"), command=self.pick_out).pack(side="left", padx=4)

        tk.Label(f, text=tr("载具类别"), bg=BG, fg=ACC, anchor="w").pack(fill="x", padx=6,
                                                                  pady=(6, 0))
        self.ex_kind_tanks = tk.BooleanVar(value=True)
        self.ex_kind_fighters = tk.BooleanVar(value=False)
        self.ex_kind_helicopters = tk.BooleanVar(value=False)
        exk = tk.Frame(f, bg=BG)
        exk.pack(fill="x", padx=8)
        for text, var in ((tr("坦克"), self.ex_kind_tanks), (tr("固定翼"), self.ex_kind_fighters),
                          (tr("直升机"), self.ex_kind_helicopters)):
            tk.Checkbutton(exk, text=text, variable=var, bg=BG, fg=FG, selectcolor=BG2,
                           activebackground=BG,
                           command=self._refresh_pickers).pack(side="left", padx=(0, 8))
        self.ex_scale = tk.BooleanVar(value=True)
        self.ex_lods = tk.BooleanVar(value=False)
        self.ex_nocamo = tk.BooleanVar(value=False)
        row3 = tk.Frame(f, bg=BG)
        row3.pack(fill="x", padx=6, pady=6)
        for text, var in ((tr("缩放到 7 倍"), self.ex_scale),
                          (tr("含 LOD1/2"), self.ex_lods),
                          (tr("不要伪装网"), self.ex_nocamo)):
            tk.Checkbutton(row3, text=text, variable=var, bg=BG, fg=FG, selectcolor=BG2,
                           activebackground=BG).pack(side="left", padx=2)
        tk.Label(f, bg=BG, fg="#8fa6c0", justify="left", anchor="w", wraplength=520,
                 text=tr("缩放到 7 倍：游戏里 1 单位 ≈ 1/7 米，×7 之后基本就是米制尺寸。")
                 ).pack(fill="x", padx=6)
        tk.Label(f, bg=BG, fg="#8fa6c0", justify="left", anchor="w", wraplength=520,
                 text=tr("含 LOD1/2：LOD 是游戏按远近切换的简化模型，LOD0 最精细；勾上会把 "
                      "LOD1/LOD2 一起写进同一个 OBJ，它们和 LOD0 重叠，一般不用。")
                 ).pack(fill="x", padx=6)
        btns = tk.Frame(f, bg=BG)
        btns.pack(fill="x", padx=6)
        ttk.Button(btns, text=tr("开始导出"), command=self.run_export).pack(side="left")
        ttk.Button(btns, text=tr("出预览图"), command=self.run_previews).pack(side="left", padx=6)
        bb = tk.Frame(f, bg=BG)
        bb.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Button(bb, text=tr("Blender 出图（上面填的车）"),
                   command=self.run_blender_batch).pack(side="left")
        tk.Label(bb, text=tr("残骸"), bg=BG, fg=FG).pack(side="left", padx=(8, 0))
        self.ex_blend_wreck = tk.BooleanVar(value=False)
        tk.Checkbutton(bb, variable=self.ex_blend_wreck, bg=BG, fg=FG, selectcolor=BG2,
                       activebackground=BG).pack(side="left")
        tk.Label(f, text=(tr("说明：导出用 mw\\export_tanks.py；随机抽样只会覆盖抽样到的车，"
                          "不会动其它目录。\n"
                          "Blender 出图走 Workbench + MTL 贴图，单张约 5–15 秒，"
                          "输出到每辆车目录下的 render.png。")),
                 bg=BG, fg="#8fa6c0", justify="left",
                 wraplength=530, anchor="w").pack(fill="x", padx=6, pady=8)
        return f

    # -- 日志页
    def _tab_log(self, nb):
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text=tr("日志"))
        self.log = ScrolledText(f, bg="#1a1c22", fg="#cfe0d0", insertbackground=FG,
                                height=28, wrap="none")
        self.log.pack(fill="both", expand=True, padx=4, pady=4)
        return f

    # -- 语言页
    def _tab_lang(self, nb):
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text="中文 / EN")
        tk.Label(f, text=tr("界面语言"), bg=BG, fg=ACC, anchor="w").pack(
            fill="x", padx=10, pady=(14, 2))
        self.lang_var = tk.StringVar(value=LANG)
        box = tk.Frame(f, bg=BG)
        box.pack(fill="x", padx=10)
        for text, val in (("中文", "zh"), ("English", "en")):
            tk.Radiobutton(box, text=text, variable=self.lang_var, value=val, bg=BG,
                           fg=FG, selectcolor=BG2, activebackground=BG,
                           command=self._apply_lang).pack(side="left", padx=(0, 14))
        tk.Label(f, bg=BG, fg="#8fa6c0", justify="left", anchor="w", wraplength=520,
                 text=tr("切换后整个界面会重建，已填的路径和选择会保留。")
                 ).pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(f, bg=BG, fg="#8fa6c0", justify="left", anchor="w", wraplength=520,
                 text=tr("本页只切换界面语言。脚本自身的输出（控制台 / 日志页）仍是中文。")
                 ).pack(fill="x", padx=10, pady=(4, 0))
        return f

    # -- 语言切换：重建整个界面（最省事也最不容易漏翻）
    def _apply_lang(self):
        global LANG
        want = self.lang_var.get()
        if want == LANG:
            return
        state = self._snapshot_state()
        LANG = want
        for w in self.winfo_children():
            w.destroy()
        self._build()
        self._restore_state(state)
        self.scan_library()
        self._refresh_pickers()
        self._update_unpack_state()
        self.after(60, self.redraw)

    def _snapshot_state(self):
        return {
            "root_dir": self.root_dir,
            "apk": self.im_apk.get(), "work": self.im_work.get(),
            "im_out": self.im_out.get(), "ex_out": self.ex_out.get(),
            "scope": self.im_scope.get(), "only": self.ex_only.get(),
            "n": self.im_n.get(), "seed": self.im_seed.get(),
            "ex_n": self.ex_n.get(), "ex_seed": self.ex_seed.get(),
            "lods": self.im_lods.get(), "nocamo": self.im_nocamo.get(),
            "im_scale": self.im_scale.get(), "ex_scale": self.ex_scale.get(),
            "im_kinds": self._im_kinds(), "ex_kinds": self._ex_kinds(),
            "im_flags": (self.im_index.get(), self.im_export.get(),
                         self.im_preview.get()),
            "ex_flags": (self.ex_lods.get(), self.ex_nocamo.get()),
            "mode": self.mode.get(), "wreck": self.wreck.get(),
            "picked": list(self.picker.picked), "picked2": list(self.picker2.picked),
            "model": self.model.obj_path if self.model else None,
        }

    def _restore_state(self, s):
        self.root_dir = s["root_dir"]
        self.im_apk.set(s["apk"])
        self.im_work.set(s["work"])
        self.im_out.set(s["im_out"])
        self.ex_out.set(s["ex_out"])
        self.im_scope.set(s["scope"])
        self.ex_only.set(s["only"])
        self.im_n.set(s["n"])
        self.im_seed.set(s["seed"])
        self.ex_n.set(s["ex_n"])
        self.ex_seed.set(s["ex_seed"])
        self.im_lods.set(s["lods"])
        self.im_nocamo.set(s["nocamo"])
        self.im_scale.set(s.get("im_scale", True))
        self.ex_scale.set(s.get("ex_scale", True))
        self.im_index.set(s["im_flags"][0])
        self.im_export.set(s["im_flags"][1])
        self.im_preview.set(s["im_flags"][2])
        self.ex_lods.set(s["ex_flags"][0])
        self.ex_nocamo.set(s["ex_flags"][1])
        self.mode.set(s["mode"])
        self.wreck.set(s["wreck"])
        for k in s["im_kinds"]:
            {"tanks": self.im_kind_tanks, "fighters": self.im_kind_fighters,
             "helicopters": self.im_kind_helicopters}[k].set(True)
        for k in s["ex_kinds"]:
            {"tanks": self.ex_kind_tanks, "fighters": self.ex_kind_fighters,
             "helicopters": self.ex_kind_helicopters}[k].set(True)
        self.picker.picked = set(s["picked"])
        self.picker2.picked = set(s["picked2"])
        self._sync_scope()
        if s["model"] and os.path.exists(s["model"]):
            self.load_tank(s["model"])

    # ------------------------------------------------------------ 车辆库
    def _library_root(self):
        """车辆库扫的是「模型输出目录」：先「提取模型」页填的，再「重导」页的。
        都没填就看启动时有没有用 --root 显式指定；也没有就是空 —— 不做任何默认猜测。"""
        for var in (getattr(self, "im_out", None), getattr(self, "ex_out", None)):
            if var is None:
                continue
            p = var.get().strip()
            if p and os.path.isdir(p):
                return p
        for var in (getattr(self, "im_out", None), getattr(self, "ex_out", None)):
            if var is not None and var.get().strip():
                return var.get().strip()
        return self.root_dir or ""

    def scan_library(self):
        self.lib = {}
        root = self._library_root()
        self._scan_root = root
        if not root:
            self.refill_tree()
            self.lib_root_lbl.set(tr("还没设置模型输出目录"))
            self.status.set(tr("车辆库为空"))
            self.title_lbl.config(text=tr("车辆库为空"))
            self.show_placeholder(
                tr("还没选「模型输出目录」。\n\n"
                "到「提取模型」页选一个文件夹（模型会写到这里），\n"
                "提取完成或点左侧「重扫输出目录」之后，这里就会列出载具。"))
            return
        if os.path.isdir(root):
            for country in sorted(os.listdir(root)):
                d = os.path.join(root, country)
                if not os.path.isdir(d):
                    continue
                for tank in sorted(os.listdir(d)):
                    obj = os.path.join(d, tank, tank + ".obj")
                    if os.path.exists(obj):
                        self.lib.setdefault(country, []).append((tank, obj))
        self.refill_tree()
        n = sum(len(v) for v in self.lib.values())
        self.lib_root_lbl.set(tr("扫描：%s") % root)
        if n:
            self.status.set(tr("车辆库：%d 个载具") % n)
            return
        # Nothing to browse: say so loudly instead of showing an empty tree.
        work = self.im_work.get().strip()
        has_bundles = bool(work) and os.path.exists(os.path.join(work, "bundles", "data.unity3d"))
        hint = [tr("这个目录里没有模型："), root, ""]
        if has_bundles:
            hint += [tr("但解包结果还在（%s\\bundles），可以直接提取：") % work,
                     tr("  · 「提取模型」页 → 选好类别和范围 → 点「提取模型」"),
                     tr("  · 或「重导」页 → 输出目录填 %s → 点开始导出") % root]
        elif work:
            hint += [tr("也找不到解包结果（%s\\bundles\\data.unity3d）。") % work,
                     tr("到「提取模型」页选 APK，点上面的「解包 APK」。")]
        else:
            hint += [tr("「提取模型」页还没填解包工作目录。"),
                     tr("选一个空文件夹当工作目录，再点「解包 APK」，模型提取好之后这里就会列出来。")]
        self.status.set(tr("车辆库为空"))
        self.title_lbl.config(text=tr("车辆库为空 —— %s") % root)
        self.show_placeholder("\n".join(hint))

    def show_placeholder(self, text):
        """Draw a hint on the preview canvas (used when there is no model)."""
        self.canvas.delete("all")
        w = max(self.canvas.winfo_width(), 320)
        self.canvas.create_text(24, 24, anchor="nw", text=text, fill="#cfe0d0",
                                font=("Microsoft YaHei UI", 11), width=max(300, w - 48),
                                justify="left")

    def refill_tree(self):
        self.tree.delete(*self.tree.get_children())
        key = self.filter.get().strip().lower()
        first = None
        for country in sorted(self.lib):
            tanks = [t for t in self.lib[country] if not key or key in t[0].lower()
                     or key in country.lower()]
            if not tanks:
                continue
            node = self.tree.insert("", "end", text="%s (%d)" % (country, len(tanks)), open=bool(key))
            for name, obj in tanks:
                iid = self.tree.insert(node, "end", text=name, values=(obj,))
                if first is None:
                    first = iid
        self._first_iid = first

    def on_tree_pick(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if vals:
            self.load_tank(vals[0])

    def pick_random(self):
        allt = [t for v in self.lib.values() for t in v]
        if allt:
            self.load_tank(random.choice(allt)[1])

    def use_selection(self):
        sel = self.tree.selection()
        names = []
        for iid in sel:
            v = self.tree.item(iid, "values")
            if v:
                names.append(os.path.splitext(os.path.basename(v[0]))[0])
        if not names:
            messagebox.showinfo(tr("提示"), tr("先在左侧选车（可多选）"))
            return
        self.ex_only.set(",".join(n for n in names if not n.endswith("_Wreck")))

    def fill_from_picker(self):
        names = self.picker2.selected()
        if not names:
            messagebox.showinfo(tr("提示"), tr("先在下面的列表里勾选车辆（可按名字搜索）"))
            return
        self.ex_only.set(",".join(names))

    # ------------------------------------------------------------ 载入
    def load_current(self):
        if self.model:
            self.load_tank(self.model.obj_path)

    def load_tank(self, obj_path):
        # 先把传进来的路径还原成「外观」那份，再按当前勾选决定要不要换成残骸。
        # （只做 外观->残骸 的单向替换的话，从残骸切回外观时路径还是残骸，
        #   会一直显示残骸。）
        if obj_path.endswith("_Wreck.obj"):
            obj_path = obj_path[:-len("_Wreck.obj")] + ".obj"
        if self.wreck.get():
            w = os.path.join(os.path.dirname(obj_path),
                             os.path.splitext(os.path.basename(obj_path))[0] + "_Wreck.obj")
            if os.path.exists(w):
                obj_path = w
            else:
                self.status.set(tr("这辆没有残骸模型"))
        try:
            self.model = TankModel(obj_path)
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror(tr("载入失败"), "%s: %s" % (type(exc).__name__, exc))
            return
        self.only_group = None
        self.title_lbl.config(text=tr("%s   %d 顶点 / %d 面 / %d 组") %
                                   (self.model.name, len(self.model.verts),
                                    len(self.model.faces), len(self.model.groups)))
        self.reset_view()                       # 先归位视角，再套微调（少渲染一次）
        self._tw_load_for(self.model.name)      # 载入这辆车记过的炮塔/炮管微调
        self.fill_parts()
        self.fill_textures()

    # -- 微调值的读写 ------------------------------------------------------
    @staticmethod
    def _tw_key(name):
        """-> 车名。残骸模型去掉 _Wreck 后缀 —— 外观和残骸共用同一套微调值。"""
        return name[:-6] if name.endswith("_Wreck") else name

    @staticmethod
    def _tw_unpack(d):
        """取出微调值。兼容中途试过的 {intact:…, wreck:…} 两层格式（取 intact）。"""
        if not isinstance(d, dict):
            return {}
        if "intact" in d or "wreck" in d:
            return d.get("intact") or {}
        return d

    def _tw_load_for(self, name):
        """载入某辆车的微调值到界面（没有就归零）。

        界面上的数值是**在当前 OBJ 基础上再挪多少**（相对量），
        tweaks.json 里存的是**绝对总量**（导出时要按它烘进文件）。
        所以这里要减掉文件里已经烘进去的那部分 —— 刚导出完的话正好是 0，
        双击预览时数值自动归零、模型位置不变。
        """
        saved = self._tw_unpack(self.tweaks.get(self._tw_key(name)) or {})
        bt, bg, _bf = self.model.baked_tweaks() if self.model else \
            ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), True)
        st = tuple(saved.get("turret") or (0.0, 0.0, 0.0))
        sg = tuple(saved.get("gun") or (0.0, 0.0, 0.0))
        self.tw_turret = tuple(a - b for a, b in zip(st, bt))
        self.tw_gun = tuple(a - b for a, b in zip(sg, bg))
        self.tw_follow.set(bool(saved.get("follow", True)))
        self._tw_to_entries()
        self._tw_apply()

    def _tw_store(self, name, turret, gun, follow):
        """把界面上的**相对量**换算成**绝对总量**存下来。"""
        bt, bg, _bf = self.model.baked_tweaks() if self.model else \
            ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), True)
        tt = tuple(a + b for a, b in zip(turret, bt))
        tg = tuple(a + b for a, b in zip(gun, bg))
        base = self._tw_key(name)
        if not any(tt) and not any(tg) and follow:
            self.tweaks.pop(base, None)          # 全零就不留记录
        else:
            self.tweaks[base] = {"turret": [round(v, 4) for v in tt],
                                 "gun": [round(v, 4) for v in tg],
                                 "follow": bool(follow)}

    def save_tweaks(self):
        """把当前这辆车的微调值写进 tweaks.json。"""
        if self.model:
            self._tw_store(self.model.name, self.tw_turret, self.tw_gun,
                           self.tw_follow.get())
        ok = save_tweaks(self.tweaks)
        if not ok:
            self.logq.put(("log", tr("[警告] 写不了 %s，微调值这次不保存。\n") % TWEAK_FILE))
        return ok

    def reset_view(self):
        self.yaw, self.pitch, self.zoom = 35.0, 20.0, 1.0
        self.pan = [0.0, 0.0]
        self.schedule(delay=0)

    def fill_parts(self):
        tv = self.part_tv
        tv.delete(*tv.get_children())
        m = self.model
        man = m.manifest()
        rows = []
        for key in ("intact", "wreck"):
            if key in man:
                for p in man[key].get("parts", []):
                    t = p.get("uv_tiling") or [1, 1, 0, 0]
                    uv = "-" if t == [1, 1, 0, 0] else "x%.2g y%.2g" % (t[0], t[1])
                    rows.append((p.get("part") or p.get("mesh"), str(p.get("submesh", "-")),
                                 str(p.get("verts", "")), str(p.get("tris", "")),
                                 p.get("material") or "", uv))
        if not rows:   # 没有 manifest 就退回按 OBJ 组
            for g in m.groups:
                n = sum(1 for x in m.group_of_face if x == g)
                rows.append((g, "-", "", str(n), "", ""))
        for r in rows:
            tv.insert("", "end", values=r)
        self.parts_meta = rows

    def on_part_pick(self, _e=None):
        sel = self.part_tv.selection()
        if not sel or not self.model:
            return
        name = self.part_tv.item(sel[0], "values")[0]
        # manifest 的部件名与 OBJ 组名一致（导出时用 safe_name(name)）
        cand = [g for g in self.model.groups if g == name or g.startswith(name + "_")]
        self.isolate(cand[0] if cand else None)

    def isolate(self, group):
        self.only_group = group
        self.status.set(tr("只渲染：%s") % group if group else tr("显示整机"))
        self.schedule(delay=0)

    def fill_textures(self):
        for w in self.tex_inner.winfo_children():
            w.destroy()
        self.tex_thumbs = []
        files = self.model.texture_files() if self.model else []
        cols = 4
        for i, p in enumerate(files):
            try:
                im = Image.open(p).convert("RGB")
                im.thumbnail((104, 104))
            except Exception:
                continue
            ph = ImageTk.PhotoImage(im)
            self.tex_thumbs.append(ph)
            cell = tk.Frame(self.tex_inner, bg=BG2)
            cell.grid(row=i // cols, column=i % cols, padx=3, pady=3)
            lbl = tk.Label(cell, image=ph, bg=BG2, cursor="hand2")
            lbl.pack()
            lbl.bind("<Double-Button-1>", lambda _e, q=p: self.show_texture(q))
            tk.Label(cell, text=os.path.basename(p)[:16], bg=BG2, fg="#9fb0c4",
                     font=("Consolas", 7)).pack()

    def show_texture(self, path):
        try:
            im = Image.open(path)
        except Exception as exc:
            messagebox.showerror(tr("打开失败"), str(exc))
            return
        top = tk.Toplevel(self)
        top.title(os.path.basename(path))
        top.configure(bg=BG)
        w, h = im.size
        sc = min(1.0, 900.0 / max(w, h))
        if sc < 1.0:
            im = im.resize((int(w * sc), int(h * sc)), Image.LANCZOS)
        ph = ImageTk.PhotoImage(im)
        lbl = tk.Label(top, image=ph, bg=BG)
        lbl.image = ph
        lbl.pack()
        tk.Label(top, text="%s   %dx%d" % (path, w, h), bg=BG, fg=FG).pack()

    # ------------------------------------------------------------ 交互
    def begin_drag(self, event, kind):
        self._drag = (kind, event.x, event.y, self.yaw, self.pitch, list(self.pan))

    def on_drag(self, event):
        if not self._drag:
            return
        kind, x, y, yaw0, pitch0, pan0 = self._drag
        dx, dy = event.x - x, event.y - y
        if kind == "orbit":
            self.yaw = yaw0 + dx * 0.4
            self.pitch = max(-89.0, min(89.0, pitch0 + dy * 0.4))
        else:
            self.pan = [pan0[0] + dx, pan0[1] + dy]
        self.schedule(delay=0, dragging=True)

    def end_drag(self, _e=None):
        self._drag = None
        self.schedule(delay=180)

    def on_wheel(self, event):
        self.zoom = max(0.15, min(8.0, self.zoom * (1.1 if event.delta > 0 else 1 / 1.1)))
        self.schedule(delay=0, dragging=True)

    def schedule(self, delay=0, dragging=False):
        self._dragging = dragging
        if self._after:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
        self._after = self.after(delay, self.redraw)
        # 拖动 / 滚轮结束后必须回到全画质。以前只有 end_drag 会复位，
        # 滚轮缩放把 _dragging 设成 True 之后没人管 —— 预览就永远停在
        # 低画质上，看起来就是「破面不恢复」。这里统一挂一个收尾计时器。
        if dragging:
            if self._settle:
                try:
                    self.after_cancel(self._settle)
                except Exception:
                    pass
            self._settle = self.after(self.SETTLE_MS, self._settle_frame)
        elif self._settle:
            try:
                self.after_cancel(self._settle)
            except Exception:
                pass
            self._settle = None

    def _settle_frame(self):
        """操作停下来之后按全画质重画一次。"""
        self._settle = None
        self.schedule(delay=0)

    def redraw(self):
        self._after = None
        if not self.model:
            return
        cw = max(240, self.canvas.winfo_width())
        ch = max(240, self.canvas.winfo_height())
        dragging = bool(getattr(self, "_dragging", False))
        # 直接按画布的宽高渲染（不再裁成正方形，上下白白空着）。
        # 拖动时也用同样的分辨率和全部面 —— 降分辨率省不下时间，丢面就是破面。
        size = (max(240, cw), max(240, ch))
        # 缓存键必须带上炮塔/炮管微调值，否则改了偏移但视角没变时
        # 会命中缓存直接 return，预览看起来「不动」
        tw = getattr(self.model, "tweak", None) or {}
        key = (round(self.yaw, 3), round(self.pitch, 3), round(self.zoom, 4),
               round(self.pan[0], 2), round(self.pan[1], 2), self.mode.get(),
               self.only_group, size, self.model.name,
               tuple(tw.get("turret") or ()), tuple(tw.get("gun") or ()),
               bool(tw.get("follow", True)))
        if key == getattr(self, "_last_key", None) and self._photo is not None:
            return
        self._last_key = key
        canvas_img = self.model.render(self.yaw, self.pitch, self.zoom, self.pan, size,
                                       mode=self.mode.get(), only_group=self.only_group)
        dr = ImageDraw.Draw(canvas_img)
        dr.text((8, 6), "%s  yaw %.0f  pitch %.0f  zoom %.2f  %s" %
                (self.model.name, self.yaw, self.pitch, self.zoom,
                 tr("整机") if not self.only_group else self.only_group), fill=(255, 212, 94))
        # 有微调时把当前偏移写在第二行，免得「看着没动」时不知道到底生效没有
        tw = getattr(self.model, "tweak", None) or {}
        tt, gg, ff = getattr(self.model, "tweak_total",
                             (tuple(tw.get("turret") or ()), tuple(tw.get("gun") or ()),
                              tw.get("follow", True)))
        if any(tt) or any(gg):
            dr.text((8, 22), "%s (%.2f, %.2f, %.2f)   %s (%.2f, %.2f, %.2f)%s" %
                    (tr("炮塔"), tt[0], tt[1], tt[2],
                     tr("炮管"), gg[0], gg[1], gg[2],
                     "" if ff else "  " + tr("不跟随")),
                    fill=(150, 220, 255))
        self._photo = ImageTk.PhotoImage(canvas_img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")

    # -- Blender 出图（带贴图的成品图） --------------------------------------
    def blender_shot(self):
        """Render the current view with Blender (Workbench + MTL textures)."""
        if not self.model:
            messagebox.showinfo(tr("提示"), tr("先选一辆车"))
            return
        png = os.path.join(self.model.dir, "render.png")
        cmd = [PY, "-u", os.path.join(MW, "blender_shot.py"), self.model.obj_path, png,
               "--yaw", "%.2f" % self.yaw, "--pitch", "%.2f" % self.pitch,
               "--zoom", "%.3f" % self.zoom, "--size", self.blend_size]
        self._start_pipeline([(tr("Blender 出图"), cmd, self._env())], tr("Blender 出图"),
                             on_done=lambda p=png: self.show_image(p))

    def show_image(self, path):
        if not os.path.exists(path):
            self.status.set(tr("没有产出图片：%s") % path)
            return
        self.status.set(tr("出图：%s") % path)
        top = tk.Toplevel(self)
        top.title(os.path.basename(path) + "  —  " + os.path.dirname(path))
        top.configure(bg=BG)
        im = Image.open(path)
        w, h = im.size
        sc = min(1.0, 1200.0 / max(w, h))
        if sc < 1.0:
            im = im.resize((int(w * sc), int(h * sc)), Image.LANCZOS)
        ph = ImageTk.PhotoImage(im)
        lbl = tk.Label(top, image=ph, bg=BG)
        lbl.image = ph
        lbl.pack()

        def save_as():
            q = filedialog.asksaveasfilename(defaultextension=".png",
                                             filetypes=[("PNG", "*.png")],
                                             initialfile=os.path.basename(path))
            if q:
                Image.open(path).save(q)
                self.status.set(tr("另存为 %s") % q)

        bar = tk.Frame(top, bg=BG)
        bar.pack(fill="x")
        ttk.Button(bar, text=tr("另存为…"), command=save_as).pack(side="left", padx=6, pady=4)
        ttk.Button(bar, text=tr("关闭"), command=top.destroy).pack(side="left")
        tk.Label(bar, text="%s   %dx%d" % (path, w, h), bg=BG, fg="#8fa6c0").pack(side="right",
                                                                                  padx=8)

    def save_shot(self):
        """Fast software render of the current view (no textures)."""
        if not self.model:
            return
        p = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")],
                                         initialfile=self.model.name + "_view.png")
        if not p:
            return
        img = self.model.render(self.yaw, self.pitch, self.zoom, self.pan, 1400,
                                mode=self.mode.get(), only_group=self.only_group,
                                max_tris=400000)
        img.save(p)
        self.status.set(tr("已保存 %s") % p)

    # ------------------------------------------------------------ 任务
    def pick_out(self):
        p = filedialog.askdirectory(initialdir=self.ex_out.get())
        if p:
            self.ex_out.set(p)

    def pick_dir(self, var):
        start = var.get().strip()
        if not start or not os.path.isdir(start):
            start = os.path.dirname(start) if start else os.path.expanduser("~")
        if not os.path.isdir(start):
            start = os.path.expanduser("~")
        p = filedialog.askdirectory(initialdir=start)
        if p:
            var.set(p)

    def _guess_apk(self):
        """找一个现成的 APK：先看已知位置，再扫几个常见目录，最后看附件仓库。"""
        for p in APK_HINTS:
            if os.path.exists(p):
                return p
        # 常见根目录下的 *.apk（只扫一层，避免卡住）
        for root in ("E:\\", "D:\\", "C:\\"):
            if not os.path.isdir(root):
                continue
            try:
                for f in sorted(os.listdir(root)):
                    if f.lower().endswith(".apk"):
                        return os.path.join(root, f)
            except OSError:
                pass
        try:
            from extract_bundles import APK_CANDIDATES
            for p in APK_CANDIDATES:
                if os.path.exists(p):
                    return p
        except Exception:
            pass
        # 附件仓库（老版本把 APK 放这儿）
        base = os.path.join(os.path.expanduser("~"), ".dsh", "attachments")
        for d in (base, MW, TANKS_DEFAULT, os.getcwd()):
            if not os.path.isdir(d):
                continue
            for r, _dd, ff in os.walk(d):
                for f in ff:
                    if f.lower().endswith(".apk"):
                        return os.path.join(r, f)
        return ""

    def pick_apk(self):
        guess = self.im_apk.get().strip()
        start = os.path.dirname(guess) if guess and os.path.exists(guess) else ""
        if not start:
            g = self._guess_apk()
            start = os.path.dirname(g) if g else MW
        p = filedialog.askopenfilename(title=tr("选择 APK"), initialdir=start,
                                       filetypes=[(tr("Android 包"), "*.apk"),
                                                  (tr("所有文件"), "*.*")])
        if p:
            self.im_apk.set(p)

    # -- 通用命令构造
    def _tool_cmd(self, script, extra):
        """构造跑某个子脚本的命令。

        打包成 exe 后 sys.executable 就是 exe 自己，直接 `exe export_tanks.py`
        会重新拉起界面，所以改成 `exe --run export_tanks.py ...`，
        由 main() 里的分发分支用 runpy 就地执行那个脚本。
        """
        if FROZEN:
            return [PY, "--run", script] + extra
        return [PY, "-u", os.path.join(MW, script)] + extra

    def _env(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        pylibs = os.path.join(MW, "pylibs")
        if os.path.isdir(pylibs):
            env["PYTHONPATH"] = pylibs
        elif FROZEN:
            env.pop("PYTHONPATH", None)   # 依赖已经打进 exe，不再需要外部 pylibs
        return env

    def _cmd(self, extra):
        return self._tool_cmd("export_tanks.py", extra), self._env()

    def _im_kinds(self):
        want = []
        if self.im_kind_tanks.get():
            want.append("tanks")
        if self.im_kind_fighters.get():
            want.append("fighters")
        if self.im_kind_helicopters.get():
            want.append("helicopters")
        return want

    def _ex_kinds(self):
        want = []
        if self.ex_kind_tanks.get():
            want.append("tanks")
        if self.ex_kind_fighters.get():
            want.append("fighters")
        if self.ex_kind_helicopters.get():
            want.append("helicopters")
        return want

    def _kind_spec(self):
        """勾选的类别 -> --kind 参数值。"""
        return ",".join(self._im_kinds())

    def _refresh_pickers(self):
        """类别勾选变化时，列表跟着换（未导出的类别不再出现在待选里）。"""
        for pk in (getattr(self, "picker", None), getattr(self, "picker2", None)):
            if pk is not None:
                pk.refresh()

    # -- 提取模型流水线
    def _unpack_steps(self, list_only=False, with_index=True):
        """第一步：解包 APK（必要时建索引）。返回步骤列表，参数不合法时返回 None。"""
        apk = self.im_apk.get().strip()
        work = self.im_work.get().strip()
        if not work:
            messagebox.showerror(tr("缺少工作目录"),
                                 tr("先填「解包工作目录」—— 解出来的 catalog 和 bundle 会放这里，"
                                 "载具列表也从这里读。\n第一次用建议选一个空文件夹。"))
            return None
        ready, _why = work_dir_state(work)
        env = self._env()

        if list_only:                    # 只看 APK 内容，那就必须有 APK
            if not apk or not os.path.exists(apk):
                messagebox.showerror(tr("缺少 APK"), tr("先选一个存在的 APK 文件"))
                return None
            return [(tr("解包 APK"), self._tool_cmd(
                "extract_bundles.py", ["--apk", apk, "--work", work, "--list-only"]), env)]

        steps = []
        if ready:
            # 工作目录里已经有 catalog.json + bundles/data.unity3d：
            # 不用再解包，也不要求选 APK —— 只在日志里说明一句
            self.logq.put(("log", tr("[跳过解包] 工作目录里已经有解包结果，直接用；"
                                     "APK 可以不填。\n")))
        else:
            if not apk or not os.path.exists(apk):
                found = self._guess_apk()
                more = ("\n\n本机找到：\n%s\n可以直接点「浏览」选它。" % found) if found else ""
                messagebox.showerror(
                    tr("缺少 APK"),
                    tr("工作目录里还没有解包结果（缺 catalog.json 或 bundles/data.unity3d），"
                       "所以必须先选一个 APK 解包。\n\n"
                       "如果已经解包过，把「解包工作目录」指向那个目录就行，APK 可以留空。")
                    + more)
                return None
            steps.append((tr("解包 APK"), self._tool_cmd(
                "extract_bundles.py", ["--apk", apk, "--work", work]), env))

        idx = os.path.join(work, "catalog_index.json")
        if with_index and (not ready or not os.path.exists(idx)):
            steps.append((tr("解析 catalog 建立索引"),
                          self._tool_cmd("build_index.py",
                                         ["--catalog", os.path.join(work, "catalog.json"),
                                          "--out", work]), env))
        return steps

    def run_unpack(self):
        """只解包 APK，不导出模型；完成后刷新载具列表。已解包则自动跳过。"""
        work = self.im_work.get().strip()
        ready, _why = work_dir_state(work)
        idx = os.path.join(work, "catalog_index.json") if work else ""
        if ready and os.path.exists(idx):
            self.status.set(tr("这个工作目录已经解包过了，不用再解 —— 直接去第二步提取模型"))
            self.logq.put(("log", tr("[跳过解包] %s 里已经有解包结果和索引。\n") % work))
            self._refresh_pickers()
            return
        steps = self._unpack_steps(with_index=self.im_index.get())
        if steps:
            self._start_pipeline(steps, tr("解包 APK（不导出模型）"),
                                 on_done=self._after_unpack)

    def _after_unpack(self):
        self._refresh_pickers()
        self._update_unpack_state()
        n = len(self.picker.names) if hasattr(self, "picker") else 0
        if n:
            self.status.set(tr("解包完成：工作目录已就绪，可提取 %d 个载具") % n)
        else:
            self.status.set(tr("解包完成，但没有索引 —— 勾上「解析 catalog 建立索引」再解一次"))

    def _import_steps(self, list_only=False):
        work = self.im_work.get().strip()
        out = self.im_out.get().strip()
        env = self._env()
        steps = self._unpack_steps(list_only=list_only, with_index=self.im_index.get())
        if steps is None or list_only:
            return steps
        if self.im_export.get():
            if not out:
                messagebox.showerror(tr("缺少输出目录"),
                                     tr("先填「模型输出目录」—— 提取出来的 OBJ / 贴图会写到这里，"
                                     "左侧车辆库也扫这里。"))
                return None
            kind = self._kind_spec()
            if not kind:
                messagebox.showerror(tr("没有选类别"), tr("「载具类别」一个都没勾：坦克 / 固定翼 / 直升机。"))
                return None
            extra = ["--work", work, "--out", out, "--kind", kind]
            scope = self.im_scope.get()
            if scope == "picked":
                picked = self.picker.selected()
                if not picked:
                    messagebox.showerror(
                        tr("没有选择车辆"),
                        tr("导出范围选了「指定载具」，但一辆都没勾选。\n\n"
                        "· 在「搜索车名」框里输名字，从下面列表勾选要导出的车\n"
                        "· 或者改成「随机 N 辆」/「全部」\n"
                        "· 或者取消勾选「导出模型」只解包不导出"))
                    return None
                extra += ["--only", ",".join(picked)]
            elif scope == "sample":
                try:
                    extra += ["--sample", str(int(self.im_n.get().strip() or 4)),
                              "--seed", str(int(self.im_seed.get().strip() or 0))]
                except ValueError:
                    messagebox.showerror(tr("参数错误"), tr("随机数量 / seed 必须是整数"))
                    return None
            if self.im_lods.get():
                extra.append("--all-lods")
            if self.im_nocamo.get():
                extra.append("--no-camo")
            extra += ["--scale", "7" if self.im_scale.get() else "1"]
            self.save_tweaks()                       # 微调值落盘，跟着这次导出一起用
            extra += ["--tweaks", TWEAK_FILE]
            steps.append((tr("导出模型（%s）") % {"picked": tr("%d 辆指定") % len(self.picker.selected()),
                                              "sample": tr("随机"),
                                              "all": tr("全部")}[scope],
                          self._tool_cmd("export_tanks.py", extra), env))
        if self.im_preview.get():
            steps.append((tr("生成预览图"),
                          self._tool_cmd("make_previews.py", ["--root", out]), env))
        return steps

    def run_import(self):
        steps = self._import_steps()
        if steps:
            self._start_pipeline(steps, tr("提取模型：解包 APK"))

    def run_import_list(self):
        steps = self._import_steps(list_only=True)
        if steps:
            self._start_pipeline(steps, tr("查看 APK 内容"))

    # -- 重导页
    def _need_ex_out(self):
        """重导页的几个动作都要求先填输出目录，留空就提示而不是猜。"""
        out = self.ex_out.get().strip()
        if not out:
            messagebox.showerror(tr("缺少输出目录"),
                                 tr("先填「模型输出目录」—— 导出/校验/出图都按这个目录来。"))
            return None
        return out

    def run_export(self):
        out = self._need_ex_out()
        if not out:
            return
        want = []
        if self.ex_kind_tanks.get():
            want.append("tanks")
        if self.ex_kind_fighters.get():
            want.append("fighters")
        if self.ex_kind_helicopters.get():
            want.append("helicopters")
        if not want:
            messagebox.showerror(tr("没有选类别"), tr("「载具类别」一个都没勾：坦克 / 固定翼 / 直升机。"))
            return
        extra = ["--out", out, "--kind", ",".join(want)]
        work = self.ex_work.get().strip()
        if work:
            extra += ["--work", work]
        only = self.ex_only.get().strip()
        n = self.ex_n.get().strip()
        # 车辆框填了就按它导；只有它为空时才走「随机 N 辆」。
        # （原来反过来，随机数默认就有值 4，导致填了车名却仍然随机导出。）
        if only:
            extra += ["--only", only]
        elif n:
            try:
                extra += ["--sample", str(int(n)), "--seed", str(int(self.ex_seed.get() or 0))]
            except ValueError:
                messagebox.showerror(tr("参数错误"), tr("随机数量 / seed 必须是整数"))
                return
        if self.ex_lods.get():
            extra.append("--all-lods")
        if self.ex_nocamo.get():
            extra.append("--no-camo")
        extra += ["--scale", "7" if self.ex_scale.get() else "1"]
        self.save_tweaks()
        extra += ["--tweaks", TWEAK_FILE]
        steps = [(tr("导出模型"), self._tool_cmd("export_tanks.py", extra), self._env())]
        self._start_pipeline(steps, tr("重新导出"))

    def run_previews(self):
        out = self._need_ex_out()
        if not out:
            return
        self._start_pipeline([(tr("预览图"),
                               self._tool_cmd("make_previews.py", ["--root", out]),
                               self._env())], tr("预览图"))

    def run_blender_batch(self):
        out = self._need_ex_out()
        if not out:
            return
        only = self.ex_only.get().strip()
        extra = ["--batch", "--root", out, "--name", "render.png"]
        if only:
            extra += ["--only", only]
        if self.ex_blend_wreck.get():
            extra.append("--wreck")
        self._start_pipeline([(tr("Blender 批量出图"),
                               self._tool_cmd("blender_shot.py", extra),
                               self._env())], tr("Blender 批量出图"))

    # -- 流水线
    def _busy(self):
        return self.worker is not None and self.worker.is_alive()

    def _start_pipeline(self, steps, title, on_done=None):
        if self._busy():
            messagebox.showinfo(tr("提示"), tr("还有任务在跑，先点停止或等它结束"))
            return
        self._on_done = on_done
        self.progress.configure(mode="determinate", maximum=100, value=0)
        self.prog_lbl.set(tr("准备中…"))
        self.logq.put(("log", "\n=== %s ===\n" % title))
        self.nb.select(self.log_tab)
        self.worker = threading.Thread(target=self._pipeline, args=(steps,), daemon=True)
        self.worker.start()
        self.progress.configure(mode="indeterminate")
        self.progress.start(60)

    def _pipeline(self, steps):
        for label, cmd, env in steps:
            self.logq.put(("log", "\n--- %s ---\n$ %s\n" % (label, " ".join(cmd))))
            self.logq.put(("phase", tr("%s 启动中") % label))
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, env=env, cwd=MW,
                                        text=True, encoding="utf-8", errors="replace",
                                        bufsize=1)
            except Exception as exc:
                self.logq.put(("log", tr("[启动失败] %r\n") % (exc,)))
                self.logq.put(("phase", tr("启动失败")))
                return
            self._proc = proc
            try:
                for line in proc.stdout:
                    m = PROG_RE.search(line)
                    if m:
                        self.logq.put(("prog", int(m.group(1)), int(m.group(2)), label))
                    self.logq.put(("log", line))
            except Exception as exc:
                self.logq.put(("log", tr("[读取输出失败] %r\n") % (exc,)))
            rc = proc.wait()
            self._proc = None
            if rc != 0:
                self.logq.put(("log", tr("[%s 退出码 %s，已中止]\n") % (label, rc)))
                self.logq.put(("phase", tr("%s 失败（退出码 %s）") % (label, rc)))
                return
        self.logq.put(("phase", tr("全部完成")))
        self.logq.put(("log", tr("\n=== 全部完成 ===\n")))
        self.logq.put(("done", None))

    def _pump_log(self):
        dirty = False
        try:
            while True:
                item = self.logq.get_nowait()
                if isinstance(item, str):
                    self.log.insert("end", item)
                    dirty = True
                    continue
                kind = item[0]
                if kind == "log":
                    self.log.insert("end", item[1])
                    dirty = True
                elif kind == "phase":
                    self.phase = item[1]
                    self.prog_lbl.set(item[1])
                    if item[1].endswith(tr("启动中")) or item[1] == tr("准备中…"):
                        # unknown duration yet: keep the bar moving
                        self.progress.configure(mode="indeterminate")
                        self.progress.start(60)
                elif kind == "done":
                    cb, self._on_done = self._on_done, None
                    if cb:
                        try:
                            cb()
                        except Exception:
                            traceback.print_exc()
                elif kind == "prog":
                    done, total, label = item[1], item[2], item[3]
                    if total > 0:
                        self.progress.stop()
                        self.progress.configure(mode="determinate", maximum=total,
                                                value=min(done, total))
                        self.prog_lbl.set("%s：%d / %d  (%.1f%%)"
                                          % (label, done, total, 100.0 * done / total))
                    else:
                        self.progress.stop()
                        self.progress.configure(mode="determinate", maximum=100, value=100)
                        self.prog_lbl.set("%s：%s" % (label, tr("完成")))
        except queue.Empty:
            pass
        if dirty:
            self.log.see("end")
        self._pump_id = self.after(120, self._pump_log)

    def destroy(self):
        """关窗时把挂着的定时器取消，否则 tkinter 会报 invalid command name。"""
        for attr in ("_pump_id", "_after", "_settle"):
            tid = getattr(self, attr, None)
            if tid:
                try:
                    self.after_cancel(tid)
                except Exception:
                    pass
                setattr(self, attr, None)
        tk.Tk.destroy(self)

    def stop_worker(self):
        proc = getattr(self, "_proc", None)
        if proc and proc.poll() is None:
            proc.terminate()
            self.logq.put(("log", tr("[已请求停止]\n")))
            self.logq.put(("phase", tr("已停止")))
        else:
            self.prog_lbl.set(tr("当前没有在跑的任务"))


def main():
    args = sys.argv[1:]

    # 打成 exe 后的子脚本分发：`exe --run export_tanks.py --kind air ...`
    # 用 runpy 就地执行，等价于原来 `python export_tanks.py ...`
    if args and args[0] == "--run":
        import runpy
        if len(args) < 2:
            sys.stderr.write("usage: <exe> --run <script.py> [args...]\n")
            return 2
        script = args[1]
        path = script if os.path.isabs(script) else os.path.join(HERE, script)
        if not os.path.exists(path):
            sys.stderr.write("script not found in bundle: %s\n" % script)
            return 2
        sys.argv = [path] + args[2:]
        sys.path.insert(0, HERE)
        runpy.run_path(path, run_name="__main__")
        return 0

    root = ""                       # 不给 --root 就不预设任何目录
    if "--root" in args:
        root = args[args.index("--root") + 1]

    # 打包成 exe 后是 console 子系统（子进程要靠它拿 stdio），开界面时把那个黑窗口藏起来
    if FROZEN and os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass

    app = App(root)
    if "--selftest" in args:
        app.update_idletasks()
        app.update()
        iid = getattr(app, "_first_iid", None)
        if iid:
            app.tree.selection_set(iid)
            app.load_tank(app.tree.item(iid, "values")[0])
            app.update_idletasks()
            app.update()
        print(tr("selftest ok: %d 个国家, 当前 %s") %
              (len(app.lib), app.model.name if app.model else tr("无")))
        app.destroy()
        return
    if "--shot" in args:
        out = args[args.index("--shot") + 1]
        allt = [t for v in app.lib.values() for t in v]
        if allt:
            app.load_tank(sorted(allt, key=lambda x: x[0])[0][1])
            app.update_idletasks()
            app.update()
            img = app.model.render(app.yaw, app.pitch, app.zoom, app.pan, 900,
                                   mode=app.mode.get(), max_tris=400000)
            img.save(out)
            print("shot ->", out)
        app.destroy()
        return
    app.mainloop()


if __name__ == "__main__":
    main()
