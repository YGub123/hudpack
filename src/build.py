# -*- coding: utf-8 -*-
"""生成 DBCHUD 数据包 + 资源包(纯原版,无插件)。所有路径相对本脚本 → tools/hudpack 自成一体。
着色器从 Position.x(标尺固定推进=检测标记)+ 颜色(x%,y%,色号)重定位;
净宽 0 靠"负宽字体"(negfont 从真实字体精确取负 advance,渲一遍不可见)自动抵消。
输出在 tools/hudpack/out/,把里面两个包拷进 MC 即可(见 README)。
"""
import os, io

# 工具根目录(vanilla/icons/out 所在):
#   1) 环境变量 HUDPACK_HOME(exe/GUI 里由界面设置);2) 本文件所在目录;若在 src/ 下则取上一级
HERE = os.environ.get("HUDPACK_HOME")
if not HERE:
    HERE = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(HERE).lower() == "src":
        HERE = os.path.dirname(HERE)
OUT  = os.path.join(HERE, "out")                       # 输出:两个成品包 + README
RP = os.path.join(OUT, "dbchud_resourcepack")
DP = os.path.join(OUT, "dbchud_datapack")
NS = "dbchud"

# —— 编码常量(须与着色器一致)——
BIAS, STEP, STEP_S, DYBIAS, N = 524288, 2048, 262144, 64, 100
# 固定:scale=1(q=15→scaleHi=3,scaleLo=3)、dy=0、dx=0、左对齐 → push 恒定
SCALE_HI = 3
PUSH = BIAS + SCALE_HI * STEP_S + (0 + DYBIAS) * STEP + 0 + STEP // 2   # =1442816

def ruler(v, negative):
    base = 0xE900 if negative else 0xE800
    out = []
    for place in range(7):
        digit = (v >> (4 * place)) & 0xF
        if digit:
            out.append(chr(base + place * 16 + digit))
    return "".join(out)

OPEN = ruler(PUSH, False)
CLOSE = ruler(PUSH, True)

# 各字号档(scaleHi 0..15)的标尺推进串。整数倍字号 k(1~4)对应 scaleHi = 4k-1(scaleLo 恒=3)。
def push_of(sh):
    return BIAS + sh * STEP_S + (0 + DYBIAS) * STEP + 0 + STEP // 2
RULER_O = [ruler(push_of(sh), False) for sh in range(16)]
RULER_C = [ruler(push_of(sh), True) for sh in range(16)]

