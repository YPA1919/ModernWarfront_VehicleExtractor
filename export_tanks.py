"""Export tank models (OBJ + MTL) and textures (PNG) from Modern Warfront.

Source of truth is assets/bin/Data/data.unity3d (the player data package).  It is
a bundle holding 12 SerializedFiles (resources.assets carries the tank prefabs as
Resources/Tanks/<Name>); path ids are only unique *within* a file, so every
reference is resolved through UnityPy's PPtr.deref() and every cache is keyed by
ObjectReader rather than by path id.

Two things make these prefabs unusual (both verified against the data):

* A "group mesh" carries one submesh per part and the prefab holds one slot
  GameObject per part.  The submeshes are already positioned in the mesh's own
  space, so a slot only has to select its submesh - the slot<->submesh pairing is
  the hierarchy order of the slots that reference the mesh, and the mesh as a
  whole must be placed with the slot that carries no extra offset (the mount).
* The same group mesh also holds the wrecked ("_Destructed") variant of each
  part as an extra submesh, which is why the intact and wreck models have to be
  split by slot rather than by mesh.

Tracks are SkinnedMeshRenderers, not MeshFilters; at prefab rest pose the skinned
result equals the mesh placed by the renderer's own transform.

Usage:
    python export_tanks.py [--only A,B] [--limit N] [--lod 0|1|2] [--out DIR]
"""
import argparse
import collections
import json
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import part_groups as PG          # 炮塔/炮管部件判定（界面预览共用同一份）

try:
    import UnityPy
    from UnityPy.files.ObjectReader import ObjectReader as _ObjectReader
    from UnityPy.helpers import TypeTreeHelper as _TTH
    from UnityPy.helpers.MeshHelper import MeshHandler
except ImportError as _exc:
    sys.stderr.write(
        "\n[缺少依赖] %s\n"
        "解包 / 导出 / 校验需要这些 Python 库：UnityPy Pillow numpy texture2ddecoder tpk_ar\n"
        "两条任选其一（在脚本目录执行）：\n"
        "    python fetch_wheels.py pylibs UnityPy Pillow numpy texture2ddecoder tpk_ar\n"
        "    pip install UnityPy Pillow numpy texture2ddecoder tpk_ar\n"
        "或者直接用打包好的 exe（release 里），不用装任何东西。\n\n" % _exc)
    sys.exit(2)

# ObjectReader defines __eq__ but no __hash__, which makes it unhashable; identity
# hashing is exactly what we want for the caches below.
if _ObjectReader.__hash__ is None:
    _ObjectReader.__hash__ = object.__hash__

# The compiled typetree reader access-violates on some ParticleSystem objects.
_TTH.read_typetree_boost = None
# 编译版 UnityPyBoost 在长跑（几百辆）时会随机触发 ACCESS_VIOLATION
# （0xC0000005，进程直接没，Python 捕不到），表现就是「全部导出跑到一半失败」。
# 三个入口全关掉走纯 Python 回退 —— UnityPy 自己的注释也提到 unpack_vertexdata
# 会崩。代价是读顶点慢一点，但不会再整批失败。
try:
    from UnityPy.helpers import MeshHelper as _MeshHelper
    _MeshHelper.UnityPyBoost = None
except Exception:
    pass
try:
    from UnityPy.helpers import ArchiveStorageManager as _ASM
    _ASM.UnityPyBoost = None
except Exception:
    pass

# ASTC 贴图 UnityPy 默认用 astc_encoder（编译模块）解，实测全量导出跑到
# 100~200 辆时进程会随机 ACCESS_VIOLATION 直接没（Python 捕不到，表现就是
# 「全部导出失败」，而且时好时坏）。换成 texture2ddecoder.decode_astc ——
# 另一套实现，同一批数据跑全量不再崩。
try:
    import texture2ddecoder as _t2d
    from PIL import Image as _PILImage
    from UnityPy.export import Texture2DConverter as _T2DC

    def _astc_safe(image_data, width, height, block_size):
        bw, bh = block_size
        raw = _t2d.decode_astc(image_data, width, height, bw, bh)
        return _PILImage.frombytes("RGBA", (width, height), raw, "raw", "BGRA")

    for _fmt in list(_T2DC.CONV_TABLE):
        if "ASTC" in _fmt.name:
            _T2DC.CONV_TABLE[_fmt] = (_astc_safe, _T2DC.CONV_TABLE[_fmt][1])
except Exception:
    pass

# 换个位置再兜一层：get_triangles 里那句纯 Python 切片会 ACCESS_VIOLATION，
# 说明 self.m_IndexBuffer / src.m_SubMeshes 底下是失效的缓冲区对象。
# 进函数先全部拷成普通 list/tuple，断开这层引用。
try:
    from UnityPy.helpers.MeshHelper import MeshHandler as _MeshHandler
    _orig_get_triangles = _MeshHandler.get_triangles

    def _safe_get_triangles(self):
        ib = getattr(self, "m_IndexBuffer", None)
        if ib is not None and type(ib) not in (list, tuple):
            try:
                self.m_IndexBuffer = list(ib)
            except Exception:
                self.m_IndexBuffer = []
        src = getattr(self, "src", None)
        subs = getattr(src, "m_SubMeshes", None)
        if subs is not None and type(subs) is not list:
            try:
                src.m_SubMeshes = list(subs)
            except Exception:
                pass
        return _orig_get_triangles(self)

    _MeshHandler.get_triangles = _safe_get_triangles
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
# 打包成 exe 后脚本在临时解包目录里，默认工作目录放到 exe 旁边；
# 源码运行时就是脚本自己所在目录（GUI 会把 --work 显式传进来，这里只是默认值）
if getattr(sys, "frozen", False):
    MW = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "work")
else:
    MW = HERE
DATA = os.path.join(MW, "bundles", "data.unity3d")
OUT = os.path.join(MW, "tanks")

# 导出时把模型等比例放大多少倍。游戏里 1 单位 ≈ 1/7 米，×7 之后就基本是米制：
# 豹2A6MC2 模型长 1.573 单位 ×7 = 11.01 m，真车 10.97 m（差 0.4%）。
SCALE = 7.0

# ---------------------------------------------------------------- 炮塔 / 炮管微调
# 游戏里武器是运行时挂上去的，导出的静态模型偶尔炮塔或炮管位置不对，
# 留一组偏移量手工推一下。偏移量用的是**导出单位**（×SCALE 之后、Blender 里看到的单位），
# 所以和界面/预览里看到的数值一致。
# 部件判定统一走 part_groups —— 界面预览用的是同一份，免得两边对不上。
TURRET_OFFSET = (0.0, 0.0, 0.0)
GUN_OFFSET = (0.0, 0.0, 0.0)
GUN_FOLLOWS_TURRET = True
BASE_TURRET = (0.0, 0.0, 0.0)      # 命令行给的全局值
BASE_GUN = (0.0, 0.0, 0.0)
BASE_FOLLOW = True
TWEAKS = {}                        # 车名 -> {"turret": [...], "gun": [...], "follow": bool}


