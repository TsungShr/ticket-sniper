#!/usr/bin/env python3
"""
taobao_checkout.py  —  毫秒级购物车结算
策略：
  1. NTP 校时，算出本机时钟偏差
  2. 开一个持久 adb shell 长连接（写命令 <1ms，无进程 spawn 开销）
  3. 在开售时刻 T - TAP_LEAD_MS 前开始发送 tap 命令
     → tap 到达 Android 系统的时刻 ≈ T + 0
  4. 持续发送 MAX_SEC 秒，直到检测到进入订单页

用法:
    python3 tools/taobao_checkout.py
"""
import subprocess, time, datetime, sys, threading, os
from pathlib import Path

import ntplib

from utils.ntp_sync import NTP_SERVERS, corrected_time, hms_to_next_ts

# ==================== 配置 ====================
# 设备 ID 通过 ADB_DEVICES 环境变量指定，优先读取；
# 空则尝试第一个在线设备。
ADB_DEVICES_ENV = os.environ.get("ADB_DEVICES", "").strip()

CX, CY   = 1655, 2628          # 结算按钮坐标（1840×2800 实测）
PAY_X, PAY_Y = 918, 2743      # 立即支付按钮坐标（确认订单页底部）

DAILY_TIMES = ["14:00:00", "20:00:00"]
SINGLE_TIME = ""               # 留空用 DAILY_TIMES → 自动选 20:00

TAP_LEAD_MS  = 55              # 提前多少毫秒开始发，让 tap 准时落地
TAP_BURST    = 30              # 到点后连续发多少次
TAP_GAP_MS   = 8               # 每次间隔（ms），持久 shell 下这是真实间隔
MAX_SEC      = 12              # 最多冲多少秒

SUCCESS_HINTS = ["提交订单", "确认订单", "实付款", "收货地址"]
# ==============================================


def _resolve_device() -> str:
    """从环境变量 → config.yaml → 自动检测 的顺序解析设备 ID"""
    if ADB_DEVICES_ENV:
        return ADB_DEVICES_ENV

    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        import yaml, os
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        # 依次检查各平台配置中的 device_id
        for platform in ("maoyan", "damai", "taobao"):
            did = cfg.get(platform, {}).get("device_id", "")
            if did:
                return did

    # Fallback: 自动取第一个在线设备
    out = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout
    lines = [l.strip() for l in out.strip().splitlines() if "\tdevice" in l]
    if lines:
        return lines[0].split()[0]
    return ""


# ── NTP 校时 ──────────────────────────────────
def get_ntp_offset() -> float:
    client = ntplib.NTPClient()
    offsets = []
    for srv in NTP_SERVERS:
        for _ in range(3):
            try:
                r = client.request(srv, version=3)
                offsets.append(r.offset)
            except Exception:
                pass
        if len(offsets) >= 5:
            break
    if not offsets:
        print("[NTP] 所有服务器不可达，使用本机时间（可能有偏差）")
        return 0.0
    offsets.sort()
    median = offsets[len(offsets) // 2]
    print(f"[NTP] 采样 {len(offsets)} 次，本机偏差 {median*1000:+.1f}ms")
    return median


# ── 时间工具 ──────────────────────────────────
def get_next_sale_ts() -> float:
    if SINGLE_TIME:
        return datetime.datetime.strptime(SINGLE_TIME, "%Y-%m-%d %H:%M:%S").timestamp()
    return min(hms_to_next_ts(t) for t in DAILY_TIMES)


def _now() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]


