# Modern Warfront 载具模型提取工具链  [English Version](https://github.com/YPA1919/ModernWarfront_VehicleExtractor/blob/main/README_EN.md)

**V1.2 2026.9.18**


从 `modern_warfront_*.apk` 里把载具模型和贴图扒出来，输出 OBJ + MTL + PNG。

按 `Resources/<类别>/<名>` 分三类：`tanks`（`Tanks/<名>`）、
`fighters`（`Fighters/<名>_Fighter`）、`helicopters`（`Helicopters/<名>_Helicopter`）。
坦克另有独立的残骸模型；**飞机没有残骸变体**。

---

# 第一部分：怎么用

## 一、双击 `tank_gui.py`

就这样，不用命令行。会带一个黑色控制台窗口（那是 Python 自己的），关掉它界面也会关，
想不留窗口可以把文件名后缀改成 `.pyw`。

界面分六页，**默认停在「提取模型」**，照着两步走就行：

| 页 | 能做什么 |
| --- | --- |
| **提取模型** | ① 选 APK + 一个**空的**工作目录 → 点「**解包 APK**」；② 选模型输出目录、勾类别和范围 → 点「**提取模型**」。带进度条，已存在的文件自动跳过，随时可停 |
| 部件 | manifest 部件表（网格名 / 子网格号 / 顶点 / 面数 / 材质 / UV 变换）。**点一行只渲染该部件**，排查错位特别快 |
| **微调** | **炮塔 / 炮管位置微调**：前后(Z) / 左右(X) / 上下(Y) 各一对 ± 按钮，步长 0.01~0.5，改一下中间预览实时跟着动。外观和残骸共用同一套值；按车名记在 `tweaks.json`，全量导出自动带上 |
| 贴图 | 该车贴图缩略图墙，双击看原图 |
| 重导 | 对已解包的 bundle 重新导出：填车名、按名字搜索多选、或随机 N 辆 |
| 日志 | 子进程输出与退出码 |
| 中文 / EN | 界面语言切换（切换后界面重建，已填路径和选择保留） |

左侧车辆库按国家分组列出全部载具，可过滤、可随机抽一辆；
「重扫输出目录」扫的是**「模型输出目录」**那个路径，下方会标注当前扫的是哪个目录。
中间是三维预览（左键旋转 / 滚轮缩放 / 右键平移），**默认「实体」模式**，另有线框，
可切外观 / 残骸。

### 源码包开箱即用

`ModernWarfront_VehicleExtractor源码.zip` 里除了脚本，还带了 `pylibs/`（UnityPy / Pillow /
numpy / texture2ddecoder 等，去掉编译中间产物后约 27 MB）。解压后在本目录直接

```powershell
python tank_gui.py
```

就能用，**不用装任何东西**。

> 只有当你只拿走 `.py` 文件、丢掉 `pylibs/` 时，才需要自己装依赖：
>
> ```powershell
> python fetch_wheels.py pylibs UnityPy Pillow numpy texture2ddecoder tpk_ar
> pip install UnityPy Pillow numpy texture2ddecoder tpk_ar
> ```
>
> 真缺了的话，程序启动时会**弹窗把缺的库逐个列出来**并给出上面两条命令，
> 不会只丢一句 `No module named 'UnityPy'`。命令行版本也有同样的提示。

### 免安装 exe

除了跑源码，也有打包好的 exe 文件，**不用装 Python 也能用，在 release 里面**。
成品是 onedir 形式（一个文件夹，里面一个 exe + `_internal`），
解压后**双击 `ModernWarfront_VehicleExtractor.exe`** 即可。

也可以自己构建：

```powershell
& $py build_exe.py     # 用 PyInstaller 构建 -> ..\exe\ModernWarfront_VehicleExtractor\
& $py pack_exe.py      # 整理成可分发的 zip（附带 README 和使用说明）
```

为什么是 onedir 而不是单文件 exe：界面是用**子进程**调用同级脚本的
（解包 / 建索引 / 导出 / 校验 / 出图）。打包后 `sys.executable` 就是 exe 自己，
所以子进程改成 `<exe> --run <脚本名>`，由 `main()` 里的分发分支用 `runpy` 就地执行。
单文件 exe 每次启动都要把整包解到临时目录，子进程也一样 —— 一次导出要解好几遍，
慢得没法用；onedir 没有这个问题。

