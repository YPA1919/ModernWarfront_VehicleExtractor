# Modern Warfront Vehicle Model Extractor

**V1.2 2026.9.18**


Pulls vehicle models and textures out of `modern_warfront_*.apk` and writes
OBJ + MTL + PNG.

Three kinds, by `Resources/<Kind>/<Name>`: `tanks` (`Tanks/<Name>`),
`fighters` (`Fighters/<Name>_Fighter`) and `helicopters`
(`Helicopters/<Name>_Helicopter`). Tanks additionally get a separate wreck
model; **aircraft have no wreck variant**.

---

# Part 1: How to use it

## 1. Double-click `tank_gui.py`

That is all - no command line needed. A black console window comes with it (that
is Python's own); closing it closes the UI. If you would rather not see it,
rename the file to `.pyw`.

The UI has six tabs and **Extract is selected by default**; just follow the two
steps:

| Tab | What it does |
| --- | --- |
| **Extract** | (1) APK + an **empty** work dir -> click **Unpack APK**; (2) output dir, kinds and scope -> click **Extract**. Progress bar, existing files are skipped, stoppable at any time |
| Parts | manifest part table (mesh / submesh / verts / tris / material / UV transform). **Click a row to render that part alone** - very handy for spotting misplaced parts |
| **Tweak** | **Nudge the turret / gun barrel**: a +/- pair each for front-back (Z), left-right (X) and up-down (Y), step 0.01-0.5; the preview follows live. Intact and wreck share the same values; stored per vehicle in `tweaks.json` and applied automatically on full exports |
| Textures | Thumbnail wall of that vehicle's textures; double-click to open one |
| Re-export | Re-export from already-unpacked bundles: by name, by search-and-multi-select, or N random |
| Log | Child process output and exit codes |
| 中文 / EN | UI language switch (the UI is rebuilt; entered paths and selections are kept) |

The library on the left groups every vehicle by country, with a filter and a
"random" button. **"Rescan output dir" scans the *model output dir* path**; the
label underneath shows which folder is currently scanned. The middle pane is a
3D preview (left-drag orbit / wheel zoom / right-drag pan), **Solid mode by
default**, plus wireframe and an intact/wreck toggle.

### The source package runs out of the box

`ModernWarfront_VehicleExtractor源码.zip` ships the scripts **and** `pylibs/` (UnityPy, Pillow,
numpy, texture2ddecoder and friends - about 27 MB once build artifacts are
stripped). Unzip it and run this in that directory:

```powershell
python tank_gui.py
```

Nothing needs to be installed.

> You only need to install dependencies yourself if you take the `.py` files and
> leave `pylibs/` behind:
>
> ```powershell
> python fetch_wheels.py pylibs UnityPy Pillow numpy texture2ddecoder tpk_ar
> pip install UnityPy Pillow numpy texture2ddecoder tpk_ar
> ```
>
> If something is missing, the app **lists the missing packages in a dialog** and
> shows those two commands, instead of a bare `No module named 'UnityPy'`. The
> command-line tools print the same hint.

### Standalone exe

Besides running from source, there is also a prebuilt exe - **no Python
installation needed; grab it from the releases**. It ships as a **onedir** bundle
(a folder containing one exe plus `_internal`); unzip it and **double-click
`ModernWarfront_VehicleExtractor.exe`**.

You can also build it yourself:

```powershell
& $py build_exe.py     # build with PyInstaller -> ..\exe\ModernWarfront_VehicleExtractor\
& $py pack_exe.py      # tidy it into a distributable zip (with the READMEs)
```

Why onedir and not a single-file exe: the UI drives its sibling scripts as **child
processes** (unpack / index / export / render). In a frozen build
`sys.executable` is the exe itself, so child calls become `<exe> --run <script>`,
dispatched inside `main()` with `runpy`. A single-file exe re-extracts the whole
bundle on every start - including every child - so one export would unpack it
several times and become unusably slow. onedir does not have that problem.

The CLI works the same way (`--run` takes the bundled script name, other arguments
are unchanged):

```powershell
ModernWarfront_VehicleExtractor.exe --run export_tanks.py --work D:\work --out D:\out --kind air
ModernWarfront_VehicleExtractor.exe --run export_tanks.py --out D:\out --only T90A --turret 0,0.05,-0.1 --gun 0,0,0.2
```

In a frozen build the scripts' default work dir becomes `<exe dir>\work`
(from source it stays the scripts' own directory).

> **Important: the vehicle list comes from `catalog_index.json` in the work
> dir** - so you must **unpack first** (with "Build catalog index" ticked) before
> vehicles appear in the list and before you can extract models. One unpack is
> enough; it stays available and nothing is copied twice.

## 2. Paths have no defaults

On first launch **APK file / work dir / model output dir** are all empty and
there are **no defaults** - clicking a button with them empty shows a prompt
instead of silently using some hard-coded path (same for the output dir on the
Re-export tab).

- **Work dir**: required. For a first run **use an empty folder** - the unpacked
  `catalog.json`, 4809 bundles and `data.unity3d` go here (it takes a fair amount
  of space, so pick a drive with room), and the vehicle list is read from here too.
- **APK file**: **may be left blank when the work dir already holds unpacked
  data**. The app checks the work dir for `catalog.json` and
  `bundles/data.unity3d`; if both are there it skips unpacking and goes straight
  to indexing/exporting. Only when they are missing does it require an APK (and
  then the dialog tells you where an APK was found on this machine).
- **Model output dir**: required; OBJ and textures are written here.

To point the library at a specific folder you can use a launch argument (rarely
needed):

```powershell
python tank_gui.py --root D:\some\exported\folder
```

## 3. Export scope

After unpacking, **nothing is exported in bulk by default**. Three scopes:

- **Picked** (default) - type a name in the search box and tick vehicles; if
  nothing is ticked you get a prompt rather than a full export.
- **Random N** - with a seed, reproducible (same number = same batch).
- **All** - every vehicle of the selected kinds.

Three more switches:

- **Scale x7** (on by default) - one game unit is about 1/7 metre, so x7 gives
  roughly real-world metres: the Leopard2A6MC2 measures 1.573 units, x7 =
  **11.01 m**, while the real tank is 10.97 m (0.4% off). Untick it to keep the
  raw game units. The factor used is written into the OBJ header
  (`# scale x7`) and into the `scale` field of the manifest, so downstream tools
  can undo it if needed.
- **LOD 0 / 1 / 2** (0 by default) - see below.
- **No camo net** (off by default).

### LOD: the chosen level is the only one exported

The game swaps to simpler models with distance; LOD0 is the most detailed. The
radio group picks one level, and that level goes into **its own OBJ** - the three
levels are not merged:

| Level | Intact | Wreck |
| --- | --- | --- |
| LOD0 | `<name>.obj` | `<name>_Wreck.obj` |
| LOD1 | `<name>_LOD1.obj` | `<name>_LOD1_Wreck.obj` |
| LOD2 | `<name>_LOD2.obj` | `<name>_LOD2_Wreck.obj` |

Each level is a **complete vehicle**. For the T90A:

| Level | Parts | Vertices | OBJ size |
| --- | --- | --- | --- |
| LOD0 | 82 | 54289 | 5.62 MB |
| LOD1 | 60 | 17930 | 1.73 MB |
| LOD2 | 59 | 6021 | 0.56 MB |

Parts are assigned by the `_LODn` in their name; parts with no LOD marker (the
`PKT` machine gun and friends - only 10 across a 40-vehicle sample) are kept in
every level. This also covers a typo of the game's own:
`Hull_ERA_Kontakt1_Side_R_01_ROD0` spells LOD0 as **`ROD0`**, so the regex is
`[LR]OD(\d)`; without that, those ERA blocks would look unmarked and leak into
every level.

**Search works across every kind**: tanks, jets and helicopters
(`mi2` -> Mi-28NM / Mi-24SuperHind, `z1` -> WZ10 / Z11WB / Z19E,
`su` -> SU-24M / SU-25 / Mi-24SuperHind...). The list **follows the "vehicle
kind" checkboxes**: only the ticked kinds are listed.
Unticking a kind drops the now-invalid selections automatically, so you never
end up with "selected but not exported".

## 4. Blender renders (textured beauty shots)

The **"Blender render"** button in the preview toolbar renders a textured PNG of
the current view via Blender in the background, saved as `render.png` in the
vehicle folder and shown in a popup window that can "Save as". The Re-export tab
has a batch button.

It follows the approach used by the "FinalFire" toolkit: the
`BLENDER_WORKBENCH` engine + `color_type='TEXTURE'` (shows MTL textures directly)
+ `light='FLAT'` (texture colours are not darkened) + cavity shading to convey
form - no lighting setup, no GPU ray tracing, about 5-15 s per image. The camera
matches the live preview exactly.

Blender is auto-detected (`D:\Blender Foundation\*`,
`C:\Program Files\Blender Foundation\*` or PATH); you can also set
`BLENDER_EXE`. **Without Blender only rendering is affected**; everything else
still works.

## 5. Command-line equivalents

Everything the UI does can also be done from a shell:

```powershell
$py = "D:\Python\Python313\python.exe"     # your interpreter
$env:PYTHONIOENCODING = "utf-8"

# 1) Unpack (--list-only just prints what is inside)
& $py extract_bundles.py --apk game.apk --work D:\work

# 2) Build the index (the vehicle list depends on it)
& $py build_index.py --catalog D:\work\catalog.json --out D:\work

# 3) Export
& $py export_tanks.py --work D:\work --out D:\out                 # all
& $py export_tanks.py --kind air --out D:\out                     # aircraft only
& $py export_tanks.py --kind helicopters --out D:\out             # helicopters only
& $py export_tanks.py --kind tanks,helicopters --out D:\out       # comma-combinable
& $py export_tanks.py --only T90A,ZBD86,M1A2SEPv2 --out D:\out    # specific vehicles
& $py export_tanks.py --kind air --only KA50_Helicopter --out D:\out
& $py export_tanks.py --sample 4 --seed 7 --out D:\out            # 4 random
& $py export_tanks.py --scale 1 --out D:\out                      # raw game units
& $py export_tanks.py --lod 1 --out D:\out                        # LOD1 only
#    --kind: tanks / fighters / helicopters / air / all
#    --lod 0|1|2 which LOD to export (default 0), one OBJ per level
#    --no-camo drops the camo net
#    --scale uniform scale factor, default 7 (see below)
#    --skip-existing skip what is already exported (resume after a native crash)

# 4) Previews and validation (optional)
& $py make_previews.py --root D:\out
& $py export_tanks.py --work D:\work --out D:\out --only T90A --turret 0,0.05,-0.1
```

Every script prints machine-readable `PROGRESS done total` lines, which the GUI
uses to drive its progress bar.

UI self-tests (no window stays open):

```powershell
& $py tank_gui.py --selftest      # build window -> load first vehicle -> exit
& $py tank_gui.py --shot a.png    # load first vehicle, render one image, exit
```

## 6. Environment and dependencies

- **Python 3.13**. The interpreter path is hard-coded in `PY` at the top of
  `tank_gui.py` - change that line on a new machine.
- Third-party packages (install them yourself):

  ```
  UnityPy  Pillow  numpy  texture2ddecoder  tpk_ar
  ```

Two ways to install:

**1) Normal pip**

```powershell
pip install UnityPy Pillow numpy texture2ddecoder tpk_ar
```

**2) When pip is unusable (restricted environment)** - use the bundled fetcher
to unpack wheels into `./pylibs`:

