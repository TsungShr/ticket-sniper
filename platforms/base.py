import asyncio
from abc import ABC, abstractmethod


class PlatformGrabber(ABC):
    def __init__(self, config: dict):
        self.config = config
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
