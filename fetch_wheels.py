"""Minimal dependency-fetching installer: downloads wheels from PyPI and unpacks
them into a target dir, bypassing pip's temp-file machinery.

Usage: python fetch_wheels.py <target_dir> <pkg> [pkg...]
"""
import io
import json
import os
import sys
import urllib.request
import zipfile

TARGET = sys.argv[1]
PKGS = sys.argv[2:]

PY_TAG = "cp313"
ABI_TAG = "cp313"
PLAT_TAGS = ["win_amd64", "any"]
PY_UNIVERSAL = ["py3", "py2.py3", None]

seen = set()
order = []


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "wheel-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def tag_ok(filename, requires_python=None):
    """Very small wheel-tag filter good enough for pure-python + cp313 win wheels."""
    if not filename.endswith(".whl"):
        return False
    parts = filename[:-4].split("-")
    if len(parts) < 5:
        return False
    pytag, abitag, plattag = parts[-3], parts[-2], parts[-1]
    py_ok = any(t in pytag.split(".") for t in ([PY_TAG] + PY_UNIVERSAL) if t)
    abi_ok = abitag == "none" or ABI_TAG in abitag.split(".")
    plat_ok = any(p in plattag.split(".") for p in PLAT_TAGS) or plattag == "any"
    return py_ok and abi_ok and plat_ok


def resolve(name):
    key = name.lower().replace("_", "-")
    if key in seen:
        return
    seen.add(key)
    data = fetch_json(f"https://pypi.org/pypi/{name}/json")
    info = data["info"]
    version = info["version"]
    urls = data["releases"].get(version, [])
    good = [u for u in urls if tag_ok(u["filename"])]
    if not good:
        good = [u for u in urls if u["filename"].endswith(".whl")]
    if not good:
        print(f"  !! no wheel for {name} {version}")
        return
    good.sort(key=lambda u: (0 if "win_amd64" in u["filename"] else 1, u["filename"]))
    chosen = good[0]
    order.append((name, version, chosen))
    for dep in info.get("requires_dist") or []:
        # strip extras / markers we do not need
        if ";" in dep:
            marker = dep.split(";", 1)[1]
            if "extra ==" in marker:
                continue
            dep = dep.split(";", 1)[0]
        dep = dep.strip()
        dep = dep.split("[")[0]
        for sep in (" ", "(", "<", ">", "=", "!", "~"):
            dep = dep.split(sep)[0]
        dep = dep.strip()
        if dep and dep.lower() not in ("python",):
            resolve(dep)


for p in PKGS:
    resolve(p)

print(f"{len(order)} wheels to install")
os.makedirs(TARGET, exist_ok=True)
for name, version, u in order:
    print(f"  {name} {version} <- {u['filename']}")
    req = urllib.request.Request(u["url"], headers={"User-Agent": "wheel-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        blob = r.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        z.extractall(TARGET)
print("done ->", TARGET)