```powershell
python fetch_wheels.py pylibs UnityPy Pillow numpy texture2ddecoder tpk_ar
set PYTHONPATH=%cd%\pylibs        # point at it when running
```

`tank_gui.py` automatically sets `PYTHONPATH=<script dir>\pylibs` for the child
processes it spawns, so installing the dependencies there is enough for the GUI
buttons to work.

> Texture decoding needs the abi3 wheel of `texture2ddecoder`
> (`cp311-abi3-win_amd64`); it works on Python 3.13 as-is.

## 7. Output layout

```
<out>/<Country>/<Name>/
├── <Name>.obj            intact model (tracks, turret, gun, camo net)
├── <Name>.mtl
├── <Name>_Wreck.obj      wreck model (separate file, fully split; not for aircraft)
├── <Name>_Wreck.mtl
├── manifest.json         part list + parts dropped as parked spares
├── preview.png / preview_wreck.png
├── render.png            Blender render (only if you made one)
└── textures/*.png        _A albedo / _N normal / _MGC / _EM
```

Coordinates: Unity is left-handed (Y up, Z forward); X is negated on export as
is conventional for OBJ. Import into Blender with **Y-Up / -Z Forward**.

Scale: models are exported **x7** by default so they come out close to metres
(see the export-scope section). The OBJ header states
`# scale x7 (1 game unit = 1/7 m)` and the manifest carries a `scale` field.

