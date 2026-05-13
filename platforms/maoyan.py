"""猫眼 ADB 自动化抢票器"""
import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from typing import Any

from platforms.base import PlatformGrabber
from utils.adb import AdbSession, adb_find_all, adb_shell

logger = logging.getLogger(__name__)

MAOYAN_ACTIVITY = "com.sankuai.movie/.welcome.Welcome"


class MaoyanController(PlatformGrabber):
    @property
    def name(self) -> str:
        return "猫眼"

    def __init__(self, cfg: dict, ntp_offset: float = 0.0) -> None:
        super().__init__(cfg, ntp_offset)
        self.device_id: str = cfg.get("device_id", "")
        self.session: AdbSession | None = None
        self.buy_pos: tuple[int, int] | None = None
        self.price_pos: tuple[int, int] | None = None
        self.viewer_pos: tuple[int, int] | None = None
        self.submit_pos: tuple[int, int] | None = None
        self._blind_mode: bool = False

        if cfg.get("price_btn"):
            self.price_pos = tuple(cfg["price_btn"])
        if cfg.get("viewer_btn"):
            self.viewer_pos = tuple(cfg["viewer_btn"])
        if cfg.get("submit_btn"):
            self.submit_pos = tuple(cfg["submit_btn"])
        if self.price_pos or self.submit_pos:
            self._blind_mode = True

    async def _launch_app(self) -> None:
        await adb_shell(
            self.device_id,
            f"am start -n {MAOYAN_ACTIVITY}",
        )
        await asyncio.sleep(3)
        logger.info("猫眼 App 已启动")

    async def _fast_find_all(self, texts: list[str]) -> dict[str, tuple[int, int]]:
        """通过持久 ADB session 做 UI dump，比 adb_find_all 快 3-5 倍"""
        found: dict[str, tuple[int, int]] = {}
        if self.session is None:
            return found
        try:
            await self.session.run("uiautomator dump /sdcard/ui_dump.xml")
            xml_str = await self.session.run("cat /sdcard/ui_dump.xml")
            root = ET.fromstring(xml_str)
            for node in root.iter("node"):
                node_text = node.get("text", "")
                node_desc = node.get("content-desc", "")
                for t in texts:
                    if t in found:
                        continue
                    if t in node_text or t in node_desc:
                        bounds = node.get("bounds", "")
                        parts = bounds.replace("][", ",").strip("[]").split(",")
                        if len(parts) == 4:
                            x1, y1, x2, y2 = map(int, parts)
                            found[t] = ((x1 + x2) // 2, (y1 + y2) // 2)
        except ET.ParseError:
            logger.debug("_fast_find_all XML 解析失败")
        except Exception as e:
            logger.debug(f"_fast_find_all 异常: {e}")
        return found

    async def _calibrate(self) -> None:
        """一次性 UI dump 预映射所有按钮坐标"""
        price = str(self.cfg.get("price", ""))
        viewer = self.cfg.get("viewer_name", "")

        targets = ["预约抢票", "立即抢购", "立即购买"]
        if price:
            targets.append(price)
        if viewer:
            targets.append(viewer)

        found = await adb_find_all(self.device_id, targets)

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

    async def _grab_loop_blind(self) -> dict[str, Any]:
        """盲点模式：零 UI dump，纯坐标点击，Phase 2+3 总耗时约 200ms"""
        sess = self.session
        if sess is None or self.buy_pos is None:
            raise RuntimeError("ADB session 或购买按钮坐标未初始化")
        bx, by = self.buy_pos
        t0 = time.time()
        TAP_GAP = 0.05

        logger.info(f"[盲点] Phase 1: 高频点击 ({bx}, {by})")
        for i in range(30):
            if self.stopped:
                raise asyncio.CancelledError("被协调器停止")
            await sess.tap(bx, by)
            await asyncio.sleep(TAP_GAP)

        elapsed_ms = int((time.time() - t0) * 1000)
        logger.info(f"[盲点] Phase 1 完成: 30 次点击 ({elapsed_ms}ms)")

        logger.info("[盲点] Phase 2: 开始盲点序列")
        phase2_start = time.time()

        for wave in range(3):
            if self.price_pos:
                await sess.tap(*self.price_pos)
                await asyncio.sleep(TAP_GAP)

            if self.viewer_pos:
                await sess.tap(*self.viewer_pos)
                await asyncio.sleep(TAP_GAP)

            if self.submit_pos:
                await sess.tap(*self.submit_pos)
                await asyncio.sleep(TAP_GAP)

            if wave < 2:
                await asyncio.sleep(0.3)

        phase2_ms = int((time.time() - phase2_start) * 1000)
        total_ms = int((time.time() - t0) * 1000)
        logger.info(f"[盲点] Phase 2 完成: 3 轮盲点序列 ({phase2_ms}ms), 总耗时 {total_ms}ms")

        if self.submit_pos:
            for _ in range(10):
                await sess.tap(*self.submit_pos)
                await asyncio.sleep(0.1)

        total_ms = int((time.time() - t0) * 1000)
        logger.info(f"[盲点] 全部完成 ({total_ms}ms)，请检查手机是否进入支付页面")
        return {"success": True, "platform": self.name, "order_id": "maoyan_blind"}

    async def _grab_loop_scan(self) -> dict[str, Any]:
        """扫描模式：通过持久 session UI dump 查找按钮"""
        sess = self.session
        if sess is None or self.buy_pos is None:
            raise RuntimeError("ADB session 或购买按钮坐标未初始化")
        price = str(self.cfg.get("price", ""))
        viewer = self.cfg.get("viewer_name", "")
        bx, by = self.buy_pos
        t0 = time.time()

        logger.info(f"[扫描] Phase 1: 高频点击 ({bx}, {by})")
        for i in range(30):
            if self.stopped:
                raise asyncio.CancelledError("被协调器停止")
            await sess.tap(bx, by)
            await asyncio.sleep(0.05)

        logger.info("[扫描] Phase 2: 选择价格/观演人")
        targets = ["提交订单", "支付", "确认"]
        if price:
            targets.append(price)
        if viewer:
            targets.append(viewer)

        for scan in range(8):
            if self.stopped:
                raise asyncio.CancelledError("被协调器停止")

            found = await self._fast_find_all(targets)
            elapsed_ms = int((time.time() - t0) * 1000)
            logger.info(f"[扫描] scan {scan + 1}: {list(found.keys())} ({elapsed_ms}ms)")

            if "支付" in found:
                return {"success": True, "platform": self.name, "order_id": "maoyan_adb"}

            if price and price in found:
                await sess.tap_wait(*found[price])
            if viewer and viewer in found:
                await sess.tap_wait(*found[viewer])
            if "提交订单" in found:
                await sess.tap_wait(*found["提交订单"])
                break
            if "确认" in found:
                await sess.tap_wait(*found["确认"])

            await sess.tap(bx, by)
            await asyncio.sleep(0.3)

        for attempt in range(15):
            if self.stopped:
                raise asyncio.CancelledError("被协调器停止")
            found = await self._fast_find_all(["提交订单", "支付", "确认", "立即支付"])
            if "支付" in found or "立即支付" in found:
                return {"success": True, "platform": self.name, "order_id": "maoyan_adb"}
            if "提交订单" in found:
                await sess.tap_wait(*found["提交订单"])
            elif "确认" in found:
                await sess.tap_wait(*found["确认"])
            else:
                await sess.tap(bx, by)
            await asyncio.sleep(0.2)

        elapsed_ms = int((time.time() - t0) * 1000)
        raise RuntimeError(f"猫眼: 未能完成下单 ({elapsed_ms}ms)")

    async def warmup(self) -> None:
        self.session = AdbSession(self.device_id)
        await self.session.start()

        await self._calibrate()

        if not self.buy_pos:
            logger.warning("未找到购买按钮，尝试启动猫眼 App...")
            await self._launch_app()
            await self._calibrate()

        if self.buy_pos:
            if self._blind_mode:
                logger.info(
                    f"猫眼预热完成 — 盲点模式\n"
                    f"  购买按钮: {self.buy_pos}\n"
                    f"  票价坐标: {self.price_pos}\n"
                    f"  观演人坐标: {self.viewer_pos}\n"
                    f"  提交坐标: {self.submit_pos}"
                )
            else:
                logger.info(
                    "猫眼预热完成 — 扫描模式"
                    "（未校准，建议运行 python tools/maoyan_calibrate.py）"
                )
        else:
            logger.warning(
                "猫眼预热完成 — 未标定坐标，请手动导航到演出详情页后重启"
            )

    async def grab(self) -> dict[str, Any]:
        await self.wait_for_sale()
        try:
            if self._blind_mode:
                logger.info("=== 猫眼: 使用盲点模式 ===")
                return await asyncio.wait_for(
                    self._grab_loop_blind(), timeout=120
                )
            else:
                logger.info("=== 猫眼: 使用扫描模式 ===")
                return await asyncio.wait_for(
                    self._grab_loop_scan(), timeout=120
                )
        finally:
            if self.session:
                await self.session.close()
