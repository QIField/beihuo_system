import pygame
import math
import sys
import ctypes
import ctypes.wintypes
import random
import time
import numpy as np
from collections import deque

# ==================== 调试工具 ====================
DEBUG = True
def dbg(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}", flush=True)

# ==================== Windows API 常量与结构体 ====================
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TOPMOST = 0x8
WS_EX_TOOLWINDOW = 0x80
WS_EX_TRANSPARENT = 0x20
LWA_COLORKEY = 0x1

class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", ctypes.c_bool),
        ("xHotspot", ctypes.wintypes.DWORD),
        ("yHotspot", ctypes.wintypes.DWORD),
        ("hbmMask", ctypes.wintypes.HBITMAP),
        ("hbmColor", ctypes.wintypes.HBITMAP),
    ]

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

# ==================== DPI 感知 ====================
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    dbg("DPI Awareness: Per-Monitor V2 设置成功")
except Exception as e:
    dbg(f"DPI Awareness 设置失败: {e}")

# ==================== Pygame 初始化 ====================
pygame.init()
info = pygame.display.Info()
W, H = info.current_w, info.current_h
dbg(f"屏幕分辨率: {W}x{H}")

screen = pygame.display.set_mode((W, H), pygame.NOFRAME | pygame.RESIZABLE)
pygame.display.set_caption("Aim Trainer - Smooth Tracking")

# ==================== 窗口样式设置 ====================
hwnd = pygame.display.get_wm_info()['window']
old_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
new_style = old_style | WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT
result = user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
layered_result = user32.SetLayeredWindowAttributes(hwnd, 0x000000, 255, LWA_COLORKEY)
dbg(f"HWND: {hwnd:#x}")
dbg(f"新窗口样式: {new_style:#010x} (含 TRANSPARENT={bool(new_style & WS_EX_TRANSPARENT)})")
dbg(f"SetWindowLongW 返回值: {result:#010x}")
if not (new_style & WS_EX_TRANSPARENT):
    dbg("⚠️ 警告: WS_EX_TRANSPARENT 未成功应用！")
else:
    dbg("✅ WS_EX_TRANSPARENT 已生效，窗口对鼠标完全穿透")

# ==================== 颜色与尺寸常量 ====================
BLACK = (0, 0, 0)
BALL_COLOR_DEFAULT = (107, 142, 35)
BALL_COLOR_HOVER = (65, 105, 225)
CURSOR_COLOR = (220, 50, 50)
CURSOR_RADIUS = 8
BALL_RADIUS = 30

VALORANT_SENSITIVITY = 0.65
WARMUP_SEC = 3.0
PRACTICE_SEC = 60.0
BUFFER_ZONE_RATIO = 0.20


# ==================== 获取系统鼠标位置 ====================
def get_system_mouse_pos():
    """
    通过 Win32 API 获取鼠标位置。
    WS_EX_TRANSPARENT 会导致 pygame.mouse.get_pos() 失效，
    必须使用 GetCursorPos 直接从系统读取。
    """
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


# ==================== Win32 硬件光标生成 ====================
def create_win32_red_circle_cursor(radius=8, color=(220, 50, 50)):
    size = radius * 2 + 2
    hotspot = size // 2

    and_mask = gdi32.CreateBitmap(size, size, 1, 1, None)

    screen_dc = user32.GetDC(None)
    xor_mask = gdi32.CreateCompatibleBitmap(screen_dc, size, size)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    user32.ReleaseDC(None, screen_dc)

    old_bmp = gdi32.SelectObject(mem_dc, xor_mask)

    brush = gdi32.CreateSolidBrush(color[0] | (color[1] << 8) | (color[2] << 16))
    old_brush = gdi32.SelectObject(mem_dc, brush)
    pen = gdi32.GetStockObject(5)  # NULL_PEN
    old_pen = gdi32.SelectObject(mem_dc, pen)

    gdi32.Ellipse(mem_dc, 0, 0, size, size)

    gdi32.SelectObject(mem_dc, old_pen)
    gdi32.SelectObject(mem_dc, old_brush)
    gdi32.DeleteObject(brush)
    gdi32.SelectObject(mem_dc, old_bmp)
    gdi32.DeleteDC(mem_dc)

    icon_info = ICONINFO()
    icon_info.fIcon = False
    icon_info.xHotspot = hotspot
    icon_info.yHotspot = hotspot
    icon_info.hbmMask = and_mask
    icon_info.hbmColor = xor_mask

    cursor_handle = user32.CreateIconIndirect(ctypes.byref(icon_info))

    gdi32.DeleteObject(and_mask)
    gdi32.DeleteObject(xor_mask)

    if not cursor_handle:
        raise RuntimeError(f"CreateIconIndirect 失败, GetLastError={ctypes.get_last_error()}")

    dbg(f"Win32 硬件光标创建成功: handle={cursor_handle:#x}, {size}x{size}px")
    return cursor_handle