# ── 持久 ADB shell ────────────────────────────
class PersistentShell:
    def __init__(self, device: str):
        self._proc = subprocess.Popen(
            ["adb", "-s", device, "shell"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def send(self, cmd: str):
        """Fire-and-forget：写入 stdin，<1ms 返回"""
        try:
            self._proc.stdin.write((cmd + "\n").encode())
            self._proc.stdin.flush()
        except BrokenPipeError:
            pass

    def close(self):
        try:
            self._proc.terminate()
        except Exception:
            pass


# ── 订单页检测（后台线程）────────────────────────
# 用截图 + 像素颜色判断，比 uiautomator dump 快 5~10 倍
# 「确认订单」页：顶部导航栏背景是白色，标题文字区颜色特征
# 快速判断：检查页面顶部中间区域是否出现「立即支付」橙色按钮
_order_detected = threading.Event()

def _checker_thread(device: str, earliest_ts: float = 0):
    """
    每次检测流程：
      1. screencap 截图到内存（不写文件，更快）
      2. 用 adb exec-out 直接拉 PNG 字节
      3. 检查页面底部是否出现橙色支付按钮（RGB≈238,96,44）
         或用 uiautomator 做文字兜底
    """
    import io
    try:
        from PIL import Image
        import numpy as np
        USE_PIXEL = True
    except ImportError:
        USE_PIXEL = False

    while not _order_detected.is_set():
        time.sleep(0.12)
        # 未到最早生效时间，跳过检测（防止旧订单页误触发）
        if earliest_ts and time.time() < earliest_ts:
            continue
        try:
            if USE_PIXEL:
                # 直接拉截图字节，不落磁盘
                raw = subprocess.run(
                    ["adb", "-s", device, "exec-out", "screencap", "-p"],
                    capture_output=True, timeout=3
                ).stdout
                if not raw:
                    continue
                img = Image.open(io.BytesIO(raw))
                arr = np.array(img)
                # 检查底部区域 (y=2690~2790) 是否出现「立即支付」按钮颜色
                # 未开售时: 淡橙 RGB≈(242,180,136)；已开售: 亮橙 RGB≈(238,96,44)
                # 购物车背景: 蓝灰 RGB≈(243,246,248) → R≈G≈B（排除）
                region = arr[2690:2790, 100:1740, :3]
                r, g, b = region[:,:,0].astype(int), region[:,:,1].astype(int), region[:,:,2].astype(int)
                # 条件：R 明显大于 B（暖色调），且 G < R-30（非灰色）
                warm = (r - b > 50) & (r - g > 20) & (r > 180)
                if warm.sum() > 800:  # 足够多的暖色像素
                    _order_detected.set()
            else:
                # fallback: uiautomator
                r = subprocess.run(
                    ["adb", "-s", device, "shell",
                     "uiautomator dump /sdcard/chk.xml && cat /sdcard/chk.xml"],
                    capture_output=True, text=True, timeout=4
                )
                if any(h in r.stdout for h in SUCCESS_HINTS):
                    _order_detected.set()
        except Exception:
            pass


# ── 主流程 ────────────────────────────────────
def main():
    # 检查设备
    device = _resolve_device()
    if not device:
        print("错误：未找到可用设备，请连接 Android 设备或配置 device_id")
        sys.exit(1)

    out = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout
    if device not in out:
        print(f"错误：设备 {device} 未连接"); sys.exit(1)

    ntp_offset = get_ntp_offset()
    sale_ts = get_next_sale_ts()
    sale_str = datetime.datetime.fromtimestamp(sale_ts).strftime("%Y-%m-%d %H:%M:%S")

    print(f"[{_now()}] 目标开售: {sale_str}")
    print(f"[{_now()}] 结算坐标: ({CX}, {CY})")
    print(f"[{_now()}] 提前发射: {TAP_LEAD_MS}ms  连射: {TAP_BURST}次 每{TAP_GAP_MS}ms")
    print(f"[{_now()}] 请确认购物车页在前台，目标商品已勾选")

    # 等到开售前 5 秒再建连接（避免长时间空闲断开）
    delta = sale_ts - corrected_time(ntp_offset)
    if delta > 6:
        print(f"[{_now()}] 等待 {delta:.0f}s ...")
        time.sleep(delta - 5)

    print(f"[{_now()}] 建立持久 shell 连接...")
    shell = PersistentShell(device)
    time.sleep(0.3)  # 让连接稳定

    # 发射前确保在购物车页（back 回去）
    print(f"[{_now()}] 检查页面状态...")
    subprocess.run(["adb", "-s", device, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=3)  # BACK 键
    time.sleep(0.5)

    # 启动后台检测线程，设最早生效时间为 T+0.3s（防止旧页面误触发）
    _order_detected.clear()
    _detect_start_ts = sale_ts + 0.3   # 开售后至少 300ms 才开始接受检测
    t = threading.Thread(target=_checker_thread, args=(device, _detect_start_ts), daemon=True)
    t.start()

    # 精确等待到 T - TAP_LEAD_MS
    fire_ts = sale_ts - TAP_LEAD_MS / 1000.0
    while corrected_time(ntp_offset) < fire_ts:
        time.sleep(0.001)

    print(f"[{_now()}] *** 发射！***")
    t0 = time.time()

    # 连射 TAP_BURST 次
    for i in range(TAP_BURST):
        shell.send(f"input tap {CX} {CY}")
        t_ms = int((time.time() - t0) * 1000)
        print(f"  发射 #{i+1:3d}  t0+{t_ms}ms", end="\r")
        time.sleep(TAP_GAP_MS / 1000.0)

        if _order_detected.is_set():
            break

    # 继续等检测结果（最多 MAX_SEC 秒）
    deadline = t0 + MAX_SEC
    print()
    while time.time() < deadline:
        if _order_detected.is_set():
            elapsed = int((time.time() - t0) * 1000)
            print(f"[{_now()}] ✅ 进入订单页！耗时 {elapsed}ms，立即点「立即支付」...")
            # 连点立即支付按钮，确保命中
            for _ in range(5):
                shell.send(f"input tap {PAY_X} {PAY_Y}")
                time.sleep(0.06)
            subprocess.run(
                ["adb", "-s", device, "shell", "cmd", "vibrator", "vibrate", "600"],
                capture_output=True, timeout=3
            )
            print(f"[{_now()}] 已点击「立即支付」，请在平板上完成指纹/密码支付！")
            shell.close()
            return True
        # 到点后继续补射
        shell.send(f"input tap {CX} {CY}")
        time.sleep(0.08)

    print(f"[{_now()}] ⚠️  {MAX_SEC}s 内未检测到订单页，请查看平板屏幕")
    shell.close()
    return False


if __name__ == "__main__":
    while True:
        ok = main()
        if ok:
            break
        ans = input("\n本轮结束，继续守候下一场？(y/n): ").strip().lower()
        if not ans.startswith("y"):
            break