def w(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(content)

# ========== 1. 字体:negfont 精确负宽 + iconpack 图标 + 合并(替代手搓宽度表)==========
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import negfont, iconpack
VANILLA = os.path.join(HERE, "vanilla")   # negfont 量原版字宽的素材(含 unifont),已随工具一起
ICONS   = os.path.join(HERE, "icons")     # 你丢 UI 图标 PNG 的地方(文件名=名字)

# ========== 2. 资源包 ==========
w(os.path.join(RP, "pack.mcmeta"),
  '{"pack":{"pack_format":42,"min_format":84,"max_format":84,'
  '"description":"§bDBCHUD§7 · 着色器 HUD 定位(资源包)"}}')

# 标尺字体(base-16 位置制;正 E800.. / 负 E900..)
adv_pairs = []
for place in range(7):
    unit = 1 << (4*place)
    for digit in range(1,16):
        a = digit*unit
        adv_pairs.append('"\\u%04X":%d' % (0xE800+place*16+digit, a))
        adv_pairs.append('"\\u%04X":%d' % (0xE900+place*16+digit, -a))
w(os.path.join(RP, "assets", NS, "font", "hudruler.json"),
  '{"providers":[{"type":"space","advances":{' + ",".join(adv_pairs) + '}}]}')

# —— 图标:iconpack 扫 ICONS/ → dbchud:icons + iconsneg(+half),持久 registry ——
def _has_png(d):
    for _r, _d, _fs in os.walk(d):
        if any(f.lower().endswith(".png") for f in _fs):
            return True
    return False
if os.path.isdir(ICONS) and _has_png(ICONS):
    _reg, _live = iconpack.build(ICONS, RP, ns=NS, vanilla_roots=[VANILLA], verbose=True)
    ICON_MAP = iconpack.resolve_map(_live)        # {名字: 转义} 给 B静态 ${} 替换用
    ICON_CHARS = {n: chr(int(e["cp"], 16)) for n, e in _live.items()}  # {名字: 字面字符} 给 B动态运行时表
    _icon = [{"type": "reference", "id": "%s:icons" % NS}]
    _iconneg = [{"type": "reference", "id": "%s:iconsneg" % NS}]
    _iconneghalf = [{"type": "reference", "id": "%s:iconsneghalf" % NS}]
    print("  图标已并入 dbchud:all/allneg:", list(ICON_MAP))
else:
    ICON_MAP = {}; ICON_CHARS = {}; _icon = _iconneg = _iconneghalf = []
    print("  (ICONS/ 无 PNG,跳过图标;以后丢图重跑即可)")

# —— 自定义字体接入:把整套字体资源(assets/<ns>/font/*.json + 贴图)丢进 fonts/,
#    构建时拷进资源包、自动量宽、生成负宽,并入总字体。字形放未占用码点(如 PUA)最稳。——
FONTS = os.path.join(HERE, "fonts")
os.makedirs(FONTS, exist_ok=True)
_extra_ids = []
_fa = os.path.join(FONTS, "assets")
if os.path.isdir(_fa):
    import shutil as _sh
    for _root, _dirs, _files in os.walk(_fa):
        for _f in _files:
            _src = os.path.join(_root, _f)
            _rel = os.path.relpath(_src, FONTS)
            _dst = os.path.join(RP, _rel)
            os.makedirs(os.path.dirname(_dst), exist_ok=True)
            _sh.copyfile(_src, _dst)
            _parts = _rel.replace(os.sep, "/").split("/")
            # assets/<ns>/font/<路径>.json → 字体 id <ns>:<路径>
            if len(_parts) >= 4 and _parts[2] == "font" and _f.lower().endswith(".json"):
                _extra_ids.append(_parts[1] + ":" + "/".join(_parts[3:])[:-5])
_extra, _extraneg, _extraneghalf = [], [], []
for _fid in _extra_ids:
    _safe = _fid.replace(":", "_").replace("/", "_")
    negfont.write_font(RP, "%s:neg_%s" % (NS, _safe),     negfont.neg_providers(_fid, [RP, VANILLA], -1.0))
    negfont.write_font(RP, "%s:neghalf_%s" % (NS, _safe), negfont.neg_providers(_fid, [RP, VANILLA], -0.5))
    _extra.append({"type": "reference", "id": _fid})
    _extraneg.append({"type": "reference", "id": "%s:neg_%s" % (NS, _safe)})
    _extraneghalf.append({"type": "reference", "id": "%s:neghalf_%s" % (NS, _safe)})
if _extra_ids:
    print("  自定义字体已并入:", ", ".join(_extra_ids))

# —— 原版全字体的精确负宽(保留 filter:{uniform:false} → 自动跟随 Force Unicode)——
negfont.write_font(RP, "%s:defaultneg" % NS,     negfont.neg_providers("minecraft:default", [RP, VANILLA], -1.0))
negfont.write_font(RP, "%s:defaultneghalf" % NS, negfont.neg_providers("minecraft:default", [RP, VANILLA], -0.5))

# —— 合并:可见 all = 自定义字体 + 图标 + 原版;负宽 allneg 同序(逐码点精确抵消)。
#    自定义在前:它定义的码点优先生效(原版 unifont 几乎覆盖全 BMP,放后面才不会盖住自定义)。——
negfont.write_font(RP, "%s:all" % NS,        _extra + _icon + [{"type": "reference", "id": "minecraft:default"}])
negfont.write_font(RP, "%s:allneg" % NS,     _extraneg + _iconneg + [{"type": "reference", "id": "%s:defaultneg" % NS}])
negfont.write_font(RP, "%s:allneghalf" % NS, _extraneghalf + _iconneghalf + [{"type": "reference", "id": "%s:defaultneghalf" % NS}])
# 可见正文用 dbchud:all,负宽用 allneg。all 引用 minecraft:default(带 uniform filter),
# 所以正文自动跟随 Force Unicode;defaultneg 保留同 filter → 两边同步,无需玩家声明。

# ========== 1b. 样式槽(hud_style.json):128 槽,每槽 = RGB 颜色 + 效果 ==========
# 默认填成 16 色 × 8 效果的网格(与旧版完全兼容);presets 里加自定义样式(任意 RGB+效果)。
import json as _json
STYLE_PATH = os.path.join(HERE, "hud_style.json")
_BEHAVIOR = {"none": 0, "wave": 1, "shake": 2, "pulse": 3, "rainbow": 4, "blink": 5, "rotate": 6}
_DEF_COLORS = [("black", "#000000"), ("dark_blue", "#0000AA"), ("dark_green", "#00AA00"),
    ("dark_aqua", "#00AAAA"), ("dark_red", "#AA0000"), ("dark_purple", "#AA00AA"),
    ("gold", "#FFAA00"), ("gray", "#AAAAAA"), ("dark_gray", "#555555"), ("blue", "#5555FF"),
    ("green", "#55FF55"), ("aqua", "#55FFFF"), ("red", "#FF5555"), ("light_purple", "#FF55FF"),
    ("yellow", "#FFFF55"), ("white", "#FFFFFF")]
if not os.path.isfile(STYLE_PATH):
    _json.dump({
        "_说明": ["样式槽共 128 个:colors×effects 的网格占前面,剩下的给 presets(自定义样式)。",
                  "presets 写法  名字: {rgb, effect} ,指令里用 color:\"名字\"(effect 填 none)。",
                  "effect 可选:none wave shake pulse rainbow blink rotate。改完点『开始构建』生效。"],
        "colors": dict(_DEF_COLORS),
        "effects": ["none", "wave", "shake", "pulse", "rainbow", "blink", "rotate"],
        "presets": {"gold_wave": {"rgb": "#FFD700", "effect": "wave"}},
    }, io.open(STYLE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
_style = _json.load(open(STYLE_PATH, encoding="utf-8"))
_colors = list(_style["colors"].items())
_effs = list(_style["effects"])
_presets = list(_style.get("presets", {}).items())
NC, NE = len(_colors), len(_effs)
NG = NC * NE
assert NG + len(_presets) <= 128, "样式槽超 128:颜色%d×效果%d=%d + 预设%d" % (NC, NE, NG, len(_presets))
for _e in _effs:
    assert _e in _BEHAVIOR, "hud_style.json 未知效果: " + _e
def _rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
slot_rgb = [(255, 255, 255)] * 128
slot_eff = [0] * 128
for _ei, _en in enumerate(_effs):
    for _ci, (_cn, _ch) in enumerate(_colors):
        slot_rgb[_ei * NC + _ci] = _rgb(_ch)
        slot_eff[_ei * NC + _ci] = _BEHAVIOR[_en]
for _k, (_pn, _p) in enumerate(_presets):
    assert _p["effect"] in _BEHAVIOR, "预设 %s 未知效果 %s" % (_pn, _p["effect"])
    slot_rgb[NG + _k] = _rgb(_p["rgb"])
    slot_eff[NG + _k] = _BEHAVIOR[_p["effect"]]
HUD_TABLES = ("const vec3 HUD_COL[128] = vec3[128](%s);\nconst int HUD_EFF[128] = int[128](%s);"
              % (",".join("vec3(%d,%d,%d)" % c for c in slot_rgb),
                 ",".join(str(e) for e in slot_eff)))
print("样式槽:%d 色 × %d 效果 = %d 网格 + %d 预设" % (NC, NE, NG, len(_presets)))

# 着色器 = 原版 rendertype_text.vsh + globals(GameTime) + HUD 分支
SHADER = r'''#version 330

#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>
#moj_import <minecraft:projection.glsl>
#moj_import <minecraft:sample_lightmap.glsl>
#moj_import <minecraft:globals.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in ivec2 UV2;

uniform sampler2D Sampler2;

out float sphericalVertexDistance;
out float cylindricalVertexDistance;
out vec4 vertexColor;
out vec2 texCoord0;

#define HUD_N 100.0
#define HUD_BIAS 524288.0
#define HUD_STEP 2048.0
#define HUD_STEP_S 262144.0
#define HUD_DYBIAS 64.0
#define HUD_BASE_Y 72.0

@HUD_TABLES@
vec3 hudHue(float h) {
    float r = abs(h*6.0-3.0)-1.0, g = 2.0-abs(h*6.0-2.0), b = 2.0-abs(h*6.0-4.0);
    return clamp(vec3(r,g,b), 0.0, 1.0);
}

void main() {
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);
    sphericalVertexDistance = fog_spherical_distance(Position);
    cylindricalVertexDistance = fog_cylindrical_distance(Position);
    vertexColor = Color * sample_lightmap(Sampler2, UV2);
    texCoord0 = UV0;

    vec3 hudW = vec3(ProjMat[0][3], ProjMat[1][3], ProjMat[2][3]);
    if (dot(hudW, hudW) < 0.25 && Position.x > 300000.0) {
        vec2 vp = vec2(abs(2.0/ProjMat[0][0]), abs(2.0/ProjMat[1][1]));
        float vpxi = floor(vp.x + 0.5);
        float vpyi = floor(vp.y + 0.5);
        ivec3 cc = ivec3(Color.rgb * 255.0 + 0.5);
        bool isShadow = cc.r >= 128;
        int slot = cc.r & 127;
        int effect = HUD_EFF[slot];
        float raw = Position.x - floor(vpxi * 0.5) - HUD_BIAS;
        float sh = floor(raw / HUD_STEP_S);
        float rem1 = raw - sh * HUD_STEP_S;
        float f = floor(rem1 / HUD_STEP);
        float letter = (rem1 - f * HUD_STEP) - HUD_STEP * 0.5;
        float dy = f - HUD_DYBIAS;
        int scaleLo = ((cc.g >> 7) & 1) | (((cc.b >> 7) & 1) << 1);
        int q = scaleLo | (int(sh) << 2);
        float s = (float(q) + 1.0) / 16.0;
        int xq = cc.g & 127;
        int yq = cc.b & 127;
        float t = GameTime * 24000.0;
        vec3 col = HUD_COL[slot] / 255.0;
        if (isShadow) col *= 0.25;
        float alpha = vertexColor.a;
        if (effect == 3) s *= 1.0 + 0.12 * sin(t * 0.35);
        float ax = floor(float(xq) / HUD_N * vpxi + 0.5);
        float ay = floor(float(yq) / HUD_N * vpyi + 0.5);
        float ox = letter * s;
        float oy = dy + (Position.y - vpyi + HUD_BASE_Y) * s;
        if (effect == 1) { oy += 2.0 * sin(t * 0.30 + letter * 0.45); }
        else if (effect == 2) { float seed = floor(t*0.6)+letter;
            ox += (fract(sin(seed)*43758.5453)-0.5)*3.0; oy += (fract(sin(seed+17.3)*43758.5453)-0.5)*3.0; }
        else if (effect == 4) { col = hudHue(fract(t*0.004 + letter*0.02)); }
        else if (effect == 5) { alpha *= 0.65 + 0.35 * sin(t * 0.40); }
        else if (effect == 6) { float a = t*0.9;
            float rx = ox*cos(a)-oy*sin(a); float ry = ox*sin(a)+oy*cos(a); ox = rx; oy = ry; }
        gl_Position = ProjMat * ModelViewMat * vec4(ax + ox, ay + oy, Position.z, 1.0);
        vertexColor = vec4(col, alpha);
    }
}
'''
w(os.path.join(RP, "assets", "minecraft", "shaders", "core", "rendertype_text.vsh"),
  SHADER.replace("@HUD_TABLES@", HUD_TABLES))

# ========== 3. 数据包 ==========
w(os.path.join(DP, "pack.mcmeta"),
  '{"pack":{"pack_format":42,"min_format":84,"max_format":84,'
  '"description":"§bDBCHUD§7 · HUD 组件编码(数据包)"}}')
w(os.path.join(DP, "data", "minecraft", "tags", "function", "load.json"),
  '{"values":["%s:load"]}' % NS)

fn = lambda name, body: w(os.path.join(DP, "data", NS, "function", name), body)

# 十六进制表 00..FF + 名字→槽号(来自 hud_style.json:网格 = 效果行×颜色列;预设 = 网格后追加)
hexlist = ",".join('"%02X"' % i for i in range(256))
palette = ",".join('"%s":%d' % (n, i) for i, (n, _h) in enumerate(_colors))
effects = ",".join('"%s":%d' % (n, i) for i, n in enumerate(_effs))
presets_snbt = ",".join('"%s":%d' % (n, NG + k) for k, (n, _p) in enumerate(_presets))
rulerO_json = ",".join('"%s"' % s for s in RULER_O)
rulerC_json = ",".join('"%s"' % s for s in RULER_C)

# 压测字符池 —— 只放"宽度表高置信"的字符:汉字/CJK标点/全角形(override=9)、谚文(override=8)、
# ASCII(专表)。这批净宽应精确抵消;若内容狂变仍稳,即证明机制本身 OK,剩下的只是符号表不全的问题。
# (刻意不放 ★☆♪→∑αβ 等:0x2600 块和希腊字母不在宽度表里,会漏 → 那是"补表"问题,不是机制问题。)
STRESS_POOL = list("血量经验金币生命魔法攻击防御速度暴击闪避格挡穿透治疗中毒眩晕冰火雷风山水木金土日月星辰龙虎")
STRESS_POOL += list("、。，！？；：「」『』（）【】〈〉《》…—～·")
STRESS_POOL += list("ＡＢＣＤＥＦＧＨＩＪ０１２３４５６７８９")
STRESS_POOL += list("가나다라마바사아자차")
STRESS_POOL += list("ABCDEFGHIJKLabcdefghijkl0123456789 !?.,/:;()[]{}@#%&+-=<>")
STRESS_MAX = len(STRESS_POOL) - 1
pool_json = ",".join('"%s"' % c for c in STRESS_POOL)

# B动态运行时图标表(名字→字面字符;SNBT 里直接放字符,不用 \u 转义)
_icon_map_snbt = ",".join('"%s":"%s"' % (n, c) for n, c in ICON_CHARS.items())

fn("load.mcfunction",
   "# DBCHUD 初始化\n"
   "scoreboard objectives add dbchud.calc dummy\n"
   "scoreboard players set #cw dbchud.calc %d\n" % NC +
   "scoreboard players set #c4 dbchud.calc 4\n"
   "scoreboard players set #cm1 dbchud.calc -1\n"
   "data modify storage dbchud:consts hex set value [%s]\n" % hexlist +
   "data modify storage dbchud:consts palette set value {%s}\n" % palette +
   "data modify storage dbchud:consts effects set value {%s}\n" % effects +
   "data modify storage dbchud:consts presets set value {%s}\n" % presets_snbt +
   "data modify storage dbchud:consts rulerO set value [%s]\n" % rulerO_json +
   "data modify storage dbchud:consts rulerC set value [%s]\n" % rulerC_json +
   "data modify storage dbchud:st pool set value [%s]\n" % pool_json +
   # —— 有状态层:分配 id 的计数器 + 清空所有玩家组件(会话级,不跨重启/重连残留)——
   "scoreboard objectives add dbchud.id dummy\n"
   "# 随机内容压测开关。/function dbchud:stress 切换\n"
   "scoreboard objectives add dbchud.stress dummy\n"
   "scoreboard players set #next dbchud.id 0\n"
   "scoreboard players set #hb dbchud.id 0\n"
   "data modify storage dbchud:data players set value {}\n"
   "# 压测是会话内工具,重载一律归零,防止残留在后台跑\n"
   "scoreboard players reset * dbchud.stress\n" +
   ("data modify storage dbchud:icons map set value {%s}\n" % _icon_map_snbt if ICON_CHARS else "") +
   'tellraw @a {"text":"[DBCHUD] 已加载","color":"aqua"}\n')

# begin:清空构建缓冲(留一个空串当中性父组件)
fn("begin.mcfunction",
   'data modify storage dbchud:build components set value [""]\n')

# encode:{x,y,color,text,effect} → g=x+128,b=y+128,r=idx+效果*16,存入 tmp,再进 _enc2
fn("encode.mcfunction",
   "# 追加一个组件到构建缓冲。参数 {x,y,color,text,effect,scale,align}\n"
   "#   x/y=0~100  color=16色名  effect=none/wave/.../rotate  scale=0.0625~4(支持小数)\n"
   "$data modify storage dbchud:tmp scaleq set value $(scale)\n"
   "execute store result score #q dbchud.calc run data get storage dbchud:tmp scaleq 16\n"
   "scoreboard players remove #q dbchud.calc 1\n"
   "execute if score #q dbchud.calc matches ..-1 run scoreboard players set #q dbchud.calc 0\n"
   "execute if score #q dbchud.calc matches 64.. run scoreboard players set #q dbchud.calc 63\n"
   "scoreboard players operation #sh dbchud.calc = #q dbchud.calc\n"
   "scoreboard players operation #sh dbchud.calc /= #c4 dbchud.calc\n"
   "execute store result storage dbchud:tmp sh int 1 run scoreboard players get #sh dbchud.calc\n"
   "scoreboard players operation #slo dbchud.calc = #sh dbchud.calc\n"
   "scoreboard players operation #slo dbchud.calc *= #c4 dbchud.calc\n"
   "scoreboard players operation #slo dbchud.calc *= #cm1 dbchud.calc\n"
   "scoreboard players operation #slo dbchud.calc += #q dbchud.calc\n"
   "$scoreboard players set #g dbchud.calc $(x)\n"
   "$scoreboard players set #b dbchud.calc $(y)\n"
   "execute if score #slo dbchud.calc matches 1 run scoreboard players add #g dbchud.calc 128\n"
   "execute if score #slo dbchud.calc matches 3 run scoreboard players add #g dbchud.calc 128\n"
   "execute if score #slo dbchud.calc matches 2.. run scoreboard players add #b dbchud.calc 128\n"
   "execute store result storage dbchud:tmp g int 1 run scoreboard players get #g dbchud.calc\n"
   "execute store result storage dbchud:tmp b int 1 run scoreboard players get #b dbchud.calc\n"
   "# color 先按预设名查(hud_style.json 的 presets,命中即为槽号);否则走 颜色×效果 网格\n"
   "data modify storage dbchud:tmp slot set value -1\n"
   '$data modify storage dbchud:tmp slot set from storage dbchud:consts presets."$(color)"\n'
   "execute store result score #sl dbchud.calc run data get storage dbchud:tmp slot\n"
   "data modify storage dbchud:tmp idx set value 15\n"
   '$data modify storage dbchud:tmp idx set from storage dbchud:consts palette."$(color)"\n'
   "data modify storage dbchud:tmp eff set value 0\n"
   '$data modify storage dbchud:tmp eff set from storage dbchud:consts effects."$(effect)"\n'
   "execute store result score #r dbchud.calc run data get storage dbchud:tmp idx\n"
   "execute store result score #e dbchud.calc run data get storage dbchud:tmp eff\n"
   "scoreboard players operation #e dbchud.calc *= #cw dbchud.calc\n"
   "scoreboard players operation #r dbchud.calc += #e dbchud.calc\n"
   "execute if score #sl dbchud.calc matches 0.. run scoreboard players operation #r dbchud.calc = #sl dbchud.calc\n"
   "execute store result storage dbchud:tmp r int 1 run scoreboard players get #r dbchud.calc\n"
   "$data modify storage dbchud:tmp text set value \"$(text)\"\n"
   "$data modify storage dbchud:tmp align set value \"$(align)\"\n"
   "function dbchud:_enc2 with storage dbchud:tmp\n")

# _enc2:{r,g,b,sh,text,align} → 查十六进制串 + 标尺,按 align 分左/居中两种拼法
fn("_enc2.mcfunction",
   "$data modify storage dbchud:tmp rr set from storage dbchud:consts hex[$(r)]\n"
   "$data modify storage dbchud:tmp gg set from storage dbchud:consts hex[$(g)]\n"
   "$data modify storage dbchud:tmp bb set from storage dbchud:consts hex[$(b)]\n"
   "$data modify storage dbchud:tmp open set from storage dbchud:consts rulerO[$(sh)]\n"
   "$data modify storage dbchud:tmp close set from storage dbchud:consts rulerC[$(sh)]\n"
   "# 按 align 分左/中/右\n"
   'execute if data storage dbchud:tmp {align:"center"} run function dbchud:_enc3c with storage dbchud:tmp\n'
   'execute if data storage dbchud:tmp {align:"right"} run function dbchud:_enc3r with storage dbchud:tmp\n'
   'execute unless data storage dbchud:tmp {align:"center"} unless data storage dbchud:tmp {align:"right"} run function dbchud:_enc3 with storage dbchud:tmp\n')

# _enc3:{rr,gg,bb,text} → 拼组件(正文 + 负宽副本)追加进缓冲
#   ["", 标尺推进, {正文 颜色=#RRGGBB 无阴影}, 标尺回退, {正文 负宽字体}]
# _enc3(左对齐):[+push][正文][−push][负宽]
snip = ('["",{"text":"$(open)","font":"%s:hudruler"},'
        '{"text":"$(text)","color":"#$(rr)$(gg)$(bb)","font":"%s:all","shadow_color":0},'
        '{"text":"$(close)","font":"%s:hudruler"},'
        '{"text":"$(text)","font":"%s:allneg"}]') % (NS, NS, NS, NS)
fn("_enc3.mcfunction",
   "$data modify storage dbchud:build components append value %s\n" % snip)

# _enc3c(居中):[+push][半负宽][正文][−push][半负宽] → 正文居中锚点
snipc = ('["",{"text":"$(open)","font":"%s:hudruler"},'
         '{"text":"$(text)","font":"%s:allneghalf"},'
         '{"text":"$(text)","color":"#$(rr)$(gg)$(bb)","font":"%s:all","shadow_color":0},'
         '{"text":"$(close)","font":"%s:hudruler"},'
         '{"text":"$(text)","font":"%s:allneghalf"}]') % (NS, NS, NS, NS, NS)
fn("_enc3c.mcfunction",
   "$data modify storage dbchud:build components append value %s\n" % snipc)

# _enc3r(右对齐):[+push][负宽][正文][−push] → 正文右边缘贴锚点(净宽仍 0)
snipr = ('["",{"text":"$(open)","font":"%s:hudruler"},'
         '{"text":"$(text)","font":"%s:allneg"},'
         '{"text":"$(text)","color":"#$(rr)$(gg)$(bb)","font":"%s:all","shadow_color":0},'
         '{"text":"$(close)","font":"%s:hudruler"}]') % (NS, NS, NS, NS)
fn("_enc3r.mcfunction",
   "$data modify storage dbchud:build components append value %s\n" % snipr)

# flush:把缓冲作为一条 actionbar 发给 @s(须 execute as <玩家> run ... with storage dbchud:build)
fn("flush.mcfunction",
   "# execute as <玩家> run function dbchud:flush with storage dbchud:build\n"
   "$title @s actionbar $(components)\n")

# demo:示例——给自己显示几个带效果的组件
fn("demo.mcfunction",
   "# 示例:给自己(@s)显示几个 HUD 组件(含效果 + 字号)\n"
   "function dbchud:begin\n"
   'function dbchud:encode {x:5,y:85,color:"red",text:"血量 20/20",effect:"none",scale:1,align:"left"}\n'
   'function dbchud:encode {x:72,y:6,color:"yellow",text:"时间 12:00",effect:"none",scale:1,align:"left"}\n'
   'function dbchud:encode {x:50,y:3,color:"white",text:"★ 神经现场 ★",effect:"rainbow",scale:2,align:"center"}\n'
   'function dbchud:encode {x:46,y:45,color:"aqua",text:"警告",effect:"rotate",scale:1,align:"left"}\n'
   'function dbchud:encode {x:40,y:70,color:"green",text:"波浪效果ABC",effect:"wave",scale:1,align:"left"}\n'
   "execute as @s run function dbchud:flush with storage dbchud:build\n")

# ========== 3b. 有状态命名组件层(指令直接 create/set/content/remove,自动渲染)==========
w(os.path.join(DP, "data", "minecraft", "tags", "function", "tick.json"),
  '{"values":["%s:tick"]}' % NS)

# 每 tick:给新玩家分配 session id;每 10 tick 心跳重发所有玩家 HUD(防淡出)
fn("tick.mcfunction",
   "execute as @a unless score @s dbchud.id matches 1.. run function dbchud:_assign\n"
   "scoreboard players add #hb dbchud.id 1\n"
   "execute if score #hb dbchud.id matches 10.. run function dbchud:_heartbeat\n"
   "# 随机内容压测:开了的玩家每 tick 换一次 actionbar 内容\n"
   "execute as @a if score @s dbchud.stress matches 1.. run function dbchud:_stress_gen\n")
fn("_assign.mcfunction",
   "scoreboard players add #next dbchud.id 1\n"
   "scoreboard players operation @s dbchud.id = #next dbchud.id\n")
fn("_heartbeat.mcfunction",
   "scoreboard players set #hb dbchud.id 0\n"
   "execute as @a run function dbchud:_render\n")
fn("_ensure_id.mcfunction",
   "execute unless score @s dbchud.id matches 1.. run function dbchud:_assign\n")

# set:建/改一个命名组件(全字段)。execute as <玩家> run function dbchud:set {...}
fn("set.mcfunction",
   "# execute as <玩家> run function dbchud:set {name,x,y,color,text,effect,scale,align}\n"
   "#   align = left(左) / center(中) / right(右)\n"
   "function dbchud:_ensure_id\n"
   "execute store result storage dbchud:s id int 1 run scoreboard players get @s dbchud.id\n"
   '$data modify storage dbchud:s comp set value {x:$(x),y:$(y),color:"$(color)",text:"$(text)",effect:"$(effect)",scale:$(scale),align:"$(align)"}\n'
   '$data modify storage dbchud:s name set value "$(name)"\n'
   "function dbchud:_set2 with storage dbchud:s\n")

# set_rich:B动态——parts 是"文本片段 + {icon:名字}"混合列表,set 时把图标名解析成字符,再当普通组件建。
#   例:function dbchud:set_rich {name:"hp",parts:["血量 ",{icon:"heart"}," 20/20"],x:5,y:85,color:"red",effect:"none",scale:1,align:"left"}
fn("set_rich.mcfunction",
   "$data modify storage dbchud:rz parts set value $(parts)\n"
   'data modify storage dbchud:rz acc set value ""\n'
   "function dbchud:_rz_loop\n"
   "function dbchud:_ensure_id\n"
   "execute store result storage dbchud:s id int 1 run scoreboard players get @s dbchud.id\n"
   '$data modify storage dbchud:s comp set value {x:$(x),y:$(y),color:"$(color)",effect:"$(effect)",scale:$(scale),align:"$(align)"}\n'
   "data modify storage dbchud:s comp.text set from storage dbchud:rz acc\n"
   '$data modify storage dbchud:s name set value "$(name)"\n'
   "function dbchud:_set2 with storage dbchud:s\n")
fn("_rz_loop.mcfunction",
   "execute if data storage dbchud:rz parts[0] run function dbchud:_rz_one\n")
fn("_rz_one.mcfunction",
   "data modify storage dbchud:rz cur set from storage dbchud:rz parts[0]\n"
   "execute if data storage dbchud:rz cur.icon run function dbchud:_rz_icon\n"          # {icon:名字}
   "execute unless data storage dbchud:rz cur.icon run function dbchud:_rz_text\n"      # 纯文本片段
   "data remove storage dbchud:rz parts[0]\n"
   "function dbchud:_rz_loop\n")
fn("_rz_text.mcfunction",
   "data modify storage dbchud:rzc acc set from storage dbchud:rz acc\n"
   "data modify storage dbchud:rzc add set from storage dbchud:rz cur\n"
   "function dbchud:_rz_cat with storage dbchud:rzc\n")
fn("_rz_icon.mcfunction",
   "data modify storage dbchud:rz name set from storage dbchud:rz cur.icon\n"
   "function dbchud:_rz_icon2 with storage dbchud:rz\n")
fn("_rz_icon2.mcfunction",
   "data modify storage dbchud:rzc acc set from storage dbchud:rz acc\n"
   'data modify storage dbchud:rzc add set value ""\n'
   "$data modify storage dbchud:rzc add set from storage dbchud:icons map.$(name)\n"    # 查表得字符(没有则留空)
   "function dbchud:_rz_cat with storage dbchud:rzc\n")
fn("_rz_cat.mcfunction",
   '$data modify storage dbchud:rz acc set value "$(acc)$(add)"\n')                     # acc = acc + add

# actionbar:代替原版 actionbar 的默认组件(保留名 "actionbar",居中、屏幕下方 ~93%,白色)
fn("actionbar.mcfunction",
   "# execute as <玩家> run function dbchud:actionbar {text}\n"
   "# 固定显示在原版 actionbar 的位置\n"
   "function dbchud:_ensure_id\n"
   "execute store result storage dbchud:s id int 1 run scoreboard players get @s dbchud.id\n"
   '$data modify storage dbchud:s comp set value {native:1b,color:"white",text:"$(text)"}\n'
   'data modify storage dbchud:s name set value "actionbar"\n'
   "function dbchud:_set2 with storage dbchud:s\n")
fn("_set2.mcfunction",
   "$execute unless data storage dbchud:data players.p$(id) run data modify storage dbchud:data players.p$(id) set value {comps:{},order:[]}\n"
   '$execute unless data storage dbchud:data players.p$(id).comps.$(name) run data modify storage dbchud:data players.p$(id).order append value "$(name)"\n'
   "$data modify storage dbchud:data players.p$(id).comps.$(name) set from storage dbchud:s comp\n"
   "function dbchud:_render\n")

# content:只改某组件显示的内容(text)。execute as <玩家> run function dbchud:content {name,text}
fn("content.mcfunction",
   "# execute as <玩家> run function dbchud:content {name,text}\n"
   "function dbchud:_ensure_id\n"
   "execute store result storage dbchud:s id int 1 run scoreboard players get @s dbchud.id\n"
   '$data modify storage dbchud:s name set value "$(name)"\n'
   '$data modify storage dbchud:s text set value "$(text)"\n'
   "function dbchud:_content2 with storage dbchud:s\n")
fn("_content2.mcfunction",
   '$data modify storage dbchud:data players.p$(id).comps.$(name).text set value "$(text)"\n'
   "function dbchud:_render\n")

# remove:删一个命名组件(并从 order 过滤)。execute as <玩家> run function dbchud:remove {name}
fn("remove.mcfunction",
   "# execute as <玩家> run function dbchud:remove {name}\n"
   "function dbchud:_ensure_id\n"
   "execute store result storage dbchud:s id int 1 run scoreboard players get @s dbchud.id\n"
   '$data modify storage dbchud:s name set value "$(name)"\n'
   "function dbchud:_remove2 with storage dbchud:s\n")
fn("_remove2.mcfunction",
   "$data remove storage dbchud:data players.p$(id).comps.$(name)\n"
   "$data modify storage dbchud:flt order set from storage dbchud:data players.p$(id).order\n"
   '$data modify storage dbchud:flt target set value "$(name)"\n'
   "data modify storage dbchud:flt out set value []\n"
   "function dbchud:_filter\n"
   "$data modify storage dbchud:data players.p$(id).order set from storage dbchud:flt out\n"
   "function dbchud:_render\n")
fn("_filter.mcfunction",
   "execute if data storage dbchud:flt order[0] run function dbchud:_filter_one with storage dbchud:flt\n")
fn("_filter_one.mcfunction",
   "data modify storage dbchud:flt head set from storage dbchud:flt order[0]\n"
   '$execute unless data storage dbchud:flt {head:"$(target)"} run data modify storage dbchud:flt out append from storage dbchud:flt head\n'
   "data remove storage dbchud:flt order[0]\n"
   "function dbchud:_filter\n")

# clear:清空某玩家所有组件。execute as <玩家> run function dbchud:clear
fn("clear.mcfunction",
   "# execute as <玩家> run function dbchud:clear\n"
   "function dbchud:_ensure_id\n"
   "execute store result storage dbchud:s id int 1 run scoreboard players get @s dbchud.id\n"
   "function dbchud:_clear2 with storage dbchud:s\n")
fn("_clear2.mcfunction",
   "$data modify storage dbchud:data players.p$(id) set value {comps:{},order:[]}\n"
   "function dbchud:_render\n")

# _render(as @s):清缓冲 → 遍历 @s 的 order 逐个 encode → flush
fn("_render.mcfunction",
   "function dbchud:_ensure_id\n"
   "execute store result storage dbchud:r id int 1 run scoreboard players get @s dbchud.id\n"
   "function dbchud:begin\n"
   "function dbchud:_render2 with storage dbchud:r\n"
   "execute if data storage dbchud:build components[1] run function dbchud:flush with storage dbchud:build\n")
fn("_render2.mcfunction",
   "$data modify storage dbchud:r order set from storage dbchud:data players.p$(id).order\n"
   "$data modify storage dbchud:r idkeep set value $(id)\n"
   "function dbchud:_render_loop\n")
fn("_render_loop.mcfunction",
   "execute if data storage dbchud:r order[0] run function dbchud:_render_one\n")
fn("_render_one.mcfunction",
   # 只把 idkeep+name(都是基本类型)装进干净的 dbchud:fa,避免把带 list 的 r 当宏源
   "data modify storage dbchud:fa idkeep set from storage dbchud:r idkeep\n"
   "data modify storage dbchud:fa name set from storage dbchud:r order[0]\n"
   "function dbchud:_render_fetch with storage dbchud:fa\n"
   "data remove storage dbchud:r order[0]\n"
   "function dbchud:_render_loop\n")
fn("_render_fetch.mcfunction",
   # 组件存到带路径的 cur.comp(storage 的 data modify 必须给路径,不能直接对根 set)
   "data remove storage dbchud:cur comp\n"
   "$data modify storage dbchud:cur comp set from storage dbchud:data players.p$(idkeep).comps.$(name)\n"
   # native 组件:不编码,拼纯文本落原生 actionbar 位置
   "execute if data storage dbchud:cur comp.native run function dbchud:_enc_native with storage dbchud:cur comp\n"
   # 普通组件:有 x(非 native)。with storage 子路径 cur.comp 当宏根,encode 的 $(x)/$(y)... 正好对上
   "execute if data storage dbchud:cur comp.x run function dbchud:encode with storage dbchud:cur comp\n")
# native actionbar:[−W/2][正文 正常色+阴影][−W/2] → 居中、净宽 0(不挤动别的组件)、不 push(不走着色器)
# 靠 actionbar 本身的原生居中+原生 y,正文落在屏幕底部正中,和原版 actionbar 一致
snipn = ('["",{"text":"$(text)","font":"%s:allneghalf"},'
         '{"text":"$(text)","color":"$(color)","font":"%s:all"},'
         '{"text":"$(text)","font":"%s:allneghalf"}]') % (NS, NS, NS)
fn("_enc_native.mcfunction",
   "$data modify storage dbchud:build components append value %s\n" % snipn)

# demo2:有状态示例
fn("demo2.mcfunction",
   "# 有状态示例:给自己(@s)建几个组件(会一直显示,直到 content/remove/clear)\n"
   'execute as @s run function dbchud:set {name:"hp",x:5,y:85,color:"red",text:"血量 20/20",effect:"none",scale:1,align:"left"}\n'
   'execute as @s run function dbchud:set {name:"time",x:95,y:6,color:"yellow",text:"12:00",effect:"none",scale:1,align:"right"}\n'
   'execute as @s run function dbchud:set {name:"title",x:50,y:3,color:"white",text:"★ 神经现场 ★",effect:"rainbow",scale:2,align:"center"}\n'
   'execute as @s run function dbchud:actionbar {text:"这是代替 actionbar 的默认组件"}\n'
   '# 改血量:      execute as @s run function dbchud:content {name:"hp",text:"血量 15/20"}\n'
   '# 改 actionbar:execute as @s run function dbchud:content {name:"actionbar",text:"你捡到了 金锭 x3"}\n'
   '# 删标题:      execute as @s run function dbchud:remove {name:"title"}\n'
   "# 全清:        execute as @s run function dbchud:clear\n")

# —— 随机内容压测:每 tick 给 actionbar 塞随机字符串(汉字+各种符号),看内容变化会不会让 HUD 偏移 ——
fn("stress.mcfunction",
   "# execute as <玩家> run function dbchud:stress —— 开/关随机 actionbar 压测(每 tick 变一次)\n"
   "# 建议先 /function dbchud:demo2 摆好其它组件,再开压测,盯着 hp/time/title 会不会跟着动。\n"
   "execute unless score @s dbchud.stress matches -2147483648.. run scoreboard players set @s dbchud.stress 0\n"
   "scoreboard players operation #o dbchud.calc = @s dbchud.stress\n"
   "execute if score #o dbchud.calc matches 1.. run scoreboard players set @s dbchud.stress 0\n"
   "execute if score #o dbchud.calc matches ..0 run scoreboard players set @s dbchud.stress 1\n"
   'execute if score @s dbchud.stress matches 1.. run tellraw @s {"text":"[DBCHUD] 随机 actionbar 压测 = 开(每 tick 变)","color":"green"}\n'
   'execute if score @s dbchud.stress matches ..0 run tellraw @s {"text":"[DBCHUD] 随机 actionbar 压测 = 关","color":"yellow"}\n')
fn("_stress_gen.mcfunction",
   'data modify storage dbchud:st acc set value ""\n'
   "execute store result score #n dbchud.calc run random value 1..12\n"
   "function dbchud:_stress_loop\n"
   "function dbchud:_stress_apply\n")
fn("_stress_loop.mcfunction",
   "execute if score #n dbchud.calc matches 1.. run function dbchud:_stress_pick\n")
fn("_stress_pick.mcfunction",
   "execute store result score #i dbchud.calc run random value 0..%d\n" % STRESS_MAX +
   "execute store result storage dbchud:st idx int 1 run scoreboard players get #i dbchud.calc\n"
   "function dbchud:_stress_getch with storage dbchud:st\n"
   "function dbchud:_stress_cat with storage dbchud:st\n"
   "scoreboard players remove #n dbchud.calc 1\n"
   "function dbchud:_stress_loop\n")
fn("_stress_getch.mcfunction",
   "$data modify storage dbchud:st ch set from storage dbchud:st pool[$(idx)]\n")
fn("_stress_cat.mcfunction",
   '$data modify storage dbchud:st acc set value "$(acc)$(ch)"\n')
fn("_stress_apply.mcfunction",
   "function dbchud:_ensure_id\n"
   "execute store result storage dbchud:s id int 1 run scoreboard players get @s dbchud.id\n"
   'data modify storage dbchud:s comp set value {native:1b,color:"white"}\n'
   "data modify storage dbchud:s comp.text set from storage dbchud:st acc\n"
   'data modify storage dbchud:s name set value "actionbar"\n'
   "function dbchud:_set2 with storage dbchud:s\n")


print("生成完成(负宽由 negfont 从 vanilla 精确出)。产物在:", OUT)
print("  ", os.path.basename(RP), "→ 拷进 .minecraft/resourcepacks/")
print("  ", os.path.basename(DP), "→ 拷进 存档/datapacks/")
