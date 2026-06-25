# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

倒水游戏自动求解器。ADB 连接安卓手机 → 自动截屏 → OpenCV 识别水杯和各层颜色 → BFS 搜索最优解法 → ADB 模拟点击自动完成。

## 功能边界

- **全自动**：截图、识别、求解、点击全链路闭环
- **平台**：安卓 + ADB（不支持 iOS）
- **输入**：安卓屏幕截图（`adb exec-out screencap -p`）
- **输出**：`adb shell input tap` 模拟点击
- **游戏规则**：每个杯子固定 4 个颜色块

## 文件结构

```
倒水游戏/
├── recognize.py     # 图像识别模块：截图、找杯子、采样颜色
├── test.py          # 求解器 + 主流程：Puzzle 类、BFS、ADB 操作
├── screenshot.png   # 测试用截图
├── CLAUDE.md        # 本文件
```

## 架构

### recognize.py — 图像识别

```
adb_screencap() → 图片
       ↓
load_image() / adb_screencap()
       ↓
find_cups()       # 灰度 → BINARY 阈值 240 → 轮廓 → 筛选杯子（h > w*2）
       ↓
sample_colors()   # 每杯等分 4 格 → 每格中心取 RGB → 与背景色比较判空/满
       ↓
compress_state()  # 去掉空位，从杯底到杯顶排列
       ↓
recognize()       # 一站式接口，返回 (杯子位置, 求解器状态)
```

关键参数：
- 杯子筛选：面积 > 500，高度 > 宽度 × 2
- 颜色容差：RGB 欧氏距离 < 30 视为同色
- 背景色：从图片四角自动检测（取出现最多的颜色）

### test.py — 求解器 + 主流程

```
main()
├── check_adb() → adb 可用则截图，否则 fallback 到本地文件测试
├── recognize.recognize() → cups, state
├── Puzzle(state, capacity=4).bfs() → path, solved_state
└── 遍历 path → adb_touch() 模拟点击
```

**Puzzle 类：**
- `state`：`list[list[tuple]]`，外层杯子列表，内层从杯底到杯顶
- `isRight()`：每杯为空或满且单色 → 解完
- `get_successors()`：生成所有合法 (action, new_state)
- `_isAction(from, to)`：合法性规则（不同杯、原杯非空、目标杯未满、顶色匹配）
- `_apply_action(from, to)`：执行倒水（不修改原状态）
- `bfs(max_attempts)`：BFS 搜索 + 剪枝（跳过 A→B 后 B→A 的对称操作）

### 重要约定

- 颜色表示：RGB 元组 `(R,G,B)`，相同 RGB = 同一颜色
- 状态方向：`state[杯索引]` = `[杯底色, ..., 杯顶色]`，空杯为 `[]`
- 搜索剪枝：连续两步互为逆操作直接跳过
- 先跑通全流程再优化

## 运行

```bash
# 测试识别+求解（用本地截图，无需 ADB）
python test.py

# 全自动（需要 ADB 连接安卓设备）
# 将安卓设备通过 USB 连接，开启 USB 调试
python test.py
```
