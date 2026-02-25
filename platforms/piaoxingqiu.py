import asyncio
import logging
import random
import string
import time

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

    def __init__(self, config: dict):
        super().__init__(config)
        self.cfg = config["piaoxingqiu"]
        self.access_token = self.cfg["access_token"]
        self.refresh_token_str = self.cfg["refresh_token"]
        self.audience_ids: list[str] = []

    # ---- helpers ----

    def _build_headers(self) -> dict:
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
        prefix = PiaoxingqiuGrabber._random_str(4)
        ts = str(int(time.time()))
        suffix = PiaoxingqiuGrabber._random_str(9)
        base = prefix + ts + suffix
        # insert 4 random chars at random positions
        result = list(base)
        for _ in range(4):
            pos = random.randint(0, len(result))
            result.insert(pos, random.choice(string.ascii_letters + string.digits))
        return "".join(result)

    def _build_order_payload(
        self,
        audience_ids: list[str],
        deliver_method: str = "E_TICKET",
    ) -> dict:
        return {
            "showId": self.cfg["show_id"],
            "sessionId": self.cfg["session_id"],
            "seatPlanId": self.cfg["seat_plan_id"],
            "audienceIds": audience_ids,
            "deliverMethod": deliver_method,
        }

    # ---- low-level HTTP ----

    async def _api_get(self, session: aiohttp.ClientSession, path: str) -> dict:
        url = f"https://{API_HOST}/{path}"
        async with session.get(url, headers=self._build_headers()) as resp:
            return await resp.json()

    async def _api_post(
        self,
        session: aiohttp.ClientSession,
        path: str,
        json_data: dict,
    ) -> dict:
        url = f"https://{API_HOST}/{path}"
        headers = self._build_headers()
        if "create_order" in path:
            headers["Blackbox"] = self._build_blackbox()
        async with session.post(url, headers=headers, json=json_data) as resp:
            return await resp.json()

    # ---- API calls ----

    async def refresh_token(self, session: aiohttp.ClientSession) -> dict:
        path = "cyy_gatewayapi/user/pub/v3/refresh_token"
        data = await self._api_post(session, path, {
            "refreshToken": self.refresh_token_str,
        })
        if data.get("statusCode") == 200:
            result = data.get("data", {})
            self.access_token = result.get("accessToken", self.access_token)
            self.refresh_token_str = result.get("refreshToken", self.refresh_token_str)
        return data

    async def get_show_detail(self, session: aiohttp.ClientSession) -> dict:
        show_id = self.cfg["show_id"]
        path = f"cyy_gatewayapi/show/pub/v3/show/{show_id}"
        return await self._api_get(session, path)

    async def get_audiences(self, session: aiohttp.ClientSession) -> dict:
        path = "cyy_gatewayapi/user/buyer/v3/user_audiences?length=500&offset=0"
        return await self._api_get(session, path)

    async def create_order(
        self,
        session: aiohttp.ClientSession,
        audience_ids: list[str],
    ) -> dict:
        path = "cyy_gatewayapi/trade/buyer/order/v3/create_order?bizCode=FHL_M&src=WEB"
        payload = self._build_order_payload(audience_ids)
        return await self._api_post(session, path, payload)

    # ---- grabber lifecycle ----

    async def warmup(self) -> None:
        async with aiohttp.ClientSession() as session:
            await self.refresh_token(session)
            data = await self.get_audiences(session)
            result = data.get("data", [])
            # API 返回 list 或 dict{"audiences": [...]}
            if isinstance(result, list):
                audiences = result
            else:
                audiences = result.get("audiences", [])
            self.audience_ids = [a["id"] for a in audiences]
            logger.info(f"票星球 观演人: {len(self.audience_ids)}人")

    async def _single_grab(
        self,
        session: aiohttp.ClientSession,
        attempt: int,
    ) -> dict:
        result = await self.create_order(session, self.audience_ids)
        status = result.get("statusCode")
        if status == 200:
            order_id = result.get("data", {}).get("orderId", "pxq_unknown")
            return {
                "success": True,
                "platform": self.name,
                "order_id": order_id,
            }
        raise RuntimeError(
            f"attempt {attempt} failed: {result.get('comments', result)}"
        )

    async def grab(self) -> dict:
        concurrent = self.cfg.get("concurrent_requests", 1)
        async with aiohttp.ClientSession() as session:
            for retry in range(10):
                if self.stopped:
                    raise asyncio.CancelledError("被协调器停止")
                logger.info(f"票星球 第{retry+1}轮 ({concurrent}路并发)")
                tasks = [
                    self._single_grab(session, retry * concurrent + i)
                    for i in range(concurrent)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, dict) and r.get("success"):
                        logger.info(f"票星球 抢票成功！订单: {r.get('order_id')}")
                        return r
                logger.warning(f"票星球 第{retry+1}轮全部失败")
                await asyncio.sleep(0.2)
        raise RuntimeError("票星球: 达到最大重试次数")
