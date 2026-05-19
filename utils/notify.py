"""推送通知 — Bark / ServerChan"""
import aiohttp
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)


async def send_bark(key: str, title: str, body: str) -> None:
    if not key:
        return
    url = f"https://api.day.app/{key}/{quote(title)}/{quote(body)}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    logger.info("Bark notification sent")
    except Exception as e:
        logger.warning(f"Bark notification failed: {e}")


async def send_serverchan(key: str, title: str, body: str) -> None:
    if not key:
        return
    try:
        url = f"https://sctapi.ftqq.com/{key}.send"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data={"title": title, "desp": body}) as resp:
                if resp.status == 200:
                    logger.info("ServerChan notification sent")
    except Exception as e:
        logger.warning(f"ServerChan notification failed: {e}")


async def notify(notify_config: dict, title: str, body: str) -> None:
    await send_bark(notify_config.get("bark_key", ""), title, body)
    await send_serverchan(notify_config.get("serverchan_key", ""), title, body)