def apply_tweaks(tank):
    """把「这一辆」的炮塔/炮管微调值装进模块级变量。外观和残骸共用同一套。"""
    global TURRET_OFFSET, GUN_OFFSET, GUN_FOLLOWS_TURRET
    d = TWEAKS.get(tank) or TWEAKS.get(tank.lower()) or {}
    # 兼容中途试过的 {intact:…, wreck:…} 两层格式（取 intact 那套）
    if "intact" in d or "wreck" in d:
        d = d.get("intact") or {}
    TURRET_OFFSET = tuple(d.get("turret") or BASE_TURRET)
    GUN_OFFSET = tuple(d.get("gun") or BASE_GUN)
    GUN_FOLLOWS_TURRET = bool(d.get("follow", BASE_FOLLOW))


def parse_xyz(text, what="offset"):
    """把 "0,0.05,-0.1" 解析成 (x, y, z)。"""
    if not text:
        return (0.0, 0.0, 0.0)
    parts = [p for p in re.split(r"[,;\s]+", text.strip()) if p]
    if len(parts) != 3:
        raise SystemExit("%s 要三个数，用逗号分隔，例如 0,0.05,-0.1（收到 %r）"
                         % (what, text))
    try:
        return tuple(float(p) for p in parts)
    except ValueError:
        raise SystemExit("%s 里有不是数字的：%r" % (what, text))


def part_offset(name):
    """这个部件要额外平移多少（导出单位）。"""
    return PG.offset_for(name, TURRET_OFFSET, GUN_OFFSET, GUN_FOLLOWS_TURRET)


def set_work(work):
    """Point the extractor at another workspace (bundles + catalog_index.json)."""
    global MW, DATA
    MW = work
    DATA = os.path.join(work, "bundles", "data.unity3d")


def progress(done, total):
    print("PROGRESS %d %d" % (done, total), flush=True)

# Slots that are never part of the visible model.
COLLIDER_RE = re.compile(r"(DamageCollider|Collider)", re.I)
LOD_RE = re.compile(r"LOD[1-9]", re.I)
# 名字里的 LOD 编号。注意游戏里有手误：`Hull_ERA_Kontakt1_Side_R_01_ROD0`
# 把 LOD0 打成了 ROD0，所以这里连 R 一起认。
LOD_NUM_RE = re.compile(r"[LR]OD(\d)", re.I)


def lod_of(name):
    """部件名里的 LOD 编号；没有标记的返回 None（这种各档都留）。"""
    m = LOD_NUM_RE.search(name or "")
    return int(m.group(1)) if m else None
WRECK_RE = re.compile(r"Destructed", re.I)
# Camo nets are Cloth meshes: the prefab stores their pre-simulation state, which
# is a flat sheet hovering over the hull rather than the draped net the game
# shows, so they are excluded unless explicitly requested.
CAMO_RE = re.compile(r"(Camo_net|Camo_Net|Cloth)", re.I)
# 特效壳（不是硬件）：49 架飞机带着超音速激波锥，网格很小但被放大 10 倍摆在机身上
EFFECT_RE = re.compile(r"(SuperSonicCone|SupersonicCone)", re.I)
# 旋翼模糊桨盘：直升机把 HelicopterBladeSmoothed 挂在名为 `blur` 的节点下（转起来才显示），
# 真正的桨叶是挂在 *_Rotor_* 下的 *_Blades_*_LOD0。同一架可能有好几个（blur / blur_001 /
# blur (2) —— Unity 给重名节点的后缀），所以后缀要一起匹配，否则会漏掉几片错位桨盘。
BLUR_RE = re.compile(r"^blur(_\d+)?( \(\d+\))?$", re.I)
# Running gear contacts the ground, so it defines the model's floor.
GEAR_RE = re.compile(r"(wheel|track|tire|tyre|roller|sprocket|idler|suspension)", re.I)
# The hull names the vehicle's footprint used by the parked-parts filter.
HULL_RE = re.compile(r"(^|_)(hull|body|tub|chassis)", re.I)
IDENTITY = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]


def mat_mul(a, b):
    """a · b for two flat column-major 4x4 matrices.

    索引必须是 result[col=i][row=j] = Σ_k a[col=k][row=j] · b[col=i][row=k]。
    早先写成 Σ_k a[col=i][row=k] · b[col=k][row=j]，算出来的是 b·a ——
    纯平移的链条两者相同，所以坦克一直看不出来；一旦链条里有旋转（飞机的起落架
    是 R_01→R_03→R_05 这种带转角的关节链），部件就会甩到错误的位置。
    """
    return [sum(a[k * 4 + j] * b[i * 4 + k] for k in range(4))
            for i in range(4) for j in range(4)]


def trs_matrix(pos, rot, scale):
    """Unity local-to-parent matrix T * R * S as a flat column-major list."""
    x, y, z, w = rot
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    sx, sy, sz = scale
    r = [
        1 - 2 * (yy + zz), 2 * (xy + wz), 2 * (xz - wy), 0.0,
        2 * (xy - wz), 1 - 2 * (xx + zz), 2 * (yz + wx), 0.0,
        2 * (xz + wy), 2 * (yz - wx), 1 - 2 * (xx + yy), 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    for c in range(3):
        for row in range(3):
            r[c * 4 + row] *= (sx, sy, sz)[c]
    r[12], r[13], r[14] = pos
    return r


def xform_point(m, p):
    x, y, z = p[0], p[1], p[2]
    return (m[0] * x + m[4] * y + m[8] * z + m[12],
            m[1] * x + m[5] * y + m[9] * z + m[13],
            m[2] * x + m[6] * y + m[10] * z + m[14])


def xform_dir(m, p):
    x, y, z = p[0], p[1], p[2]
    return (m[0] * x + m[4] * y + m[8] * z,
            m[1] * x + m[5] * y + m[9] * z,
            m[2] * x + m[6] * y + m[10] * z)


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9_.\-]+", "_", str(s) or "unnamed").strip("_") or "unnamed"


def try_deref(ptr):
    if not ptr or not ptr.m_PathID:
        return None
    try:
        return ptr.deref()
    except Exception:
        return None


def median(values):
    s = sorted(values)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


