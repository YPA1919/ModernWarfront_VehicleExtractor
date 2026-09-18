"""Scan every extracted bundle with UnityPy and emit a JSONL inventory.

Per bundle: container guid -> catalog asset path, and for each interesting
object its class, name, path id and a few cheap properties.
"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import UnityPy

# The compiled typetree reader (UnityPyBoost) access-violates on some
# ParticleSystem objects; the pure-python fallback handles them fine.
from UnityPy.helpers import TypeTreeHelper as _TTH

_TTH.read_typetree_boost = None

BUNDLES = os.path.join(HERE, "bundles")
OUT = os.path.join(HERE, "scan/bundles.jsonl")

TYPEINFO = {
    "Texture2D": ("m_Width", "m_Height", "m_TextureFormat", "m_MipCount"),
    "Mesh": ("m_VertexCount",),
    "Material": (),
    "GameObject": (),
    "AudioClip": (),
}
WANT = set(TYPEINFO) | {"MonoBehaviour", "MeshFilter", "MeshRenderer", "SkinnedMeshRenderer",
                        "Transform", "AnimationClip", "Shader", "Sprite"}


def main():
    import faulthandler
    faulthandler.enable()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    files = sorted(os.listdir(BUNDLES))
    if len(sys.argv) > 1:
        files = files[int(sys.argv[1]):int(sys.argv[1]) + int(sys.argv[2])]
    print(f"{len(files)} bundles", flush=True)
    done = 0
    t0 = time.time()
    with open(OUT, "w", encoding="utf-8") as out, open(OUT + ".cur", "w", encoding="utf-8") as cur:
        for fn in files:
            path = os.path.join(BUNDLES, fn)
            cur.seek(0)
            cur.write(fn + "\n")
            cur.flush()
            cur.truncate()
            rec = {"file": fn, "objects": [], "container": {}, "error": None,
                   "deps": [], "unity": None, "types": {}}
            try:
                env = UnityPy.load(path)
                for cf in env.files.values():
                    if getattr(cf, "container", None):
                        rec["container"].update({k: str(v) for k, v in cf.container.items()})
                    if getattr(cf, "unity_version", None):
                        rec["unity"] = cf.unity_version
                    deps = getattr(cf, "m_Dependencies", None)
                    if deps:
                        rec["deps"] = [str(d) for d in deps]
                for o in env.objects:
                    tn = o.type.name
                    rec["types"][tn] = rec["types"].get(tn, 0) + 1
                    entry = {"t": tn, "id": o.path_id}
                    if tn in WANT:
                        try:
                            d = o.read()
                            name = getattr(d, "m_Name", None)
                            entry["n"] = name if isinstance(name, str) else str(name)
                            for attr in TYPEINFO.get(tn, ()):
                                v = getattr(d, attr, None)
                                if v is not None and not hasattr(v, "__len__"):
                                    entry[attr[2:]] = v
                                elif isinstance(v, (int, float)):
                                    entry[attr[2:]] = v
                            if tn == "MonoBehaviour":
                                entry["n"] = entry.get("n") or ""
                                script = getattr(d, "m_Script", None)
                                if script is not None:
                                    try:
                                        entry["script"] = os.path.basename(str(script.read().m_Name))
                                    except Exception:
                                        pass
                        except Exception as exc:
                            entry["err"] = type(exc).__name__
                    rec["objects"].append(entry)
            except Exception as exc:
                rec["error"] = f"{type(exc).__name__}: {exc}"
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            done += 1
            if done % 250 == 0:
                print(f"  {done}/{len(files)} {time.time()-t0:.0f}s", flush=True)
    print(f"done {done} in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