# ==================== 数据分析器 ====================
class MouseAnalyzer:
    def __init__(self, sample_rate=144):
        self.sample_rate = sample_rate
        self.buffer = deque()
        self.hover_frames = 0
        self.total_frames = 0

    def record(self, mx, my, ball_pos, hovered):
        self.buffer.append((time.perf_counter(), mx, my, *ball_pos, hovered))
        self.total_frames += 1
        if hovered:
            self.hover_frames += 1

    def analyze(self):
        if len(self.buffer) < 30:
            dbg(f"⚠️ 数据不足: buffer={len(self.buffer)}, 需要>=30")
            return None

        data = np.array(self.buffer)
        timestamps = data[:, 0]
        mouse_xy = data[:, 1:3].astype(float)
        ball_xy = data[:, 3:5].astype(float)

        diffs = np.diff(mouse_xy, axis=0)
        path_length = np.sum(np.linalg.norm(diffs, axis=1))
        straight_dist = np.linalg.norm(mouse_xy[-1] - mouse_xy[0])
        path_efficiency = straight_dist / max(path_length, 1e-6)

        dt = np.diff(timestamps)
        velocity = np.linalg.norm(diffs, axis=1) / np.maximum(dt, 1e-9)
        acceleration = np.diff(velocity) / np.maximum(dt[:-1], 1e-9)
        jitter_ratio = np.std(acceleration) / max(np.mean(velocity), 1e-6)

        mouse_centered = mouse_xy - mouse_xy.mean(axis=0)
        ball_centered = ball_xy - ball_xy.mean(axis=0)
        corr = np.correlate(mouse_centered[:, 0], ball_centered[:, 0], mode='full')
        lag_idx = np.argmax(corr) - (len(mouse_xy) - 1)
        avg_dt = np.mean(dt) if len(dt) > 0 else 1 / self.sample_rate
        lag_ms = abs(lag_idx * avg_dt * 1000)

        hover_ratio = self.hover_frames / max(self.total_frames, 1)

        noise_energy = 0.0
        if len(velocity) >= 64:
            fft_mag = np.abs(np.fft.rfft(velocity - np.mean(velocity)))
            freqs = np.fft.rfftfreq(len(velocity), d=avg_dt)
            high_freq_mask = freqs > 20.0
            noise_energy = np.sum(fft_mag[high_freq_mask] ** 2) / max(np.sum(fft_mag ** 2), 1e-12)

        report = {
            'path_efficiency': float(path_efficiency),
            'jitter_ratio': float(jitter_ratio),
            'lag_ms': float(lag_ms),
            'hover_ratio': float(hover_ratio),
            'noise_energy': float(noise_energy),
            'hand_relaxed': path_efficiency > 0.6 and jitter_ratio < 1.0 and noise_energy < 0.10,
            'aim_precise': hover_ratio > 0.60 and lag_ms < 80
        }
        dbg(f"分析完成: samples={len(self.buffer)}, hover_frames={self.hover_frames}")
        return report


