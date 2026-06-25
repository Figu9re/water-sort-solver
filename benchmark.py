"""
算法性能对比脚本
对同一关卡运行多种搜索算法，比较步数、搜索量和耗时
不修改现有 test.py 代码
"""

import recognize
from test import Puzzle
import time
import heapq


# ── 启发函数 ──────────────────────────────────────────────

def heuristic(puzzle):
    """未归位的颜色种类数

    一种颜色如果出现在 2+ 个杯子中（或不满杯），就还没有归位，
    至少需要 1 步来整理。
    """
    color_cups = {}   # color -> set of cup indices
    for i, cup in enumerate(puzzle.state):
        seen = set()
        for c in cup:
            if c not in seen:
                seen.add(c)
                color_cups.setdefault(c, set()).add(i)

    unsorted = 0
    for c, cups in color_cups.items():
        if len(cups) > 1:
            unsorted += 1
        else:
            # 只出现在一个杯子，但不满杯或混色
            idx = next(iter(cups))
            cup = puzzle.state[idx]
            if len(cup) != puzzle.capacity or not puzzle._all_elements_same(cup):
                unsorted += 1

    return unsorted


# ── 搜索算法包装 ──────────────────────────────────────────

def bench_bfs(puzzle, max_attempts=2000000):
    """BFS — 基准线"""
    q = [([], puzzle)]
    visited = {puzzle._state_key(puzzle.state)}
    expanded = 0
    start = time.perf_counter()

    while q:
        path, pz = q.pop(0)

        if pz.isRight():
            return path, expanded, time.perf_counter() - start

        if len(path) >= 2:
            last, prev = path[-1], path[-2]
            if last[1] == prev[0] and last[0] == prev[1]:
                continue

        for act, suc_pz in pz.get_successors():
            key = suc_pz._state_key(suc_pz.state)
            if key not in visited:
                visited.add(key)
                q.append((path + [act], suc_pz))
                expanded += 1
                if expanded > max_attempts:
                    return None, expanded, time.perf_counter() - start

    return None, expanded, time.perf_counter() - start


def bench_astar(puzzle, max_attempts=2000000):
    """A* 搜索 (f = g + h)，保证最短路径"""
    h = heuristic(puzzle)
    if h == 0:
        return [], 0, 0.0

    start = time.perf_counter()
    # (f, g, tie_breaker, path, puzzle)
    seq = 0
    q = [(h, 0, seq, [], puzzle)]
    visited = {puzzle._state_key(puzzle.state): 0}
    expanded = 0

    while q:
        f, g, _, path, pz = heapq.heappop(q)

        if pz.isRight():
            return path, expanded, time.perf_counter() - start

        if len(path) >= 2:
            last, prev = path[-1], path[-2]
            if last[1] == prev[0] and last[0] == prev[1]:
                continue

        for act, suc_pz in pz.get_successors():
            key = suc_pz._state_key(suc_pz.state)
            new_g = g + 1
            if key not in visited or new_g < visited[key]:
                visited[key] = new_g
                seq += 1
                new_h = heuristic(suc_pz)
                heapq.heappush(q, (new_g + new_h, new_g, seq, path + [act], suc_pz))
                expanded += 1
                if expanded > max_attempts:
                    return None, expanded, time.perf_counter() - start

    return None, expanded, time.perf_counter() - start


def bench_greedy(puzzle, max_attempts=2000000):
    """贪婪最佳优先 (只用 h)，不保证最优但可能极快"""
    h = heuristic(puzzle)
    if h == 0:
        return [], 0, 0.0

    start = time.perf_counter()
    seq = 0
    q = [(h, seq, [], puzzle)]
    visited = {puzzle._state_key(puzzle.state)}
    expanded = 0

    while q:
        h_val, _, path, pz = heapq.heappop(q)

        if pz.isRight():
            return path, expanded, time.perf_counter() - start

        if len(path) >= 2:
            last, prev = path[-1], path[-2]
            if last[1] == prev[0] and last[0] == prev[1]:
                continue

        for act, suc_pz in pz.get_successors():
            key = suc_pz._state_key(suc_pz.state)
            if key not in visited:
                visited.add(key)
                seq += 1
                heapq.heappush(q, (heuristic(suc_pz), seq, path + [act], suc_pz))
                expanded += 1
                if expanded > max_attempts:
                    return None, expanded, time.perf_counter() - start

    return None, expanded, time.perf_counter() - start


# ── 随机生成关卡 ──────────────────────────────────────────

import random