命令行同样可用（`--run` 后面跟包内脚本名，其余参数不变）：

```powershell
ModernWarfront_VehicleExtractor.exe --run export_tanks.py --work D:\work --out D:\out --kind air
ModernWarfront_VehicleExtractor.exe --run export_tanks.py --out D:\out --only T90A --turret 0,0.05,-0.1 --gun 0,0,0.2
```

打包后脚本里的默认工作目录会变成 `<exe 所在目录>\work`（源码运行时仍是脚本自己所在目录）。

> **重要：载具列表来自工作目录里的 `catalog_index.json`** —— 所以必须**先解包**
> （并勾上「解析 catalog 建立索引」），列表里才会出现载具，也才能提取模型。
> 解包一次后一直可用，不会重复搬运。

## 二、路径必须自己选，没有默认值

首次打开时 **APK 文件 / 解包工作目录 / 模型输出目录** 三处都是空的，**没有任何默认值**，
留空点按钮会直接提示，不会偷偷用某个写死的路径（「重导」页的输出目录同理）。

- **解包工作目录**：必填。第一次用**建议选一个空文件夹** —— 解出来的 `catalog.json` +
  4809 个 bundle + `data.unity3d` 会放在这里（占空间不小，挑个空间够的盘），
  载具列表也从这里读。
- **APK 文件**：**工作目录里已经有解包结果时可以留空**。程序会检查工作目录有没有
  `catalog.json` 和 `bundles/data.unity3d`：有就跳过解包、直接建索引和导出；
  没有才要求选 APK（这时弹窗里还会告诉你本机哪里找得到 APK）。
- **模型输出目录**：必填，OBJ / 贴图写到这里。

想指定车辆库扫哪个目录，可以用启动参数（一般用不上）：

```powershell
python tank_gui.py --root D:\某个已导出的目录
```

## 三、导出范围

解包后**默认不会全量导出**，三种范围：

- **指定载具**（默认）—— 搜索框输名字，列表里勾选（可多选），只导这些；未勾选会提示，
  不会误全量。
- **随机 N 辆** —— 带 seed，可复现（同一个数字每次抽到同一批）。
- **全部** —— 当前类别下的所有载具。

另外两个开关，加一个 LOD 选择：

- **缩放到 7 倍**（默认开）—— 游戏里 1 单位 ≈ 1/7 米，×7 之后基本就是米制尺寸：
  豹2A6MC2 模型长 1.573 单位，×7 = **11.01 m**，真车 10.97 m（差 0.4%）。
  取消勾选就保持游戏原始单位。实际用的倍数写在 OBJ 头部的 `# scale x7` 注释和
  `manifest.json` 的 `scale` 字段里。
- **LOD ○0 ○1 ○2**（默认 0）—— 见下。
- **不要伪装网**（默认关）。

### LOD 选哪档就只导哪档

游戏按远近切换简化模型，LOD0 最精细。界面上是三选一，**选中的那一档单独出一个
OBJ**，不是拼在一起：

| 档 | 外观 | 残骸 |
| --- | --- | --- |
| LOD0 | `<车名>.obj` | `<车名>_Wreck.obj` |
| LOD1 | `<车名>_LOD1.obj` | `<车名>_LOD1_Wreck.obj` |
| LOD2 | `<车名>_LOD2.obj` | `<车名>_LOD2_Wreck.obj` |

三档各自都是**完整的一台车**。以 T90A 为例：

| 档 | 部件 | 顶点 | OBJ 大小 |
| --- | --- | --- | --- |
| LOD0 | 82 | 54289 | 5.62 MB |
| LOD1 | 60 | 17930 | 1.73 MB |
| LOD2 | 59 | 6021 | 0.56 MB |

部件按名字里的 `_LODn` 归到对应档；名字里没有 LOD 标记的（`PKT` 机枪那种，全库
40 辆抽查只有 10 个）各档都保留。顺带认了个游戏自己的手误：
`Hull_ERA_Kontakt1_Side_R_01_ROD0` 里的 **`ROD0` 其实是 `LOD0`**，正则写成
`[LR]OD(\d)` 一起认，否则这块爆反会被当成"无标记"混进每一档。