class GameData:
    def __init__(self, path=DATA):
        t0 = time.time()
        self.env = UnityPy.load(path)
        self.sfs = []
        for _, cf in self.env.files.items():
            inner = getattr(cf, "files", None)
            if inner:
                self.sfs.extend(f for f in inner.values() if getattr(f, "objects", None))
            elif getattr(cf, "objects", None):
                self.sfs.append(cf)

        self.go_name = {}
        self.tr = {}
        self.mf = {}
        self.mr = {}
        self.smr = {}
        # StaticBatchInfo(firstSubMesh, subMeshCount)：Unity 静态合批时每个
        # MeshRenderer 声明自己画哪一段子网格。整车就是这么拼起来的 —— 见 build_plan。
        self.sbi = {}
        self.batch_root = {}
        for sf in self.sfs:
            for o in sf.objects.values():
                tn = o.type.name
                try:
                    if tn == "GameObject":
                        self.go_name[o] = o.read().m_Name
                    elif tn == "Transform":
                        self.tr[o] = o.read()
                    elif tn == "MeshFilter":
                        d = o.read()
                        go = try_deref(d.m_GameObject)
                        mesh = try_deref(d.m_Mesh)
                        if go is not None and mesh is not None:
                            self.mf[go] = mesh
                    elif tn == "MeshRenderer":
                        d = o.read()
                        go = try_deref(d.m_GameObject)
                        if go is not None:
                            self.mr[go] = [r for r in
                                           (try_deref(m) for m in (d.m_Materials or [])) if r]
                            s = getattr(d, "m_StaticBatchInfo", None)
                            if s is not None:
                                self.sbi[go] = (int(getattr(s, "firstSubMesh", 0) or 0),
                                                int(getattr(s, "subMeshCount", 0) or 0))
                            rt = try_deref(getattr(d, "m_StaticBatchRoot", None))
                            if rt is not None:
                                self.batch_root[go] = rt
                    elif tn == "SkinnedMeshRenderer":
                        d = o.read()
                        go = try_deref(d.m_GameObject)
                        mesh = try_deref(d.m_Mesh)
                        if go is not None and mesh is not None:
                            self.smr[go] = (mesh, [r for r in
                                                   (try_deref(m) for m in (d.m_Materials or [])) if r])
                except Exception:
                    continue

        self.go2tr = {}
        self.tr_go = {}
        self.tr_kids = collections.defaultdict(list)
        for tp, d in self.tr.items():
            go = try_deref(d.m_GameObject)
            if go is not None:
                self.go2tr[go] = tp
                self.tr_go[tp] = go
        for tp, d in self.tr.items():
            for child in (d.m_Children or ()):
                cr = try_deref(child)
                if cr is not None:
                    self.tr_kids[tp].append(cr)

        self._mesh_cache = {}
        self._mat_cache = {}
        self._tex_cache = {}
        self._handler_cache = {}
        print(f"indexed {len(self.go_name)} GameObjects / {len(self.tr)} Transforms / "
              f"{len(self.mf)} MeshFilters / {len(self.mr)} MeshRenderers / "
              f"{len(self.smr)} SkinnedMeshRenderers from {len(self.sfs)} files "
              f"in {time.time()-t0:.1f}s", flush=True)

    # ---- accessors -------------------------------------------------
    def mesh(self, reader):
        if reader not in self._mesh_cache:
            try:
                self._mesh_cache[reader] = reader.read()
            except Exception:
                self._mesh_cache[reader] = None
        return self._mesh_cache[reader]

    def material(self, reader):
        if reader not in self._mat_cache:
            try:
                self._mat_cache[reader] = reader.read()
            except Exception:
                self._mat_cache[reader] = None
        return self._mat_cache[reader]

    def texture(self, reader):
        if reader not in self._tex_cache:
            try:
                self._tex_cache[reader] = reader.read()
            except Exception:
                self._tex_cache[reader] = None
        return self._tex_cache[reader]

    def handler(self, reader):
        """Processed MeshHandler, cached per mesh; cleared between tanks."""
        if reader not in self._handler_cache:
            mesh = self.mesh(reader)
            h = None
            if mesh is not None:
                try:
                    h = MeshHandler(mesh)
                    h.process()
                    if not h.m_Vertices:
                        h = None
                except Exception:
                    h = None
            if h is not None:
                # mesh.m_IndexBuffer 可能是指向 SerializedFile 缓冲区的 memoryview，
                # 缓冲区释放后再切片就是 ACCESS_VIOLATION（0xC0000005，整批导出
                # 跑到一半突然进程消失，Python 捕不到）。立刻拷成普通序列断开引用。
                ib = h.m_IndexBuffer
                if ib is not None and not isinstance(ib, (list, tuple)):
                    try:
                        h.m_IndexBuffer = list(ib)
                    except Exception:
                        h = None
                if h is not None and h.m_Vertices is not None \
                        and not isinstance(h.m_Vertices, list):
                    try:
                        h.m_Vertices = [tuple(v) for v in h.m_Vertices]
                    except Exception:
                        h = None
            self._handler_cache[reader] = h
        return self._handler_cache[reader]

    def clear_caches(self):
        """Drop everything cached for the previous tank.

        Without this the mesh cache grows by ~60 meshes per tank and holds the
        whole 1.5 GB asset file's geometry alive, which eventually makes the
        process misbehave.
        """
        self._handler_cache.clear()
        self._mesh_cache.clear()
        self._mat_cache.clear()
        self._tex_cache.clear()

    def material_textures(self, mat):
        out = []
        props = getattr(mat, "m_SavedProperties", None)
        for key, val in (getattr(props, "m_TexEnvs", None) or []):
            reader = try_deref(getattr(val, "m_Texture", None))
            if reader is not None:
                out.append((str(key), reader))
        return out

    def albedo_transform(self, mat):
        """Unity samples the albedo as uv * tiling + offset; OBJ has to bake it."""
        if mat is None:
            return (1.0, 1.0, 0.0, 0.0)
        props = getattr(mat, "m_SavedProperties", None)
        for key, val in (getattr(props, "m_TexEnvs", None) or []):
            slot = str(key).strip("_").lower()
            if slot in ("maintex", "basemap", "albedo", "diffusemap", "basecolormap",
                        "basecolor", "diffuse"):
                sc = getattr(val, "m_Scale", None)
                of = getattr(val, "m_Offset", None)
                if sc is not None and of is not None:
                    if (sc.x, sc.y, of.x, of.y) != (1.0, 1.0, 0.0, 0.0):
                        return (sc.x, sc.y, of.x, of.y)
        return (1.0, 1.0, 0.0, 0.0)

    def world_matrix(self, tr):
        chain = []
        cur = tr
        while cur is not None and len(chain) < 512:
            d = self.tr.get(cur)
            if d is None:
                break
            chain.append(d)
            cur = try_deref(d.m_Father)
        m = list(IDENTITY)
        for d in reversed(chain):
            lp, lr, ls = d.m_LocalPosition, d.m_LocalRotation, d.m_LocalScale
            m = mat_mul(m, trs_matrix((lp.x, lp.y, lp.z),
                                      (lr.x, lr.y, lr.z, lr.w),
                                      (ls.x, ls.y, ls.z)))
        return m

    def materials_of(self, go):
        if go in self.smr:
            return self.smr[go][1]
        return self.mr.get(go, [])

    def root_candidates(self, tank_names):
        cand = collections.defaultdict(list)
        for go, n in self.go_name.items():
            if n in tank_names:
                cand[n].append(go)

        def depth(go):
            tp = self.go2tr.get(go)
            d = 0
            while tp is not None and d < 500:
                father = try_deref(self.tr[tp].m_Father)
                if father is None:
                    return d
                tp = self.go2tr.get(father)
                if tp is None:
                    return d
                d += 1
            return d

        roots = {}
        for n, gos in cand.items():
            zero = [g for g in gos if depth(g) == 0]
            roots[n] = zero[0] if zero else gos[0]
        return roots


