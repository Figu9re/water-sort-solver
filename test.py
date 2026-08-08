import recognize
import subprocess
import time
import heapq
import cv2
import numpy as np

AD_RETRY_MAX = 8                # 结算阶段最大尝试轮数（应对视频广告倒计时）
STAGE_TIMEOUT = 20              # 点击"下一关"后等待进入新关卡的最大秒数
CLOSE_WAIT_SEC = 1.0            # 通关操作结束后 / 点×后 的等待秒数（等页面元素出现）
HOUGH_MIN_RADIUS = 20           # ×圆圈最小半径
HOUGH_MAX_RADIUS = 100          # ×圆圈最大半径


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


def adb_touch(x, y, hold_ms=0):
    """ADB 模拟点击坐标 (x, y)

    hold_ms > 0 时用长按压（input swipe 同点停留），更接近真实手指，
    部分游戏按钮对瞬时 tap 无响应。
    """
    if hold_ms > 0:
        cmd = ["adb", "shell", "input", "swipe",
               str(x), str(y), str(x), str(y), str(int(hold_ms))]
    else:
        cmd = ["adb", "shell", "input", "tap", str(x), str(y)]
    subprocess.run(cmd, capture_output=True, timeout=5)


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


def screencap_recognize():
    """截图 + 识别 + 屏幕尺寸 一步封装；失败返回 (None, None, None)"""
    try:
        img = recognize.adb_screencap()
        cups, state = recognize.recognize(img)
        return cups, state, recognize.screen_size(img)
    except Exception:
        return None, None, None


def is_cleared(state):
    """是否通关：空杯或满且单色"""
    if not state:
        return False
    return Puzzle(state, capacity=4).isRight()


def _on_game_screen(cups, state):
    """是否已在正常游戏关卡（识别到杯子 且 非通关态）"""
    return bool(cups) and not is_cleared(state)


def tap_pt(img, pt, tag, hold_ms=0):
    """点击指定坐标，并把点击位置标注到截图副本存到 debug/ 供校准"""
    x, y = int(pt[0]), int(pt[1])
    try:
        annotated = img.copy()
        cv2.circle(annotated, (x, y), 30, (0, 0, 255), 5)
        recognize.save_debug(annotated, tag)
    except Exception:
        pass
    adb_touch(x, y, hold_ms=hold_ms)
    return (x, y)


