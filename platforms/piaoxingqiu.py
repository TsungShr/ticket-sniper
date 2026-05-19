"""票星球 HTTP API 抢票器"""
import asyncio
import logging
import random
import string
import time
from typing import Any

import aiohttp

from platforms.base import PlatformGrabber

logger = logging.getLogger(__name__)

API_HOST = "m.piaoxingqiu.com"
API_VER = "4.1.2-20240305183007"
API_SRC = "WEB"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
    "Mobile/15E148 Safari/604.1"
)


class PiaoxingqiuGrabber(PlatformGrabber):
    name = "票星球"

    def __init__(self, cfg: dict, ntp_offset: float = 0.0) -> None:
        super().__init__(cfg, ntp_offset)
        self.access_token: str = cfg["access_token"]
        self.refresh_token_str: str = cfg["refresh_token"]
        self.audience_ids: list[str] = []
        self._session: aiohttp.ClientSession | None = None

    def _build_headers(self) -> dict[str, str]:
        return {
            "User-Agent": UA,
            "access-token": self.access_token,
            "host": API_HOST,
            "terminal-src": API_SRC,
            "src": API_SRC,
            "ver": API_VER,
            "origin": f"https://{API_HOST}",
            "referer": f"https://{API_HOST}/",
            "content-type": "application/json",
        }

    @staticmethod
    def _random_str(length: int) -> str:
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def _build_blackbox(self) -> str:
        """构造一个更接近真实 Tongdun 格式的 Blackbox 指纹

        真实格式约为 300~500 字符 base64 串，内部包含时间戳、设备段等结构。
        此处生成一个带时间戳特征 + 随机数据段的假指纹。
        """
        ts_ms = str(int(time.time() * 1000))
        segments = [
            self._random_str(6),
            ts_ms,
            self._random_str(4),
            self._random_str(8),
            self._random_str(3),
            self._random_str(10),
        ]
        result = "".join(segments)
        for _ in range(8):
            pos = random.randint(0, len(result))
            result = result[:pos] + random.choice(string.ascii_letters + string.digits) + result[pos:]
        return result

    def _build_order_payload(
        self,
        audience_ids: list[str],
        deliver_method: str = "E_TICKET",
    ) -> dict[str, Any]:
        return {
            "showId": self.cfg["show_id"],
            "sessionId": self.cfg["session_id"],
            "seatPlanId": self.cfg["seat_plan_id"],
            "audienceIds": audience_ids,
            "deliverMethod": deliver_method,
        }

    async def _api_get(self, session: aiohttp.ClientSession, path: str) -> dict[str, Any]:
        url = f"https://{API_HOST}/{path}"
        async with session.get(url, headers=self._build_headers()) as resp:
            return await resp.json()

    async def _api_post(
        self, session: aiohttp.ClientSession, path: str, json_data: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"https://{API_HOST}/{path}"
        headers = self._build_headers()
        if "create_order" in path:
            headers["Blackbox"] = self._build_blackbox()
        async with session.post(url, headers=headers, json=json_data) as resp:
            return await resp.json()

    async def refresh_token(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        path = "cyy_gatewayapi/user/pub/v3/refresh_token"
        data = await self._api_post(session, path, {"refreshToken": self.refresh_token_str})
        if data.get("statusCode") == 200:
            result = data.get("data", {})
            self.access_token = result.get("accessToken", self.access_token)
            self.refresh_token_str = result.get("refreshToken", self.refresh_token_str)
        return data

    async def get_show_detail(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        show_id = self.cfg["show_id"]
        path = f"cyy_gatewayapi/show/pub/v3/show/{show_id}"
        return await self._api_get(session, path)

    async def get_audiences(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        path = "cyy_gatewayapi/user/buyer/v3/user_audiences?length=500&offset=0"
        return await self._api_get(session, path)

    async def create_order(
        self, session: aiohttp.ClientSession, audience_ids: list[str]
    ) -> dict[str, Any]:
        path = "cyy_gatewayapi/trade/buyer/order/v3/create_order?bizCode=FHL_M&src=WEB"
        payload = self._build_order_payload(audience_ids)
        return await self._api_post(session, path, payload)

    def _make_session(self) -> aiohttp.ClientSession:
        conn = aiohttp.TCPConnector(
            limit=20,
            limit_per_host=20,
            ttl_dns_cache=300,
            keepalive_timeout=60,
        )
        return aiohttp.ClientSession(connector=conn)

    async def warmup(self) -> None:
        async with self._make_session() as session:
            await self.refresh_token(session)
            data = await self.get_audiences(session)
            result = data.get("data", [])
            if isinstance(result, list):
                audiences = result
            else:
                audiences = result.get("audiences", [])
            self.audience_ids = [a["id"] for a in audiences]
            logger.info(f"票星球 观演人: {len(self.audience_ids)}人")

        self._session = self._make_session()
        concurrent = self.cfg.get("concurrent_requests", 5)
        warmup_tasks = [
            self.get_show_detail(self._session)
            for _ in range(concurrent)
        ]
        await asyncio.gather(*warmup_tasks, return_exceptions=True)
        logger.info(f"票星球 连接池预热完成 ({concurrent} 条连接)")

    async def _single_grab(
        self,
        session: aiohttp.ClientSession,
        attempt: int,
    ) -> dict[str, Any]:
        result = await self.create_order(session, self.audience_ids)
        status = result.get("statusCode")
        if status == 200:
            order_id = result.get("data", {}).get("orderId", "pxq_unknown")
            return {
                "success": True,
                "platform": self.name,
                "order_id": order_id,
            }
        comments = result.get("comments", "")
        if status == 469:
            raise RuntimeError(f"风控拦截 (469): {comments}")
        raise RuntimeError(f"attempt {attempt} failed: {comments or result}")

    async def grab(self) -> dict[str, Any]:
        await self.wait_for_sale()
        concurrent = self.cfg.get("concurrent_requests", 5)
        session = self._session
        t0 = time.time()
        try:
            total_attempts = concurrent * 10
            tasks = [
                self._single_grab(session, i)
                for i in range(total_attempts)
            ]
            for coro in asyncio.as_completed(tasks):
                if self.stopped:
                    raise asyncio.CancelledError("被协调器停止")
                try:
                    r = await coro
                    if isinstance(r, dict) and r.get("success"):
                        elapsed = int((time.time() - t0) * 1000)
                        logger.info(
                            f"票星球 抢票成功！订单: {r.get('order_id')} ({elapsed}ms)"
                        )
                        return r
                except Exception as e:
                    logger.debug(f"票星球 单次请求失败: {e}")
            raise RuntimeError("票星球: 全部请求均失败")
        finally:
            if session:
                await session.close()
