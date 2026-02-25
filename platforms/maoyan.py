import asyncio
import logging
import time

from platforms.base import PlatformGrabber
from utils.adb import AdbSession, adb_shell, adb_find_all

logger = logging.getLogger(__name__)

MAOYAN_ACTIVITY = "com.sankuai.movie/.welcome.Welcome"


class MaoyanController(PlatformGrabber):
    @property
    def name(self) -> str:
        return "猫眼"

    def __init__(self, cfg: dict, ntp_offset: float = 0.0):
        super().__init__(cfg, ntp_offset)
        self.device_id = cfg.get("device_id", "")
        self.session: AdbSession | None = None
        # Pre-calibrated coordinates
        self.buy_pos: tuple[int, int] | None = None
        self.price_pos: tuple[int, int] | None = None
        self.viewer_pos: tuple[int, int] | None = None

    async def _launch_app(self) -> None:
        await adb_shell(
            self.device_id,
            f"am start -n {MAOYAN_ACTIVITY}",
        )
        await asyncio.sleep(3)
        logger.info("猫眼 App 已启动")

    async def _calibrate(self) -> None:
        """One-time UI dump to pre-map all button coordinates."""
        price = str(self.cfg.get("price", ""))
        viewer = self.cfg.get("viewer_name", "")

        targets = ["预约抢票", "立即抢购", "立即购买"]
        if price:
            targets.append(price)
        if viewer:
            targets.append(viewer)

        found = await adb_find_all(self.device_id, targets)

        # Buy button — use whichever is visible
        for btn in ("立即抢购", "立即购买", "预约抢票"):
            if btn in found:
                self.buy_pos = found[btn]
                logger.info(f"购买按钮 [{btn}]: {self.buy_pos}")
                break

        if price and price in found:
            self.price_pos = found[price]
            logger.info(f"价格档位 [¥{price}]: {self.price_pos}")

        if viewer and viewer in found:
            self.viewer_pos = found[viewer]
            logger.info(f"观演人 [{viewer}]: {self.viewer_pos}")

    async def _grab_loop(self) -> dict:
        sess = self.session
        price = str(self.cfg.get("price", ""))
        viewer = self.cfg.get("viewer_name", "")

        if not self.buy_pos:
            raise RuntimeError("猫眼: 未标定购买按钮坐标，请在演出详情页重新 warmup")

        bx, by = self.buy_pos
        t0 = time.time()

        # ── Phase 1: 高频点击购买按钮 ──
        logger.info(f"Phase 1: 高频点击购买按钮 ({bx}, {by})")
        for i in range(100):
            if self.stopped:
                raise asyncio.CancelledError("被协调器停止")
            await sess.tap(bx, by)
            await asyncio.sleep(0.05)  # 50ms interval

            # Every 20 taps (~1s), log progress
            if (i + 1) % 20 == 0:
                elapsed_ms = int((time.time() - t0) * 1000)
                logger.info(f"Phase 1: 已点击 {i + 1} 次 ({elapsed_ms}ms)")

        # ── Phase 2: 选价格 + 选观演人 ──
        logger.info("Phase 2: 选择价格/观演人")
        # Re-calibrate after page transition
        targets = ["提交订单", "支付"]
        if price:
            targets.append(price)
        if viewer:
            targets.append(viewer)

        found = await adb_find_all(self.device_id, targets)

        if "支付" in found:
            logger.info("=== 猫眼: 已进入支付页面 ===")
            return {"success": True, "platform": self.name, "order_id": "maoyan_adb"}

        if price and price in found:
            cx, cy = found[price]
            await sess.tap_wait(cx, cy)
            logger.info(f"已选价格 ¥{price}")

        if viewer and viewer in found:
            cx, cy = found[viewer]
            await sess.tap_wait(cx, cy)
            logger.info(f"已选观演人 {viewer}")

        # ── Phase 3: 提交订单 ──
        # Re-scan for submit button (might need viewer/price selected first)
        for attempt in range(10):
            if self.stopped:
                raise asyncio.CancelledError("被协调器停止")

            found = await adb_find_all(self.device_id, ["提交订单", "支付"])

            if "支付" in found:
                logger.info("=== 猫眼: 已进入支付页面 ===")
                return {"success": True, "platform": self.name, "order_id": "maoyan_adb"}

            if "提交订单" in found:
                cx, cy = found["提交订单"]
                await sess.tap_wait(cx, cy)
                logger.info(f"=== 猫眼: 已点击提交订单 (attempt {attempt + 1}) ===")
                await asyncio.sleep(0.3)
                continue

            # Nothing found, try tapping buy again
            await sess.tap(bx, by)
            await asyncio.sleep(0.3)

        elapsed_ms = int((time.time() - t0) * 1000)
        raise RuntimeError(f"猫眼: 未能完成下单 ({elapsed_ms}ms)")

    async def warmup(self) -> None:
        # Open persistent shell
        self.session = AdbSession(self.device_id)
        await self.session.start()

        # Try calibrating on current screen first (user should be on detail page)
        await self._calibrate()

        if not self.buy_pos:
            # Not on detail page — launch app and let user navigate
            logger.warning("未找到购买按钮，尝试启动猫眼 App...")
            await self._launch_app()
            await self._calibrate()

        if self.buy_pos:
            logger.info("猫眼预热完成 — 坐标已标定")
        else:
            logger.warning("猫眼预热完成 — 未标定坐标，请手动导航到演出详情页后重启")

    async def grab(self) -> dict:
        await self.wait_for_sale()
        try:
            return await asyncio.wait_for(self._grab_loop(), timeout=120)
        finally:
            if self.session:
                await self.session.close()