**可按名字搜索任意类别**：坦克、固定翼、直升机都能搜（`mi2` → Mi-28NM / Mi-24SuperHind，
`z1` → WZ10 / Z11WB / Z19E，`su` → SU-24M / SU-25 / Mi-24SuperHind…）。
待选列表**跟着「载具类别」勾选走**：勾了哪类就只列哪类；
取消某类别时，已勾选但不在列表里的名字会自动清掉，不会出现「选了却导不出来」。

## 四、Blender 出图（带贴图的成品图）

预览工具栏的 **「Blender 出图」**：按当前视角调 Blender 后台渲一张带贴图的 PNG，
存到该车目录的 `render.png`，完成后弹窗预览，可「另存为」。「重导」页还有批量按钮。

做法沿用「最后一炮」那套：`BLENDER_WORKBENCH` 引擎 + `color_type='TEXTURE'` 直接显示
MTL 贴图 + `light='FLAT'`（贴图颜色不被压暗）+ cavity 凹陷阴影交代形体，不用搭灯光、
不用 GPU 光追，单张约 5–15 秒。相机角度与实时预览完全一致。

Blender 路径自动查找（`D:\Blender Foundation\*`、`C:\Program Files\Blender Foundation\*`
或 PATH），也可用环境变量 `BLENDER_EXE` 指定。**没装 Blender 只影响出图**，其它功能照常。

## 五、命令行等价写法

界面上点的那几步，命令行都能做：

```powershell
$py = "D:\Python\Python313\python.exe"     # 换成你自己的解释器
$env:PYTHONIOENCODING = "utf-8"

# 1) 解包（--list-only 可以只看 APK 里有什么，不解）
& $py extract_bundles.py --apk game.apk --work D:\work

# 2) 建索引（载具列表要靠它）
& $py build_index.py --catalog D:\work\catalog.json --out D:\work

# 3) 导出
& $py export_tanks.py --work D:\work --out D:\out                 # 全部
& $py export_tanks.py --kind air --out D:\out                     # 只要飞机
& $py export_tanks.py --kind helicopters --out D:\out             # 只要直升机
& $py export_tanks.py --kind tanks,helicopters --out D:\out       # 逗号组合
& $py export_tanks.py --only T90A,ZBD86,M1A2SEPv2 --out D:\out    # 指定载具
& $py export_tanks.py --kind air --only KA50_Helicopter --out D:\out
& $py export_tanks.py --sample 4 --seed 7 --out D:\out            # 随机 4 辆
& $py export_tanks.py --scale 1 --out D:\out                      # 保持游戏原始单位
& $py export_tanks.py --lod 1 --out D:\out                        # 只导 LOD1
#    --kind: tanks / fighters / helicopters / air / all
#    --lod 0|1|2 导出哪一档（默认 0），每档单独一个 OBJ
#    --no-camo 去掉伪装网
#    --scale 等比例放大倍数，默认 7（见下）
#    --skip-existing 跳过已导出的（原生崩溃后续跑用）

# 4) 预览与校验（可选）
& $py make_previews.py --root D:\out
& $py export_tanks.py --work D:\work --out D:\out --only T90A --turret 0,0.05,-0.1
```

所有脚本都会输出机器可读的 `PROGRESS done total`，GUI 用它驱动进度条。

界面自检（不开窗口，跑一遍就退）：

```powershell
& $py tank_gui.py --selftest      # 建窗 → 载入第一个载具 → 退出
& $py tank_gui.py --shot a.png    # 载入首辆车渲一张图后退出
```

## 六、运行环境与依赖

- **Python 3.13**。脚本里的解释器路径写在 `tank_gui.py` 顶部的 `PY`，换机器请改这一行。
- 第三方库（需自行安装）：

  ```
  UnityPy  Pillow  numpy  texture2ddecoder  tpk_ar
  ```

装法二选一：

**1) 正常 pip**

```powershell
pip install UnityPy Pillow numpy texture2ddecoder tpk_ar
```

**2) pip 用不了时（受限环境）** —— 用自带的下载器装到 `./pylibs`：

```powershell
python fetch_wheels.py pylibs UnityPy Pillow numpy texture2ddecoder tpk_ar
set PYTHONPATH=%cd%\pylibs        # 运行时指向它
```

