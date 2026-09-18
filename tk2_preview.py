"""坦克争锋 · OBJ 预览 / 渲染模块（独立可复用）

只用 numpy + Pillow，不依赖本项目的其它文件，可以直接 import 给自己的脚本用。

    import tk2_preview as P

    # 1) 最省事：一个 OBJ 文件 -> 一张图
    img = P.render_obj("tank.obj", size=(1200, 800), view=(38, 20))
    img.save("tank.png")

    # 2) 一个 OBJ + 贴图
    img = P.render_obj("tank.obj", tex="tank.png", out="tank_preview.png")

    # 3) 自己拼多个部件（各自的贴图/颜色），再渲染
    pv = P.Preview()
    for part in parts:                      # part 见下面 load_obj_file 的返回
        pv.add(part["verts"], part["normals"], part["tris"], part["uvs"], tex_path)
    pv.yaw, pv.pitch = 0.9, 0.3             # 弧度；也可用 P.deg(38), P.deg(20)
    img = pv.render_hq((1200, 800))         # 逐像素 z-buffer 贴图（慢但清楚）
    img_fast = pv.render((900, 600))        # 画家算法（快，拖拽/预览用）
    pv.clear()                              # 清空重新 add

    # 4) 命令行
    python tk2_preview.py 模型.obj -o out.png --size 1200x800 --view 38,20 --tex 贴图.png

要点：
* 两档渲染：render() 是画家算法（快，适合交互），render_hq() 是逐像素 z-buffer（
  带贴图采样与 alpha 抠图，适合出图）。
* 贴图默认按 RGB 读取：游戏贴图的 alpha 常是无效数据（成片 A=0），而 Pillow 缩放 RGBA
  会按 alpha 预乘把 RGB 抹黑；需要 alpha 抠图（如贴花）时传 keep_alpha=True。
* 背景色 BG_RGB 可改。
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

BG_RGB = (58, 64, 72)          # 预览背景（中灰蓝：深色涂装也能看出轮廓）


def deg(d: float) -> float:
    """角度 -> 弧度（写视角时方便）"""
    return math.radians(d)


# ============================================================== 软渲染预览
class Preview:
    """软件渲染：拖动时用画家算法 + PIL 多边形填充（快）；
    停手后用逐像素 z-buffer 贴图渲染（HQ，轮子/细节才看得出贴图）。"""

    def __init__(self):
        self.parts = []            # 每项：dict(v,n,t,uv,c,tex)
        self.yaw, self.pitch = 0.9, 0.30
        self.zoom, self.pan = 1.0, np.zeros(2)
        self.wire = False
        self._V = np.zeros((0, 3))
        self._T = np.zeros((0, 3), np.int64)
        self._C = np.zeros((0, 3), np.uint8)
        self._texcache: dict[str, np.ndarray | None] = {}

    # ---------------------------------------------------------- 纹理取色
    def _tex_arr(self, path: Path | None, maxedge: int = 512, keep_alpha: bool = False):
        """取预览用贴图数组。默认转 RGB —— 游戏贴图的 alpha 是无效数据（常见成片 A=0），
        而 Pillow 缩放 RGBA 会按 alpha 预乘，A=0 的地方 RGB 会被抹成纯黑（负重轮就会整块变黑）。
        只有贴花需要 alpha 抠图，此时按通道分别缩放，避免预乘。"""
        if path is None:
            return None
        key = f"{path}|{maxedge}|{keep_alpha}"
        if key not in self._texcache:
            try:
                im = Image.open(path)
                if keep_alpha:
                    im = im.convert("RGBA")
                    if max(im.size) > maxedge:
                        sc = maxedge / max(im.size)
                        nw, nh = max(1, int(im.width * sc)), max(1, int(im.height * sc))
                        a = im.getchannel("A").resize((nw, nh), Image.BILINEAR)
                        rgb = im.convert("RGB").resize((nw, nh), Image.BILINEAR)
                        rgb.putalpha(a)
                        im = rgb
                else:
                    im = im.convert("RGB")
                    if max(im.size) > maxedge:
                        im.thumbnail((maxedge, maxedge), Image.BILINEAR)
                self._texcache[key] = np.asarray(im, np.uint8)
            except Exception:
                self._texcache[key] = None
        return self._texcache[key]

    def add(self, verts, normals, tris, uvs, tex: Path | None, base=(150, 152, 158), colors=None,
            keep_alpha: bool = False):
        if not len(verts) or not len(tris):
            return
        arr = self._tex_arr(tex, keep_alpha=keep_alpha)
        if colors is None or len(colors) != len(tris):
            colors = (self.face_colors(tris, uvs, tex, base, keep_alpha) if arr is not None
                      else np.tile(np.asarray(base, np.uint8), (len(tris), 1)))
        self.parts.append(dict(v=np.asarray(verts, np.float64), n=np.asarray(normals, np.float64),
                               t=np.asarray(tris, np.int64), uv=np.asarray(uvs, np.float64),
                               c=np.asarray(colors, np.uint8), tex=arr, path=str(tex) if tex else ""))

    def face_colors(self, tris, uvs, tex: Path | None, base=(150, 152, 158), keep_alpha: bool = False):
        """按 UV 面中心取贴图颜色（快渲染用；可在组装时缓存）"""
        arr = self._tex_arr(tex, keep_alpha=keep_alpha)
        if arr is None:
            return np.tile(np.asarray(base, np.uint8), (len(tris), 1))
        tri = uvs[tris]
        uv = tri.mean(axis=1)
        h, w = arr.shape[:2]
        u = np.mod(uv[:, 0], 1.0) * (w - 1)
        v = np.mod(1.0 - uv[:, 1], 1.0) * (h - 1)
        return arr[np.clip(v.astype(np.int32), 0, h - 1), np.clip(u.astype(np.int32), 0, w - 1), :3]

    def clear(self):
        self.parts.clear()

    def _build(self):
        vs, ts, cs, off = [], [], [], 0
        for p in self.parts:
            vs.append(p["v"]); ts.append(p["t"] + off); cs.append(p["c"]); off += len(p["v"])
        self._V = np.concatenate(vs) if vs else np.zeros((0, 3))
        self._T = np.concatenate(ts) if ts else np.zeros((0, 3), np.int64)
        self._C = np.concatenate(cs) if cs else np.zeros((0, 3), np.uint8)

    # ------------------------------------------------------ 相机（两种渲染共用）
    def _camera(self, W, H):
        V = np.concatenate([p["v"] for p in self.parts]) if self.parts else np.zeros((0, 3))
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        c = (V.max(axis=0) + V.min(axis=0)) / 2
        span = float(np.max(V.max(axis=0) - V.min(axis=0))) or 1.0
        pts = (V - c) @ (Ry.T @ Rx.T)
        sc = (min(W, H) * 0.62) / max(span / 2, 1e-6) * self.zoom
        px = pts[:, 0] * sc + W / 2 + self.pan[0]
        py = -pts[:, 1] * sc + H / 2 + self.pan[1]
        return pts, px, py

    def render_hq(self, size=(1000, 700)) -> Image.Image:
        """逐像素 z-buffer + UV 贴图 + 法线插值（质量高，用于静止画面）"""
        W, H = max(160, int(size[0])), max(160, int(size[1]))
        img = np.empty((H, W, 3), np.float32)
        img[:] = BG_RGB
        if not self.parts:
            return Image.fromarray(img.astype(np.uint8))
        pts, px, py = self._camera(W, H)
        # 注意：视图空间里 z 越大越靠近相机（与画家算法"按 z 升序=由远及近"一致）
        zbuf = np.full((H, W), -1e9, np.float32)
        light = np.array([0.35, 0.5, 0.80]); light /= np.linalg.norm(light)
        light2 = np.array([-0.55, 0.35, -0.75]); light2 /= np.linalg.norm(light2)
        off = 0
        for part in self.parts:
            T, UV = part["t"], part["uv"]
            N = part["n"]
            n0 = len(part["v"])
            if not len(T):
                continue
            # 预剔除：背面 / 屏幕外 / 亚像素三角面（有 z-buffer，顺序无所谓）
            X, Y = px[T + off], py[T + off]
            Z = pts[T + off, 2]
            signed = (X[:, 1] - X[:, 0]) * (Y[:, 2] - Y[:, 0]) - (X[:, 2] - X[:, 0]) * (Y[:, 1] - Y[:, 0])
            keep = (np.abs(signed) >= 0.4) & \
                   (np.minimum(np.minimum(X[:, 0], X[:, 1]), X[:, 2]) <= W) & \
                   (np.maximum(np.maximum(X[:, 0], X[:, 1]), X[:, 2]) >= 0) & \
                   (np.minimum(np.minimum(Y[:, 0], Y[:, 1]), Y[:, 2]) <= H) & \
                   (np.maximum(np.maximum(Y[:, 0], Y[:, 1]), Y[:, 2]) >= 0)
            for tri_i in np.nonzero(keep)[0]:
                a, b, c_ = T[tri_i]
                ax, ay, az = X[tri_i, 0], Y[tri_i, 0], Z[tri_i, 0]
                bx, by, bz = X[tri_i, 1], Y[tri_i, 1], Z[tri_i, 1]
                cx_, cy_, cz_ = X[tri_i, 2], Y[tri_i, 2], Z[tri_i, 2]
                x0 = int(max(0, math.floor(min(ax, bx, cx_))))
                x1 = int(min(W - 1, math.ceil(max(ax, bx, cx_))))
                y0 = int(max(0, math.floor(min(ay, by, cy_))))
                y1 = int(min(H - 1, math.ceil(max(ay, by, cy_))))
                if x1 < x0 or y1 < y0:
                    continue
                den = (by - cy_) * (ax - cx_) + (cx_ - bx) * (ay - cy_)
                if abs(den) < 1e-9:
                    continue
                gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
                l0 = ((by - cy_) * (gx - cx_) + (cx_ - bx) * (gy - cy_)) / den
                l1 = ((cy_ - ay) * (gx - cx_) + (ax - cx_) * (gy - cy_)) / den
                l2 = 1.0 - l0 - l1
                inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
                if not inside.any():
                    continue
                z = l0 * az + l1 * bz + l2 * cz_
                sub = zbuf[y0:y1 + 1, x0:x1 + 1]
                sel = inside & (z > sub)
                if not sel.any():
                    continue
                tex = part["tex"]
                if tex is not None:
                    th, tw = tex.shape[:2]
                    u = l0 * UV[a][0] + l1 * UV[b][0] + l2 * UV[c_][0]
                    v = l0 * UV[a][1] + l1 * UV[b][1] + l2 * UV[c_][1]
                    ui = np.clip((np.mod(u, 1.0) * (tw - 1)), 0, tw - 1).astype(np.int32)
                    vi = np.clip((1.0 - np.mod(v, 1.0)) * (th - 1), 0, th - 1).astype(np.int32)
                    texel = tex[vi, ui]
                    col = texel[..., :3].astype(np.float32)
                    if tex.shape[2] == 4:              # 贴花：抠掉透明像素
                        sel = sel & (texel[..., 3] > 128)
                        if not sel.any():
                            continue
                else:
                    col = np.full(gx.shape + (3,), 150.0, np.float32)
                nx = l0 * N[a][0] + l1 * N[b][0] + l2 * N[c_][0]
                ny = l0 * N[a][1] + l1 * N[b][1] + l2 * N[c_][1]
                nz = l0 * N[a][2] + l1 * N[b][2] + l2 * N[c_][2]
                ln = np.sqrt(nx * nx + ny * ny + nz * nz); ln[ln == 0] = 1
                lam = np.abs((nx * light[0] + ny * light[1] + nz * light[2]) / ln)
                rim = np.clip((nx * light2[0] + ny * light2[1] + nz * light2[2]) / ln, 0, 1)
                shade = (0.32 + 0.62 * lam + 0.16 * rim)[..., None]
                col = np.clip(col * shade, 0, 255)
                sub[sel] = z[sel]
                img[y0:y1 + 1, x0:x1 + 1][sel] = col[sel]
            off += n0
        return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))

    def render(self, size=(760, 560), fast=False) -> Image.Image:
        W, H = max(160, int(size[0])), max(160, int(size[1]))
        img = Image.new("RGB", (W, H), BG_RGB)
        if not self.parts:
            ImageDraw.Draw(img).text((12, 12), "无模型", fill=(200, 200, 200))
            return img
        self._build()
        S = min(W, H)
        V = self._V
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        c = (V.max(axis=0) + V.min(axis=0)) / 2
        span = float(np.max(V.max(axis=0) - V.min(axis=0))) or 1.0
        pts = (V - c) @ (Ry.T @ Rx.T)
        sc = (S * 0.62) / max(span / 2, 1e-6) * self.zoom
        px = pts[:, 0] * sc + W / 2 + self.pan[0]
        py = -pts[:, 1] * sc + H / 2 + self.pan[1]

        t = self._T
        x0, y0 = px[t[:, 0]], py[t[:, 0]]
        x1, y1 = px[t[:, 1]], py[t[:, 1]]
        x2, y2 = px[t[:, 2]], py[t[:, 2]]
        v0, v1, v2 = pts[t[:, 0]], pts[t[:, 1]], pts[t[:, 2]]
        nrm = np.cross(v1 - v0, v2 - v0)
        ln = np.linalg.norm(nrm, axis=1, keepdims=True); ln[ln == 0] = 1
        n = nrm / ln
        light = np.array([0.35, 0.5, 0.80]); light /= np.linalg.norm(light)
        light2 = np.array([-0.55, 0.35, -0.75]); light2 /= np.linalg.norm(light2)
        lam = np.abs(n @ light)
        rim = np.clip(n @ light2, 0, 1)
        shade = 0.30 + 0.62 * lam + 0.16 * rim
        signed = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        minx = np.minimum(np.minimum(x0, x1), x2); maxx = np.maximum(np.maximum(x0, x1), x2)
        miny = np.minimum(np.minimum(y0, y1), y2); maxy = np.maximum(np.maximum(y0, y1), y2)
        keep = (maxx >= 0) & (minx <= W) & (maxy >= 0) & (miny <= H) & (np.abs(signed) >= 0.5)
        front = keep & (signed <= 0)
        if front.sum() >= 0.25 * max(1, int(keep.sum())):
            keep = front
        k = np.nonzero(keep)[0]
        if not len(k):
            return img
        zc = pts[t[k, 0], 2] + pts[t[k, 1], 2] + pts[t[k, 2], 2]
        order = k[np.argsort(zc)]
        g = np.clip(255.0 * shade[order], 0, 255)
        rgb = np.clip(self._C[order].astype(np.float64) * (g[:, None] / 210.0), 0, 255).astype(np.uint8)
        tri = np.stack([x0[order], y0[order], x1[order], y1[order], x2[order], y2[order]], axis=1).tolist()
        cols = [tuple(int(x) for x in c_) for c_ in rgb.tolist()]
        dr = ImageDraw.Draw(img)
        poly = dr.polygon
        for i, q in enumerate(tri):
            poly(q, fill=cols[i])
        if self.wire:
            for q in tri:
                dr.line([(q[0], q[1]), (q[2], q[3]), (q[4], q[5]), (q[0], q[1])], fill=(20, 20, 20))
        return img


# ============================================================ 通用 OBJ 读取
def load_obj_file(path, split_material: bool = True, smooth_normals: bool = True):
    """读一个 OBJ 文件 -> 部件列表

    返回 [{'name': 组名, 'material': 材质名(usemtl，可空), 'verts': (N,3) float64,
           'normals': (N,3), 'uvs': (N,2), 'tris': (M,3) int64}, ...]
    （按 o/g 分组；文件里没有法线时按面自动算法线）
    """
    path = Path(path)
    vs, vts, vns = [], [], []
    groups = [[path.stem, "", []]]

    def _idx(i, n):
        return i - 1 if i > 0 else (n + i if i else -1)

    mat = ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                p = line.split(); vs.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("vt "):
                p = line.split(); vts.append((float(p[1]), float(p[2])))
            elif line.startswith("vn "):
                p = line.split(); vns.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("usemtl "):
                mat = line.split(None, 1)[1].strip()
                if groups[-1][2] and split_material:
                    groups.append([path.stem, mat, []])
                else:
                    groups[-1][1] = mat
            elif line[:2] in ("o ", "g "):
                nm = line.split(None, 1)[1].strip() if len(line.split(None, 1)) > 1 else path.stem
                if groups[-1][2]:
                    groups.append([nm, mat, []])
                else:
                    groups[-1][0] = nm
            elif line.startswith("f "):
                idx = []
                for tok in line.split()[1:]:
                    q = tok.split("/")
                    vi = _idx(int(q[0]), len(vs))
                    ti = _idx(int(q[1]), len(vts)) if len(q) > 1 and q[1] else -1
                    ni = _idx(int(q[2]), len(vns)) if len(q) > 2 and q[2] else -1
                    idx.append((vi, ti, ni))
                for k in range(1, len(idx) - 1):
                    groups[-1][2].append((idx[0], idx[k], idx[k + 1]))
    if not vs:
        return []
    V = np.asarray(vs, np.float64)
    parts = []
    for name, material, faces in groups:
        if not faces:
            continue
        key2i, lv, lt, ln, ltri = {}, [], [], [], []
        for tri in faces:
            row = []
            for vi, ti, ni in tri:
                if not (0 <= vi < len(V)):
                    row = []
                    break
                k = (vi, ti)
                j = key2i.get(k)
                if j is None:
                    j = len(lv)
                    key2i[k] = j
                    lv.append(V[vi])
                    lt.append(vts[ti] if 0 <= ti < len(vts) else (0.0, 0.0))
                    ln.append(vns[ni] if 0 <= ni < len(vns) else (0.0, 0.0, 0.0))
                row.append(j)
            if len(row) == 3:
                ltri.append(row)
        if not ltri:
            continue
        lv = np.asarray(lv, np.float64)
        lt = np.asarray(lt, np.float64)
        ln = np.asarray(ln, np.float64)
        tris = np.asarray(ltri, np.int64)
        if smooth_normals and not np.any(ln):
            fn = np.cross(lv[tris[:, 1]] - lv[tris[:, 0]], lv[tris[:, 2]] - lv[tris[:, 0]])
            ln = np.zeros_like(lv)
            for i in range(3):
                np.add.at(ln, tris[:, i], fn)
            nrm = np.linalg.norm(ln, axis=1, keepdims=True)
            nrm[nrm == 0] = 1
            ln = ln / nrm
        parts.append({"name": name, "material": material, "verts": lv, "normals": ln,
                      "uvs": lt, "tris": tris})
    return parts


def tex_thumb(path, maxedge: int = 256):
    """读一张贴图为数组（RGB，长边不超过 maxedge），失败返回 None"""
    return Preview()._tex_arr(Path(path), maxedge=maxedge)


# ============================================================ 便捷渲染
def render_parts(parts, size=(1200, 800), view=(38, 20), tex=None, textures=None,
                 wire: bool = False, hq: bool = True, keep_alpha=False):
    """渲染若干部件（parts 见 load_obj_file；每个部件可取不同贴图）

    tex       : 所有部件统一用的贴图路径
    textures  : {部件名: 贴图路径} 或 与 parts 等长的列表，优先于 tex
    """
    pv = Preview()
    pv.wire = wire
    for i, p in enumerate(parts):
        t = tex
        if isinstance(textures, dict):
            t = textures.get(p.get("name"), tex)
        elif isinstance(textures, (list, tuple)) and i < len(textures):
            t = textures[i]
        pv.add(p["verts"], p["normals"], p["tris"], p["uvs"], Path(t) if t else None,
               keep_alpha=keep_alpha)
    pv.yaw, pv.pitch = deg(view[0]), deg(view[1])
    return pv.render_hq(size) if hq else pv.render(size)


def render_obj(path, size=(1200, 800), view=(38, 20), tex=None, out=None,
               wire: bool = False, hq: bool = True, keep_alpha=False):
    """读一个 OBJ（可选贴图）渲染成图；给了 out 就存成 PNG 并返回路径"""
    parts = load_obj_file(path)
    if not parts:
        raise SystemExit(f"{path} 里没有网格")
    img = render_parts(parts, size, view, tex=tex, wire=wire, hq=hq, keep_alpha=keep_alpha)
    if out:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        return out
    return img


# ============================================================ 命令行
def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="OBJ 预览渲染（独立模块，也可直接跑）")
    ap.add_argument("obj", help="OBJ 文件")
    ap.add_argument("-o", "--out", help="输出 PNG（不给则打印信息）")
    ap.add_argument("--tex", help="贴图文件（可选）")
    ap.add_argument("--size", default="1200x800", help="尺寸 宽x高")
    ap.add_argument("--view", default="38,20", help="视角 方位角,俯仰角")
    ap.add_argument("--fast", action="store_true", help="用快渲染（画家算法）")
    ap.add_argument("--wire", action="store_true", help="叠加线框")
    ap.add_argument("--alpha", action="store_true", help="贴图保留 alpha（抠图用）")
    a = ap.parse_args(argv)
    w, h = (int(x) for x in a.size.lower().split("x"))
    az, el = (float(x) for x in a.view.split(","))
    parts = load_obj_file(a.obj)
    tris = sum(len(p["tris"]) for p in parts)
    print(f"{a.obj}: 部件 {len(parts)}  三角面 {tris:,}")
    img = render_parts(parts, (w, h), (az, el), tex=a.tex, wire=a.wire,
                       hq=not a.fast, keep_alpha=a.alpha)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        img.save(a.out)
        print(f"渲染 -> {a.out}")
    else:
        print(f"渲染完成：{img.size[0]}x{img.size[1]}（加 -o 输出.png 保存）")


if __name__ == "__main__":
    main()
