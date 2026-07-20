# 预构建包（开箱即用，无自定义图标）

这里是**已经构建好的** DBCHUD 数据包和资源包，只想用指令做文字 HUD、不需要自定义图标的话，
直接拿这两个就行，**不用装工具、不用构建**。

> 适用 Minecraft 26.1.x（Java 版）。想加**自定义图标或字体**，才需要上层目录的 `hudpack.exe` 自己构建。

## 用法

两个 zip **不用解压**，直接放进对应文件夹：

- `dbchud_resourcepack.zip` → `.minecraft/resourcepacks/`，进游戏在资源包列表里启用它，按 `F3+T` 重载。
- `dbchud_datapack.zip` → 你存档的 `datapacks/` 文件夹，进游戏输 `/reload`。

装好后试一下：

```
/function dbchud:demo2
```

屏幕上出现示例组件就成功了。指令用法见上层目录的 `README.md`（`set` / `content` / `remove` / `set_rich` 等）。

## 里面是什么

- 资源包：文字着色器 + 负宽字体（净宽 0 对齐用），不含任何 Minecraft 原版贴图，也不含图标。
- 数据包：全部 HUD 指令函数。

因为没有图标，`set_rich` 里的 `{icon:"..."}` 用不了；想要图标就用 `hudpack.exe` 加图后自行构建，
生成的包会覆盖这里这份。
