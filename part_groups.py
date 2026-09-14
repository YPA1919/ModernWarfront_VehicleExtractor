# -*- coding: utf-8 -*-
"""炮塔 / 炮管的部件判定。

导出脚本和界面预览都用这一份，免得两边正则写得不一样、预览和实际导出对不上。

判定规则（部件名就是 OBJ 里的 `g` 名，来自 GameObject 名 + 子网格号）：

- **炮塔**：名字里含 `turret` 的都算 —— 包括 `Turret_LOD0`、`Turret_ERA_*`、
  `Camo_Net_Turret`，以及架在炮塔上的 `Machinegun_01_Turret_LOD0`（它确实长在炮塔上）。
- **炮管**：含 `barrel` / `cannon`，或含 `gun` 但**不是**机枪。
  机枪（`M2HB_Machinegun`、`Gun_Machinegun_LOD0`、`Lenta_Machinegun`…）要排除掉，
  否则挪主炮时会把车顶机枪一起拖走。
"""
import re

TURRET_RE = re.compile(r"turret", re.I)
# "Machinegun" 里也含 gun，必须先认出来
MACHINEGUN_RE = re.compile(r"machine\s*gun|machinegun|\bmg\b", re.I)
GUN_RE = re.compile(r"barrel|cannon|(?<!machine)gun", re.I)

ZERO = (0.0, 0.0, 0.0)


def classify(name):
    """-> "turret" / "gun" / None"""
    if TURRET_RE.search(name):
        return "turret"
    if GUN_RE.search(name) and not MACHINEGUN_RE.search(name):
        return "gun"
    return None


def offset_for(name, turret=ZERO, gun=ZERO, follow=True):
    """这个部件要平移多少。炮管默认跟着炮塔一起动（炮是装在炮塔上的）。"""
    kind = classify(name)
    if kind == "turret":
        return tuple(turret)
    if kind == "gun":
        if follow:
            return tuple(a + b for a, b in zip(turret, gun))
        return tuple(gun)
    return ZERO


def count_kinds(names):
    """-> (炮塔件数, 炮管件数)，给界面显示「会影响哪些部件」用。"""
    t = g = 0
    for n in names:
        k = classify(n)
        if k == "turret":
            t += 1
        elif k == "gun":
            g += 1
    return t, g