`tank_gui.py` 给自己启动的子进程会自动设好 `PYTHONPATH=<脚本目录>\pylibs`，
所以只要把依赖装在那，界面里点按钮就能正常工作。

> 贴图解码需要 `texture2ddecoder` 的 abi3 轮子（`cp311-abi3-win_amd64`），
> 它可以直接用在 Python 3.13 上。

## 七、输出结构

```
<out>/<国家>/<车名>/
├── <车名>.obj            外观模型（履带、炮塔、火炮、伪装网齐全）
├── <车名>.mtl
├── <车名>_Wreck.obj      残骸模型（独立文件，与外观完全分离；飞机没有此项）
├── <车名>_Wreck.mtl
├── manifest.json         部件清单 + 被剔除的停放备件
├── preview.png / preview_wreck.png
├── render.png            Blender 出图（用了才有）
└── textures/*.png        _A 基础色 / _N 法线 / _MGC / _EM
```

坐标系：Unity 左手系（Y 上、Z 前），导出 OBJ 时按惯例对 X 取反。
Blender 导入请选 **Y-Up / -Z Forward**。

尺度：默认整体放大 **7 倍**，让模型接近米制（见「导出范围」一节）。
OBJ 第一行会写明 `# scale x7 (1 game unit = 1/7 m)`，manifest 里也有 `scale` 字段。

## 八、包里有什么

全部 Python 脚本平铺在同一层，**不要拆到子文件夹** —— 脚本之间是互相 `import` 的，
`tank_gui.py` 也用*自己所在目录*去拼 `export_tanks.py` / `extract_bundles.py` 的路径，
一旦分目录界面就调不到子脚本了。

| 脚本 | 作用 |
| --- | --- |
| `tank_gui.py` | **图形界面**（入口）：解包 / 浏览 / 检查 / 提取 / 出图一体 |
| `extract_bundles.py` | 解包 APK（catalog + 4809 个 bundle + `data.unity3d`） |
| `build_index.py` | 解析 Addressables catalog，建「资源路径 ↔ GUID ↔ bundle」索引 |
| `aacatalog.py` | catalog 二进制解析器（被 `build_index.py` 调用） |
| `export_tanks.py` | **主导出脚本** |
| `make_previews.py` | 批量预览图 + 两张总览图 |
| `part_groups.py` | 炮塔 / 炮管部件判定（导出与界面预览共用一份） |
| `check_sample.py` | 随机抽 N 辆导出并出图 |
| `blender_shot.py` | **Blender 出图**（单张 / 批量） |
| `get_preview_ref.py` | 提取游戏自带的官方预览图（当拼装基准用） |
| `render_obj.py` / `render_textured.py` | 离线渲染（无贴图四视图 / 带贴图） |
| `fetch_wheels.py` | 依赖下载器（pip 不好使时用） |
| `diag_*.py`（30 个） | 排查用的一次性探针 |
| `_gui_*.py` / `_i18n_check.py`（9 个） | 自检脚本 |
| `README.md` / `README_EN.md` | 本文档（中 / 英） |

**不包含**：游戏 APK、解包出来的 bundle、导出的模型与贴图、第三方依赖库。

---

# 第二部分：原理

## 九、游戏是怎么把载具拼起来的

可见模型不在 Addressables bundle 里（bundle 内只有碰撞体），而在
`data.unity3d` → `resources.assets`（47 万对象）中，以 `Resources/<类别>/<车名>`
预制体形式存在。

**拼装方式是 Unity 静态合批，代码照着字段直译，不做任何几何推断。**
每个部件的 MeshRenderer 上有两个字段说明了拼法：

```
m_StaticBatchInfo(firstSubMesh, subMeshCount)   "我负责画第 firstSubMesh 段子网格"
m_StaticBatchRoot                              顶点烘在这个节点的坐标系里
```

于是规则只有两条：

| 情况 | 摆放用哪个变换 | 取哪几段子网格 |
| --- | --- | --- |
| 有 StaticBatchInfo（合批件） | **合批根节点的变换** | 只取 `[firstSubMesh, firstSubMesh+subMeshCount)` |
| 没有（普通网格，如伪装网、探照灯） | 对象自己的变换 | 整个网格 |