# ==================== 游走小球（平滑追踪版） ====================
class WanderingBall:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.radius = BALL_RADIUS
        self.margin = self.radius + 2

        buffer_size = min(w, h) * BUFFER_ZONE_RATIO
        self.buf_left = buffer_size
        self.buf_right = w - buffer_size
        self.buf_top = buffer_size
        self.buf_bottom = h - buffer_size
        self.buffer_size = buffer_size

        # 基础振幅仅决定活动范围，不再决定瞬时速度
        sens_scale = VALORANT_SENSITIVITY / 0.35
        base_amp_x = 80 * sens_scale
        base_amp_y = 60 * sens_scale * (h / w)
        amp_weights = [1.8, 0.5, 0.1]
        self.amp_x = [base_amp_x * wt * random.uniform(0.90, 1.10) for wt in amp_weights]
        self.amp_y = [base_amp_y * wt * random.uniform(0.90, 1.10) for wt in amp_weights]

        phi = 1.6180339887
        self.freq_x = [0.31, 0.31 * phi, 0.31 * phi * phi]
        self.freq_y = [0.23, 0.23 * math.sqrt(2), 0.23 * math.e / 2]
        self.phase_x = [random.uniform(0, math.tau) for _ in range(3)]
        self.phase_y = [random.uniform(0, math.tau) for _ in range(3)]

        # 【关键】独立的速度控制系统
        self.base_speed = 3.0       # 基础速率标量
        self.min_speed_mult = 0.6   # 最低速度倍率 → 3.0*0.6=1.8，永不接近停止
        self.max_speed_mult = 1.8   # 最高速度倍率

        # X/Y 轴各自独立的速度噪声种子，确保直线段两轴速度变化不同步
        self.vx_noise_seed = random.random() * 1000
        self.vy_noise_seed = random.random() * 1000

        # 脉冲系统：作用于速度向量而非相位
        self.pulse_timer = 0.0
        self.pulse_interval = random.uniform(0.2, 0.6)
        self.pulse_vx = 0.0
        self.pulse_vy = 0.0

        self.elapsed = 0.0
        dbg(f"WanderingBall v3: 速度-位置解耦 | base={self.base_speed} | range=[{self.base_speed*self.min_speed_mult:.1f}, {self.base_speed*self.max_speed_mult:.1f}]")

    def _axis_speed_noise(self, t: float) -> float:
        """生成单轴速度噪声，返回值域约 [-0.4, +0.6]"""
        return (
            0.25 * math.sin(t * 1.1) * math.cos(t * 1.7) +
            0.20 * math.sin(t * 2.9 + 0.8) * math.cos(t * 0.6) +
            0.15 * math.sin(t * 4.3 + 2.1)
        )

    def update(self, dt_sec):
        self.elapsed += dt_sec

        # === 1. 计算全局速率标量（含脉冲）===
        self.pulse_timer += dt_sec
        if self.pulse_timer >= self.pulse_interval:
            self.pulse_timer = 0.0
            self.pulse_interval = random.uniform(0.15, 0.55)
            angle = random.uniform(0, math.tau)
            strength = random.uniform(0.5, 1.5)
            self.pulse_vx = math.cos(angle) * strength
            self.pulse_vy = math.sin(angle) * strength

        decay = math.exp(-dt_sec * 15.0)
        self.pulse_vx *= decay
        self.pulse_vy *= decay

        # === 2. 各轴独立速度噪声（使用独立的 seed）===
        vx_noise = self._axis_speed_noise(self.elapsed + self.vx_noise_seed)
        vy_noise = self._axis_speed_noise(self.elapsed + self.vy_noise_seed)

        # === 3. 合成各轴实际速度倍率 ===
        raw_vx_mult = self.base_speed * (1.0 + vx_noise) + self.pulse_vx
        raw_vy_mult = self.base_speed * (1.0 + vy_noise) + self.pulse_vy

        # 钳制到安全范围，保证永不停止
        min_s = self.base_speed * self.min_speed_mult
        max_s = self.base_speed * self.max_speed_mult
        
        # 保留符号的同时限制绝对值在 [min_s, max_s] 之间
        vx_mult = max(min_s, min(max_s, abs(raw_vx_mult))) * (1 if raw_vx_mult >= 0 else -1)
        vy_mult = max(min_s, min(max_s, abs(raw_vy_mult))) * (1 if raw_vy_mult >= 0 else -1)

        # === 4. 用独立速度驱动相位（解耦的核心）===
        for i in range(3):
            self.phase_x[i] += self.freq_x[i] * vx_mult * dt_sec
            self.phase_y[i] += self.freq_y[i] * vy_mult * dt_sec

    def get_pos(self):
        raw_x = self.w / 2 + sum(a * math.sin(p) for a, p in zip(self.amp_x, self.phase_x))
        raw_y = self.h / 2 + sum(a * math.sin(p) for a, p in zip(self.amp_y, self.phase_y))
        x, y = raw_x, raw_y

        if x < self.buf_left:
            push = min(1.0, (self.buf_left - x) / self.buffer_size) ** 2
            x += push * self.buffer_size * 0.8
        elif x > self.buf_right:
            push = min(1.0, (x - self.buf_right) / self.buffer_size) ** 2
            x -= push * self.buffer_size * 0.8
        if y < self.buf_top:
            push = min(1.0, (self.buf_top - y) / self.buffer_size) ** 2
            y += push * self.buffer_size * 0.8
        elif y > self.buf_bottom:
            push = min(1.0, (y - self.buf_bottom) / self.buffer_size) ** 2
            y -= push * self.buffer_size * 0.8

        x = max(self.margin, min(self.w - self.margin, x))
        y = max(self.margin, min(self.h - self.margin, y))
        return (int(x), int(y))

    def is_hovered(self, mouse_pos):
        bx, by = self.get_pos()
        return math.hypot(mouse_pos[0] - bx, mouse_pos[1] - by) <= self.radius