def _find_popup(img):
    """找居中弹窗区域（非暗色大连通域），返回 (x,y,w,h) 或 None"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, bright = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    return cv2.boundingRect(max(contours, key=cv2.contourArea))


def _is_in_circle(img, pt, region):
    """验证坐标 pt 是否位于圆形元素（× 的圆圈）内部

    在 pt 周围的聚焦窗口内跑 HoughCircles，避免广告装饰元素的噪圆；
    多个 param2 梯度尝试，兼顾"白底白圈"这类低对比度圆（整窗检测会漏）。
    实测：干扰界面1 的 × 圆圈 (864,554,r56)、干扰界面2 的 (933,705,r~55) 均能命中。
    """
    cx, cy = int(pt[0]), int(pt[1])
    half = 110
    x0, y0 = max(0, cx - half), max(0, cy - half)
    x1, y1 = min(img.shape[1], cx + half), min(img.shape[0], cy + half)
    roi = img[y0:y1, x0:x1]
    if roi.size == 0:
        return False
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    for p2 in (15, 20):
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=1, minDist=20,
            param1=100, param2=p2,
            minRadius=HOUGH_MIN_RADIUS, maxRadius=HOUGH_MAX_RADIUS)
        if circles is None:
            continue
        for ccx, ccy, r in circles[0]:
            ox, oy = x0 + ccx, y0 + ccy
            dx, dy = cx - ox, cy - oy
            if dx * dx + dy * dy <= r * r:
                return True
    return False


def find_close_x(img):
    """自动定位弹窗右上角的"圆圈内×"，返回 (x,y) 或 None

    流程：_find_popup 定位弹窗 → 顶部 15% + 右侧 40% 区域提取白色块候选
    → 候选按距右上角距离排序 → 用 _is_in_circle 验证块位于圆圈内。
    只有"圆圈内的×"才算广告关闭按钮，避免误点普通装饰白块。
    """
    popup = _find_popup(img)
    if popup is None:
        return None
    px, py, pw, ph = popup
    roi_h = max(60, int(ph * 0.15))
    roi = img[py:py + roi_h, px:px + pw]
    _, white = cv2.threshold(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), 220, 255, cv2.THRESH_BINARY)
    white = cv2.morphologyEx(white, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for c in cs:
        bx, by, bw, bh = cv2.boundingRect(c)
        if not (15 < bw < 90 and 15 < bh < 90):
            continue
        cx = px + bx + bw // 2
        cy = py + by + bh // 2
        if cx < px + pw * 0.6:
            continue
        candidates.append((cx, cy))
    if not candidates:
        return None
    # 距弹窗右上角越近越优先，只认"圆圈内"的块
    candidates.sort(key=lambda p: (px + pw - p[0]) + (p[1] - py))
    for cx, cy in candidates:
        if _is_in_circle(img, (cx, cy), popup):
            return (cx, cy)
    return None


def find_next_button(img):
    """按位置特征定位"下一关"按钮，返回按钮中心 (x,y) 或 None

    "下一关"按钮特征：水平居中、垂直偏下。在扫描区域（屏幕中线 ±25% 屏宽、
    高度 60%~95%）内用 HSV 饱和度提取彩色块，取最大块中心。
    上边界取 60% 而非 50%，避开按钮上方的标题/装饰把最大块中心拉偏
    （真机验证过此参数命中按钮中心）。
    """
    h, w = img.shape[:2]
    xc = w // 2
    x0 = xc - int(w * 0.25)
    top = int(h * 0.6)
    roi = img[top:int(h * 0.95), x0:xc + int(w * 0.25)]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    _, m = cv2.threshold(hsv[:, :, 1], 80, 255, cv2.THRESH_BINARY)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs:
        return None
    x, y, bw, bh = cv2.boundingRect(max(cs, key=cv2.contourArea))
    return (x0 + x + bw // 2, top + y + bh // 2)


def _click_next_until_game():
    """点"下一关"，等待进入新关卡；若中途仍停留在恭喜页则重试点击

    关键：点完"下一关"后耐心轮询（最长 STAGE_TIMEOUT），绝不乱点其他位置，
    避免打断关卡加载。若按钮消失（界面已变）则交给 handle_clear 重新判断。

    返回: 是否已进入新关卡
    """
    end = time.time() + STAGE_TIMEOUT
    last_tap = 0.0
    while time.time() < end:
        now = time.time()
        if now - last_tap >= 6:
            img = recognize.adb_screencap()
            pt = find_next_button(img)
            if pt is None:
                return False   # 不再是恭喜页 → 交给主循环
            tap_pt(img, pt, "auto_next", hold_ms=120)
            last_tap = now
        time.sleep(2)
        cups, state, _ = screencap_recognize()
        if _on_game_screen(cups, state):
            return True
    return False


def handle_clear():
    """结算流程状态机（通关后自动进入下一关）

      通关点击操作结束后，按节奏执行：
      1. 等待 CLOSE_WAIT_SEC → 分析页面元素
      2. 出现"下一关"按钮 → 点击并耐心等新关卡加载
      3. 没有"下一关" → 找"圆圈内×"（广告关闭按钮）→ 点击 → 回到步骤 2
      4. 二者都没有 → 存证截图重试（不盲点），超轮数退出

    修复：不再用固定比例坐标盲点 × / "下一关"（曾误点恭喜页内其他按钮）。
    """
    time.sleep(CLOSE_WAIT_SEC)  # 通关操作结束后等页面元素稳定
    for _ in range(AD_RETRY_MAX):
        cups, state, _ = screencap_recognize()
        if _on_game_screen(cups, state):
            return True
        img = recognize.adb_screencap()

        # 检测"下一关"按钮 → 点击并耐心等待进入新关卡
        pt = find_next_button(img)
        if pt:
            if _click_next_until_game():
                return True
            continue

        # 无"下一关" → 广告/奖励弹窗 → 找"圆圈内×"并点击，回到循环重新分析
        pt = find_close_x(img)
        if pt:
            tap_pt(img, pt, "auto_close")
            time.sleep(CLOSE_WAIT_SEC)
            continue

        # 未知界面 → 保存现场截图，稍等重试（不盲点）
        recognize.save_debug(img, "unknown_screen")
        time.sleep(CLOSE_WAIT_SEC)
    return False


def auto_play(max_levels=None):
    """全自动多关卡循环：识别→求解→执行→通关→结算（广告/恭喜页面）→下一关"""
    level = 0
    try:
        while max_levels is None or level < max_levels:
            cups, state, _ = screencap_recognize()
            if not cups:
                print("[异常] 识别不到杯子，尝试恢复游戏界面...")
                if handle_clear():
                    continue
                print("[退出] 无法恢复游戏界面，停止")
                break

            level += 1
            print(f"\n===== 第 {level} 关 =====")
            print(f"找到 {len(cups)} 个杯子，正在求解...")
            puzzle = Puzzle(state, capacity=4)
            result = puzzle.solve()
            if result is None:
                print("[退出] 本关无解，停止")
                break

            path, _ = result
            print(f"解法: {len(path)} 步，开始倒水...")
            for i, (from_idx, to_idx) in enumerate(path):
                from_center = get_cup_center(*cups[from_idx])
                to_center = get_cup_center(*cups[to_idx])
                move_water(i, from_center, to_center)

            # 通关检测（三态）：
            #   识别到通关态杯子 或 识别不到杯子（弹窗遮罩）→ 视为通关
            #   识别到非通关态杯子 → 重试
            retry = 0
            while True:
                time.sleep(2)
                cups2, state2, _ = screencap_recognize()
                if _on_game_screen(cups2, state2):
                    retry += 1
                    if retry > 3:
                        print("[退出] 通关检测异常，停止")
                        return
                    print(f"[警告] 执行完后仍识别到未通关画面（第{retry}次），重试...")
                    continue
                print("本关通关！进入结算流程（关广告 → 点下一关）...")
                if not handle_clear():
                    print("[退出] 结算流程超时，停止")
                    return
                break
    except KeyboardInterrupt:
        print("\n已手动停止")


def main():
    # ADB 可用 → 全自动多关卡循环；否则 fallback 到本地文件测试
    if not check_adb():
        print("ADB 不可用，运行文件测试模式...")
        run_local_test()
        return

    auto_play()


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
