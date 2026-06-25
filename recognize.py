import cv2
import numpy as np
import subprocess
import tempfile
import os

COLOR_TOLERANCE = 30  # RGB 欧氏距离容差
CUP_TOP_GAP = 49     # 杯顶到第一个色块的距离（实测，含白边+空隙）
BLOCK_HEIGHT = 90    # 每个色块的高度（实测）


def adb_screencap():
    """通过 ADB 截取手机屏幕，返回 OpenCV 图像"""
    result = subprocess.run(
        ["adb", "exec-out", "screencap", "-p"],
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ADB 截图失败: {result.stderr.decode()}")
    img_array = np.frombuffer(result.stdout, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("截图解码失败")
    return img


def load_image(path):
    """从文件加载图片"""
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"无法读取图片: {path}")
    return img


def find_cups(img):
    """找出图片中所有水杯的位置

    返回: list of (x, y, w, h)，按从左到右排序
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # BINARY 阈值 240 提取杯子轮廓（杯子玻璃边框比背景亮）
    _, cup_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(cup_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    cups = []
    for c in contours:
        area = cv2.contourArea(c)
        x, y, w, h = cv2.boundingRect(c)
        # 筛选条件：面积 > 500 且 高度 > 宽度 × 2（杯子是竖长的）
        if area > 500 and h > w * 2:
            cups.append((x, y, w, h))

    cups.sort(key=lambda r: r[0])  # 从左到右排序
    return cups


def _sample_block_color(img, cy, cx, half_width, background_rgb):
    """在杯子中轴线上采样多个像素取中值，抵抗反光/噪点

    返回: (R,G,B) 或 None（全部接近背景色，说明该位置无水）
    """
    samples = []
    for dx in range(-half_width, half_width + 1):
        px = cx + dx
        b, g, r = img[cy, px]
        rgb = (int(r), int(g), int(b))
        if _color_distance(rgb, background_rgb) >= COLOR_TOLERANCE:
            samples.append(rgb)

    if not samples:
        return None

    # 对每个通道取中值（抗噪）
    n = len(samples)
    sorted_r = sorted(s[0] for s in samples)
    sorted_g = sorted(s[1] for s in samples)
    sorted_b = sorted(s[2] for s in samples)
    mid = n // 2
    if n % 2 == 0:
        return (
            (sorted_r[mid - 1] + sorted_r[mid]) // 2,
            (sorted_g[mid - 1] + sorted_g[mid]) // 2,
            (sorted_b[mid - 1] + sorted_b[mid]) // 2,
        )
    return (sorted_r[mid], sorted_g[mid], sorted_b[mid])


def sample_colors(img, cups, background_rgb, num_blocks=4):
    """用固定尺寸定位每个色块的精确位置，采样颜色

    参数:
        img: OpenCV 图像 (BGR)
        cups: find_cups 返回的杯子位置列表
        background_rgb: 背景 RGB 值，用于识别空位
        num_blocks: 每个杯子固定分 4 格

    返回: list of list of (R,G,B) or None
        每杯 [块1, 块2, ...]，从上到下排列
        None 表示该格为空
    """
    state = []
    for cup in cups:
        x, y, w, h = cup
        cx = x + w // 2
        half_width = max(1, w // 6)  # 在杯子宽度的中间 1/3 区域采样

        cup_colors = []
        for i in range(num_blocks):
            block_center_y = y + CUP_TOP_GAP + BLOCK_HEIGHT * i + BLOCK_HEIGHT // 2
            # 防止越界
            if block_center_y >= y + h:
                cup_colors.append(None)
                continue
            rgb = _sample_block_color(img, block_center_y, cx, half_width, background_rgb)
            cup_colors.append(rgb)
        state.append(cup_colors)
    return state


def compress_state(raw_state):
    """将采样状态转为求解器格式：去掉空位，转为从杯底到杯顶的顺序

    输入: [[(R,G,B) or None, ...], ...] 从上到下排列（index 0 = 杯顶方向）
    输出: [[(R,G,B), ...], ...] 从杯底到杯顶，不含空位
    """
    compressed = []
    for cup in raw_state:
        # 水总是从杯底开始填充，空位在顶部，过滤掉 None
        colors = [c for c in cup if c is not None]
        # raw_state 是上→下，求解器需要底→顶，所以翻转
        compressed.append(list(reversed(colors)))
    return compressed


def recognize(path_or_img):
    """一站式识别：输入图片路径或 OpenCV 图像，返回杯子位置和求解器状态

    返回: (cups, state)
        cups: [(x,y,w,h), ...]
        state: [[(R,G,B), ...], ...] 从杯底到杯顶，不含空位
    """
    if isinstance(path_or_img, str):
        img = load_image(path_or_img)
    else:
        img = path_or_img

    background_rgb = _detect_background_color(img)
    cups = find_cups(img)
    raw_state = sample_colors(img, cups, background_rgb)
    state = compress_state(raw_state)
    return cups, state


def _detect_background_color(img):
    """从图片四角采样，取最多的颜色作为背景色"""
    h, w = img.shape[:2]
    # 取四角 10x10 区域的颜色
    corners = [
        img[0:10, 0:10],
        img[0:10, w-10:w],
        img[h-10:h, 0:10],
        img[h-10:h, w-10:w],
    ]
    all_pixels = np.concatenate([corner.reshape(-1, 3) for corner in corners])
    # 取出现次数最多的 BGR 值
    unique, counts = np.unique(all_pixels, axis=0, return_counts=True)
    bgr = unique[counts.argmax()]
    return (int(bgr[2]), int(bgr[1]), int(bgr[0]))


def _color_distance(c1, c2):
    """RGB 欧氏距离"""
    return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2) ** 0.5


# === 测试 ===
if __name__ == "__main__":
    bg = _detect_background_color(load_image("live_screenshot.png"))
    print(f"检测到背景色: RGB{bg}")
    cups, state = recognize("live_screenshot.png")
    print(f"找到 {len(cups)} 个杯子:")
    for i, (x, y, w, h) in enumerate(cups):
        print(f"  杯子{i}: pos=({x},{y}) size=({w}x{h})")
    print()
    print(f"状态 (从杯底到杯顶):")
    for i, cup in enumerate(state):
        color_names = []
        for rgb in cup:
            color_names.append(str(rgb))
        print(f"  杯子{i}: {color_names}")
