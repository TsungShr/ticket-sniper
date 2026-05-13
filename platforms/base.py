"""平台抢票器抽象基类"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)


class PlatformGrabber(ABC):
    def __init__(self, cfg: dict, ntp_offset: float = 0.0) -> None:
        self.cfg: dict = cfg
        self.ntp_offset: float = ntp_offset
        self._stop_event: asyncio.Event = asyncio.Event()

    @property
    @abstractmethod
    def name(self) -> str:
        """平台名称，如"票星球" """
        pass

    @abstractmethod
    async def warmup(self) -> None:
        """预热：建立连接、校准坐标、预热资源"""
        pass

    @abstractmethod
    async def grab(self) -> dict:
        """执行抢票，返回 {"success": bool, "platform": str, "order_id": str}"""
        pass

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()

    async def wait_for_sale(self) -> None:
        """等待各自平台的开售时间。各平台独立等待。"""
        sale_time_str = self.cfg.get("sale_time", "")
        if not sale_time_str:
            return
        sale_ts = datetime.strptime(sale_time_str, "%Y-%m-%d %H:%M:%S").timestamp()
        now = time.time() + self.ntp_offset
        remaining = sale_ts - now
        if remaining <= 0:
            logger.info(f"[{self.name}] 开售时间已过，立即开始")
            return
        logger.info(f"[{self.name}] 等待开售: {sale_time_str} (还有 {remaining:.1f}s)")
        if remaining > 0.2:
            await asyncio.sleep(remaining - 0.2)
        while time.time() + self.ntp_offset < sale_ts:
            await asyncio.sleep(0.001)
        logger.info(f"[{self.name}] === 开售！===")
