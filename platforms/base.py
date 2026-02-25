import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)


class PlatformGrabber(ABC):
    def __init__(self, cfg: dict, ntp_offset: float = 0.0):
        self.cfg = cfg
        self.ntp_offset = ntp_offset
        self._stop_event = asyncio.Event()

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def warmup(self) -> None:
        pass

    @abstractmethod
    async def grab(self) -> dict:
        pass

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()

    async def wait_for_sale(self) -> None:
        """Wait until this platform's own sale_time. Each platform waits independently."""
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
        # Coarse wait — sleep until 200ms before sale
        if remaining > 0.2:
            await asyncio.sleep(remaining - 0.2)
        # Busy-wait for precision
        while time.time() + self.ntp_offset < sale_ts:
            await asyncio.sleep(0.001)
        logger.info(f"[{self.name}] === 开售！===")
