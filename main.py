#!/usr/bin/env python3
"""
周杰伦2026杭州演唱会抢票系统 — 协调器主入口
三平台并发抢票：票星球 > 猫眼 > 大麦
"""
import asyncio
import logging
import sys
import time
from datetime import datetime

import yaml

from platforms.base import PlatformGrabber
from platforms.piaoxingqiu import PiaoxingqiuGrabber
from platforms.maoyan import MaoyanController
from platforms.damai import DamaiController
from utils.ntp_sync import get_ntp_offset, wait_until_sale_time
from utils.notify import notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestrator")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def run_orchestrator(
    grabbers: list[PlatformGrabber],
    sale_timestamp: float,
    ntp_offset: float,
    notify_config: dict,
) -> dict:
    active_grabbers = []
    for g in grabbers:
        try:
            await g.warmup()
            logger.info(f"[{g.name}] 预热完成")
            active_grabbers.append(g)
        except Exception as e:
            logger.error(f"[{g.name}] 预热失败，已禁用: {e}")

    if not active_grabbers:
        logger.error("所有平台预热失败！")
        await notify(
            {"notification": notify_config},
            "抢票失败",
            "所有平台预热失败",
        )
        return {"success": False, "platform": "none", "order_id": ""}

    if sale_timestamp > 0:
        remaining = sale_timestamp - (time.time() + ntp_offset)
        if remaining > 0:
            logger.info(f"等待开售，还有 {remaining:.1f} 秒")
            await wait_until_sale_time(sale_timestamp, ntp_offset)

    logger.info("=== 开售！三平台并发抢票 ===")

    tasks = {
        asyncio.create_task(g.grab(), name=g.name): g
        for g in active_grabbers
    }

    result = None
    remaining = set(tasks.keys())

    while remaining and result is None:
        done, remaining = await asyncio.wait(
            remaining, return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            try:
                r = task.result()
                if isinstance(r, dict) and r.get("success"):
                    result = r
                    logger.info(
                        f"=== 抢票成功！平台: {r['platform']}，"
                        f"订单号: {r.get('order_id')} ==="
                    )
                    break
            except Exception as e:
                logger.error(f"[{task.get_name()}] 失败: {e}")

    for task in remaining:
        grabber = tasks[task]
        grabber.stop()
        task.cancel()
    if remaining:
        await asyncio.gather(*remaining, return_exceptions=True)

    if result:
        await notify(
            {"notification": notify_config},
            "抢票成功！",
            f"平台: {result['platform']}，订单号: {result.get('order_id')}",
        )
    else:
        await notify(
            {"notification": notify_config},
            "抢票失败",
            "三个平台均未成功",
        )
        result = {"success": False, "platform": "none", "order_id": ""}

    return result


async def main():
    config = load_config()

    try:
        ntp_offset = get_ntp_offset()
        logger.info(f"NTP 时间偏差: {ntp_offset*1000:.1f}ms")
    except Exception as e:
        logger.warning(f"NTP 同步失败，使用本地时间: {e}")
        ntp_offset = 0.0

    sale_time_str = config.get("sale_time", "")
    if sale_time_str:
        sale_dt = datetime.strptime(sale_time_str, "%Y-%m-%d %H:%M:%S")
        sale_timestamp = sale_dt.timestamp()
    else:
        logger.warning("未设置开售时间，立即开始")
        sale_timestamp = 0

    grabbers: list[PlatformGrabber] = []

    if config.get("piaoxingqiu", {}).get("access_token"):
        grabbers.append(PiaoxingqiuGrabber(config))
        logger.info("票星球模块: 已启用")

    if config.get("maoyan", {}).get("device_id"):
        grabbers.append(MaoyanController(config))
        logger.info("猫眼模块: 已启用")

    if config.get("damai", {}).get("device_id"):
        grabbers.append(DamaiController(config))
        logger.info("大麦模块: 已启用")

    if not grabbers:
        logger.error("没有启用任何平台！请检查 config.yaml")
        sys.exit(1)

    logger.info(f"已启用 {len(grabbers)} 个平台: "
                + ", ".join(g.name for g in grabbers))

    result = await run_orchestrator(
        grabbers=grabbers,
        sale_timestamp=sale_timestamp,
        ntp_offset=ntp_offset,
        notify_config=config.get("notification", {}),
    )

    if result["success"]:
        logger.info("请立即完成支付！")
    else:
        logger.info("本次抢票未成功")


if __name__ == "__main__":
    asyncio.run(main())
