# -*- coding: utf-8 -*-
"""iconpack —— UI 图片管理 + 图标字体生成(配合 negfont 出负宽)。
你往 icons/ 丢 PNG(文件名=图标名),本工具:
  · 维护持久 registry.json(名字 → 稳定码点 + height/ascent + hash)
  · 每次重跑自动对账(新增分配码点 / 换图保码点 / 删图保留占位并警告)
  · 生成图标字体 <ns>:icons、拷图、调 negfont 出 <ns>:iconsneg(+half)
  · 产出三种用法的表:速查表(A 贴字符)/ ${} 替换(B静态)/ 运行时 map(B动态)
无第三方依赖。"""
import os, io, json, struct, hashlib, shutil
import negfont

# ---------- 基础 ----------
def png_dims(path):
    d = open(path, "rb").read(26)
    assert d[:8] == b'\x89PNG\r\n\x1a\n', "not PNG: " + path
    w, h = struct.unpack(">II", d[16:24])
    return w, h

def file_hash(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()[:12]

def esc(cp):
    """码点 → JSON/命令里的转义写法(BMP 直接 \\uXXXX,补充平面用代理对)。"""
    if cp <= 0xFFFF:
        return "\\u%04X" % cp
    c = cp - 0x10000
    return "\\u%04X\\u%04X" % (0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF))