def ordered_gameobjects(g, root_go):
    """Depth-first pre-order over the prefab; slot order defines submesh order.

    Returns (gameobject, is_wreck, is_camo) triples.  A slot counts as wreck (or
    camo) when the name of the slot itself *or of any ancestor group* says so -
    some tanks keep the wreck under e.g. HullGroup_Destructed/Hull_LOD0 without
    renaming the leaf.

    A node whose name matches BLUR_RE marks its whole subtree: the game hangs a
    helicopter's motion-blur rotor disc (`HelicopterBladeSmoothed` under a node
    literally named `blur`) there, next to the real `*_Blades_*_LOD0` assembly.
    """
    start = g.go2tr.get(root_go)
    out, seen = [], set()
    if start is None:
        return out
    stack = [(start, False, False, False)]
    while stack:
        tp, parent_wreck, parent_camo, parent_blur = stack.pop()
        if tp in seen:
            continue
        seen.add(tp)
        go = g.tr_go.get(tp)
        is_wreck, is_camo, is_blur = parent_wreck, parent_camo, parent_blur
        if go is not None:
            name = g.go_name.get(go, "")
            if WRECK_RE.search(name):
                is_wreck = True
            if CAMO_RE.search(name):
                is_camo = True
            if BLUR_RE.search(name):
                is_blur = True
            out.append((go, is_wreck, is_camo, is_blur))
        for c in reversed(g.tr_kids.get(tp, ())):
            stack.append((c, is_wreck, is_camo, is_blur))
    return out


# 只写模型不写贴图（排查崩溃用，见 write_model 里的注释）
NO_TEX = os.environ.get("MW_NO_TEX") == "1"
# 每张贴图解码前打一行格式/尺寸（定位是哪张贴图解码时崩的）
DEBUG_TEX = os.environ.get("MW_DEBUG_TEX") == "1"


def build_plan(g, order, lod=0, skip_camo=False):
    """按游戏自己的拼装方式组装模型 —— 不做任何几何推断。

    游戏把整车用 Unity **静态合批**烘成一个网格。每个部件的 MeshRenderer 通过
    `m_StaticBatchInfo(firstSubMesh, subMeshCount)` 声明「我负责画第几段子网格」；
    合批时顶点已经被变换到合批根（预制体根）的坐标系里，所以：

        * 部件摆放 = identity，顶点已经在正确位置
        * 只取它声明的那一段子网格

    实测抽查 60 辆车：6214 个共享网格的渲染器里 6212 个带这个字段，且各段
    firstSubMesh 恰好铺满 0..N-1。这就是游戏真正的拼法。

    没有 StaticBatchInfo 的渲染器是普通网格（非合批件，比如伪装网、探照灯）：
    整个网格 + 它自己 Transform 的变换。

    `lod` 选出哪一档：每个部件按名字里的 `_LODn` 归到对应档，只留 `lod` 那一档。
    名字里没有 LOD 标记的（PKT 机枪、`ROD0` 手误那种）各档都保留 —— 全库 40 辆
    抽查下来只有 10 个，留着比漏掉稳妥。

    每项 = (gameobject, mesh_reader, transform, submesh_indices_or_None, materials)
    """
    intact, wreck = [], []

    def keep(go, is_wreck, is_camo, is_blur):
        name = g.go_name.get(go, "") or ""
        if COLLIDER_RE.search(name) or EFFECT_RE.search(name):
            return False
        if is_blur:
            return False
        n = lod_of(name)
        if n is not None and n != lod:
            return False
        if is_camo and skip_camo:
            return False
        return True

    for go, is_wreck, is_camo, is_blur in order:
        if not keep(go, is_wreck, is_camo, is_blur):
            continue
        mf = g.mf.get(go)
        smr = g.smr.get(go)
        if mf is not None:
            mesh_reader = mf
            mats = g.mr.get(go) or g.materials_of(go)
        elif smr is not None:
            mesh_reader = smr[0]
            mats = smr[1]
        else:
            continue
        mesh = g.mesh(mesh_reader)
        if mesh is None:
            continue
        nsub = len(getattr(mesh, "m_SubMeshes", ()) or ())

        first, count = g.sbi.get(go, (0, 0))
        if count > 0 and nsub > 0:
            # 静态合批件：顶点烘在**合批根**的坐标系里，只画自己那一段子网格。
            # 合批根由 m_StaticBatchRoot 直接给出（TurretGroup / BarrelGroup /
            # Cloth01 / 车体根…），不用猜。Type89MLRS 的伪装网网格是 100 倍画的，
            # 它的合批根 Cloth01 带 0.01 缩放，套上去正好还原。
            lo = max(0, min(first, nsub - 1))
            hi = max(lo + 1, min(first + count, nsub))
            subs = list(range(lo, hi))
            rt = g.batch_root.get(go)
            tr = None
            if rt is not None:
                tr = g.go2tr.get(rt)
                if tr is None and rt in g.tr:
                    tr = rt
            mnt = g.world_matrix(tr) if tr is not None else list(IDENTITY)
        else:
            # 普通网格（没参与合批）：整个网格，用对象自己的变换
            subs = None
            tr = g.go2tr.get(go)
            if tr is None:
                continue
            mnt = g.world_matrix(tr)
        item = (go, mesh_reader, mnt, subs, mats)
        (wreck if is_wreck else intact).append(item)
    return intact, wreck