## 8. What is in this package

Every Python script sits flat in one folder. **Do not move them into
subfolders** - the scripts `import` each other, and `tank_gui.py` resolves
`export_tanks.py` / `extract_bundles.py` relative to *its own directory*, so the
GUI would lose its child scripts if you split them up.

| Script | Purpose |
| --- | --- |
| `tank_gui.py` | **GUI** (entry point): unpack / browse / inspect / extract / render |
| `extract_bundles.py` | Unpack the APK (catalog + 4809 bundles + `data.unity3d`) |
| `build_index.py` | Parse the Addressables catalog into an asset-path <-> GUID <-> bundle index |
| `aacatalog.py` | Binary catalog parser (used by `build_index.py`) |
| `export_tanks.py` | **Main export script** |
| `make_previews.py` | Batch previews plus two contact sheets |
| `part_groups.py` | Turret / gun part classification (shared by export and the preview) |
| `check_sample.py` | Export N randomly sampled vehicles with previews |
| `blender_shot.py` | **Blender renders** (single or batch) |
| `get_preview_ref.py` | Extract the game's own preview sprites (assembly reference) |
| `render_obj.py` / `render_textured.py` | Offline rendering (untextured 4-view / textured) |
| `fetch_wheels.py` | Dependency fetcher (for when pip is unusable) |
| `diag_*.py` (30) | One-off diagnostic probes |
| `_gui_*.py` / `_i18n_check.py` (9) | Self-test scripts |
| `README.md` / `README_EN.md` | This document (Chinese / English) |

