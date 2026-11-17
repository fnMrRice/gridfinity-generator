# Gridfinity Generator

用 Python + OpenSCAD 生成 Gridfinity 拼接底板、电池收纳盒和通用收纳盒。提供 Tkinter 图形界面和三个独立命令行模块，无需 SolidWorks。

![2×2、6U 镂空收纳盒](docs/images/storage-bin.png)

## 功能

- **拼接底板**：输入抽屉内长宽，自动铺设 42 mm 网格、补边并按打印范围分块。无底面；通槽燕尾榫连接，角部使用半榫。
- **电池收纳盒**：输入 Grid 行列数，自动计算规则排列或密排容量。支持 AA、AAA、C、D、LR9、LR44、CR2032、CR123A、18650、21700、9V 和自定义尺寸。底部定位，上方留出取放空间。
- **通用收纳盒**：输入 Grid 行列和高度 U，生成无内部隔板的可堆叠盒。可选菱形侧壁镂空，保留完整底面、四角和上下边框。
- 支持输出可编辑 SCAD、打印 STL、布局 SVG/JSON 和几何检查报告。
- GUI 与 CLI 共用参数验证、布局和模型生成逻辑。

## 运行环境

- Python 3.10 或以上；GUI 需要 Tkinter。程序仅使用 Python 标准库，无需安装 pip 依赖。
- 安装 [OpenSCAD](https://openscad.org/downloads.html)，并加入 `PATH`。本项目使用 OpenSCAD 2021.01 验证。
- 也可通过 `GRIDFINITY_OPENSCAD` 环境变量或 CLI 的 `--openscad` 指定程序路径。

仅计算布局（`--plan-only`）或生成源码（`--source-only`）不需要 OpenSCAD。完整 STL 导出需要 OpenSCAD；`--no-preview` 可跳过 PNG 渲染。

## 图形界面

在仓库根目录运行：

```sh
python app_scad.py
```

Windows 可双击 `启动生成器.cmd`。启动脚本优先使用仓库内的 `.venv`，其次兼容原工作区的 Python 环境，最后使用 `PATH` 中的 Python。

界面有底板、电池盒、通用收纳盒三个标签页，支持调整参数、查看布局、生成文件及在 OpenSCAD 中打开模型。

## 命令行

```sh
# 450×320 mm 抽屉；每块打印范围不超过 240×240 mm
python -m gridfinity.baseplate --length 450 --width 320 --max-x 240 --max-y 240

# 2×2 Grid 的 AA 电池盒，自动密排
python -m gridfinity.battery --columns 2 --rows 2 --battery AA --packing dense

# 2×2 Grid、6U 的镂空侧壁收纳盒
python -m gridfinity.bin --columns 2 --rows 2 --height-u 6 --hollow

# 只计算布局；不调用 OpenSCAD
python -m gridfinity.bin --columns 2 --rows 3 --height-u 6 --plan-only
```

Windows 也可用 `生成底板.cmd`、`生成电池盒.cmd`、`生成收纳盒.cmd`，参数相同。每个模块支持 `--help`；完整选项、JSON 配置和 Python API 见 [命令行使用说明](命令行使用说明.txt)。

## 尺寸与打印

- 行列数均指 **Grid 数量**，每格间距 42 mm；盒体外长宽为 `42 × 格数 − 0.5 mm`。
- 高度每 U 为 7 mm，包含底脚；堆叠边另加 3.8 mm。例如 6U 本体 42 mm，总高 45.8 mm。
- 收纳盒整体打印；底板自动分块，尺寸检查包含凸出的榫头。默认平面打印范围为 240×240 mm，可按打印机调整；通用盒还支持高度上限。
- 菱形侧孔顶角为 45°；底脚之间仍有小跨度桥接。孔尺寸过小时自动保留完整侧壁。
- 镂空侧壁可能漏出小物件。配合间隙、承载和切片参数需通过实物试印确认。
- 密排在实现的规则、交错、转向候选方案中择优，不保证任意装箱问题的全局最优解。

完整使用说明见 [使用说明](使用说明_OpenSCAD.txt)。预设电池尺寸来源保存在 [battery_presets.json](scad/battery_presets.json)。

## 输出与验证

默认结果保存在 `OpenSCAD输出/` 下，每次生成新目录；`--output` 可指定一个尚不存在的目录。源码引用的公共 SCAD 文件会一并复制。

STL 生成后检查闭合性、连通体、外形尺寸、底脚及堆叠边剖面，并按模型检查孔位、贯通及悬垂。结果写入 `verification.json`；这些几何检查不代替实物配合和承载测试。

运行无需 OpenSCAD 的参数、布局和 CLI 测试：

```sh
python -m unittest discover -v
```

## 代码结构

| 路径 | 内容 |
| --- | --- |
| `gridfinity/baseplate.py` | 底板分块、榫槽及生成入口 |
| `gridfinity/battery.py` | 电池尺寸、排列及生成入口 |
| `gridfinity/bin.py` | 通用盒、镂空及生成入口 |
| `gridfinity/cli.py` | 参数转换、配置和命令行处理 |
| `gridfinity/shared.py` | OpenSCAD 调用与输出管理 |
| `gridfinity/mesh.py` | STL 几何验证 |
| `scad/` | OpenSCAD 模板及公共接口 |
| `app_scad.py` | Tkinter GUI |

本地运行环境、生成模型、个人参数和旧 SolidWorks 实验文件不纳入版本控制。