def drop_off_model(g, items):
    """Remove parts parked far outside the vehicle (spare attachments)."""
    prepared = []
    for it in items:
        go, mesh_reader, m, sub_idx, _mats = it
        mesh = g.mesh(mesh_reader)
        h = g.handler(mesh_reader)
        if h is None:
            continue
        V = h.m_Vertices
        tris = h.get_triangles()
        if sub_idx is not None:
            use = [tris[i] for i in sub_idx if i < len(tris)]
            idxs = sorted({j for t in use for tri in t for j in tri})
        else:
            idxs = range(len(V))
        if not idxs:
            continue
        pts = [xform_point(m, V[j]) for j in idxs]
        mn = [min(p[i] for p in pts) for i in range(3)]
        mx = [max(p[i] for p in pts) for i in range(3)]
        prepared.append({"it": it, "h": h, "mn": mn, "mx": mx,
                         "centre": [(mn[i] + mx[i]) / 2 for i in range(3)],
                         "diag": sum((mx[i] - mn[i]) ** 2 for i in range(3)) ** 0.5})
    if len(prepared) < 4:
        return prepared, []
    kept, dropped = list(prepared), []

    # 停放备件判定一：与"模型其余部分"的间隙。
    # 真部件（机炮、旋翼叶片、火箭巢、侧裙、车轮）即使伸得很远，包围盒仍与机体相接；
    # 而停放件是悬空另放的（Cheonma2 的机枪在 x=-1.29、K21 的浮囊在 ±2.3、
    # Archer 的机枪在 57 处、Type89MLRS 的伪装网在 42 处）。所以判据看**间隙**而不是
    # 包络范围——早先用"相对车体的横向/纵向包络"会把 A10 机炮、直升机旋翼叶片、
    # 火箭巢这些合法外伸件一起删掉。
    if 4 <= len(kept) <= 400:
        keep2 = []
        for i, p in enumerate(kept):
            lo = [min(q["mn"][k] for j, q in enumerate(kept) if j != i) for k in range(3)]
            hi = [max(q["mx"][k] for j, q in enumerate(kept) if j != i) for k in range(3)]
            gap = 0.0
            for k in range(3):
                if p["mx"][k] < lo[k]:
                    gap += (lo[k] - p["mx"][k]) ** 2
                elif p["mn"][k] > hi[k]:
                    gap += (p["mn"][k] - hi[k]) ** 2
            gap **= 0.5
            diag = sum((hi[k] - lo[k]) ** 2 for k in range(3)) ** 0.5
            if gap <= 0.25 * max(diag, 1e-6):
                keep2.append(p)
            else:
                p["why"] = "gap %.2f / diag %.2f" % (gap, diag)
                dropped.append(p)
        kept = keep2

    # A vehicle stands on its running gear, so anything entirely below the wheel
    # or track bottom is a spare attachment the prefab keeps parked (weapons and
    # turrets are separate SubSystems/<weapon>_<tank> prefabs mounted at runtime;
    # e.g. M3A3 keeps its TOW launcher under the floor while M3Bradley has the
    # same mesh mounted on the turret).
    gear = [p for p in kept if GEAR_RE.search(g.go_name.get(p["it"][0], ""))]
    if gear and kept:
        floor = min(p["mn"][1] for p in gear)
        keep2 = []
        for p in kept:
            if p["mx"][1] < floor - 0.02:
                p["why"] = "below floor %.2f" % floor
                dropped.append(p)
            else:
                keep2.append(p)
        kept = keep2
    return kept, dropped