**Not included**: the game APK, unpacked bundles, exported models/textures, or
the third-party dependencies.

---

# Part 2: How it works

## 9. How the game assembles a vehicle

The visible meshes are not in the Addressables bundles (those only hold
colliders). They live in `data.unity3d` -> `resources.assets` (471,725 objects)
as `Resources/<Kind>/<Name>` prefabs.

**The assembly is Unity static batching, and the code just reads the fields - it
does no geometric guessing.** Every part's MeshRenderer carries two fields that
state how it is drawn:

```
m_StaticBatchInfo(firstSubMesh, subMeshCount)  "I draw the firstSubMesh-th submesh"
m_StaticBatchRoot                             vertices are baked in this node's space
```

So there are exactly two rules:

| Case | Placement transform | Submeshes taken |
| --- | --- | --- |
| Has StaticBatchInfo (batched) | the **batch root node's** transform | only `[firstSubMesh, firstSubMesh+subMeshCount)` |
| No StaticBatchInfo (plain mesh, e.g. camo net, searchlight) | the object's own transform | the whole mesh |

Measured over a 60-vehicle sample: of 6214 renderers sharing a mesh, **6212 carry
the field**, and the ranges tile `0..N-1` exactly, with no overflow.

Batch roots are grouped **per part family**; a vehicle has several:

