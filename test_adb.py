"""确认哪种点击方案能在小米13上生效"""

import subprocess
import time


def adb(args, timeout=10):
    result = subprocess.run(["adb"] + args, capture_output=True, timeout=timeout)
    return result.stdout.decode(), result.stderr.decode(), result.returncode


# 屏幕分辨率
W, H = 1080, 2400

# === 检查 Android 14 untrusted touches 设置 ===
print("=== Android 14 触控限制检查 ===")
stdout, _, _ = adb(["shell", "settings", "get", "global", "block_untrusted_touches"])
val = stdout.strip()
print(f"block_untrusted_touches = {val}")
if val == "1":
    print("→ 这是阻止 ADB 点击的原因，尝试关闭...")
    _, _, rc = adb(["shell", "settings", "put", "global", "block_untrusted_touches", "0"])
    print(f"   设置结果 rc={rc}")
    time.sleep(1)
    stdout, _, _ = adb(["shell", "settings", "get", "global", "block_untrusted_touches"])
    print(f"   重新读取 = {stdout.strip()}")
else:
    print("→ 未限制，应该允许 ADB 点击")

print()

# === 再试 input tap ===
print("=== 测试 input tap ===")
_, stderr, rc = adb(["shell", "input", "tap", str(W//2), str(H//2)])
print(f"input tap → rc={rc}")
if "SecurityException" in stderr:
    print("  结果: 仍被拒绝")
else:
    print("  结果: 可能成功!")

print()

# === 测试 uiautomator ===
print("=== 测试 uiautomator ===")
for cmd in [
    ["shell", "uiautomator", "click", str(W//2), str(H//2)],
]:
    stdout, stderr, rc = adb(cmd)
    out = stdout.strip()
    err = stderr.strip()
    print(f"{' '.join(cmd[2:])} → rc={rc}")
    if out:
        print(f"  stdout: {out[:200]}")
    if err:
        print(f"  stderr: {err[:200]}")

print()
print("观察：1. 设置修改后 phone 是否有反应？")
print("       2. uiautomator click 是否生效？")
