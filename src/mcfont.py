# -*- coding: utf-8 -*-
"""MC 原版点阵字渲染(tkinter PhotoImage)——与游戏同源:
ASCII 用 vanilla/ascii.png 的真字形,汉字用 unifont.zip 的真点阵。
整数倍放大保持像素锐利;可带 1px(游戏像素)硬阴影。素材缺失时 available=False,调用方回退系统字体。"""
import os, zipfile
import tkinter as tk
import negfont


class McFont:
    def __init__(self, vanilla_dir):
        self.available = False
        self._cache = {}
        self._uni = None
        try:
            png = os.path.join(vanilla_dir, "assets", "minecraft", "textures", "font", "ascii.png")
            W, H, alpha = negfont.png_alpha(png)
            self._mask = alpha
            self._cw, self._ch = W // 16, H // 16          # 8x8 格
            self._unizip = os.path.join(vanilla_dir, "assets", "minecraft", "font", "unifont.zip")
            self.available = True
        except Exception:
            pass

    # ---- 字形 ----
    def _load_uni(self):
        if self._uni is not None:
            return
        self._uni = {}
        try:
            zf = zipfile.ZipFile(self._unizip)
            for name in zf.namelist():
                if name.endswith(".hex"):
                    for line in zf.read(name).decode("utf-8").splitlines():
                        c = line.find(":")
                        if c > 0:
                            self._uni[int(line[:c], 16)] = line[c + 1:]
        except Exception:
            pass

    def _glyph(self, cp):
        """→ (宽, 每格像素数8|16, {(x,y)});未知字形回 None。"""
        if cp == 0x20:
            return (3, 8, frozenset())
        if 0x20 < cp < 0x80:                                # ascii.png:code 即网格序号
            x0, y0 = (cp % 16) * self._cw, (cp // 16) * self._ch
            pts = set(); mx = -1
            for y in range(self._ch):
                row = self._mask[y0 + y]
                for x in range(self._cw):
                    if row[x0 + x]:
                        pts.add((x, y)); mx = max(mx, x)
            return (mx + 1 if mx >= 0 else 3, 8, frozenset(pts))
        self._load_uni()
        b = self._uni.get(cp)
        if b is None:
            return None
        rl = len(b) // 16
        w = rl * 4
        pts = set()
        for y in range(16):
            rowv = int(b[y * rl:(y + 1) * rl], 16)
            for x in range(w):
                if rowv >> (w - 1 - x) & 1:
                    pts.add((x, y))
        if pts:
            xs = [p[0] for p in pts]
            x0, x1 = min(xs), max(xs)
            pts = frozenset((x - x0, y) for x, y in pts)
            w = x1 - x0 + 1
        else:
            w = 8
        return (w, 16, pts)

    def _layout(self, text, z):
        """→ (总宽, 总高, [(x偏移, 像素尺寸, pts)]);unifont 半分辨率(像素=z/2)。"""
        items = []; x = 0
        for ch in text:
            g = self._glyph(ord(ch)) or (5, 8, frozenset())
            w, res, pts = g
            pz = z if res == 8 else max(1, z // 2)
            items.append((x, pz, pts))
            x += w * pz + z                                  # 字距 = 1 游戏像素
        return x, 8 * z, items

    def measure(self, text, z=2):
        return self._layout(text, z)[0]

    # ---- 渲染(结果缓存;PhotoImage 底透明) ----
    def render(self, text, z=2, color="#ffffff", shadow="#3e3e3e"):
        key = (text, z, color, shadow)
        img = self._cache.get(key)
        if img is not None:
            return img
        W, H, items = self._layout(text, z)
        img = tk.PhotoImage(width=max(1, W + z), height=H + z)
        for col, dx, dy in (((shadow, z, z),) if shadow else ()) + ((color, 0, 0),):
            for x0, pz, pts in items:
                for (px, py) in pts:
                    X, Y = x0 + px * pz + dx, py * pz + dy
                    img.put(col, to=(X, Y, X + pz, Y + pz))
        self._cache[key] = img
        return img