```
AHSKrab     root AHSKrab      -> Hull_*            scale (1, 1, 1)
            root TurretGroup  -> CommandTower_*    world (0, 0.268, -0.201)
            root BarrelGroup  -> Barrel_*          world (0, 0.353, 0.235)
            root Cloth01      -> Camo_net_Hull_*   scale (1, 1, 1)
Type89MLRS  root Cloth01      -> Camo_net_Hull_*   scale (0.01, 0.01, 0.01)   <- key
```

Type89MLRS's camo net mesh is authored at **100x** and is scaled back down by
`Cloth01`'s 0.01. That 0.01 is only obtainable from `m_StaticBatchRoot`. Guess it
wrong and the net blows up 100x out of the vehicle, stretching the whole bounding
box to 811 units and forcing the preview camera kilometres away - which looks
like "nothing was exported at all".

> **This section used to describe a different theory**: "group meshes + slot order
> determine submeshes" and "the mesh's coordinate space decides the placement
> transform", inferred by checking whether slot *i*'s world position coincided
> with submesh *i*'s centre. That happened to hold for most vehicles and broke on
> Type89MLRS. Reading `m_StaticBatchInfo` / `m_StaticBatchRoot` directly removed
> the guessing; the heuristic code (`choose_mount`, `group_mount`,
> `resolve_camo_mounts`, `submesh_centres`, `assign_by_position` and 4 more) has
> been deleted.

### Layer 0: what tanks and aircraft share, and what they do not

Aircraft (fixed-wing and helicopters) reuse the exact same export path: the
country is looked up from the collider assets under
`Assets/Content/Mesh/<Kind>/<Country>/<Name>/`, and the prefab name is the last
segment of the Resources path (`A10A_Fighter`, `KA50_Helicopter`). Two
differences:

- Their hierarchy is **nested**: `<Name>_Helicopter` (root) -> `<Name>` ->
  `<Name>_Hull_LOD0` -> parts; wings, landing gear and rotors hang off the hull.
  You must walk the `m_Father` chain to get correct transforms.
- Helicopters have an extra **`blur` group** holding the rotor blur disc
  (see pitfall 6), which must be excluded.

### Layer 1: wreck detection follows the hierarchy path

Intact and wreck geometry live in the same batched mesh and are told apart by
name: `Hull_LOD0` and `Hull_Destructed_LOD0` are two submeshes of one mesh. Wreck
detection cannot rely on the leaf name alone - PzH2000's wreck sits at
`HullGroup_Destructed/Hull_LOD0` with no "Destructed" in the leaf - so
`ordered_gameobjects` propagates the flag down each subtree.

### Layer 2: weapons/turrets are separate subsystem prefabs