实测抽查 60 辆车：6214 个共享网格的渲染器里 **6212 个带这个字段**，且各段
`firstSubMesh` 恰好铺满 `0..N-1`、无越界。

合批根是按**部件族**分的，一辆车上有好几个：

```
AHSKrab     根 AHSKrab      -> Hull_*            缩放(1, 1, 1)
            根 TurretGroup  -> CommandTower_*    世界(0, 0.268, -0.201)
            根 BarrelGroup  -> Barrel_*          世界(0, 0.353, 0.235)
            根 Cloth01      -> Camo_net_Hull_*   缩放(1, 1, 1)
Type89MLRS  根 Cloth01      -> Camo_net_Hull_*   缩放(0.01, 0.01, 0.01)   ← 关键
```

Type89MLRS 的伪装网网格是按 **100 倍**画的，靠 `Cloth01` 的 0.01 缩放还原 ——
这个 0.01 只有从 `m_StaticBatchRoot` 拿得到。猜错的后果：网被放大 100 倍甩到车外，
整车包围盒被撑到 811 单位，预览视角被迫拉到几千米外，看起来"什么都没导出来"。

> **这一节以前写的是另一套理论**：「组网格 + 槽位顺序决定子网格」「网格的坐标空间
> 决定摆放变换」，靠统计「第 i 个 slot 的世界坐标与第 i 个子网格中心重合」来推。
> 那套在多数车上碰巧成立，遇到 Type89MLRS 这种就崩了。改成直接读
> `m_StaticBatchInfo` / `m_StaticBatchRoot` 之后不用猜了 —— 相关启发式代码
> （`choose_mount` / `group_mount` / `resolve_camo_mounts` / `submesh_centres` /
> `assign_by_position` 等 9 个函数）已全部删除。

### 第 0 层：坦克和飞机共用什么、不共用什么

飞机（固定翼 / 直升机）完全复用同一套导出流程：国家从
`Assets/Content/Mesh/<类别>/<国家>/<名>/` 的碰撞体资源反查，预制体名就是
Resources 路径最后一段（`A10A_Fighter`、`KA50_Helicopter`）。差别有两点：

- 层级是**嵌套**的：`<名>_Helicopter`（根）→ `<名>` → `<名>_Hull_LOD0` →
  各部件，机翼 / 起落架 / 旋翼都挂在机体下面。走 `m_Father` 链才能得到正确变换。
- 直升机多一个 **`blur` 分组**：旋翼模糊盘挂在这里（见坑 6），必须排除。

### 第 1 层：残骸判定看层级路径

外观件与残骸件在同一个合批网格里，靠名字区分：`Hull_LOD0` 与
`Hull_Destructed_LOD0` 是同一网格的两段子网格。残骸判定不能只看叶子名 ——
PzH2000 的残骸是 `HullGroup_Destructed/Hull_LOD0`，叶子名里根本没有 `Destructed`，
所以 `ordered_gameobjects` 往下走时把「残骸」标记传给整棵子树。

### 第 2 层：武器 / 炮塔是独立子系统预制体

游戏有 **662 个 `SubSystems/<武器>_<车名>_<口径>`** 预制体（如
`M3A3_BGM71TOW_152mm`、`Ksp39C_7mm`），运行时挂载。坦克预制体里因此留有
**未挂载的备用副本**，被停在车体外：地面以下（M3A3 的 TOW、PansirSM/PinakaMk3 的支架、
Strv2000 的 KSP39C）、车体左右之外（Cheonma2 的 `Gun_LOD0` 在 x=−1.29）。

## 十、踩过的坑（都已在代码里处理）

1. **UV 必须烘焙材质的 tiling/offset**：Unity 采样做 `uv * tiling + offset`
   （`_MainTex_ST`）。570 个材质里 88 个反照率 tiling 非默认（多为 `(1,2)`，
   另有 `(1,4)` 的 `StingerLauncher`、`(1,8)` 的 `LAV600_Wheels`）。已烘进 `vt`，
   应用值记在 manifest 的 `uv_tiling`。

2. **履带是 SkinnedMeshRenderer**（910 个，191/223 辆车），不是 MeshFilter。
   其网格是骨骼局部空间，绑定姿态下按渲染器自身变换放置。

