"""大麦 ADB 坐标点击自动化抢票器"""
import asyncio
import logging
from typing import Any

from platforms.base import PlatformGrabber
from utils.adb import adb_shell, adb_tap, adb_screencap

logger = logging.getLogger(__name__)

DAMAI_ACTIVITY = "cn.damai/.launcher.splash.SplashMainActivity"


class DamaiController(PlatformGrabber):
    @property
    def name(self) -> str:
        return "大麦"

    def __init__(self, cfg: dict, ntp_offset: float = 0.0) -> None:
        super().__init__(cfg, ntp_offset)
        self.device_id: str = cfg.get("device_id", "")
        self.buy_btn: list[int] = cfg.get("buy_btn", [1600, 2650])
        self.confirm_btn: list[int] = cfg.get("confirm_btn", [920, 2500])

    async def _launch_app(self) -> None:
        await adb_shell(
            self.device_id,
            f"am start -n {DAMAI_ACTIVITY}",
        )
        await asyncio.sleep(3)
        logger.info("大麦 App 已启动")

    async def _grab_loop(self) -> dict[str, Any]:
        bx, by = self.buy_btn
        cx, cy = self.confirm_btn

        for attempt in range(60):
            if self.stopped:
                raise asyncio.CancelledError("被协调器停止")

            if attempt % 10 == 0:
                logger.info(f"大麦 第{attempt + 1}次尝试")

            await adb_tap(self.device_id, bx, by)
            await asyncio.sleep(0.15)

            await adb_tap(self.device_id, cx, cy)
            await asyncio.sleep(0.15)

            if attempt > 0 and attempt % 10 == 0:
                try:
                    path = await adb_screencap(
                        self.device_id, "/tmp/damai_check.png"
                    )
                    logger.info(f"大麦 截图保存: {path} (请检查进度)")
                except Exception:
                    pass

        raise RuntimeError("大麦: 达到最大重试次数")

    async def warmup(self) -> None:
        await self._launch_app()
        logger.info(
            f"大麦预热完成 — 请确保已手动登录并进入演出详情页\n"
            f"  购买按钮坐标: {self.buy_btn}\n"
            f"  确认按钮坐标: {self.confirm_btn}\n"
            f"  如需校准，运行: python tools/damai_calibrate.py"
        )

    async def grab(self) -> dict[str, Any]:
        await self.wait_for_sale()
        return await asyncio.wait_for(
            self._grab_loop(), timeout=120
        )