The game has **662 `SubSystems/<Weapon>_<Vehicle>_<Caliber>`** prefabs (e.g.
`M3A3_BGM71TOW_152mm`, `Ksp39C_7mm`) mounted at runtime. Tank prefabs therefore
keep **unmounted spare copies** parked outside the hull: below ground (M3A3's
TOW, the PansirSM/PinakaMk3 mounts, Strv2000's KSP39C) or beside the hull
(Cheonma2's `Gun_LOD0` at x=-1.29).

## 10. Pitfalls (all handled in the code)

1. **UVs must bake the material tiling/offset**: Unity samples with
   `uv * tiling + offset` (`_MainTex_ST`). 88 of 570 materials use a non-default
   albedo tiling (mostly `(1,2)`; also `(1,4)` for `StingerLauncher` and `(1,8)`
   for `LAV600_Wheels`). Baked into `vt`; the applied values are recorded in the
   manifest as `uv_tiling`.

2. **Tracks are SkinnedMeshRenderers** (910 of them, in 191/223 tanks), not
   MeshFilters. Their meshes are in bone-local space and are placed by the
   renderer's own transform at bind pose.

3. **The camo net is draped normally**: material `TankCloth`, and the prefab stores
   the already-draped net hugging the hull/turret/barrel. `--no-camo` drops it.
   49.5% of its texture is transparent, but the **RGB channel is a complete camo
   leaf pattern** (the RGB under the transparent pixels is ordinary olive/khaki,
   not black), so in the preview it is simply textured as-is and reads as a normal
   camo net. It was once alpha-cut, which left only scattered leaves and looked
   worse than not cutting at all.

4. **Parked spares must be detected by *gap*, not by *envelope*** (only exposed
   by the aircraft). The game parks unmounted spare weapons outside the vehicle
   and they must be dropped, but the rule was once "lateral/longitudinal
   envelope relative to the hull", which also deleted **legitimate protruding
   parts**: the A-10's nose gun, helicopter rotor blades, rocket pods. An even
   earlier "diagonal > 20x median" guard backfired: aircraft have many small
   panels, which dragged the median down until **the hull itself** was dropped,
   the envelope reference then fell onto a small wing panel, and the whole
   vehicle was wiped out.

   > The rule is now "gap to the AABB of the rest of the model > 0.25 x model
   > diagonal" - a real part's AABB still **touches** the hull however far it
   > protrudes, while a parked spare floats free. Measured: Cheonma2's spare MG
   > gap 0.95, K21's floats 1.97, Archer's MG 75.6, Type89MLRS's camo net 20.8 -
   > all caught; while the A-10 gun, rotor blades and F-16 landing gear all have
   > gap 0.00 (kept).

6. **Effect meshes must be excluded separately**, two kinds:

   - `FighterSuperSonicCone` (the supersonic shock cone): 49 aircraft carry it,
     the mesh itself is only +-0.09 across but it is scaled 10x over the fuselage
     and renders as a giant funnel. It is not hardware.
   - **Anything under a `blur` node is a rotor blur disc**: helicopters hang
     `HelicopterBladeSmoothed` (~6 per aircraft) under a node literally named
     `blur` - that is the blur disc shown when the rotor spins fast. The real
     blades are `*_Blades_01/02_LOD0` under `*_Rotor_01/02_LOD0`. All 27
     helicopters have this. The whole `blur` subtree must be excluded by name,
     otherwise every helicopter gains a ring of mis-angled blades (this was the
     source of the "parts are in the wrong place" report).

     > Unity appends suffixes to duplicate node names: some helicopters have
     > **`blur_001`** in addition to `blur`. Matching only `^blur$` missed it and
     > left Mi-24 with two stray blades. The current regex
     > `^blur(_\d+)?( \(\d+\))?$` covers all spellings.

   Exclusion works on the **ancestor chain**: `ordered_gameobjects` propagates
   the `blur` flag down the subtree.

7. **Matrix multiplication had its arguments swapped** (the subtlest one - this
   was the aircraft landing-gear misplacement). `mat_mul(a, b)` was indexed as
   `sum_k a[col=i][row=k] * b[col=k][row=j]`, which in column-major computes
   **`b * a`** - so `world_matrix` multiplied the parent chain from leaf to root.

   > Why tanks never showed it: when the chain is **pure translation**,
   > `a*b == b*a` and the order does not matter. Aircraft landing gear is a
   > **jointed chain with rotations** (`R_01 -> R_03 -> R_05`); with the wrong
   > order, `Chassis_L_03` and `Chassis_R_03` both snapped onto the centreline
   > and the wheels and struts fell apart. After the fix the left/right parts
   > mirror correctly (L at x[-0.15,-0.11], R at x[0.11,0.15]). Verified against
   > numpy with 200 random matrices: `mat_mul(A,B) == A@B`.

8. **Cross-file path_id collisions**: `data.unity3d` holds 12 SerializedFiles
   and path_ids are only unique within a file (92,084 collisions globally).
   Every reference must go through `PPtr.deref()`, and caches must be keyed by
   `ObjectReader`.

9. **`ObjectReader` is unhashable**: UnityPy generates `__eq__` via attrs but no
   `__hash__`. Patched with `ObjectReader.__hash__ = object.__hash__`.

10. **The compiled modules crash natively** (this is what "the full export fails
    halfway" really was). The symptom is the process vanishing with exit code
    `-1073741819` (`0xC0000005`, ACCESS_VIOLATION) - **Python cannot catch it**, so
    the GUI can only report "exit code ...". Two sources:

    - `UnityPyBoost`: the typetree reader crashes on some ParticleSystems, and the
      vertex unpacker `unpack_vertexdata` crashes too. All three entry points are
      set to None so the pure-Python fallback is used.
    - **ASTC texture decoding** (the main one): UnityPy defaults to
      `astc_encoder`, which crashed randomly after 100-200 vehicles on a full run.
      `faulthandler` pointed at `MeshHelper.get_triangles`, but that is just where
      the already-corrupted heap happened to blow up, not the cause. Bisecting with
      `MW_NO_TEX=1` (write models, skip textures) settled it: with textures 5 of 7
      runs crashed, without them 303/303 completed. `MW_DEBUG_TEX=1` (print each
      texture's format/size) showed the textures being decoded right before every
      crash were all ASTC. **Swapping in `texture2ddecoder.decode_astc`** (a
      different implementation) made full runs pass repeatedly - the two decoders
      agree to a mean pixel difference of 0.22/255, max 1.

    A native crash cannot be caught, so there are two safety nets:
    `--skip-existing` for resuming, and the GUI automatically re-running with
    `--skip-existing` on a non-zero exit (up to 8 rounds, stopping when it stops
    making progress).

11. **Caches must be cleared between vehicles**: otherwise after ~200 vehicles
    you get memory corruption such as
    `'range_iterator' object is not callable`. With clearing, RSS stays flat at
    about 2.8 GB.

12. **`catalog.json` and `settings.json` must not be written to the same path**
    during unpacking (settings once overwrote the catalog with an empty file).

13. **Texture decoding** needs the abi3 wheel of `texture2ddecoder`, usable on
    Python 3.13.

## 11. How to verify the assembly

The game ships an **official preview sprite** for every vehicle, which is a far
better reference than eyeballing:

```powershell
& $py get_preview_ref.py F16 A10A KA50 AH64E M60A3TTS M3A3 ZBD86
# -> _preview_ref\<Name>.png   (has an alpha channel; opaque = vehicle)
```

Render the exported model from a similar angle and put the two side by side.
These images come from the game's own artists, so a misplaced part is obvious at
a glance - the landing-gear bug was found exactly this way.

Structural validation (no images needed):

```powershell
& $py validate_models.py --root D:\out --work D:\work
```

And the cheapest sanity check of all: **look at the bounding-box span** of each
exported vehicle. A normal tank is 9-15 (exported metre units), bombers scale with
their real size, and anything in the tens or hundreds means a part was misplaced.

## 12. Live preview

The middle pane is a software-rendered preview (left-drag orbits, wheel zooms,
right-drag pans) with **two quality tiers**:

| When | Renderer | Cost |
| --- | --- | --- |
| While dragging / wireframe | painter's algorithm + PIL polygon fills | ~30-45 ms/frame, keeps up |
| After release (with "Texture" on) | per-pixel z-buffer + real UV sampling + interpolated normals | see below |

The textured tier runs in a **background thread** as a three-step ladder, so the
UI never freezes:

```
on release      the fast tier lands immediately (~90 ms, never a blank pane)
+0.37 s         0.55x texture (soft, but the colours are there)
+0.71 s         1.0x native canvas resolution, sharp
+1.25 s         1.5x supersampled, downsampled for antialiasing
```

Dragging or zooming again discards the in-flight background work, so images never
cross. The approach follows `tk2_preview.py` (a standalone, reusable renderer
using only numpy + Pillow; usable on its own).

### What the renderer does to afford that (T90A: 1.30 s -> 0.46 s)

- **Exact-size bbox bucketing, batched rasterisation**: same-sized triangles are
  stacked into `(G, bh, bw)` and their barycentrics and depths computed together.
  The original cost ~60 small numpy calls per triangle (24.5 us measured), so
  20k triangles spent over 0.5 s purely on call overhead - the bottleneck is
  **call count, not arithmetic**, which is why lowering the resolution did not
  help. Padding buckets to powers of two was tried and was *worse* (1.74 s): the
  wasted pixels ate the gain.
- **Early depth test**: do the z comparison inside the bucket first, collect the
  surviving samples, and only then compute colours once. Texture sampling and
  lighting touch only genuinely visible pixels, so overdraw costs nothing.
- All material textures are stacked into a single **atlas**, so one fancy index
  fetches the texels for a whole batch.
- float32 on the hot paths.

### Details worth knowing

- Textures are `convert("RGB")`-ed **before** resizing: resizing RGBA directly
  makes Pillow premultiply by alpha, and game textures often have whole regions
  with alpha 0, which would black out the RGB (road wheels go solid black).
- Preview textures are downscaled to 512 on the long edge.
- Two lights: key + fill, shading = `0.32 + 0.62*key + 0.16*fill`.
- Background is mid grey-blue `(58,64,72)` so dark liveries still show an outline.
- **The camo net is textured like everything else** (see pitfall 3).
- Editing the turret/gun offsets on the Tweak tab updates the preview live, with
  no re-export needed.

## 13. Diagnostic and self-test scripts

Diagnostics honour the `MW_KIND` environment variable (`tanks` / `air` / ...):

```powershell
$env:MW_KIND = "air"
& $py diag_parts2.py KA50_Helicopter     # per-part world AABB
& $py diag_chain.py KA50_Helicopter      # real parent chain of each part
& $py diag_gap.py                        # parked-spare gap calibration
```

| Script | Purpose |
| --- | --- |
| `diag_tank.py` / `diag_parts2.py` | Slot mapping / per-part AABB for one vehicle |
| `diag_chain.py` / `diag_root.py` | Parent chain, hierarchy flatness (aircraft work) |
| `diag_filter.py` / `diag_risk.py` / `diag_gap.py` | Parked-spare filter review / residual risk / gap calibration |
| `diag_net.py` / `diag_uv.py` / `diag_camo.py` | Camo net and UV investigations |
| `diag_gear.py` / `diag_gear_health.py` / `diag_lod.py` | Landing gear transforms / whole-fleet gear check / cross-LOD consistency |
| `_gui_verify.py` / `_gui_layout_check.py` / `_gui_picker_test.py` | GUI function / layout clipping / picker tests |
| `_i18n_check.py` | Lists Chinese strings not wrapped in `tr()` |

Current validation state (tanks): `vertical_gap` / `hull_floats` / `proportions`
are all 0; `collider_extent` differences only appear in **length** (the model
includes the gun barrel, the collider does not), width deviation <=0.27.
Aircraft: `proportions` / `vertical_gap` flag a few, but that validator is tuned
for tanks (wingspan ratios and ground clearance do not apply to aircraft); each
model was visually confirmed complete.

## 14. Known trade-offs

- **LOD is a pick-one choice** (LOD0 by default): each level is a complete vehicle
  in its own OBJ, see section 3.
- Damage colliders (`*DamageCollider*` / `*DeathCollider*`), parked spares, the
  supersonic shock cone and rotor blur discs are skipped; the dropped part names
  are recorded in the manifest under `skipped_off_model`.
- **Aircraft have no wreck variant**, so only intact OBJs.
- The 662 `SubSystems/*` alternate weapons are not merged into the vehicles; the
  OBJ contains the turret and gun that ship with the prefab.
- OBJ carries a single UV set: albedo tiling is baked into `vt`, so secondary
  maps whose tiling differs from the albedo (e.g. `BMP2_track`) appear stretched.
- Tracks are baked to a static mesh at bind pose; no skinning is kept.
- The live preview is software-rendered; the painter's-algorithm tier has no depth
  buffer, so overlapping thin sheets (the camo net) can sort slightly wrong. The
  z-buffer tier after release does not have that problem.
- The UI is bilingual (中文 / EN tab), but **script output (console / Log tab)
  is still Chinese**.