# ---------- 主流程 ----------
def scan(icons_dir, registry_path=None, start_cp=0xE000, default_height=None, verbose=True):
    """只对账 registry(扫盘、分配码点、换图/删除标记)并存盘,不生成字体。
    轻量、即时——GUI 添加图标后立即调它,新图当场拿到码点并显示。返回 (reg, warnings)。"""
    if registry_path is None:
        registry_path = os.path.join(icons_dir, "registry.json")
    reg = {"next": "%04X" % start_cp, "free": [], "icons": {}}
    if os.path.isfile(registry_path):
        reg = json.load(open(registry_path, encoding="utf-8"))
    reg.setdefault("free", [])          # 可复用码点池(释放的退役码点、未转正就删的码点)
    icons = reg["icons"]
    nxt = int(reg["next"], 16)

    # 扫盘(递归任意嵌套)。**名字=纯文件名(不含路径)**——子文件夹只是整理,不进身份;
    # 引用(${name}/{icon:name})、复制、registry 键都用短名。跨文件夹重名 → 警告并跳过后者。
    warnings = []
    found = {}          # 短名 → (完整路径, 相对路径含扩展名)
    for root, _dirs, files in os.walk(icons_dir):
        for fn in sorted(files):
            if fn.lower().endswith(".png"):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, icons_dir).replace(os.sep, "/")
                base = os.path.splitext(fn)[0]
                if base in found:
                    warnings.append("重名跳过: %s(已有 %s)—— 图标名不含路径,不同文件夹也不能同名" % (rel, found[base][1]))
                    continue
                found[base] = (full, rel)

    # 旧版 registry 迁移:键带路径的(ui/heart)改成短名(heart),码点不变
    for name in list(icons):
        if "/" in name:
            base = name.rsplit("/", 1)[1]
            if base not in icons:
                icons[base] = icons.pop(name)
            else:
                warnings.append("迁移冲突: '%s' 与已有 '%s' 重名,保留旧键" % (name, base))
    # 对账:删除的(registry 有、盘上没了)
    for name in list(icons):
        if name not in found:
            warnings.append("图标 '%s' 源文件没了 → 码点 %s 保留占位(不重用),字体里剔除" % (name, icons[name]["cp"]))
            icons[name]["missing"] = True

    # 对账:新增 / 换图 / 挪目录
    for name, (path, rel) in found.items():
        w, h = png_dims(path)
        hsh = file_hash(path)
        if name not in icons:                       # 新图 → 分配码点(优先复用释放池)
            if reg["free"]:
                reg["free"].sort()
                cph = reg["free"].pop(0); cp = int(cph, 16)
                src = "复用"
            else:
                cp = nxt; nxt += 1; src = "新"
            ht = default_height or h
            # built:False = 临时登记,构建过一次才转正;转正前删除会直接回收码点
            icons[name] = {"cp": "%04X" % cp, "file": rel, "built": False,
                           "w": w, "h": h, "height": ht, "ascent": min(ht, ht - 1), "hash": hsh}
            if verbose: print("  + 新图 %-12s → U+%04X (%dx%d, %s)" % (name, cp, w, h, src))
        else:                                        # 老图 → 保码点;换图或挪了文件夹就更新记录
            e = icons[name]; e.pop("missing", None)
            if e.get("hash") != hsh or e.get("file") != rel:
                e.update({"file": rel, "w": w, "h": h, "hash": hsh})
                if verbose: print("  ~ 更新 %-12s (码点 %s 不变)" % (name, e["cp"]))
        e = icons[name]
        e.setdefault("built", True)                  # 本工具早期版本登记的都进过包,视为已转正
        e.setdefault("height", default_height or e["h"])
        e.setdefault("ascent", min(e["height"], e["height"] - 1))

    reg["next"] = "%04X" % nxt
    json.dump(reg, io.open(registry_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return reg, warnings


def build(icons_dir, out_pack, ns="dbchud", vanilla_roots=(), registry_path=None,
          start_cp=0xE000, default_height=None, verbose=True):
    """scan 对账 → 出字体/负宽/表。返回 registry。"""
    if registry_path is None:
        registry_path = os.path.join(icons_dir, "registry.json")
    reg, warnings = scan(icons_dir, registry_path, start_cp, default_height, verbose)
    icons = reg["icons"]

    # ---- 拷图 + 生成图标字体(每图一个 bitmap provider)----
    tex_dir = os.path.join(out_pack, "assets", ns, "textures", "font", "icons")
    os.makedirs(tex_dir, exist_ok=True)
    providers = []
    for name, e in sorted(icons.items(), key=lambda kv: kv[1]["cp"]):
        if e.get("missing"):
            continue
        dst = os.path.join(tex_dir, *e["file"].split("/"))     # 保留子目录
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(icons_dir, *e["file"].split("/")), dst)
        cp = int(e["cp"], 16)
        providers.append({"type": "bitmap",
                          "file": "%s:font/icons/%s" % (ns, e["file"]),
                          "height": e["height"], "ascent": e["ascent"],
                          "chars": [chr(cp)]})
    negfont.write_font(out_pack, "%s:icons" % ns, providers)

    # ---- negfont 出负宽(全 + 半)----
    roots = [out_pack] + list(vanilla_roots)
    negfont.write_font(out_pack, "%s:iconsneg" % ns,     negfont.neg_providers("%s:icons" % ns, roots, -1.0))
    negfont.write_font(out_pack, "%s:iconsneghalf" % ns, negfont.neg_providers("%s:icons" % ns, roots, -0.5))

    # ---- 进包的图标转正(built=True):此后删除只留占位,不再自动回收码点 ----
    live = {n: e for n, e in icons.items() if not e.get("missing")}
    for e in live.values():
        e["built"] = True
    # A:速查表
    sheet = ["图标速查表(名字 → 转义 → 码点)", "=" * 40]
    for n, e in sorted(live.items()):
        sheet.append("  %-14s %-14s U+%s" % (n, esc(int(e["cp"], 16)), e["cp"]))
    write(os.path.join(out_pack, "ICONS-cheatsheet.txt"), "\n".join(sheet) + "\n")
    # B动态:运行时 map(mcfunction 片段,塞进你的 load)
    m = ",".join('"%s":"%s"' % (n, esc(int(e["cp"], 16))) for n, e in sorted(live.items()))
    write(os.path.join(out_pack, "ICONS-runtime-map.mcfunction"),
          "# 把这行加进你的 load:B动态({\"icon\":\"名字\"})运行时查这张表\n"
          "data modify storage %s:icons map set value {%s}\n" % (ns, m))

    json.dump(reg, io.open(registry_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if verbose:
        for w_ in warnings: print("  ! " + w_)
        print("  图标字体 %s:icons(%d 个)+ 负宽 iconsneg/iconsneghalf 已生成" % (ns, len(providers)))
    return reg, live

def discard(icons_dir, name, registry_path=None):
    """把某条登记彻底移除,码点放进可复用池(free)。用于:
    ① 未转正(built=False)的图标删除时自动回收;② 码点管理面板里用户确认『释放』失效占位。
    注意:若地图里还有该码点的旧引用,释放后它会指到未来复用此码点的新图标——所以要用户确认。"""
    if registry_path is None:
        registry_path = os.path.join(icons_dir, "registry.json")
    reg = json.load(open(registry_path, encoding="utf-8"))
    reg.setdefault("free", [])
    e = reg["icons"].pop(name, None)
    if e is None:
        raise KeyError("没有登记: " + name)
    if e["cp"] not in reg["free"]:
        reg["free"].append(e["cp"])
        reg["free"].sort()
    json.dump(reg, io.open(registry_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return e["cp"]


def rename(icons_dir, old, new, registry_path=None):
    """保码点改名:同时改 registry 键和 PNG 文件名,cp 不变。改完重跑 build 更新字体/表。"""
    if registry_path is None:
        registry_path = os.path.join(icons_dir, "registry.json")
    reg = json.load(open(registry_path, encoding="utf-8"))
    icons = reg["icons"]
    if old not in icons:
        raise KeyError("没有图标: " + old)
    if new in icons:
        raise KeyError("目标名已存在: " + new)
    if "/" in new:
        raise ValueError("名字不含路径(子文件夹只是整理);要挪目录直接在文件管理器里移动 PNG 即可")
    e = icons.pop(old)
    ext = os.path.splitext(e["file"])[1]
    oldp = os.path.join(icons_dir, *e["file"].split("/"))
    d = e["file"].rsplit("/", 1)[0] + "/" if "/" in e["file"] else ""
    newf = d + new + ext                               # 文件留在原目录,只改名字段
    newp = os.path.join(icons_dir, *newf.split("/"))
    if os.path.isfile(oldp):
        os.replace(oldp, newp)
    e["file"] = newf
    icons[new] = e
    json.dump(reg, io.open(registry_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("重命名 %s → %s(码点 %s 不变,文件已改)。重跑 build 更新字体/表。" % (old, new, e["cp"]))

def resolve_map(live):
    """给 B静态 用:{名字: 转义字符串}。造包脚本拿它做 ${name} 替换。"""
    return {n: esc(int(e["cp"], 16)) for n, e in live.items()}

def resolve_text(s, rmap):
    """B静态:把源文本里的 ${name} 替换成转义;未知名字报错。转义符/其它原样。"""
    import re
    def sub(mm):
        n = mm.group(1)
        if n not in rmap:
            raise KeyError("未知图标: ${%s}" % n)
        return rmap[n]
    return re.sub(r"\$\{(\w[\w/]*)\}", sub, s)

def write(path, data, binary=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    (open(path, "wb") if binary else io.open(path, "w", encoding="utf-8", newline="\n")).write(data)
