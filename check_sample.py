"""Export a random sample of tanks and build a small review sheet.

Usage: python check_sample.py [N] [--seed S] [--out DIR]
"""
import argparse
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# 打包成 exe 后脚本在临时解包目录里，默认工作目录放到 exe 旁边；
# 源码运行时就是脚本自己所在目录（GUI 会把 --work 显式传进来，这里只是默认值）
if getattr(sys, "frozen", False):
    MW = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "work")
else:
    MW = HERE
PY = sys.executable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", nargs="?", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=os.path.join(MW, "sample"))
    args = ap.parse_args()

    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(MW, "pylibs")
    cmd = [PY, "-u", os.path.join(MW, "export_tanks.py"),
           "--sample", str(args.n), "--seed", str(args.seed), "--out", args.out]
    print("running:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)

    ps = [PY, "-u", os.path.join(MW, "make_previews.py"), "--root", args.out,
          "--size", "480", "--tris", "60000", "--cols", str(max(2, args.n))]
    subprocess.run(ps, check=True, env=env)
    print("review sheets in", args.out, flush=True)


if __name__ == "__main__":
    main()
