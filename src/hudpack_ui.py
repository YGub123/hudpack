# -*- coding: utf-8 -*-
"""HUDPack 图形界面 —— MC 像素风(照 baketool McKit 的思路):
压暗泥土平铺背景 / 石灰面板(背包 GUI 斜面)/ 物品槽网格 / 石质按钮(黑描边+斜面+白字硬阴影)/
文字用 MC 原版字形(ascii.png + unifont,与游戏同源,见 mcfont.py)。
纯标准库 tkinter。开发:python src/hudpack_ui.py;成品:hudpack.exe。"""
import os, sys, io, json, shutil, threading, subprocess, runpy, contextlib, traceback
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

# ---------- 路径:exe(frozen)→ exe 所在目录;开发 → src/ 的上一级 ----------
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    BASE = os.path.dirname(os.path.abspath(sys.executable))
    BUILD_SCRIPT = os.path.join(sys._MEIPASS, "build.py")
else:
    _here = os.path.dirname(os.path.abspath(__file__))
    BASE = os.path.dirname(_here) if os.path.basename(_here).lower() == "src" else _here
    BUILD_SCRIPT = os.path.join(_here, "build.py")
    sys.path.insert(0, _here)
import iconpack, mcfont, vanilla_setup

ICONS   = os.path.join(BASE, "icons")
OUT     = os.path.join(BASE, "out")
REG     = os.path.join(ICONS, "registry.json")
VANILLA = os.path.join(BASE, "vanilla")

# ---------- MC 配色(取自 McKit) ----------
PANEL   = "#C6C6C6"   # 石灰面板
PANEL_L = "#FFFFFF"   # 斜面亮
PANEL_D = "#555555"   # 斜面暗
OUTLINE = "#1B1B1B"   # 黑描边
SLOT    = "#8B8B8B"   # 槽位底
SLOT_D  = "#373737"   # 槽位暗边(左上)
BTN     = "#9C9C9C"; BTN_H = "#AEAEAE"; BTN_T = "#C8C8C8"; BTN_B = "#5E5E5E"
ORG     = "#CF7E33"; ORG_H = "#E59346"; ORG_T = "#F2B368"; ORG_B = "#7C4416"
INK     = "#3F3F3F"   # 灰面板上的深色字
CREAM   = "#F2E6C8"   # 标题米黄
DIRTS   = ["#3A2C1E", "#33261A", "#413324", "#2C2015", "#372A1C"]

MC = mcfont.McFont(VANILLA)
FALLBACK = ("Microsoft YaHei UI", 10, "bold")

def ensure_vanilla(root):
    """vanilla/ 不全时引导用户从自己的客户端 jar 提取(发布包不带 Mojang 资产)。"""
    if vanilla_setup.is_complete(VANILLA):
        return True
    messagebox.showinfo(
        "首次使用",
        "需要从你的 Minecraft 客户端提取字体素材(只做一次,全程离线)。\n\n"
        "下一步请选择原版客户端 jar,一般在:\n.minecraft/versions/26.1.2/26.1.2.jar",
        parent=root)
    while True:
        jar = filedialog.askopenfilename(
            title="选择 Minecraft 客户端 jar(如 26.1.2.jar)",
            initialdir=vanilla_setup.guess_versions_dir(),
            filetypes=[("Minecraft 客户端 jar", "*.jar")], parent=root)
        if not jar:
            messagebox.showwarning(
                "先跳过", "未配置字体素材:界面能用,但『开始构建』会失败。\n重开程序会再次引导。",
                parent=root)
            return False
        try:
            probs = vanilla_setup.setup_from_jar(VANILLA, jar, log=lambda s: None)
        except Exception as ex:
            probs = [str(ex)]
        if not probs:
            global MC
            MC = mcfont.McFont(VANILLA)          # 素材就位,切换到 MC 原版字形
            messagebox.showinfo("完成", "字体素材配置完成!", parent=root)
            return True
        messagebox.showerror("有问题", "\n".join(probs), parent=root)

def px_img(text, z=2, color="#ffffff", shadow="#3e3e3e"):
    return MC.render(text, z, color, shadow) if MC.available else None