# ==================== 报告打印 ====================
def print_report(report):
    print("\n" + "=" * 40)
    print("     60秒平滑追踪训练分析报告")
    print("=" * 40)
    print(f"  路径效率: {report['path_efficiency']:.3f}  {'✅ 放松' if report['path_efficiency'] > 0.6 else '⚠️ 紧张'}")
    print(f"  速度抖动: {report['jitter_ratio']:.3f}  {'✅ 平滑' if report['jitter_ratio'] < 1.0 else '⚠️ 颤抖'}")
    print(f"  滞后时间: {report['lag_ms']:.1f}ms   {'✅ 及时' if report['lag_ms'] < 80 else '⚠️ 迟缓'}")
    print(f"  悬停驻留: {report['hover_ratio']:.3f}  {'✅ 精准' if report['hover_ratio'] > 0.60 else '⚠️ 不稳'}")
    print(f"  高频噪声: {report['noise_energy']:.3f}  {'✅ 干净' if report['noise_energy'] < 0.10 else '⚠️ 震颤'}")
    print("-" * 40)
    relaxed = "✅ 手部放松" if report['hand_relaxed'] else "❌ 手部紧张"
    precise = "✅ 瞄准精准" if report['aim_precise'] else "❌ 精准度不足"
    print(f"  综合评估: {relaxed} | {precise}")
    print("=" * 40 + "\n")


# ==================== 主程序入口 ====================
if __name__ == "__main__":
    win32_cursor_handle = None
    original_cursor = None

    try:
        win32_cursor_handle = create_win32_red_circle_cursor(CURSOR_RADIUS, CURSOR_COLOR)
        original_cursor = user32.SetCursor(win32_cursor_handle)
        pygame.mouse.set_visible(True)
        dbg("✅ Win32 硬件红色光标已激活")
        USE_SOFTWARE_CURSOR = False
    except Exception as e:
        dbg(f"⚠️ Win32 硬件光标创建失败: {e}，回退到软件绘制")
        pygame.mouse.set_visible(False)
        USE_SOFTWARE_CURSOR = True

    ball = WanderingBall(W, H)
    analyzer = MouseAnalyzer()
    clock = pygame.time.Clock()
    running = True
    start_time = time.perf_counter()
    practice_started = False
    frame_count = 0
    fps_log_interval = 144

    dbg(f"主循环启动 | 预热:{WARMUP_SEC}s | 练习:{PRACTICE_SEC}s | 软件光标:{USE_SOFTWARE_CURSOR}")

    try:
        while running:
            dt_ms = clock.tick(144)
            dt_sec = dt_ms / 1000.0
            elapsed = time.perf_counter() - start_time
            frame_count += 1

            if frame_count % fps_log_interval == 0:
                fps = clock.get_fps()
                phase = "预热" if elapsed < WARMUP_SEC else ("练习" if elapsed < WARMUP_SEC + PRACTICE_SEC else "结束")
                dbg(f"帧:{frame_count} | FPS:{fps:.1f} | 经过:{elapsed:.1f}s | 阶段:{phase} | buffer:{len(analyzer.buffer)}")

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    dbg("收到 QUIT 事件")
                    running = False
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_F12, pygame.K_ESCAPE):
                    dbg(f"收到退出按键: {pygame.key.name(event.key)}")
                    running = False

            mx, my = get_system_mouse_pos()
            pos = ball.get_pos()
            hovered = ball.is_hovered((mx, my))

            screen.fill(BLACK)

            if elapsed < WARMUP_SEC:
                pygame.draw.circle(screen, BALL_COLOR_DEFAULT, (W // 2, H // 2), BALL_RADIUS)
            elif elapsed < WARMUP_SEC + PRACTICE_SEC:
                if not practice_started:
                    practice_started = True
                    ball = WanderingBall(W, H)
                    dbg("✅ 进入练习阶段，小球已重置(平滑模式)")
                ball.update(dt_sec)
                analyzer.record(mx, my, pos, hovered)
                color = BALL_COLOR_HOVER if hovered else BALL_COLOR_DEFAULT
                pygame.draw.circle(screen, color, pos, BALL_RADIUS)
            else:
                dbg("⏱️ 练习时间到，准备退出")
                running = False

            if USE_SOFTWARE_CURSOR:
                pygame.draw.circle(screen, CURSOR_COLOR, (mx, my), CURSOR_RADIUS)

            pygame.display.flip()

    except Exception as e:
        import traceback
        print(f"\n[ERROR] 主循环异常崩溃:")
        traceback.print_exc()

    finally:
        dbg("正在清理资源...")
        if original_cursor:
            user32.SetCursor(original_cursor)
        if win32_cursor_handle:
            user32.DestroyIcon(win32_cursor_handle)
        pygame.mouse.set_visible(True)
        dbg("✅ 系统光标已恢复")
        pygame.quit()

        report = analyzer.analyze()
        if report:
            print_report(report)
        else:
            print("⚠️ 有效数据不足，无法生成分析报告")
        sys.exit()