3. **伪装网是正常披挂的**：材质 `TankCloth`，预制体存的就是披挂好的网（贴合车体 /
   炮塔 / 炮管）。`--no-camo` 可去掉。它那张贴图 49.5% 的像素是透明的，但
   **RGB 通道是一张完整的迷彩叶片图案**（透明区的 RGB 也是正常橄榄 / 卡其，不是黑的），
   所以预览里直接按 RGB 贴上去就是一张正常的迷彩网 —— 一度按 alpha 抠图，抠完只剩
   零散叶片，比不抠还难看。

4. **停放备件的判据要按「间隙」而不是「包络」**（加飞机时才暴露）。游戏把未挂载的
   备用武器停在载具之外，需要剔除；但判据一度写成「相对车体的横向 / 纵向包络」，
   于是把 A10 机头那门机炮、直升机旋翼叶片、火箭巢这些**合法外伸件**一起删了。
   更早还有一条「对角线 > 20×中位数」的护栏：飞机上大量小面板把中位数压得很低，
   **机体自己**先被删掉，包络基准随即落到一片小机翼上，整车零件全灭。

   > 现在按「与模型其余部分包围盒的间隙 > 0.25×模型对角线」剔除 —— 真部件即使伸得远，
   > 包围盒仍与机体**相接**；停放件是悬空另放的。实测：Cheonma2 备用机枪 gap 0.95、
   > K21 浮囊 1.97、Archer 机枪 75.6、Type89MLRS 伪装网 20.8 全部命中；
   > 而 A10 机炮、旋翼叶片、F-16 起落架的 gap 都是 0.00（保留）。

6. **特效件要单独排除**，两类：

   - `FighterSuperSonicCone`（超音速激波锥）：49 架飞机带着它，网格本身只有 ±0.09 大，
     却被放大 10 倍罩在机身上，渲染成一个巨大漏斗。它不是硬件。
   - **`blur` 节点下的东西 = 旋翼模糊桨盘**：直升机把 `HelicopterBladeSmoothed`
     （每架 6 片左右）挂在名为 `blur` 的节点下 —— 那是旋翼高速旋转时才显示的模糊盘，
     真正的桨叶是挂在 `*_Rotor_01/02_LOD0` 下的 `*_Blades_01/02_LOD0`。27 架直升机都有。
     整棵 `blur` 子树都要按名字排除，否则每架直升机都会多出一圈角度错乱的桨叶
     （这正是「零件位置不对」的来源）。

     > 注意 Unity 会给重名节点加后缀：有的直升机除了 `blur` 还有 **`blur_001`**。
     > 只匹配 `^blur$` 会漏掉后面这个，Mi-24 就因此还剩两片错位桨盘。
     > 现在的正则 `^blur(_\d+)?( \(\d+\))?$` 把几种写法都覆盖了。

   排除是按**祖先链**做的：`ordered_gameobjects` 往下走时把 `blur` 标记传给整棵子树。

7. **矩阵乘法写错了参数顺序**（最隐蔽的一个，飞机起落架错位就是它）。
   `mat_mul(a, b)` 的索引原本写成 `Σ_k a[col=i][row=k] · b[col=k][row=j]`，
   在列主序下这算的是 **`b · a`** —— 于是 `world_matrix` 把父链从叶到根反着乘了。

   > 为什么坦克一直看不出来：链条里全是**纯平移**时 `a·b == b·a`，顺序无所谓。
   > 飞机起落架是 `R_01 → R_03 → R_05` 这种**带转角的关节链**，顺序一错，
   > `Chassis_L_03` 和 `Chassis_R_03` 双双甩到中轴线上重叠，轮子和支柱随之散开。
   > 修正后左右件正确镜像（L 在 x[−0.15,−0.11]、R 在 x[0.11,0.15]）。
   > 用 200 组随机矩阵与 numpy 对拍：修正后 `mat_mul(A,B) == A@B`。

8. **跨文件 path_id 冲突**：`data.unity3d` 内含 12 个 SerializedFile，path_id 只在
   文件内唯一（全局 92,084 冲突）。所有引用必须走 `PPtr.deref()`，缓存以
   `ObjectReader` 为键。

9. **`ObjectReader` 不可哈希**：UnityPy 用 attrs 生成 `__eq__` 却没有 `__hash__`。
   打补丁 `ObjectReader.__hash__ = object.__hash__`。

