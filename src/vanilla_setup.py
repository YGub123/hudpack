# -*- coding: utf-8 -*-
"""vanilla/ 首次配置:从用户自己的 MC 客户端 jar 提取字体素材(Mojang 资产不随包分发)。
发布包只带可再分发的 GNU Unifont 两个 zip + 本工具自写的 unifont.json 配置;
其余(ascii.png 等贴图、字体 json)由本模块从用户选择的 jar 现场提取。全程离线。"""
import os, io, json, zipfile

# 自写的 include/unifont.json(等价于原版行为:jp 变体优先 + 主 unifont;CJK/全角/谚文按区定宽)。
# 纯功能性配置数据,非 Mojang 创作内容,可随包分发。
_OV = lambda a, b, l, r: {"from": a, "to": b, "left": l, "right": r}
UNIFONT_JSON = {"providers": [
    {"type": "unihex", "hex_file": "minecraft:font/unifont_jp.zip",
     "size_overrides": [_OV("㈀", "鿿", 0, 15), _OV("豈", "﫿", 0, 15)],
     "filter": {"jp": True}},
    {"type": "unihex", "hex_file": "minecraft:font/unifont.zip",
     "size_overrides": [
         _OV("、", "ヿ", 0, 15), _OV("㈀", "鿿", 0, 15),
         _OV("ᄀ", "ᇿ", 0, 15), _OV("㄰", "㆏", 0, 15),
         _OV("ꥠ", "꥿", 0, 15), _OV("ힰ", "퟿", 0, 15),
         _OV("가", "힯", 1, 15), _OV("豈", "﫿", 0, 15),
         _OV("！", "～", 0, 15)]},
]}

_KEY_FILES = [                                   # vanilla 是否可用的判据
    ("assets", "minecraft", "textures", "font", "ascii.png"),
    ("assets", "minecraft", "font", "include", "default.json"),
    ("assets", "minecraft", "font", "default.json"),
    ("assets", "minecraft", "font", "unifont.zip"),
]

def is_complete(vanilla):
    for parts in _KEY_FILES:
        if not os.path.isfile(os.path.join(vanilla, *parts)):
            return False
    # include/unifont.json 必须非空壳(jar 里那份是空 providers)
    try:
        p = os.path.join(vanilla, "assets", "minecraft", "font", "include", "unifont.json")
        return bool(json.load(open(p, encoding="utf-8")).get("providers"))
    except Exception:
        return False

def guess_versions_dir():
    """猜 .minecraft/versions 位置,给文件选择框当起始目录。"""
    cands = [os.path.join(os.environ.get("APPDATA", ""), ".minecraft", "versions")]
    # 常见的"版本隔离"启动器:桌面/各处的 .minecraft
    home = os.path.expanduser("~")
    for d in (os.path.join(home, "Desktop"), home):
        try:
            for n in os.listdir(d):
                p = os.path.join(d, n, ".minecraft", "versions")
                if os.path.isdir(p):
                    cands.append(p)
        except Exception:
            pass
    for c in cands:
        if os.path.isdir(c):
            return c
    return home

def setup_from_jar(vanilla, jar_path, log=print):
    """从客户端 jar 提取字体素材到 vanilla/。unifont zip 须已随包在位。返回问题列表(空=成功)。"""
    problems = []
    zf = zipfile.ZipFile(jar_path)
    names = zf.namelist()
    picked = [n for n in names
              if (n.startswith("assets/minecraft/font/") and n.endswith(".json"))
              or (n.startswith("assets/minecraft/textures/font/") and n.endswith(".png"))]
    if not any(n.endswith("textures/font/ascii.png") for n in picked):
        problems.append("这个 jar 里没有字体资源(选错文件了?要选原版客户端 jar,如 26.1.2.jar)")
        return problems
    for n in picked:
        dst = os.path.join(vanilla, *n.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(zf.read(n))
    log("已从 jar 提取 %d 个字体文件" % len(picked))
    # 覆盖空壳 unifont.json 为自写配置
    p = os.path.join(vanilla, "assets", "minecraft", "font", "include", "unifont.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(UNIFONT_JSON, io.open(p, "w", encoding="utf-8"), ensure_ascii=False)
    log("已写入 unifont.json 配置")
    for z in ("unifont.zip", "unifont_jp.zip"):
        if not os.path.isfile(os.path.join(vanilla, "assets", "minecraft", "font", z)):
            problems.append("缺 %s(应随发布包在 vanilla/assets/minecraft/font/ 下,别删)" % z)
    return problems
