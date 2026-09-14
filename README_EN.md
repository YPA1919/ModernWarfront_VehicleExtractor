# Modern Warfront Vehicle Model Extractor

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

Two more switches, both on by default:

- **Scale x7** (on by default) - one game unit is about 1/7 metre, so x7 gives
  roughly real-world metres: the Leopard2A6MC2 measures 1.573 units, x7 =
  **11.01 m**, while the real tank is 10.97 m (0.4% off). Untick it to keep the
  raw game units. The factor used is written into the OBJ header
  (`# scale x7`) and into the `scale` field of `manifest.json`;
  the manifest, so downstream tools can undo it if needed.
- **Include LOD1/2** (off by default) - see below.

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
#    --kind: tanks / fighters / helicopters / air / all
#    --all-lods includes LOD1/2; --no-camo drops the camo net
#    --scale uniform scale factor, default 7 (see below)

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
as `Resources/<Kind>/<Name>` prefabs. **Assembly works in three layers**:

### Layer 0: what tanks and aircraft share, and what they do not

Aircraft (fixed-wing and helicopters) reuse the exact same export path: the
country is looked up from the collider assets under
`Assets/Content/Mesh/<Kind>/<Country>/<Name>/`, and the prefab name is the last
segment of the Resources path (`A10A_Fighter`, `KA50_Helicopter`). Three
differences:

- Aircraft have almost no **group meshes** (only 4 across all 80, and their
  submesh/slot counts disagree), so layer 1 rarely applies to them.
- Their hierarchy is **nested**: `<Name>_Helicopter` (root) -> `<Name>` ->
  `<Name>_Hull_LOD0` -> parts; wings, landing gear and rotors hang off the hull.
  You must walk the `m_Father` chain to get correct transforms.
- Helicopters have an extra **`blur` group** holding the rotor blur disc
  (see pitfall 6), which must be excluded.

### Layer 1: group meshes + slot order determine submeshes

A prefab splits a tank into **slots**, each slot's `MeshFilter` pointing at a
group mesh. Of 3663 group meshes, **3633 satisfy "submesh count == number of
slots referencing it"**, and slot *i*'s world position coincides with the
centre of submesh *i* (error 0.01-0.06).

> **slot i <-> submesh i, in hierarchy pre-order.**

Intact and wreck geometry share one mesh: `Hull_LOD0` (slot 27) -> sub27 is only
the suspension arms, while `Hull_Destructed_LOD0` (slot 28) -> sub28 contains the
wheels and the holes. Wreck detection must look at the **hierarchy path**
(PzH2000's wreck lives at `HullGroup_Destructed/Hull_LOD0` with no "Destructed"
in the leaf name).

### Layer 2: the mesh's coordinate space decides the placement transform

A mesh may be authored in vehicle space or in a sub-assembly (turret/gun) space.
The test is whether the slot world positions coincide with the corresponding
submesh centres:

- coincide -> already in vehicle space, **do not apply another transform** (identity)
- do not coincide -> use the **slot without extra offset** (the mount)

> Just picking the "closest to identity slot" fails: ZBD86's hull mesh is in
> vehicle space but none of its slots sit at the origin, so the whole vehicle
> was lifted by 0.19 and the hull appeared to float above the tracks.
> **22 vehicles / 62 group meshes** were affected (BMP1 +0.19, BMPT72 +0.167,
> 2S19MstaS -0.182, ...) and are now fixed.

### Layer 3: weapons/turrets are separate subsystem prefabs

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

3. **The camo net is draped normally**: it has a `Cloth` component and a
   `TankCloth` material, and the prefab stores the already-draped net hugging the
   hull/turret/barrel. It only looks thin from the side because it lies on the
   surface. `--no-camo` drops it.

4. **When submesh and slot counts disagree** (30/3663), recover the pairing
   geometrically: submeshes within 0.15 of a slot world position pair directly,
   the rest are handed to the offset-free slots in order.

5. **Parked spares must be detected by *gap*, not by *envelope*** (only exposed
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

10. **The compiled typetree reader crashes**: `UnityPyBoost.read_typetree` hits
    an ACCESS_VIOLATION on some ParticleSystems. Switched to the pure-Python
    fallback.

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

## 12. Diagnostic and self-test scripts

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

## 13. Known trade-offs

- Only **LOD0** is exported by default; `--all-lods` adds LOD1/2 (they are
  simplified whole-vehicle copies that overlap LOD0, rarely useful).
- Damage colliders (`*DamageCollider*` / `*DeathCollider*`), parked spares, the
  supersonic shock cone and rotor blur discs are skipped; the dropped part names
  are recorded in the manifest under `skipped_off_model`.
- **Aircraft have no wreck variant**, so only intact OBJs.
- The 662 `SubSystems/*` alternate weapons are not merged into the vehicles; the
  OBJ contains the turret and gun that ship with the prefab.
- OBJ carries a single UV set: albedo tiling is baked into `vt`, so secondary
  maps whose tiling differs from the albedo (e.g. `BMP2_track`) appear stretched.
- Tracks are baked to a static mesh at bind pose; no skinning is kept.
- The UI is bilingual (中文 / EN tab), but **script output (console / Log tab)
  is still Chinese**.
