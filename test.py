import recognize
import subprocess
import time
import heapq


class Puzzle:
    def __init__(self, state, capacity=4):
        self.state = state          # [[(R,G,B), ...], ...] 从杯底到杯顶
        self.capacity = capacity    # 每个杯子最多装几层
        self.cup_num = len(state)   # 杯子数

    def isRight(self):
        """检查是否已解完：每杯为空或为单一颜色"""
        for cup in self.state:
            if len(cup) == 0:
                continue
            if len(cup) != self.capacity:
                return False
            if not self._all_elements_same(cup):
                return False
        return True

    def get_successors(self):
        """生成所有合法后继状态

        返回: list of ((from, to), Puzzle)
        """
        successors = []
        for j in range(self.cup_num):
            for i in range(self.cup_num):
                if j == i:
                    continue
                if not self._is_action(j, i):
                    continue
                new_state = self._apply_action(j, i)
                successors.append(((j, i), Puzzle(new_state, self.capacity)))
        return successors

    @staticmethod
    def _count_top_blocks(cup):
        """计算杯顶连续同色块的数量"""
        if len(cup) == 0:
            return 0
        count = 1
        for i in range(len(cup) - 2, -1, -1):
            if cup[i] == cup[-1]:
                count += 1
            else:
                break
        return count

    def _is_action(self, from_idx, to_idx):
        """判断从 from_idx 倒到 to_idx 是否合法"""
        from_cup = self.state[from_idx]
        to_cup = self.state[to_idx]

        # 原杯不能为空
        if len(from_cup) == 0:
            return False
        # 原杯已满且颜色统一，不需再动
        if len(from_cup) == self.capacity and self._all_elements_same(from_cup):
            return False
        # 目标杯不能满
        if len(to_cup) == self.capacity:
            return False

        # 杯顶颜色必须匹配
        if len(to_cup) > 0 and from_cup[-1] != to_cup[-1]:
            return False

        # 游戏规则：必须能倒完所有连续同色块，否则操作无效
        top_count = self._count_top_blocks(from_cup)
        remaining = self.capacity - len(to_cup)
        return top_count <= remaining

    def _apply_action(self, from_idx, to_idx):
        """执行倒水动作，返回新状态（不修改原状态）"""
        new_state = [list(cup) for cup in self.state]
        from_cup = new_state[from_idx]
        to_cup = new_state[to_idx]

        # 从原杯顶部倒到目标杯，直到原杯顶部颜色改变或任一满/空
        while len(from_cup) > 0 and len(to_cup) < self.capacity:
            if len(to_cup) > 0 and from_cup[-1] != to_cup[-1]:
                break
            to_cup.append(from_cup.pop())

        return new_state

    def _all_elements_same(self, cup):
        """判断杯子里是否全是同一颜色"""
        if len(cup) <= 1:
            return True
        first = cup[0]
        return all(c == first for c in cup)

    def bfs(self, max_attempts=1000000):
        """BFS 搜索最优解法

        返回: (path, puzzle_state) or None
            path: [(from, to), ...] 倒水步骤列表
        """
        q = [([], self)]
        visited = set()
        visited.add(self._state_key(self.state))
        attempts = 0

        while q:
            path, pz = q.pop(0)

            if pz.isRight():
                print(f"搜索了 {attempts} 个状态")
                return path, pz

            if len(path) >= 2:
                last = path[-1]
                prev = path[-2]
                # 剪枝：上一步从 A→B，下一步从 B→A，跳过
                if last[1] == prev[0] and last[0] == prev[1]:
                    continue

            for act, suc_pz in pz.get_successors():
                key = self._state_key(suc_pz.state)
                if key not in visited:
                    visited.add(key)
                    q.append((path + [act], suc_pz))
                    attempts += 1
                    if attempts > max_attempts:
                        print("超出最大搜索次数")
                        return None

        print("无解")
        return None

    def _state_key(self, state):
        """将状态转为可哈希的 key（用于去重）"""
        return tuple(tuple(cup) for cup in state)

    def _heuristic(self):
        """启发函数：未归位的颜色种类数

        一种颜色如果出现在 2+ 个杯子中（或不满杯），就还没有归位。
        """
        color_cups = {}
        for i, cup in enumerate(self.state):
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
                idx = next(iter(cups))
                cup = self.state[idx]
                if len(cup) != self.capacity or not self._all_elements_same(cup):
                    unsorted += 1
        return unsorted

    def greedy_search(self, max_attempts=2000000):
        """贪婪最佳优先搜索（只用启发函数 h，不保证最优但极快）

        返回: (path, puzzle_state) or None
        """
        h = self._heuristic()
        if h == 0:
            return [], self

        seq = 0
        q = [(h, seq, [], self)]
        visited = {self._state_key(self.state)}
        attempts = 0

        while q:
            _, _, path, pz = heapq.heappop(q)

            if pz.isRight():
                print(f"贪心搜索了 {attempts} 个状态")
                return path, pz

            if len(path) >= 2:
                last, prev = path[-1], path[-2]
                if last[1] == prev[0] and last[0] == prev[1]:
                    continue

            for act, suc_pz in pz.get_successors():
                key = suc_pz._state_key(suc_pz.state)
                if key not in visited:
                    visited.add(key)
                    seq += 1
                    heapq.heappush(q, (suc_pz._heuristic(), seq, path + [act], suc_pz))
                    attempts += 1
                    if attempts > max_attempts:
                        print("贪心搜索超出最大次数")
                        return None

        print("贪心搜索无解")
        return None

    def astar(self, max_attempts=2000000):
        """A* 搜索 (f = g + h)，保证最短路径

        返回: (path, puzzle_state) or None
        """
        h = self._heuristic()
        if h == 0:
            return [], self

        seq = 0
        q = [(h, 0, seq, [], self)]
        visited = {self._state_key(self.state): 0}
        attempts = 0

        while q:
            f, g, _, path, pz = heapq.heappop(q)

            if pz.isRight():
                print(f"A* 搜索了 {attempts} 个状态")
                return path, pz

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
                    heapq.heappush(q, (new_g + suc_pz._heuristic(), new_g, seq, path + [act], suc_pz))
                    attempts += 1
                    if attempts > max_attempts:
                        print("A* 搜索超出最大次数")
                        return None

        print("A* 搜索无解")
        return None

    def solve(self):
        """默认求解策略：贪心优先 → A* 保底

        贪心极快但可能找不到解（很少发生），
        A* 保证最优和完备性。
        """
        r = self.greedy_search()
        if r is not None:
            return r
        print("使用 A* 保底求解...")
        return self.astar()


