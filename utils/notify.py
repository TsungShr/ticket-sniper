import aiohttp
import logging

logger = logging.getLogger(__name__)


async def send_bark(key: str, title: str, body: str) -> None:
    if not key:
        return
    url = f"https://api.day.app/{key}/{title}/{body}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                logger.info("Bark notification sent")


async def send_serverchan(key: str, title: str, body: str) -> None:
    if not key:
        return
    url = f"https://sctapi.ftqq.com/{key}.send"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={"title": title, "desp": body}) as resp:
            if resp.status == 200:
                logger.info("ServerChan notification sent")


async def notify(config: dict, title: str, body: str) -> None:
    nc = config.get("notification", {})
    await send_bark(nc.get("bark_key", ""), title, body)
    await send_serverchan(nc.get("serverchan_key", ""), title, body)
