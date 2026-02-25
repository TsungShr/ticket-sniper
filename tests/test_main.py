import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from platforms.base import PlatformGrabber


class MockSuccess(PlatformGrabber):
    name = "票星球"
    async def warmup(self): pass
    async def grab(self):
        await asyncio.sleep(0.1)
        return {"success": True, "platform": "票星球", "order_id": "pxq_001"}


class MockSlow(PlatformGrabber):
    name = "猫眼"
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
async def test_orchestrator_stops_on_first_success():
    from main import run_orchestrator
    with patch("main.notify", new_callable=AsyncMock):
        result = await run_orchestrator(
            grabbers=[MockSuccess({}), MockSlow({}), MockSlow({})],
            notify_config={},
        )
    assert result["success"] is True
    assert result["platform"] == "票星球"


@pytest.mark.asyncio
async def test_first_fail_doesnt_kill_others():
    """When PXQ fails fast, orchestrator should NOT cancel Maoyan/Damai."""
    from main import run_orchestrator
    with patch("main.notify", new_callable=AsyncMock):
        result = await run_orchestrator(
            grabbers=[MockFail({}, "票星球"), MockSuccess({})],
            notify_config={},
        )
    assert result["success"] is True
    assert result["platform"] == "票星球"


@pytest.mark.asyncio
async def test_all_fail():
    from main import run_orchestrator
    with patch("main.notify", new_callable=AsyncMock):
        result = await run_orchestrator(
            grabbers=[MockFail({}, "票星球"), MockFail({}, "猫眼"), MockFail({}, "大麦")],
            notify_config={},
        )
    assert result["success"] is False