class PxLabel(tk.Label):
    """MC 点阵字标签(素材缺失时回退系统字体)。"""
    def __init__(self, master, text, z=2, color="#ffffff", shadow="#3e3e3e", bg=PANEL):
        img = px_img(text, z, color, shadow)
        if img is not None:
            super().__init__(master, image=img, bg=bg, bd=0)
            self._img = img
        else:
            super().__init__(master, text=text, bg=bg, fg=color, font=FALLBACK, bd=0)
        self._z, self._sh = z, shadow

    def set(self, text, color=None):
        img = px_img(text, self._z, color or "#ffffff", self._sh)
        if img is not None:
            self.config(image=img)
            self._img = img
        else:
            self.config(text=text, fg=color or "#ffffff")

# ---------- MC 石质按钮(黑描边 + 斜面 + 白字硬阴影,悬停黄字,按下下沉) ----------
class McBtn(tk.Canvas):
    def __init__(self, master, text, cmd, primary=False, z=2, minw=0, bg=PANEL):
        self.text, self.z, self.primary, self.cmd = text, z, primary, cmd
        tw = MC.measure(text, z) if MC.available else 10 * len(text)
        self.W = max(minw, tw + 14 * z)
        self.H = 8 * z + 7 * z
        super().__init__(master, width=self.W, height=self.H, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.state = "n"
        self._draw()
        self.bind("<Enter>", lambda e: self._set("h"))
        self.bind("<Leave>", lambda e: self._set("n"))
        self.bind("<Button-1>", lambda e: self._set("p"))
        self.bind("<ButtonRelease-1>", self._click)

    def _set(self, s):
        self.state = s
        self._draw()

    def _click(self, e):
        inside = 0 <= e.x < self.W and 0 <= e.y < self.H
        self._set("h" if inside else "n")
        if inside:
            self.cmd()

    def _draw(self):
        self.delete("all")
        base = (ORG_H if self.state == "h" else ORG) if self.primary else (BTN_H if self.state == "h" else BTN)
        top = ORG_T if self.primary else BTN_T
        bot = ORG_B if self.primary else BTN_B
        W, H = self.W, self.H
        self.create_rectangle(0, 0, W, H, fill=OUTLINE, width=0)
        self.create_rectangle(2, 2, W - 2, H - 2, fill=base, width=0)
        self.create_rectangle(2, 2, W - 2, 4, fill=top, width=0)
        self.create_rectangle(2, H - 4, W - 2, H - 2, fill=bot, width=0)
        off = 1 if self.state == "p" else 0
        col = "#FFFFA0" if self.state == "h" else "#FFFFFF"
        sh = ORG_B if self.primary else "#3A3A3A"
        img = px_img(self.text, self.z, col, sh)
        if img is not None:
            self.create_image(W // 2 + off, H // 2 + off, image=img)
            self._img = img
        else:
            self.create_text(W // 2 + off, H // 2 + off, text=self.text, fill=col, font=FALLBACK)

# ---------- 泥土画布 ----------
def dirt_tile(px=3):
    img = tk.PhotoImage(width=16 * px, height=16 * px)
    for y in range(16):
        for x in range(16):
            h = ((x * 73856093) ^ (y * 19349663) ^ (x * y * 83492791)) & 0x7fffffff
            img.put(DIRTS[h % len(DIRTS)], to=(x * px, y * px, (x + 1) * px, (y + 1) * px))
    return img

def logo_img(px=3):
    m = ["                ", " ############## ", " #............# ", " #.cc......cc.# ",
         " #.c........c.# ", " #............# ", " #.....ww.....# ", " #....w..w....# ",
         " #.rr.rr......# ", " #.rrrrr.yyy..# ", " #..rrr..yyy..# ", " #...r........# ",
         " #.gggggggg...# ", " #.c........c.# ", " #.cc......cc.# ", " ############## "]
    c = {"#": "#3a3d42", ".": "#141518", "c": "#45c4e8", "r": "#e05555",
         "g": "#4caf50", "y": "#e6b422", "w": "#f2f2f2"}
    img = tk.PhotoImage(width=16 * px, height=16 * px)
    for y, row in enumerate(m):
        for x, ch in enumerate(row):
            if ch != " ":
                img.put(c[ch], to=(x * px, y * px, (x + 1) * px, (y + 1) * px))
    return img

# ---------- 物品槽(凹陷斜面) ----------
class Slot(tk.Canvas):
    SZ = 44
    def __init__(self, master, name, thumb, on_pick):
        super().__init__(master, width=self.SZ, height=self.SZ, bg=SLOT,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.name, self.thumb, self.on_pick = name, thumb, on_pick
        self.selected = False
        self.hover = False
        self._draw()
        self.bind("<Enter>", lambda e: self._h(True))
        self.bind("<Leave>", lambda e: self._h(False))
        self.bind("<Button-1>", lambda e: on_pick(self.name))

    def _h(self, v):
        self.hover = v
        self._draw()

    def mark(self, sel):
        self.selected = sel
        self._draw()

    def _draw(self):
        self.delete("all")
        s = self.SZ
        fill = "#A6A6A6" if (self.hover or self.selected) else SLOT
        self.create_rectangle(0, 0, s, s, fill=fill, width=0)
        self.create_rectangle(0, 0, s, 2, fill=SLOT_D, width=0)
        self.create_rectangle(0, 0, 2, s, fill=SLOT_D, width=0)
        self.create_rectangle(0, s - 2, s, s, fill="#FFFFFF", width=0)
        self.create_rectangle(s - 2, 0, s, s, fill="#FFFFFF", width=0)
        if self.thumb is not None:
            self.create_image(s // 2, s // 2, image=self.thumb)
        if self.selected:
            self.create_rectangle(2, 2, s - 2, s - 2, outline="#FFFFFF", width=2)

# ---------- registry ----------
def load_rows():
    if not os.path.isfile(REG):
        return []
    reg = json.load(open(REG, encoding="utf-8"))
    rows = []
    for name, e in reg.get("icons", {}).items():
        if not e.get("missing"):
            rows.append((name, e["cp"], iconpack.esc(int(e["cp"], 16)), e["file"]))
    return sorted(rows, key=lambda r: r[1])


class UI:
    def __init__(self, root):
        self.root = root
        root.title("HUDPack")
        w, h = 880, 680
        x = max(0, (root.winfo_screenwidth() - w) // 2)
        y = max(0, (root.winfo_screenheight() - h) // 2 - 20)   # 略偏上,视觉居中
        root.geometry("%dx%d+%d+%d" % (w, h, x, y))
        root.minsize(760, 580)
        self._imgs = []           # PhotoImage 防回收
        self.sel = None           # 选中的图标名
        self.slots = {}

        # 泥土画布打底,面板浮在上面
        self.cv = tk.Canvas(root, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.tile = dirt_tile()
        self.logo = logo_img()
        self._title = px_img("HUDPack", 4, CREAM, "#1a1a1a")
        self._sub = px_img("DBCHUD 构建 · 图标管理与查表", 2, "#B8B8B8", "#1a1a1a")

        self._panel()
        self.cv.bind("<Configure>", self._relayout)
        self.refresh()
        self.set_status("就绪 —— 丢图 → 构建 → 拷进 MC", INK)

    # ---- 泥土 + 顶部题字 + 面板窗口 ----
    def _relayout(self, e=None):
        w = self.cv.winfo_width(); h = self.cv.winfo_height()
        self.cv.delete("bg")
        tw = self.tile.width()
        for y in range(0, h, tw):
            for x in range(0, w, tw):
                self.cv.create_image(x, y, image=self.tile, anchor="nw", tags="bg")
        self.cv.tag_lower("bg")
        self.cv.delete("head")
        self.cv.create_image(22, 14, image=self.logo, anchor="nw", tags="head")
        if self._title is not None:
            self.cv.create_image(84, 14, image=self._title, anchor="nw", tags="head")
            self.cv.create_image(86, 52, image=self._sub, anchor="nw", tags="head")
        if not hasattr(self, "_win"):
            return
        top = 84
        self.cv.coords(self._win, 14, top)
        self.cv.itemconfigure(self._win, width=w - 28, height=h - top - 12)

    def _panel(self):
        # 黑描边 + 石灰面板(raised 斜面),即 McPanel
        outer = tk.Frame(self.cv, bg=OUTLINE)
        inner = tk.Frame(outer, bg=PANEL, bd=3, relief="raised")
        inner.pack(fill="both", expand=True, padx=2, pady=2)
        self._win = self.cv.create_window(14, 84, window=outer, anchor="nw")

        # 工具行:搜索(黑底 MC 输入框) + 图标操作按钮
        bar = tk.Frame(inner, bg=PANEL)
        bar.pack(fill="x", padx=12, pady=(12, 6))
        PxLabel(bar, "搜索", 2, INK, None).pack(side="left")
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *a: self.refresh())
        ent = tk.Entry(bar, textvariable=self.search, bg="#000000", fg="#E8E8E8",
                       insertbackground="#FFFFFF", relief="flat",
                       highlightthickness=1, highlightbackground="#A0A0A0",
                       highlightcolor="#FFFFFF", font=("Consolas", 11))
        ent.pack(side="left", fill="x", expand=True, padx=(8, 10), ipady=4)
        McBtn(bar, "添加图标", self.add_icons).pack(side="left", padx=2)
        McBtn(bar, "重命名", self.rename_icon).pack(side="left", padx=2)
        McBtn(bar, "删除", self.remove_icon).pack(side="left", padx=2)
        McBtn(bar, "码点管理", self.cp_manager).pack(side="left", padx=2)

        # 槽位网格(可滚)
        gridwrap = tk.Frame(inner, bg=PANEL)
        gridwrap.pack(fill="both", expand=True, padx=12)
        self.gcv = tk.Canvas(gridwrap, bg=PANEL, highlightthickness=0, bd=0, height=150)
        sb = tk.Scrollbar(gridwrap, orient="vertical", command=self.gcv.yview)
        self.gcv.configure(yscrollcommand=sb.set)
        self.gcv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.grid = tk.Frame(self.gcv, bg=PANEL)
        self.gcv.create_window(0, 0, window=self.grid, anchor="nw")
        self.grid.bind("<Configure>", lambda e: self._sync_scroll())
        self.gcv.bind("<Configure>", lambda e: (self._regrid(), self._sync_scroll()))
        self.gcv.bind_all("<MouseWheel>", self._wheel)

        # 详情条(凹陷槽):预览 + 名字/码点/转义 + 复制
        det = tk.Frame(inner, bg=SLOT, bd=2, relief="sunken")
        det.pack(fill="x", padx=12, pady=(8, 6))
        self.prev = tk.Canvas(det, width=40, height=40, bg=SLOT, highlightthickness=0)
        self.prev.pack(side="left", padx=(10, 8), pady=6)
        dd = tk.Frame(det, bg=SLOT)
        dd.pack(side="left", fill="x", expand=True, pady=6)
        self.d_name = PxLabel(dd, "(未选中图标 —— 点上面的格子)", 2, "#EFEFEF", "#3a3a3a", bg=SLOT)
        self.d_name.pack(anchor="w")
        self.d_info = PxLabel(dd, "", 2, "#D8D8D8", "#3a3a3a", bg=SLOT)
        self.d_info.pack(anchor="w", pady=(3, 0))
        bcol = tk.Frame(det, bg=SLOT)
        bcol.pack(side="right", padx=10)
        McBtn(bcol, "复制转义符", lambda: self.copy(2), bg=SLOT).pack(pady=2)
        McBtn(bcol, "复制名字", lambda: self.copy(0), bg=SLOT).pack(pady=2)

        # 主操作行:构建(橙色主按钮) + 打开文件夹 + 状态
        act = tk.Frame(inner, bg=PANEL)
        act.pack(fill="x", padx=12, pady=(2, 6))
        McBtn(act, "开 始 构 建", self.build, primary=True, minw=170).pack(side="left")
        McBtn(act, "取成品包(拷进MC)", lambda: self.open_folder(OUT)).pack(side="left", padx=6)
        McBtn(act, "打开图标库", lambda: self.open_folder(ICONS)).pack(side="left")
        self.status = PxLabel(act, "", 2, INK, None)
        self.status.pack(side="right")

        # 日志(黑底,像聊天栏)
        logwrap = tk.Frame(inner, bg=OUTLINE, bd=2, relief="sunken")
        logwrap.pack(fill="x", padx=12, pady=(0, 12))
        self.log = tk.Text(logwrap, height=6, bg="#101010", fg="#E0E0E0", relief="flat",
                           font=("Consolas", 9), insertbackground="#FFFFFF", wrap="word")
        self.log.pack(fill="both", expand=True, padx=1, pady=1)
        self.log.tag_configure("ok", foreground="#6FE26F")
        self.log.tag_configure("err", foreground="#FF7A7A")
        self.log.tag_configure("mut", foreground="#9A9A9A")
        self.logline("HUDPack 就绪。图标丢进 icons/(或点『添加图标』)→『开始构建』→ out/ 拷进 MC。", "mut")

    # ---- 槽位网格 ----
    def refresh(self):
        for w in self.grid.winfo_children():
            w.destroy()
        self.slots.clear()
        self._imgs.clear()
        q = self.search.get().strip().lower() if hasattr(self, "search") else ""
        self.rows = {}
        for name, cp, esc, file in load_rows():
            if q and q not in name.lower() and q not in cp.lower():
                continue
            self.rows[name] = (name, cp, esc, file)
            t = self._thumb(os.path.join(ICONS, *file.split("/")))
            s = Slot(self.grid, name, t, self.pick)
            self.slots[name] = s
        self._regrid()
        if self.sel in self.slots:
            self.slots[self.sel].mark(True)
        elif self.slots:
            self.pick(next(iter(self.slots)))

    def _sync_scroll(self):
        # 内容不足一屏:滚动区收紧 + 归位,滚轮/滚动条都不再能把内容推出空白
        self.gcv.configure(scrollregion=self.gcv.bbox("all") or (0, 0, 0, 0))
        b = self.gcv.bbox("all")
        if not b or b[3] - b[1] <= self.gcv.winfo_height():
            self.gcv.yview_moveto(0)

    def _wheel(self, e):
        lo, hi = self.gcv.yview()
        if hi - lo >= 1.0:            # 全部可见,不滚
            return
        self.gcv.yview_scroll(-e.delta // 120, "units")

    def _regrid(self):
        w = max(self.gcv.winfo_width(), 200)
        cols = max(1, (w - 8) // (Slot.SZ + 6))
        for i, s in enumerate(self.slots.values()):
            s.grid_configure(row=i // cols, column=i % cols, padx=3, pady=3) if s.winfo_manager() \
                else s.grid(row=i // cols, column=i % cols, padx=3, pady=3)

    def _thumb(self, path, big=False):
        try:
            img = tk.PhotoImage(file=path)
            w = img.width()
            lim = 32 if big else 28
            if w * 4 <= lim:   img = img.zoom(4)
            elif w * 3 <= lim: img = img.zoom(3)
            elif w * 2 <= lim: img = img.zoom(2)
            elif w > lim:      img = img.subsample(max(1, -(-w // lim)))
            self._imgs.append(img)
            return img
        except Exception:
            return None

    def pick(self, name):
        if self.sel in self.slots:
            self.slots[self.sel].mark(False)
        self.sel = name
        if name in self.slots:
            self.slots[name].mark(True)
        name_, cp, esc, file = self.rows[name]
        folder = file.rsplit("/", 1)[0] + "/" if "/" in file else ""
        self.d_name.set(name_ + ("    (%s)" % folder if folder else ""))
        self.d_info.set("U+%s    %s" % (cp, esc))
        self.prev.delete("all")
        t = self._thumb(os.path.join(ICONS, *file.split("/")), big=True)
        if t is not None:
            self.prev.create_image(20, 20, image=t)

    def copy(self, col):
        if self.sel not in self.rows:
            return self.set_status("先选一个图标", "#8B2525")
        v = self.rows[self.sel][col]
        self.root.clipboard_clear()
        self.root.clipboard_append(v)
        self.root.update()
        self.set_status("已复制: " + v, "#1E5A74")

    # ---- 图标增删改 ----
    def add_icons(self):
        files = filedialog.askopenfilenames(title="选 PNG 图标(可多选)", filetypes=[("PNG", "*.png")])
        last = None
        for f in files:
            default = os.path.splitext(os.path.basename(f))[0]
            path = simpledialog.askstring(
                "图标名字", "给 %s 起名(写 ui/heart 可放进子文件夹整理,名字取最后一段):" % os.path.basename(f),
                initialvalue=default, parent=self.root)
            if not path:
                continue
            dst = os.path.join(ICONS, *(path + ".png").split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(f, dst)
            last = path.rsplit("/", 1)[-1]           # 身份 = 短名(不含路径)
            self.logline("已添加 %s" % last)
        if last is not None:
            _, warns = iconpack.scan(ICONS, verbose=False)   # 立即登记(分配码点),不等构建
            for w_ in warns:
                self.logline(w_, "err")
            self.sel = last
            self.refresh()
            self.set_status("已添加并登记,记得『开始构建』让它进包", "#7A5A1E")

    def rename_icon(self):
        if self.sel not in self.rows:
            return self.set_status("先选一个图标", "#8B2525")
        old = self.sel
        new = simpledialog.askstring("重命名", "把 '%s' 改成(码点不变,文件留在原文件夹):" % old,
                                     initialvalue=old, parent=self.root)
        if not new or new == old:
            return
        try:
            iconpack.rename(ICONS, old, new)
            self.sel = new
            self.logline("重命名 %s → %s(码点不变),点『开始构建』刷新" % (old, new))
            self.refresh()
        except Exception as ex:
            messagebox.showerror("重命名失败", str(ex), parent=self.root)

    def remove_icon(self):
        if self.sel not in self.rows:
            return self.set_status("先选一个图标", "#8B2525")
        name = self.sel
        reg = json.load(open(REG, encoding="utf-8"))
        e = reg["icons"].get(name)
        if e is None:
            return
        built = e.get("built", True)
        if built:
            msg = ("删除图标 '%s'?\n\n它已进过构建,码点 U+%s 将保留占位(防旧引用串位)。\n"
                   "以后可在『码点管理』里手动释放。") % (name, e["cp"])
        else:
            msg = ("删除图标 '%s'?\n\n它还没进过任何构建,码点 U+%s 会直接回收复用。") % (name, e["cp"])
        if not messagebox.askyesno("删除", msg, parent=self.root):
            return
        p = os.path.join(ICONS, *e["file"].split("/"))
        if os.path.isfile(p):
            os.remove(p)
        self.sel = None
        if built:
            iconpack.scan(ICONS, verbose=False)      # 标记 missing,占位保留
            self.logline("已删除 %s,码点 U+%s 保留占位(『码点管理』可释放)" % (name, e["cp"]))
        else:
            iconpack.discard(ICONS, name)            # 未转正 → 直接回收进复用池
            self.logline("已删除 %s,码点 U+%s 已回收复用" % (name, e["cp"]))
        self.refresh()

    # ---- 码点管理:列出失效占位(已删除但码点保留的),可确认后释放进复用池 ----
    def cp_manager(self):
        win = tk.Toplevel(self.root)
        win.title("码点管理")
        win.configure(bg=PANEL)
        ww, wh = 460, 360
        wx = self.root.winfo_x() + (self.root.winfo_width() - ww) // 2
        wy = self.root.winfo_y() + (self.root.winfo_height() - wh) // 2
        win.geometry("%dx%d+%d+%d" % (ww, wh, max(0, wx), max(0, wy)))
        win.transient(self.root)
        PxLabel(win, "失效码点(图标已删,编号保留占位)", 2, INK, None).pack(anchor="w", padx=14, pady=(12, 2))
        PxLabel(win, "释放 = 编号交还复用池,之后可能分给新图标。", 2, "#6A6A6A", None).pack(anchor="w", padx=14)
        lst = tk.Frame(win, bg=SLOT, bd=2, relief="sunken")
        lst.pack(fill="both", expand=True, padx=14, pady=8)
        self._free_lbl = PxLabel(win, "", 2, INK, None)
        self._free_lbl.pack(anchor="w", padx=14, pady=(0, 4))
        McBtn(win, "关 闭", win.destroy).pack(pady=(0, 12))

        def reload_list():
            for w in lst.winfo_children():
                w.destroy()
            reg = json.load(open(REG, encoding="utf-8")) if os.path.isfile(REG) else {"icons": {}, "free": []}
            dead = sorted(((n, e) for n, e in reg.get("icons", {}).items() if e.get("missing")),
                          key=lambda kv: kv[1]["cp"])
            free = sorted(reg.get("free", []))
            self._free_lbl.set("可复用池: " + (" ".join("U+" + c for c in free) if free else "(空)"), INK)
            if not dead:
                PxLabel(lst, "没有失效码点。", 2, "#EFEFEF", "#3a3a3a", bg=SLOT).pack(pady=18)
                return
            for n, e in dead:
                row = tk.Frame(lst, bg=SLOT)
                row.pack(fill="x", padx=8, pady=3)
                PxLabel(row, "U+%s  %s" % (e["cp"], n), 2, "#EFEFEF", "#3a3a3a", bg=SLOT).pack(side="left")
                McBtn(row, "释放", lambda n=n, e=e: do_release(n, e), bg=SLOT).pack(side="right")

        def do_release(n, e):
            if not messagebox.askyesno(
                    "释放码点",
                    "释放 U+%s('%s')?\n\n释放后这个编号会分配给以后的新图标;\n"
                    "如果地图/指令里还留有它的旧引用,旧引用会显示成那张新图。\n"
                    "确定没有残留引用了吗?" % (e["cp"], n),
                    parent=win):
                return
            iconpack.discard(ICONS, n)
            self.logline("已释放码点 U+%s(原 %s)→ 进复用池" % (e["cp"], n))
            reload_list()
            self.refresh()

        reload_list()

    # ---- 构建 ----
    def build(self):
        if not vanilla_setup.is_complete(VANILLA):   # 首次引导被跳过时,这里再补
            if not ensure_vanilla(self.root):
                return self.set_status("缺字体素材,无法构建", "#8B2525")
        self.set_status("构建中……", "#7A5A1E")
        self.log.delete("1.0", "end")
        self.logline("$ build", "mut")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        buf = io.StringIO()
        code = 0
        try:
            os.environ["HUDPACK_HOME"] = BASE
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                runpy.run_path(BUILD_SCRIPT, run_name="__main__")
        except SystemExit as e:
            code = int(e.code or 0)
        except Exception:
            buf.write(traceback.format_exc())
            code = 1
        self.root.after(0, lambda: self._done(buf.getvalue(), code))

    def _done(self, out, code):
        if out.strip():
            self.logline(out.strip())
        if code == 0:
            self.logline("构建完成 —— out/ 里两个包拷进 MC(资源包 F3+T,数据包 /reload)", "ok")
            self.set_status("构建完成", "#2F6B2F")
        else:
            self.logline("构建出错(见上)", "err")
            self.set_status("构建出错", "#8B2525")
        self.refresh()

    # ---- 杂项 ----
    def set_status(self, text, color=INK):
        self.status.set(text, color)

    def logline(self, s, tag=None):
        self.log.insert("end", s + "\n", tag or ())
        self.log.see("end")

    def open_folder(self, path):
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])


def main():
    if "--check" in sys.argv:
        io.open(os.path.join(BASE, "hudpack_check.txt"), "w", encoding="utf-8").write(
            "ok base=%s frozen=%s icons=%d mcfont=%s\n" % (BASE, FROZEN, len(load_rows()), MC.available))
        return
    if "--build" in sys.argv:
        buf = io.StringIO()
        code = 0
        try:
            os.environ["HUDPACK_HOME"] = BASE
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                runpy.run_path(BUILD_SCRIPT, run_name="__main__")
        except SystemExit as e:
            code = int(e.code or 0)
        except Exception:
            buf.write(traceback.format_exc())
            code = 1
        io.open(os.path.join(BASE, "hudpack_check.txt"), "w", encoding="utf-8").write(
            ("BUILD OK\n" if code == 0 else "BUILD FAIL\n") + buf.getvalue())
        sys.exit(code)
    root = tk.Tk()
    root.withdraw()                    # 先隐藏,引导完再现身(避免半成品窗口)
    ensure_vanilla(root)
    UI(root)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
