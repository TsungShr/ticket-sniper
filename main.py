#!/usr/bin/env python3
"""
多平台演唱会抢票系统 — 协调器主入口
三平台并发抢票：票星球 / 猫眼 / 大麦
"""
import asyncio
import logging
import sys

import yaml

from platforms.base import PlatformGrabber
from platforms.piaoxingqiu import PiaoxingqiuGrabber
from platforms.maoyan import MaoyanController
from platforms.damai import DamaiController
from utils.ntp_sync import get_ntp_offset
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

    # Each grabber waits for its own sale_time internally
    logger.info("=== 各平台已启动，等待各自开售时间 ===")

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

    grabbers: list[PlatformGrabber] = []

    pxq_cfg = config.get("piaoxingqiu", {})
    if pxq_cfg.get("access_token"):
        grabbers.append(PiaoxingqiuGrabber(pxq_cfg, ntp_offset))
        logger.info(f"票星球模块: 已启用 (开售: {pxq_cfg.get('sale_time', '未设置')})")

    my_cfg = config.get("maoyan", {})
    if my_cfg.get("device_id"):
        grabbers.append(MaoyanController(my_cfg, ntp_offset))
        logger.info(f"猫眼模块: 已启用 (开售: {my_cfg.get('sale_time', '未设置')})")

    dm_cfg = config.get("damai", {})
    if dm_cfg.get("device_id"):
        grabbers.append(DamaiController(dm_cfg, ntp_offset))
        logger.info(f"大麦模块: 已启用 (开售: {dm_cfg.get('sale_time', '未设置')})")

    if not grabbers:
        logger.error("没有启用任何平台！请检查 config.yaml")
        sys.exit(1)

    logger.info(f"已启用 {len(grabbers)} 个平台: "
                + ", ".join(g.name for g in grabbers))

    result = await run_orchestrator(
        grabbers=grabbers,
        notify_config=config.get("notification", {}),
    )

    if result["success"]:
        logger.info("请立即完成支付！")
    else:
        logger.info("本次抢票未成功")


if __name__ == "__main__":
    asyncio.run(main())