def generate_puzzle(num_cups, capacity=4, num_colors=None):
    """生成随机测试关卡

    参数:
        num_cups: 杯子总数（含空杯）
        capacity: 每杯容量
        num_colors: 颜色种类（默认 = (num_cups - 2)）
    """
    if num_colors is None:
        num_colors = num_cups - 2

    colors = [(random.randint(30, 240), random.randint(30, 240), random.randint(30, 240))
              for _ in range(num_colors)]

    # 每种颜色恰好 capacity 个块
    blocks = []
    for c in colors:
        blocks.extend([c] * capacity)

    random.shuffle(blocks)

    # 分配到前 num_cups 个杯子（留 2 个空杯）
    state = []
    for i in range(num_cups):
        start = i * capacity
        if start < len(blocks):
            cup = blocks[start:start + capacity]
        else:
            cup = []
        state.append(cup)

    return state


# ── 彩色输出 ──────────────────────────────────────────────

def rgb_to_ansi(r, g, b):
    """RGB → ANSI 近似色块"""
    r16 = round(r / 255 * 5)
    g16 = round(g / 255 * 5)
    b16 = round(b / 255 * 5)
    code = 16 + 36 * r16 + 6 * g16 + b16
    return f"\033[48;5;{code}m  \033[0m"


def render_state(state):
    """打印关卡状态（带颜色）"""
    rows = []
    for i, cup in enumerate(state):
        blocks = "".join(rgb_to_ansi(*c) for c in reversed(cup))
        rows.append(f"  杯子{i}: {blocks} {len(cup)}层")
    return "\n".join(rows)


# ── 主测试 ────────────────────────────────────────────────

ALGORITHMS = [
    ("BFS",     bench_bfs),
    ("A*",      bench_astar),
    ("贪心",    bench_greedy),
]


def run_benchmark(state, capacity=4):
    """对所有算法跑同一关卡，打印对比表格"""
    puzzle = Puzzle(state, capacity)

    print(f"关卡: {len(state)} 杯, 容量 {capacity}")
    print()
    print("状态（杯底 → 杯顶）:")
    for i, cup in enumerate(state):
        colors = " ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in cup) if cup else "空"
        print(f"  杯子{i}: [{colors}] ({len(cup)}层)")
    print()

    results = []
    for name, func in ALGORITHMS:
        path, expanded, elapsed = func(puzzle)
        steps = len(path) if path is not None else "—"
        results.append((name, steps, expanded, elapsed, path))

    # 表格
    header = f"{'算法':<6} {'步数':>6} {'搜索状态':>10} {'耗时':>10}"
    sep = "─" * len(header)
    print(header)
    print(sep)
    for name, steps, expanded, elapsed, path in results:
        s = f"{steps}" if steps != "—" else "无解"
        print(f"{name:<6} {s:>6} {expanded:>10,} {elapsed:>8.4f}s")
    print()

    # 如果有 BFS 结果作为基准，算加速比
    bfs_result = results[0]
    if bfs_result[1] != "—":
        bfs_steps, bfs_exp, bfs_time = bfs_result[1], bfs_result[2], bfs_result[3]
        for name, steps, expanded, elapsed, path in results[1:]:
            if expanded == 0:
                continue
            speedup = bfs_exp / expanded if expanded > 0 else float("inf")
            print(f"  {name} 搜索量是 BFS 的 1/{speedup:.1f} (减少 {100-100/speedup:.0f}%)")
            if isinstance(steps, int):
                print(f"  步数: {steps} vs BFS {bfs_steps} {'(相同)' if steps == bfs_steps else '(更长!)'}")


def test_with_screenshot():
    """用本地截图测试"""
    print("=" * 50)
    print("  测试 1: 本地截图 live_screenshot.png")
    print("=" * 50)
    print()
    img = recognize.load_image("live_screenshot.png")
    cups, state = recognize.recognize(img)
    run_benchmark(state)


def test_random():
    """用随机生成的关卡测试"""
    print("=" * 50)
    print("  测试 2: 随机生成关卡")
    print("=" * 50)
    print()

    for num_cups in [7, 9, 12]:
        state = generate_puzzle(num_cups)
        puzzle = Puzzle(state, capacity=4)

        # 先 BFS 尝试（太小可能无解）
        result = puzzle.bfs(max_attempts=50000)
        if result is None:
            print(f"{num_cups} 杯: BFS 50k 步未找到解，跳过")
            print()
            continue

        print(f"{num_cups} 杯 (颜色 {len({c for cup in state for c in cup})} 种):")
        for name, func in ALGORITHMS:
            path, expanded, elapsed = func(Puzzle(state, capacity=4))
            steps = len(path) if path is not None else "—"
            print(f"  {name}: {steps} 步, {expanded:,} 状态, {elapsed:.4f}s")
        print()


if __name__ == "__main__":
    test_with_screenshot()
    print()
    test_random()
