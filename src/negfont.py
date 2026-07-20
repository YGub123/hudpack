# -*- coding: utf-8 -*-
"""negfont —— 纯标准库的 Minecraft 字体量宽 + 负宽字体生成 + 合并工具。
扫一个字体的所有 provider(bitmap 扫 PNG alpha / unihex 读 hex / space 取值 / reference 递归),
量出每个字形的 advance(和 MC 一致),生成"负宽 space 字体"(advance = -宽*factor,保留 filter)。
无第三方依赖(PNG 自解码,unihex 用 zipfile)。TTF 暂不支持(原版/位图图标用不到)。
"""
import os, io, json, zlib, struct, zipfile

# ============================================================
#  PNG 解码:返回 alpha[y][x](0/不透明>0)。支持 palette(1/2/4/8bit) 和 RGBA/GA/gray(8bit)。
# ============================================================
def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
    if pa <= pb and pa <= pc: return a
    return b if pb <= pc else c

def png_alpha(path):
    d = open(path, "rb").read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', "not a PNG: " + path
    W = H = bitdepth = colortype = 0
    plte = None; trns = None; idat = bytearray()
    i = 8
    while i < len(d):
        ln = struct.unpack(">I", d[i:i+4])[0]; typ = d[i+4:i+8]; data = d[i+8:i+8+ln]
        if typ == b'IHDR':
            W, H, bitdepth, colortype = struct.unpack(">IIBB", data[:10])
        elif typ == b'PLTE': plte = data
        elif typ == b'tRNS': trns = data
        elif typ == b'IDAT': idat += data
        elif typ == b'IEND': break
        i += 12 + ln
    raw = zlib.decompress(bytes(idat))
    # 每像素通道数
    channels = {0:1, 2:3, 3:1, 4:2, 6:4}[colortype]
    bpp_bits = channels * bitdepth
    scanline_bytes = (W * bpp_bits + 7) // 8
    filt_bpp = max(1, (bpp_bits + 7) // 8)   # 滤波用的"前一像素"字节偏移
    # 反滤波,得到每行原始字节
    rows = []
    prev = bytearray(scanline_bytes)
    pos = 0
    for y in range(H):
        ft = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos+scanline_bytes]); pos += scanline_bytes
        if ft == 1:      # Sub
            for x in range(filt_bpp, scanline_bytes): line[x] = (line[x] + line[x-filt_bpp]) & 255
        elif ft == 2:    # Up
            for x in range(scanline_bytes): line[x] = (line[x] + prev[x]) & 255
        elif ft == 3:    # Average
            for x in range(scanline_bytes):
                a = line[x-filt_bpp] if x >= filt_bpp else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif ft == 4:    # Paeth
            for x in range(scanline_bytes):
                a = line[x-filt_bpp] if x >= filt_bpp else 0
                c = prev[x-filt_bpp] if x >= filt_bpp else 0
                line[x] = (line[x] + _paeth(a, prev[x], c)) & 255
        rows.append(line); prev = line
    # 提取 alpha
    alpha = [[0]*W for _ in range(H)]
    def sample_indices(line):   # 对 <8bit,逐像素解包索引
        out = []
        if bitdepth == 8:
            return list(line[:W*channels])  # 调用方按 channels 取
        # palette 且 bitdepth<8
        mask = (1 << bitdepth) - 1
        per_byte = 8 // bitdepth
        for x in range(W):
            b = line[x // per_byte]
            shift = 8 - bitdepth * (x % per_byte + 1)
            out.append((b >> shift) & mask)
        return out
    for y in range(H):
        line = rows[y]
        if colortype == 6:       # RGBA 8bit
            for x in range(W): alpha[y][x] = line[x*4 + 3]
        elif colortype == 4:     # gray+alpha 8bit
            for x in range(W): alpha[y][x] = line[x*2 + 1]
        elif colortype == 3:     # palette
            idxs = sample_indices(line) if bitdepth < 8 else list(line[:W])
            for x in range(W):
                pi = idxs[x]
                a = 255
                if trns is not None and pi < len(trns): a = trns[pi]
                alpha[y][x] = a
        elif colortype in (0, 2): # gray / RGB:无 alpha,全不透明(字体极少用,兜底)
            for x in range(W): alpha[y][x] = 255
    return W, H, alpha

# ============================================================
#  资源定位
# ============================================================
def _split_id(rid, default_ns="minecraft"):
    return rid.split(":", 1) if ":" in rid else (default_ns, rid)

def find_file(namespace, kind, location, roots, ext=""):
    rel = os.path.join("assets", namespace, kind, *(location + ext).split("/"))
    for r in roots:
        p = os.path.join(r, rel)
        if os.path.isfile(p): return p
    return None

def load_font_json(font_id, roots):
    ns, loc = _split_id(font_id)
    p = find_file(ns, "font", loc, roots, ".json")
    if not p: raise FileNotFoundError("font not found: " + font_id + " in " + repr(roots))
    return json.load(open(p, encoding="utf-8"))

# ============================================================
#  逐 provider 量宽 → {codepoint: advance(float)}
# ============================================================
def measure_bitmap(prov, roots):
    ns, loc = _split_id(prov["file"])
    png = find_file(ns, "textures", loc, roots)
    if not png: raise FileNotFoundError("texture not found: " + prov["file"])
    W, H, alpha = png_alpha(png)
    chars = prov["chars"]
    height = prov.get("height", 8)
    rows = len(chars); cols = max(len(r) for r in chars)  # 每行的码点数(用码点计,非 UTF-16)
    # chars 每行是字符串,按码点拆
    grid = [[cp for cp in row] for row in chars]  # row 是 str,for cp in row 按码点遍历(py3)
    cell_h = H // rows
    out = {}
    for r, row in enumerate(grid):
        cell_w = W // len(row) if len(row) else 0
        for c, ch in enumerate(row):
            cp = ord(ch)
            if cp == 0 or ch == ' ': continue
            x0 = c * cell_w; y0 = r * cell_h
            # 从右往左找最右非透明列
            width = 0
            for lx in range(cell_w-1, -1, -1):
                col_on = any(alpha[y0+ly][x0+lx] != 0 for ly in range(cell_h))
                if col_on: width = lx + 1; break
            scale = height / cell_h
            adv = width * scale + 1.0        # MC:字形像素宽*缩放 + 1px 间距(保留浮点,不取整)
            out[cp] = adv
    return out

def measure_space(prov, roots):
    out = {}
    for k, v in prov["advances"].items():
        out[ord(k)] = float(v)
    return out

def measure_unihex(prov, roots):
    ns, loc = _split_id(prov["hex_file"])
    zpath = find_file(ns, "", loc, roots)  # hex_file 是完整 location,如 font/unifont.zip
    if not zpath: raise FileNotFoundError("hex zip not found: " + prov["hex_file"])
    # size_overrides:范围 → advance(right-left+1 的半宽+1)
    overrides = []
    for ov in prov.get("size_overrides", []):
        lo = ord(ov["from"]); hi = ord(ov["to"]); wpx = ov["right"] - ov["left"] + 1
        overrides.append((lo, hi, wpx))
    def ov_width(cp):
        for lo, hi, wpx in overrides:
            if lo <= cp <= hi: return wpx
        return None
    out = {}
    zf = zipfile.ZipFile(zpath)
    for name in zf.namelist():
        if not name.endswith(".hex"): continue
        for line in zf.read(name).decode("utf-8").splitlines():
            if ":" not in line: continue
            code, bmp = line.split(":", 1)
            cp = int(code, 16)
            w = ov_width(cp)
            if w is None:
                w = _hex_width(bmp)
            adv = int(0.5 * w) + 1 if w else 0   # unifont:半宽 + 1(与 MC/FWC 一致)
            if adv: out[cp] = float(adv)
    return out

def _hex_width(bmp):
    # bmp 是 16 行拼起来的十六进制;每行 row_len//16... 实际:len(bmp)//16 个 hex 字符/行
    row_len = len(bmp) // 16
    if row_len == 0: return 0
    lo, hi = row_len*4, -1
    for i in range(16):
        row = int(bmp[i*row_len:(i+1)*row_len], 16)
        if row == 0: continue
        low = (row & -row).bit_length()
        lo = min(low, lo); hi = max(row.bit_length(), hi)
    return 0 if hi == -1 else hi - lo + 1

def measure_providers(font_id, roots, _seen=None):
    """返回 [(advances_dict, filter_or_None), ...],顺序 = provider 优先级顺序。"""
    if _seen is None: _seen = set()
    if font_id in _seen: return []
    _seen = _seen | {font_id}
    result = []
    for prov in load_font_json(font_id, roots)["providers"]:
        t = prov["type"]
        filt = prov.get("filter")
        if t == "reference":
            for adv, f in measure_providers(prov["id"], roots, _seen):
                result.append((adv, f if f is not None else filt))
        elif t == "bitmap":
            result.append((measure_bitmap(prov, roots), filt))
        elif t == "space":
            result.append((measure_space(prov, roots), filt))
        elif t == "unihex":
            result.append((measure_unihex(prov, roots), filt))
        elif t == "ttf":
            raise NotImplementedError("ttf provider 暂不支持(用 bitmap 图标字体)")
        else:
            raise Exception("未知 provider 类型: " + t)
    return result

def merged_advances(font_id, roots):
    """扁平化成 {cp: advance}(第一个命中的 provider 胜),用于自测/查值。"""
    out = {}
    for adv, _ in measure_providers(font_id, roots):
        for cp, a in adv.items():
            out.setdefault(cp, a)
    return out

# ============================================================
#  负宽字体生成 + 写盘
# ============================================================
def _num(x):
    xi = round(x)
    return int(xi) if abs(x - xi) < 1e-9 else round(x, 4)

def neg_providers(font_id, roots, factor):
    """把 font_id 的每个 provider 转成负宽 space provider(advance=-宽*factor,保留 filter)。
    相邻同 filter 的 provider 合并(first-wins,保持 MC 的"前者优先"语义),减少 provider 数。"""
    # factor=-1 → 全负宽(-advance);factor=-0.5 → 半负宽(-advance/2)
    groups = []   # [(advances_dict, filter), ...]
    for advances, filt in measure_providers(font_id, roots):
        adv = {chr(cp): _num(a * factor) for cp, a in advances.items()}
        if groups and groups[-1][1] == filt:          # 与上一个同 filter → 合并
            merged = groups[-1][0]
            for k, v in adv.items():
                merged.setdefault(k, v)                # first-wins:不覆盖前者
        else:
            groups.append((adv, filt))
    provs = []
    for adv, filt in groups:
        sp = {"type": "space", "advances": adv}
        if filt is not None:
            sp["filter"] = filt
        provs.append(sp)
    return provs

def write_font(out_pack, out_id, providers):
    ns, loc = _split_id(out_id)
    path = os.path.join(out_pack, "assets", ns, "font", *(loc + ".json").split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"providers": providers}, io.open(path, "w", encoding="utf-8"),
              ensure_ascii=True, separators=(",", ":"))
    return path

if __name__ == "__main__":
    # 自测:量 minecraft:default 的 ASCII,验证已知 advance
    import sys
    roots = sys.argv[1:] or [r"C:\Users\86183\Desktop\fwc_vanilla"]
    adv = merged_advances("minecraft:default", roots)
    known = {'A':6, 'a':6, 'i':2, 't':4, 'l':3, 'W':6, ' ':4, '!':2, 'M':6, '0':6}
    print("== ASCII 自测(应全部一致)==")
    ok = True
    for ch, exp in known.items():
        got = adv.get(ord(ch))
        mark = "OK" if got == exp else "×差异"
        if got != exp: ok = False
        print("  '%s' 期望 %d  实测 %s  %s" % (ch, exp, got, mark))
    print("== 汉字(override 应=9)==")
    for ch in "血量中":
        print("  '%s' advance = %s" % (ch, adv.get(ord(ch))))
    print("总计码点数:", len(adv), " ASCII 全对:", ok)