def _tex_expected_bytes(fmt, w, h):
    """这张贴图按格式至少需要多少字节压缩数据（不含 mip）。

    BC1/DXT1/ETC1/ETC2_RGB 是 4x4 块 8 字节，BC3/BC5/BC7 是 16 字节；
    ASTC 一律 16 字节一块，块大小看格式名（ASTC_RGB_8x8 -> 8x8）。
    返回 None 表示这格式不按块算（未压缩 RGBA 之类），不用检查。
    """
    name = getattr(fmt, "name", str(fmt))
    up = name.upper()
    if "ASTC" in up:
        m = re.search(r"ASTC_\w*?(\d+)X(\d+)", up)
        bx, by = (int(m.group(1)), int(m.group(2))) if m else (4, 4)
        return max(1, (w + bx - 1) // bx) * max(1, (h + by - 1) // by) * 16
    if up.startswith(("DXT1", "BC1", "ETC", "EAC", "ATC", "PVRTC")):
        n = 8 if ("DXT1" in up or "BC1" in up or "ETC1" in up
                  or up in ("ETC2_RGB", "ETC_RGB4")) else 16
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * n
    if up.startswith(("DXT5", "BC3", "BC4", "BC5", "BC6", "BC7")):
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16
    return None


def texture_data_available(tex):
    """这张贴图的数据够不够安全解码。

    编译版解码器（texture2ddecoder / astc_encoder / etcpak）是**按声明的宽高**
    往输出缓冲区写的：输入哪怕只有几十字节，它照样写满 宽×高×4，于是越界把堆写坏，
    进程随后随机崩在别处（实测多次落在 MeshHelper.get_triangles），
    表现就是「全部导出跑到一半失败」，而且时好时坏。

    数据要么在 m_Data 里，要么按 m_StreamData 去 .resS 取；拿到的字节数少于
    格式所需就跳过这张，不交给解码器。
    """
    w = int(getattr(tex, "m_Width", 0) or 0)
    h = int(getattr(tex, "m_Height", 0) or 0)
    fmt = getattr(tex, "m_TextureFormat", None)
    need = _tex_expected_bytes(fmt, w, h) if (w and h) else None

    data = getattr(tex, "m_Data", None)
    n = len(data) if data else 0
    if n:
        return need is None or n >= need

    sd = getattr(tex, "m_StreamData", None)
    path = getattr(sd, "path", "") if sd is not None else ""
    size = int(getattr(sd, "size", 0) or 0)
    if not path:
        return need is None or need == 0        # 没数据也不用解
    try:
        from UnityPy.helpers.ResourceReader import get_resource_data
        reader = getattr(tex, "object_reader", None)
        af = getattr(reader, "assets_file", None) if reader is not None else None
        if af is None:
            return False
        blob = get_resource_data(path, af, getattr(sd, "offset", 0), size)
        got = len(blob) if blob is not None else 0
    except Exception:
        return False
    if got <= 0:
        return False
    if need is not None and got < need:
        return False
    return True


def write_model(g, tank, prepared, outdir, basename, header):
    """Write OBJ + MTL + textures for a set of prepared parts."""
    texdir = os.path.join(outdir, "textures")
    os.makedirs(texdir, exist_ok=True)
    obj = [f"# {tank} - {header}\n",
           f"# Unity coords, X negated for OBJ\n",
           f"# scale x{SCALE:g} (1 game unit = 1/{SCALE:g} m)\n",
           f"mtllib {basename}.mtl\n"]
    mtl = [f"# materials for {tank} ({header})\n"]
    written_tex = {}
    mat_seen = set()
    skipped_tex = set()
    vbase = 0
    total_v = total_f = 0
    parts = []

    for p in prepared:
        go, mesh_reader, m, sub_idx, _mats = p["it"]
        mesh = g.mesh(mesh_reader)
        h = p["h"]
        name = g.go_name.get(go, "part")
        tris = h.get_triangles()
        if sub_idx is not None:
            use = [tris[i] for i in sub_idx if i < len(tris)]
            flat = [t for group in use for t in group]
        else:
            flat = [t for group in tris for t in group]
        if not flat:
            continue
        order_idx = sorted({j for t in flat for j in t})
        remap = {old: i for i, old in enumerate(order_idx)}

        mat_names = []
        uv_st = (1.0, 1.0, 0.0, 0.0)
        for reader in p["it"][4]:
            mat = g.material(reader)
            mname = getattr(mat, "m_Name", None) if mat else None
            mname = mname or f"mat_{reader.path_id}"
            mat_names.append(mname)
            if mat is not None and uv_st == (1.0, 1.0, 0.0, 0.0):
                uv_st = g.albedo_transform(mat)
            if mat is None or mname in mat_seen:
                continue
            mat_seen.add(mname)
            mtl.append(f"\nnewmtl {safe_name(mname)}\nKd 0.8 0.8 0.8\nKa 0 0 0\n"
                       f"Ks 0 0 0\nNs 10\nillum 1\n")
            for slot, tex_reader in g.material_textures(mat):
                tex = g.texture(tex_reader)
                if tex is None:
                    continue
                tname = getattr(tex, "m_Name", None) or f"tex_{tex_reader.path_id}"
                fname = safe_name(tname) + ".png"
                saved = written_tex.get(fname)
                if saved is None and not texture_data_available(tex):
                    # 流式数据不在（见函数注释）—— 跳过，硬解会把堆写坏
                    saved = False
                    written_tex[fname] = False
                    skipped_tex.add(tname)
                if saved is None:
                    if DEBUG_TEX:
                        # 崩溃前最后一行就是元凶：记下格式/尺寸/数据长度
                        # （变量名别用 h/n，那会盖掉外层的 MeshHandler / 计数）
                        try:
                            dfmt = getattr(tex, "m_TextureFormat", "?")
                            dw = getattr(tex, "m_Width", -1)
                            dh = getattr(tex, "m_Height", -1)
                            dn = len(getattr(tex, "m_Data", b"") or b"")
                            sys.stderr.write(
                                "[tex] %-40s fmt=%-22s %dx%d data=%d\n"
                                % (tname, getattr(dfmt, "name", dfmt), dw, dh, dn))
                            sys.stderr.flush()
                        except Exception:
                            pass
                    try:
                        # MW_NO_TEX=1 只写模型不写贴图 —— 用来定位崩溃是不是
                        # 出在贴图解码（texture2ddecoder / etcpak / astc_encoder 是编译模块）
                        if NO_TEX:
                            raise RuntimeError("MW_NO_TEX")
                        tex.image.save(os.path.join(texdir, fname))
                        saved = True
                    except Exception as exc:
                        saved = False
                        if not NO_TEX:
                            print(f"    ! texture {tname}: {type(exc).__name__}: {exc}", flush=True)
                    written_tex[fname] = saved
                if saved:
                    slotname = slot.strip("_").lower()
                    if any(x in slotname for x in ("maintex", "base", "diffuse", "albedo")):
                        mtl.append(f"map_Kd textures/{fname}\n")
                    elif "normal" in slotname or "bump" in slotname or slotname.endswith("_n"):
                        mtl.append(f"map_Bump textures/{fname}\n")

        gname = safe_name(f"{name}_{sub_idx[0]}" if sub_idx else name)
        obj.append(f"g {gname}\no {gname}\n")
        has_uv = bool(h.m_UV0)
        has_n = bool(h.m_Normals)
        k = SCALE
        ox, oy, oz = part_offset(gname)
        pts = [xform_point(m, h.m_Vertices[j]) for j in order_idx]
        obj.extend(f"v {-p[0]*k+ox:.6g} {p[1]*k+oy:.6g} {p[2]*k+oz:.6g}\n" for p in pts)
        if has_uv:
            sx, sy, ox, oy = uv_st
            obj.extend(f"vt {h.m_UV0[j][0]*sx+ox:.6g} {h.m_UV0[j][1]*sy+oy:.6g}\n"
                       for j in order_idx)
        if has_n:
            # 法线不随等比缩放变化
            nrm = [xform_dir(m, h.m_Normals[j]) for j in order_idx]
            obj.extend(f"vn {-p[0]:.6g} {p[1]:.6g} {p[2]:.6g}\n" for p in nrm)
        if mat_names:
            obj.append(f"usemtl {safe_name(mat_names[0])}\n")
        for a, b, c in flat:
            A, B, C = remap[c] + vbase + 1, remap[b] + vbase + 1, remap[a] + vbase + 1
            if has_uv and has_n:
                obj.append(f"f {A}/{A}/{A} {B}/{B}/{B} {C}/{C}/{C}\n")
            elif has_uv:
                obj.append(f"f {A}/{A} {B}/{B} {C}/{C}\n")
            else:
                obj.append(f"f {A} {B} {C}\n")
        vbase += len(order_idx)
        total_v += len(order_idx)
        total_f += len(flat)
        parts.append({"part": name, "mesh": getattr(mesh, "m_Name", None),
                      "submesh": sub_idx[0] if sub_idx else None,
                      "verts": len(order_idx), "tris": len(flat),
                      "material": mat_names[0] if mat_names else None,
                      "uv_tiling": list(uv_st)})

    objp = os.path.join(outdir, basename + ".obj")
    with open(objp, "w", encoding="utf-8") as fh:
        fh.write("".join(obj))
    with open(os.path.join(outdir, basename + ".mtl"), "w", encoding="utf-8") as fh:
        fh.write("".join(mtl))
    return {"parts": parts, "vertices": total_v, "triangles": total_f,
            "scale": SCALE,
            "turret_offset": list(TURRET_OFFSET), "gun_offset": list(GUN_OFFSET),
            "gun_follows_turret": GUN_FOLLOWS_TURRET,
            "textures": sorted(k for k, v in written_tex.items() if v),
            "skipped_textures": sorted(skipped_tex)}


def export_tank(g, tank, root_go, country, outroot, lod=0, skip_camo=False):
    g.clear_caches()
    order = ordered_gameobjects(g, root_go)
    intact_items, wreck_items = build_plan(g, order, lod, skip_camo)
    if not intact_items and not wreck_items:
        return None
    outdir = os.path.join(outroot, safe_name(country), safe_name(tank))
    os.makedirs(outdir, exist_ok=True)

    # LOD0 用原来的文件名（预览/微调都按这个找），LOD1/2 带后缀区分开
    base = safe_name(tank) + ("" if lod == 0 else "_LOD%d" % lod)
    result = {"tank": tank, "country": country, "lod": lod}
    # 外观和残骸共用同一套微调值
    apply_tweaks(tank)
    if intact_items:
        kept, dropped = drop_off_model(g, intact_items)
        res = write_model(g, tank, kept, outdir, base, "intact LOD%d" % lod)
        res["skipped_off_model"] = [g.go_name.get(p["it"][0], "?") for p in dropped]
        result["intact"] = res
    if wreck_items:
        kept, dropped = drop_off_model(g, wreck_items)
        res = write_model(g, tank, kept, outdir, base + "_Wreck", "wreck LOD%d" % lod)
        res["skipped_off_model"] = [g.go_name.get(p["it"][0], "?") for p in dropped]
        result["wreck"] = res

    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    return result


# Tanks whose collider asset path does not exist / does not match their prefab
# name, so country cannot be derived from the catalog.
COUNTRY_OVERRIDE = {
    "Karrar": "Iran", "Type59": "China", "BTR80A": "Russian", "BTRBM": "Russian",
    "T62545": "Russian", "BM572Kochevnik": "Russian", "T14": "Russian",
    "T14152": "Russian", "T104Bastion": "Russian", "M10Booker": "USA",
    "MerkavaMk3b": "Israel", "MerkavaMk4": "Israel", "K1A1": "Korea",
    "K3NGMBT": "Korea", "PL1": "China", "PzH2000": "Germany",
    "Type86": "China", "Type90AProto": "Japan", "Strv105": "Sweden",
    "Strv2000": "Sweden", "PinakaMk3": "India", "LeclercSii2AZUR": "France",
    "9A522Smerch": "Russian", "9K31Strela1": "India",
    "FV101Scorpion90Tai": "Thailand", "KNDSLeopard2120ARC3": "Germany",
    "Leopard2Revolution": "Germany", "AntiAirNPC": "Other", "T62": "Russian",
    # 飞机的目录名和预制体名对不上的几架（其余靠前缀/相似度自动匹配）
    "J10_Fighter": "China", "AMCAMk2_Fighter": "India",
    "NorthropF5E_Fighter": "Mexico",      # 目录 Mexican/F5ETiger2
    "TU222_Fighter": "Russian",           # 目录在 Bombers/ 下
    "Lancet53_Fighter": "Russian", "SwitchBlade600Remote_Fighter": "USA",
    "aleCF3_Fighterter": "French",        # 名字本身是乱的，对应 French/RafaleCf3
}


# 载具类别：Resources/<前缀>/<名> 是预制体，Assets/Content/Mesh/<目录>/<国家>/<名>/
# 是碰撞体资源（用来定国家）。坦克、固定翼、直升机用的是同一套拼装规则。
KINDS = {
    "tanks": [("Tanks/", "Tanks")],
    "fighters": [("Fighters/", "Fighters")],
    "helicopters": [("Helicopters/", "Helicopters")],
    "air": [("Fighters/", "Fighters"), ("Helicopters/", "Helicopters")],
    "all": [("Tanks/", "Tanks"), ("Fighters/", "Fighters"),
            ("Helicopters/", "Helicopters")],
}
KIND = "tanks"
_ACTIVE = KINDS["tanks"]


def set_kind(spec):
    """spec 可以是 tanks / fighters / helicopters / air / all，也可以逗号组合，
    例如 "tanks,helicopters"。"""
    global KIND, _ACTIVE
    KIND = spec
    pairs, seen = [], set()
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if part not in KINDS:
            raise SystemExit("unknown kind %r (可用: %s)"
                             % (part, ", ".join(sorted(KINDS))))
        for pr in KINDS[part]:
            if pr[0] not in seen:
                seen.add(pr[0])
                pairs.append(pr)
    _ACTIVE = pairs or KINDS["tanks"]


def tank_name_set(kinds=None):
    active = kinds or _ACTIVE
    prefixes = [p for p, _d in active]
    return {r["path"].split("/")[-1] for r in
            json.load(open(os.path.join(MW, "catalog_index.json"), encoding="utf-8"))
            if any(r["path"].startswith(p) for p in prefixes)}


def build_country_map(kinds=None):
    """prefab name -> country folder, from the collider asset paths.

    Aircraft prefab names carry a _Fighter/_Helicopter suffix and a few folder
    names differ from the prefab name (Mi35P folder vs Mi35M prefab), so the
    folder name, its collider asset names and a similarity fallback are all used.
    """
    import difflib
    # 国家表从所有载具目录建（TU222 的网格在 Bombers/ 下，但它作为 Fighter 导出）
    kinddirs = {d for _p, d in KINDS["all"]} | {"Bombers"}
    pairs = []          # (candidate name lower, country)
    for r in json.load(open(os.path.join(MW, "catalog_index.json"), encoding="utf-8")):
        m = re.match(r"Assets/Content/Mesh/([^/]+)/([^/]+)/([^/]+)/", r["path"])
        if not m or m.group(1) not in kinddirs:
            continue
        country, folder = m.group(2), m.group(3)
        pairs.append((folder.lower(), country))
        stem = re.sub(r"(_colliders)?(_lod\d)?\.[a-z]+$", "",
                      r["path"].rsplit("/", 1)[-1], flags=re.I)
        if stem and stem.lower() != folder.lower():
            pairs.append((stem.lower(), country))

    cmap = {}
    for name in tank_name_set(kinds):
        key = re.sub(r"_(fighter|helicopter|bomber)$", "", name, flags=re.I).lower()
        best = None
        for cand, country in pairs:
            if key == cand:
                best = (1000, country)
                break
            n = 0
            for a, b in zip(key, cand):
                if a != b:
                    break
                n += 1
            if n >= 4 and (best is None or n > best[0]):
                best = (n, country)
        if best is None:
            near = difflib.get_close_matches(key, [c for c, _ in pairs], n=1, cutoff=0.7)
            if near:
                for cand, country in pairs:
                    if cand == near[0]:
                        best = (1, country)
                        break
        if best:
            cmap[name] = best[1]
    cmap.update(COUNTRY_OVERRIDE)
    return cmap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sample", type=int, default=0,
                    help="export N randomly chosen tanks instead of all")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--lod", type=int, default=0, choices=(0, 1, 2),
                    help="导出哪一档 LOD（0/1/2，默认 0）。每档单独出一个 OBJ，"
                         "LOD1/2 的文件名带 _LODn 后缀")
    ap.add_argument("--no-camo", action="store_true",
                    help="drop camo nets (they are Cloth meshes, but their stored "
                         "state is the draped net and is correct)")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--kind", default="tanks",
                    help="tanks / fighters / helicopters / air / all，可逗号组合"
                         "（如 tanks,helicopters）")
    ap.add_argument("--work", default=MW,
                    help="workspace holding bundles/data.unity3d and catalog_index.json")
    ap.add_argument("--scale", type=float, default=7.0,
                    help="等比例放大倍数，默认 7（游戏 1 单位 ≈ 1/7 米，×7 后接近米制）；"
                         "--scale 1 保持原始游戏单位")
    ap.add_argument("--turret", default="", metavar="X,Y,Z",
                    help="炮塔整体平移（导出单位，正负都行），如 0,0.05,-0.1")
    ap.add_argument("--gun", default="", metavar="X,Y,Z",
                    help="炮管平移（导出单位），如 0,0,0.2")
    ap.add_argument("--gun-no-follow", action="store_true",
                    help="默认炮管跟着炮塔一起动，加这个则炮管只按 --gun 走")
    ap.add_argument("--tweaks", default="", metavar="JSON",
                    help="逐车微调表（GUI 存的那份）：{\"车名\": {\"turret\":[x,y,z], "
                         "\"gun\":[x,y,z], \"follow\":true}}；有它时按车名取，优先于 --turret/--gun")
    ap.add_argument("--skip-existing", action="store_true",
                    help="已经导出过的车跳过（原生崩溃后接着导剩下的用）")
    args = ap.parse_args()
    set_kind(args.kind)
    global SCALE, BASE_TURRET, BASE_GUN, BASE_FOLLOW, TWEAKS
    SCALE = args.scale
    BASE_TURRET = parse_xyz(args.turret, "--turret")
    BASE_GUN = parse_xyz(args.gun, "--gun")
    BASE_FOLLOW = not args.gun_no_follow
    if args.tweaks:
        try:
            # utf-8-sig：记事本 / PowerShell 存的 json 常带 BOM，普通 utf-8 会读不了
            TWEAKS = json.load(open(args.tweaks, encoding="utf-8-sig"))
            print("tweaks: %s（%d 辆）" % (args.tweaks, len(TWEAKS)), flush=True)
        except Exception as exc:
            print("!! 读不了 --tweaks %s: %s" % (args.tweaks, exc), flush=True)

    if os.path.abspath(args.work) != os.path.abspath(MW):
        set_work(args.work)

    if not os.path.exists(DATA):
        print("player data not found: %s" % DATA, flush=True)
        print("run extract_bundles.py first (GUI: 提取模型 页)", flush=True)
        return 2
    print("work: %s" % MW, flush=True)
    g = GameData(DATA)
    roots = g.root_candidates(tank_name_set())
    cmap = build_country_map()
    print(f"{len(roots)} tank prefab roots", flush=True)

    names = sorted(roots)
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        names = [n for n in names if n in want]
    if args.limit:
        names = names[:args.limit]
    if args.sample:
        rng = random.Random(args.seed)
        names = sorted(rng.sample(names, min(args.sample, len(names))))
        print(f"random sample (seed={args.seed}): {', '.join(names)}", flush=True)

    os.makedirs(args.out, exist_ok=True)
    summary, t0 = [], time.time()

    # --skip-existing：已经导出的跳过。原生崩溃会整批中断（Python 捕不到），
    # 重跑时带上这个就能接着导剩下的。
    def done_before(n):
        d = os.path.join(args.out, safe_name(cmap.get(n, "Other")), safe_name(n))
        p = os.path.join(d, safe_name(n) + ".obj")
        try:
            return os.path.getsize(p) > 0
        except OSError:
            return False

    if args.skip_existing:
        todo = [n for n in names if not done_before(n)]
        if len(todo) != len(names):
            print("skip-existing: 已有 %d 辆，剩 %d 辆要导"
                  % (len(names) - len(todo), len(todo)), flush=True)
        names = todo

    progress(0, len(names))
    for i, n in enumerate(names, 1):
        # 具体哪一套（外观/残骸）由 export_tank 自己按模型切换
        try:
            res = export_tank(g, n, roots[n], cmap.get(n, "Other"), args.out,
                              args.lod, args.no_camo)
        except Exception:
            import traceback
            traceback.print_exc()
            res = None
        if res:
            it = res.get("intact", {})
            wk = res.get("wreck", {})
            summary.append({"tank": n, "country": res["country"],
                            "intact_verts": it.get("vertices", 0),
                            "intact_tris": it.get("triangles", 0),
                            "intact_parts": len(it.get("parts", [])),
                            "wreck_verts": wk.get("vertices", 0),
                            "wreck_tris": wk.get("triangles", 0),
                            "wreck_parts": len(wk.get("parts", [])),
                            "textures": len(it.get("textures", []))})
            print(f"  [{i}/{len(names)}] {res['country']:14s} {n:26s} "
                  f"intact p={len(it.get('parts', [])):3d} v={it.get('vertices', 0):7d} | "
                  f"wreck p={len(wk.get('parts', [])):3d} v={wk.get('vertices', 0):7d} | "
                  f"tex={len(it.get('textures', [])):2d}  ({time.time()-t0:.0f}s)", flush=True)
        else:
            print(f"  [{i}/{len(names)}] {n:26s} -- nothing exported", flush=True)
        progress(i, len(names))

    with open(os.path.join(args.out, "_summary.json"), "w", encoding="utf-8") as fh:
        json.dump({"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "tanks": summary,
                   "totals": {
                       "tanks": len(summary),
                       "intact_vertices": sum(s["intact_verts"] for s in summary),
                       "intact_triangles": sum(s["intact_tris"] for s in summary),
                       "wreck_vertices": sum(s["wreck_verts"] for s in summary),
                       "wreck_triangles": sum(s["wreck_tris"] for s in summary)}},
                  fh, indent=1)
    print(f"done: {len(summary)} tanks in {time.time()-t0:.0f}s -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