10. **编译版模块会原生崩溃**（这是"全部导出跑到一半失败"的真凶）。症状是进程直接
    消失、退出码 `-1073741819`（`0xC0000005` ACCESS_VIOLATION），**Python 捕不到**，
    所以 GUI 只能报一句"退出码 …"。两个来源：

    - `UnityPyBoost`：typetree 读取器在部分 ParticleSystem 上崩；顶点解包
      `unpack_vertexdata` 也会崩。三个入口全部置 None 走纯 Python 回退。
    - **ASTC 贴图解码**（主因）：UnityPy 默认用 `astc_encoder`，实测全量导出跑到
      100~200 辆时随机崩，`faulthandler` 抓到的栈是 `MeshHelper.get_triangles`
      —— 那只是堆被写坏之后碰巧崩的地方，不是真凶。用 `MW_NO_TEX=1` 只写模型不写
      贴图二分：带贴图 7 次崩 5 次，关掉贴图 303/303 一次没崩；再加
      `MW_DEBUG_TEX=1` 逐张打印格式尺寸，才定位到崩溃前解码的清一色是 ASTC 贴图。
      **换成 `texture2ddecoder.decode_astc`**（另一套实现）后连续跑通 ——
      两套解码结果对拍：平均像素差 0.22/255，最大差 1。

    因为原生崩溃没法兜住，另外加了两道保险：`--skip-existing` 断点续跑，
    以及 GUI 遇到非零退出码时自动带 `--skip-existing` 续跑（最多 8 轮，无进展则停）。

11. **每个载具之间必须清空缓存**：否则长跑 200 辆后出现
    `'range_iterator' object is not callable` 这类内存错乱。清空后 RSS 稳定在 2.8 GB。

12. **解包时 `catalog.json` 与 `settings.json` 不能写同一个目标**（曾被 settings 覆盖成空文件）。

13. **贴图解码**：需要 `texture2ddecoder` 的 abi3 轮子，可直接用于 Python 3.13。

## 十一、实时预览

界面中间是软件渲染的预览（左键转、滚轮缩放、右键平移），**两档渲染**：

| 何时 | 用什么 | 耗时 |
| --- | --- | --- |
| 拖动中 / 线框 | 画家算法 + PIL 多边形填充 | 约 30~45 ms/帧，跟手 |
| 松手后（开了「上贴图」） | 逐像素 z-buffer + 真实 UV 贴图 + 法线插值 | 见下 |

贴图那档在**后台线程**跑三级梯度，界面全程不冻：

```
松手瞬间     快档先上屏（约 90 ms 就有画面，不会白屏）
+0.37 s     0.55x 贴图（软一点，但花色立刻能看到）
+0.71 s     1.0x 画布原生分辨率，清晰
+1.25 s     1.5x 超采样再缩回来，边缘抗锯齿
```

中途再拖动 / 缩放会作废后台结果重新来，不会串图。做法参考 `tk2_preview.py`
（一个独立可复用的渲染模块，只用 numpy + Pillow，也能单独用）。

### 渲染器为了这个做的优化（T90A 实测 1.30 s → 0.46 s）

- **按包围盒尺寸精确分桶批量光栅化**：同尺寸的三角形摞成 `(G, bh, bw)` 一起算重心
  坐标和深度。原本每个三角形约 60 次 numpy 小数组调用（实测 24.5 µs/个），2 万个
  光调用开销就 0.5 s 以上 —— 瓶颈是**调用次数**不是算力，所以降分辨率没用。
  试过"补齐到 2 的幂"分桶，反而更慢（1.74 s），白算的像素把收益吃掉了。
- **早深度测试**：先在桶内做 z 比较，把活下来的样本收集起来最后一次性算颜色，
  贴图采样和光照只作用在真正可见的像素上，overdraw 不白花。
- 所有材质贴图竖拼成一张**图集**，一次 fancy index 取整批样本的颜色。
- 热路径用 float32。

### 几个细节

- 贴图先 `convert("RGB")` 再缩放 —— 直接缩 RGBA 的话 Pillow 会按 alpha 预乘，
  游戏贴图 alpha 常是成片 0，RGB 会被抹成纯黑（负重轮整块变黑）。
