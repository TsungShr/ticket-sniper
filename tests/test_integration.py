import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from platforms.base import PlatformGrabber


class MockPXQ(PlatformGrabber):
    name = "票星球"
    async def warmup(self): pass
    async def grab(self):
        await asyncio.sleep(0.1)
        return {"success": True, "platform": "票星球", "order_id": "pxq_001"}


class MockMaoyan(PlatformGrabber):
    name = "猫眼"
    async def warmup(self): pass
    async def grab(self):
        await asyncio.sleep(999)


class MockDamai(PlatformGrabber):
    name = "大麦"
    async def warmup(self): pass
    async def grab(self):
        await asyncio.sleep(999)


class MockFail(PlatformGrabber):
    def __init__(self, config, pname):
        super().__init__(config)
        self._name = pname
    @property
    def name(self): return self._name
    async def warmup(self): pass
    async def grab(self):
        raise RuntimeError(f"{self._name} failed")


@pytest.mark.asyncio
async def test_full_flow_pxq_success():
    from main import run_orchestrator
    with patch("main.notify", new_callable=AsyncMock):
        result = await run_orchestrator(
            grabbers=[MockPXQ({}), MockMaoyan({}), MockDamai({})],
            sale_timestamp=0,
            ntp_offset=0,
            notify_config={},
        )
    assert result["success"] is True
    assert result["platform"] == "票星球"
    assert result["order_id"] == "pxq_001"


@pytest.mark.asyncio
async def test_all_fail():
    from main import run_orchestrator
    with patch("main.notify", new_callable=AsyncMock):
        result = await run_orchestrator(
            grabbers=[MockFail({}, "票星球"), MockFail({}, "猫眼"), MockFail({}, "大麦")],
            sale_timestamp=0,
            ntp_offset=0,
            notify_config={},
        )
    assert result["success"] is False
