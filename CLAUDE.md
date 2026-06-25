# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

倒水游戏自动求解器。ADB 连接安卓手机 → 自动截屏 → OpenCV 识别水杯和各层颜色 → 贪心搜索(默认) / A*(保底) → ADB 模拟点击自动完成。

## 功能边界

- **全自动**：截图、识别、求解、点击全链路闭环
- **平台**：安卓 + ADB（不支持 iOS）
- **输入**：安卓屏幕截图（`adb exec-out screencap -p`）
- **输出**：`adb shell input tap` 模拟点击
- **游戏规则**：每个杯子固定 4 个颜色块。倒水时，杯顶连续同色块必须全部倒入，目标杯必须有足够空间容纳全部这些块。

## 文件结构

```
倒水游戏/
├── recognize.py       # 图像识别模块：截图、找杯子、采样颜色
├── test.py            # 求解器 + 主流程：Puzzle 类、贪心/A* 搜索、ADB 操作
├── benchmark.py       # 算法性能对比脚本（不影响现有代码）
├── live_screenshot.png # 测试用截图（5 杯，1080×2400）
├── CLAUDE.md          # 本文件
```

## 硬件参数（小米 13，1080×2400）

```
杯顶白边 ~7px，间隙 49px（CUP_TOP_GAP），每色块 90px（BLOCK_HEIGHT）
杯子总高 ≈ 427px（含白边）, 杯宽 ≈ 122px
```

## 架构

### recognize.py — 图像识别

```
adb_screencap() / load_image() → 图片
       ↓
find_cups()       # 灰度 → BINARY 阈值 240 → 轮廓 → 筛选（h > w*2）
       ↓
sample_colors()   # CUP_TOP_GAP + BLOCK_HEIGHT 固定定位 4 块 →
                   # _sample_block_color() 多像素中值采样
       ↓
compress_state()  # 过滤 None + 翻转（上→下 转为 底→顶）
       ↓
recognize()       # 一站式返回 (cups, state)
```

关键参数：
- `CUP_TOP_GAP = 49` — 杯顶到第一个色块的距离（实测）
- `BLOCK_HEIGHT = 90` — 每个色块高度（实测）
- `COLOR_TOLERANCE = 30` — 判断像素是否接近背景色
- 杯子筛选：面积 > 500，高度 > 宽度 × 2
- 背景色：图片四角取出现最多的颜色
- 采样方式：每个块在杯子中轴左右各取 w/6 像素，对 RGB 每通道取中值

### test.py — 求解器 + 主流程

```
main()
├── check_adb() → adb 可用则截图，否则 fallback 到本地文件测试
├── recognize.recognize() → cups, state
├── Puzzle(state, capacity=4).solve()
│   ├── greedy_search()     # 贪婪最佳优先（默认，极快，~98% 情况有解）
│   └── astar()             # A* 保底（贪心无解时自动启用，完备+最优）
└── 遍历 path → adb_touch() 模拟点击（0.3s 间隔，2.5s 每步）
```

**Puzzle 类：**
- `state`：`list[list[tuple]]`，外层杯子列表，内层从杯底到杯顶
- `isRight()`：每杯为空或满且单色 → 解完
- `_is_action(from, to)`：合法性规则（原杯非空、目标杯未满、顶色匹配、倒出的连续同色块数 ≤ 目标杯剩余空位）
- `_count_top_blocks(cup)`：统计杯顶连续同色的块数（从列表末尾向前遍历）
- `_apply_action(from, to)`：从原杯末尾 pop，append 到目标杯末尾，直到颜色变或满/空
- `_heuristic()`：启发函数——统计未归位的颜色种类数（出现在 2+ 杯 或 不满杯单色）
- `solve()` → `greedy_search()` / `astar()`：默认求解策略
- `greedy_search(max_attempts)`：贪婪最佳优先搜索（只用 h，不保证最优）
- `astar(max_attempts)`：A* 搜索（f = g + h，保证最短路径）
- `bfs(max_attempts)`：BFS 搜索（保留作基准对照）

搜索剪枝（三种算法共用）：连续两步互为逆操作直接跳过。

### 重要约定

- 颜色表示：RGB 元组 `(R,G,B)`，相同 RGB = 同一颜色
- 状态方向：`state[杯索引]` = `[杯底色, ..., 杯顶色]`，`[-1]` = 杯顶，`pop()` = 倒出顶层
- `compress_state` 必须翻转（`reversed()`），因为 `sample_colors` 输出上→下，求解器需要底→顶
- BFS 剪枝：连续两步互为逆操作直接跳过
- 像素级水区扫描（`_find_water_zone`）已被移除——间隙处像素反光会导致误判，改用固定尺寸定位

## 运行

```bash
# 测试识别+求解（用本地截图，无需 ADB）
python test.py

# 全自动（需要 ADB 连接安卓设备）
# 将安卓设备通过 USB 连接，开启 USB 调试 + 安全设置中开启"USB 调试（安全设置）"
python test.py
```