- 预览用贴图缩到长边 512。
- 两盏灯：主光 + 补光，明暗 = `0.32 + 0.62·主光 + 0.16·补光`。
- 底色中灰蓝 `(58,64,72)`，深色涂装的车轮廓不至于看不出来。
- **伪装网照常贴图**（理由见坑 3）。
- 微调页改了炮塔 / 炮管偏移，预览实时跟着动，不用重新导出。

## 十二、怎么验证拼装对不对

游戏自带每个载具的**官方预览图**，直接拿来当基准比肉眼猜可靠得多：

```powershell
& $py get_preview_ref.py F16 A10A KA50 AH64E M60A3TTS M3A3 ZBD86
# -> _preview_ref\<名>.png   （带 alpha 通道，不透明处就是载具轮廓）
```

对照方法：把导出的模型渲一张同角度的图，和预览图并排比。这些图是游戏美术自己出的，
零件位置对不对一眼就能看出来 —— 起落架那个 bug 就是这么定位的。

结构校验（不用看图）：

```powershell
& $py validate_models.py --root D:\out --work D:\work
```

再加一条最省事的自检：**看整车的包围盒跨度**。正常坦克 9~15（导出的米制单位），
轰炸机按实际尺寸，除此之外出现几十上百就是有零件被放错了。

## 十三、诊断与自检脚本

诊断脚本都认环境变量 `MW_KIND`（`tanks` / `air` / …）：

```powershell
$env:MW_KIND = "air"
& $py diag_parts2.py KA50_Helicopter     # 逐部件世界包围盒
& $py diag_chain.py KA50_Helicopter      # 打印部件的真实父链
& $py diag_gap.py                        # 停放件间隙标定
```

| 脚本 | 用途 |
| --- | --- |
| `diag_tank.py` / `diag_parts2.py` | 单车的部件 / 逐部件包围盒 |
| `diag_chain.py` / `diag_root.py` | 父链、层级扁平度（飞机排查用） |
| `diag_filter.py` / `diag_risk.py` / `diag_gap.py` | 停放备件过滤复盘 / 残余风险 / 间隙标定 |
| `diag_net.py` / `diag_uv.py` / `diag_camo.py` | 伪装网、UV 专项 |
| `diag_gear.py` / `diag_gear_health.py` / `diag_lod.py` | 起落架变换 / 全机起落架体检 / 跨 LOD 一致性 |
| `_gui_verify.py` / `_gui_layout_check.py` / `_gui_picker_test.py` | GUI 功能 / 布局裁切 / 选择器 |
| `_i18n_check.py` | 列出没被 `tr()` 包住的中文串 |

校验现状（坦克）：`vertical_gap` / `hull_floats` / `proportions` 均为 0；
`collider_extent` 的差异只出现在**车长**（模型含炮管、碰撞体不含），宽度偏差 ≤0.27。
飞机另跑：`proportions` / `vertical_gap` 会报几架，但那是校验器按坦克调的
（翼展比例、离地间隙对飞机不适用），逐架目视确认过模型是完整的。

## 十四、已知取舍

- **LOD 选哪档只导哪档**（默认 LOD0），三档各自完整、各自一个 OBJ，见第三节。
- 跳过伤害判定盒（`*DamageCollider*` / `*DeathCollider*`）、停放备件、超音速激波锥、
  旋翼模糊盘；被剔除的部件名记录在 manifest 的 `skipped_off_model`。
- **飞机没有残骸变体**，所以只有外观 OBJ。
- `SubSystems/*` 的 662 个换装武器未并入整车；整车 OBJ 含该车预制体自带的炮塔与火炮。
- OBJ 只有一套 UV：反照率 tiling 已烘进 `vt`；少数材质法线 / 金属图 tiling 与反照率不同
  （如 `BMP2_track`），其次要贴图在 OBJ 里会被拉伸。
- 履带按绑定姿态烘焙为静态网格，不含骨骼蒙皮。
- 实时预览是软件渲染，画家算法那档没有深度缓冲，重叠薄片（如伪装网）会有少量排序错位；
  停手后的 z-buffer 那档没有这个问题。
- 界面是中英双语的（「中文 / EN」页切换），但**脚本自身的输出（控制台 / 日志页）仍是中文**。