def adb_touch(x, y):
    """ADB 模拟点击坐标 (x, y)"""
    subprocess.run(
        ["adb", "shell", "input", "tap", str(x), str(y)],
        capture_output=True,
        timeout=5,
    )


def check_adb():
    """检查 ADB 是否可用"""
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, timeout=5)
        output = result.stdout.decode()
        lines = [l for l in output.split("\n") if l.strip() and "List" not in l]
        return len(lines) > 0 and "device" in lines[0]
    except Exception:
        return False


def move_water(action_idx, from_pos, to_pos):
    """模拟一次倒水操作：先点倒出杯，再点倒入杯"""
    print(f"  步骤{action_idx+1}: ({from_pos[0]}, {from_pos[1]}) → ({to_pos[0]}, {to_pos[1]})")
    adb_touch(from_pos[0], from_pos[1])
    time.sleep(0.3)
    adb_touch(to_pos[0], to_pos[1])
    time.sleep(2.5)


def get_cup_center(x, y, w, h):
    """计算杯子中心坐标（点击位置）"""
    return (x + w // 2, y + h // 2)


def main():
    # 1. 截图
    if not check_adb():
        print("ADB 不可用，运行文件测试模式...")
        run_local_test()
        return

    print("正在截图...")
    img = recognize.adb_screencap()

    # 2. 识别
    print("正在识别...")
    cups, state = recognize.recognize(img)
    print(f"找到 {len(cups)} 个杯子")
    for i, cup in enumerate(state):
        print(f"  杯子{i}: {len(cup)} 层 {cup}")

    # 3. 求解
    print("正在求解...")
    puzzle = Puzzle(state, capacity=4)
    result = puzzle.solve()

    if result is None:
        print("无解")
        return

    path, solved = result
    print(f"解法: {len(path)} 步")

    # 4. 执行
    print("开始倒水...")
    for i, (from_idx, to_idx) in enumerate(path):
        from_center = get_cup_center(*cups[from_idx])
        to_center = get_cup_center(*cups[to_idx])
        move_water(i, from_center, to_center)

    print("完成!")


def run_local_test(path="live_screenshot.png"):
    """用本地图片文件测试识别+求解"""
    img = recognize.load_image(path)
    cups, state = recognize.recognize(img)
    print(f"找到 {len(cups)} 个杯子")
    for i, cup in enumerate(state):
        print(f"  杯子{i}: {len(cup)} 层 {cup}")

    print("正在求解...")
    puzzle = Puzzle(state, capacity=4)
    result = puzzle.solve()

    if result is None:
        print("无解")
        return

    path, solved = result
    print(f"解法: {len(path)} 步")
    for i, (f, t) in enumerate(path):
        print(f"  步骤{i+1}: 杯子{f} → 杯子{t}")
    print(f"最终状态: {solved.state}")


if __name__ == "__main__":
    main()
