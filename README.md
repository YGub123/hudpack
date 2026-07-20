# HUDPack

给 Minecraft（26.1，Java 版）做**自定义屏幕 HUD** 的工具：血条、任务栏、标题、图标……
想显示什么、显示在哪，全用指令控制。不需要客户端 mod，玩家只要装一个资源包。

**下载**：到 [Releases](../../releases) 下载 `HUDPack.zip`（解压即用，含 exe）；
或克隆仓库后运行 `python src/hudpack_ui.py`（纯标准库，无需 pip）。

## 快速上手（三步）

**1. 双击 `hudpack.exe`，点「开始构建」。**
> 第一次打开会请你选一下自己的 Minecraft 客户端 jar（一般在
> `.minecraft/versions/26.1.2/26.1.2.jar`），工具从里面提取字体素材，只做一次。

**2. 装进游戏：**
- 点「取成品包（拷进MC）」打开产物文件夹；
- `dbchud_resourcepack` 拷到 `.minecraft/resourcepacks/`，进游戏启用它，按 F3+T；
- `dbchud_datapack` 拷到存档的 `datapacks/` 文件夹，游戏里输 `/reload`。

**3. 游戏里试一下：**
```
/function dbchud:demo2
```
屏幕上出现几个示例组件，就说明装好了。

## 指令一览

每个组件有个名字（比如 hp），建了之后随时按名字改内容、删除。给谁显示就 `execute as 谁`。

**建组件 / 整个替换**（七个参数都要写）：
```
execute as @s run function dbchud:set {name:"hp",x:5,y:85,color:"red",text:"血量 20/20",effect:"none",scale:1,align:"left"}
```
| 参数 | 意思 |
|---|---|
| name | 组件名字，之后改内容、删除都用它 |
| x， y | 屏幕位置，百分比，左上角是 0，0 |
| color | 颜色：16 个原版颜色名（red、gold、aqua、white……），或你在 hud_style.json 里定义的样式名（见「自定义颜色样式」） |
| text | 显示的文字 |
| effect | 动效：none 无 / wave 波浪 / shake 抖动 / pulse 缩放 / rainbow 彩虹 / blink 闪烁 / rotate 旋转 |
| scale | 字号倍数，支持小数（比如 1.5） |
| align | 对齐：left 左 / center 中 / right 右（锚在 x 的哪一侧） |

**只改文字**（位置样式不动，最常用）：
```
execute as @s run function dbchud:content {name:"hp",text:"血量 15/20"}
```

**删一个 / 全清：**
```
execute as @s run function dbchud:remove {name:"hp"}
execute as @s run function dbchud:clear
```

**替代原版 actionbar**（固定显示在原版 actionbar 的位置，名字固定叫 actionbar）：
```
execute as @s run function dbchud:actionbar {text:"你捡到了 金锭 x3"}
```

**带图标的组件**（图标按名字写，见下一节）：
```
execute as @s run function dbchud:set_rich {name:"hp",parts:["血量 ",{icon:"heart"}," 20"],x:5,y:85,color:"red",effect:"none",scale:1,align:"left"}
```

**自测工具：**
- `/function dbchud:demo2` 摆几个示例组件；
- `/function dbchud:stress` 开/关压力测试（actionbar 每刻换随机字，用来检查其它组件会不会被挤动；重载后自动关）。

注意：组件是"会话级"的——服务器重启或 `/reload` 后清空，由你的命令系统按需重建。

## 用图片当图标

1. 界面里点「添加图标」选 PNG（透明底），起个名字；
2. 点「开始构建」，并把 out/ 里的新包重新拷进游戏；
3. 用法二选一：
   - 界面里点一下图标 → 转义符已复制，直接粘进指令的 text 里；
   - 或者用上面的 `set_rich`，按名字写 `{icon:"heart"}`。

图标的编号（码点）是永久的：换图、改名、挪文件夹都不影响已经写好的指令。
删除的图标编号会保留占位，防止旧指令显示错图；确定不要了可以在「码点管理」里释放。

## 自定义字体

不想一张张导图标、而是自己写了一套字体（json + 贴图）？把整套资源按资源包的目录结构丢进 `fonts/`：

```
fonts/assets/myns/font/fancy.json
fonts/assets/myns/textures/font/fancy.png
```

点「开始构建」，工具会把它拷进资源包、逐字量宽、生成负宽版，并入总字体——**你的字形直接在组件 text 里打字符就能用**，对齐全自动，和内置字体待遇相同。两点建议：字形尽量放在没被占用的码点（私用区 U+E000 起最稳，会与图标共存，注意别和 `icons/` 分到的码点撞上，可从高段如 U+F000 开始）；TrueType（ttf）类型暂不支持，用 bitmap。

## 自定义颜色样式

颜色不止 16 个原版色。打开 `hud_style.json`，在 `presets` 里加一条「样式」（任意 RGB 颜色 + 一个效果）：

```
"presets": {
  "gold_wave": {"rgb": "#FFD700", "effect": "wave"},
  "warn":      {"rgb": "#FF6B00", "effect": "blink"}
}
```

点「开始构建」后，指令里把样式名当颜色用（effect 填 none 即可，样式自带效果）：

```
execute as @s run function dbchud:set {name:"t",x:50,y:20,color:"warn",text:"BOSS 来了",effect:"none",scale:2,align:"center"}
```

说明：样式槽一共 128 个，默认的 16 色 × 8 效果占了 112 个，**自定义最多再加 16 条**；
想加更多，就在 `hud_style.json` 里删掉用不到的效果或颜色给预设腾位置（比如去掉一个效果 = 多出 16 个空槽）。

## 文件夹里都是什么

| 东西 | 说明 |
|---|---|
| `hudpack.exe` | 主程序，双击开 |
| `icons/` | 你的图标 PNG（里面的 registry.json 是编号账本，**别删，记得备份**） |
| `fonts/` | 你自己的字体资源（可选，构建时自动量宽并入） |
| `hud_style.json` | 颜色/效果/自定义样式配置（首次构建自动生成） |
| `out/` | 构建产物（要拷进游戏的两个包在这） |
| `vanilla/` | 原版字体素材，工具量字宽用（**别删**） |
| `src/` | 源码，想改功能才需要看（见 src/DEV.md） |

## 常见问题

- **打开 exe 被 Windows 拦？** 无签名程序的正常提示，点「更多信息 → 仍要运行」。
- **文字/图标位置不对？** 确认资源包已启用且按过 F3+T，数据包已 `/reload`。
- **改了图标怎么不生效？** 任何图标改动都要再点一次「开始构建」，并把 out/ 里的新包重新拷进游戏。
- **玩家开了"强制 Unicode 字体"会乱吗？** 不会，自动适配，什么都不用设。
- **和别的资源包冲突？** 本包改了文字着色器（rendertype_text），和同样改这个文件的包只能二选一。

## 版权说明

- `vanilla/` 内置的 `unifont*.zip` 来自 GNU Unifont（自由字体，允许再分发）。
- Minecraft 本体的字体贴图与配置**不随本仓库分发**，首次运行时从你自己的客户端 jar 提取。
