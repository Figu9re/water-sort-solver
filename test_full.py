"""全流程测试版：自动通关 → 固定坐标关闭干扰界面 → 识别点击"下一关"

与正式 test.py 的区别：通关后干扰界面的关闭不检测×，改用固定坐标三步：
  ① 点击 (540, 366)
  ② 等 5s 后点击 (867, 538)
  ③ 识别-点击"下一关"（位置扫描，复用 test.find_next_button）
其余（截图识别、求解、倒水、通关检测）全部复用 test.py / recognize.py。
"""
import time
import recognize
import test

AD_POINT_1 = (540, 366)   # 干扰界面关闭 第①步
AD_POINT_2 = (867, 538)   # 干扰界面关闭 第②步（5s 后）
AD_POINT_GAP = 5.0        # ①②两步之间的等待秒数


def close_interference():
    """固定坐标关闭干扰界面：点① → 等5s → 点②"""
    print(f"[固定坐标] 第①步 点击 {AD_POINT_1}")
    time.sleep(1)
    test.adb_touch(*AD_POINT_1)
    time.sleep(AD_POINT_GAP)
    print(f"[固定坐标] 第②步 点击 {AD_POINT_2}")
    test.adb_touch(*AD_POINT_2)
    time.sleep(test.CLOSE_WAIT_SEC)


def clear_stage():
    """通关后结算：固定坐标关干扰 → 识别点击"下一关"并等新关卡"""
    close_interference()
    print("[识别] 定位并点击'下一关'...")
    return test._click_next_until_game()


def auto_play(max_levels=None):
    """全流程测试版主循环"""
    level = 0
    try:
        while max_levels is None or level < max_levels:
            cups, state, _ = test.screencap_recognize()
            if not cups:
                print("[异常] 识别不到杯子，尝试恢复...")
                if clear_stage():
                    continue   #跳过当前 while 循环的剩余代码，进入下一次循环
                print("[退出] 无法恢复，停止")
                break

            level += 1
            print(f"\n===== 第 {level} 关 =====")
            print(f"找到 {len(cups)} 个杯子，求解...")
            puzzle = test.Puzzle(state, capacity=4)
            result = puzzle.solve()
            if result is None:
                print("[退出] 本关无解，停止")
                break

            path, _ = result
            print(f"解法: {len(path)} 步，开始倒水...")
            for i, (fi, ti) in enumerate(path):
                from_c = test.get_cup_center(*cups[fi])
                to_c = test.get_cup_center(*cups[ti])
                test.move_water(i, from_c, to_c)

            retry = 0
            while True:
                time.sleep(2)
                cups2, state2, _ = test.screencap_recognize()
                if test._on_game_screen(cups2, state2):
                    retry += 1
                    if retry > 3:
                        print("[退出] 通关检测异常，停止")
                        return
                    print(f"[警告] 仍识别到未通关画面（第{retry}次），重新执行结算三步...")
                    if clear_stage():
                        print("[结算] 三步生效，已进入新关卡")
                        break
                    print("[警告] 结算三步未生效，继续重试...")
                    continue
                print("本关通关！进入结算（固定坐标关干扰 → 识别点下一关）...")
                if not clear_stage():
                    print("[退出] 结算流程超时，停止")
                    return
                break
    except KeyboardInterrupt:
        print("\n已手动停止")


if __name__ == "__main__":
    auto_play()
