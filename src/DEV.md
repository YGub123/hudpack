# 开发者说明(改功能 / 重打 exe 才需要看)

## 源码分工

| 文件 | 作用 |
|---|---|
| `hudpack_ui.py` | 图形界面(tkinter,MC 像素风;`python src/hudpack_ui.py` 可直接跑) |
| `build.py` | 主构建:生成 DBCHUD 数据包+资源包(`python src/build.py` 命令行构建) |
| `negfont.py` | 库:解析字体、逐像素量字宽、生成负宽字体(纯标准库,自带 PNG 解码) |
| `iconpack.py` | 库:图标 registry、码点分配/复用池、rename/discard、查表 |
| `mcfont.py` | 库:用 vanilla 的 ascii.png + unifont 渲染 MC 原版点阵字(界面文字用) |

exe 附带 CLI:`hudpack.exe --build`(无界面构建)、`hudpack.exe --check`(自检写 hudpack_check.txt)。

## 重打 exe

需要 Python 3 + PyInstaller(`pip install pyinstaller`)。在 hudpack/ 目录下:

```
python -m PyInstaller --onefile --windowed --name hudpack ^
  --add-data "src\build.py;." ^
  --hidden-import negfont --hidden-import iconpack --hidden-import mcfont ^
  --distpath . src/hudpack_ui.py
```

## 原理速记

- 定位:一条 actionbar 消息,把坐标/颜色/字号编进文字顶点数据(颜色三字节 + Position.x 位段),
  资源包顶点着色器解码重定位。多组件互不干扰靠"净宽 0"。
- 净宽 0:每段可见文字后跟同文本的"负宽字体"副本(每字 advance 取负),宽度自动抵消。
  负宽由 negfont 从 vanilla/ 真实字体逐像素量出,与 MC 完全一致。
- Force Unicode 自动适配:可见字体与负宽字体保留同样的 `filter:{uniform:false}`,两边随客户端设置同步切换。
- 图标:PUA 码点,registry 永久分配;`built` 标记(构建过才转正),未转正删除自动回收,
  转正后删除留占位,「码点管理」可释放进复用池。
- 详细设计与踩坑记录见项目对话/记忆(dbchud-datapack)。
