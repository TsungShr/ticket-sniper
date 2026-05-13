import logging
import time
import asyncio
import datetime
import ntplib

logger = logging.getLogger(__name__)

NTP_SERVERS = [
    "ntp.aliyun.com",
    "ntp.tencent.com",
    "cn.ntp.org.cn",
]


def get_ntp_offset(server: str = "ntp.aliyun.com", samples: int = 5) -> float:
    """多次采样取中位数，减少网络抖动误差"""
    client = ntplib.NTPClient()
    offsets = []
    for srv in NTP_SERVERS:
        for _ in range(samples):
            try:
                resp = client.request(srv, version=3)
                offsets.append(resp.offset)
            except Exception:
                pass
        if len(offsets) >= samples:
            break
    if not offsets:
        raise RuntimeError("所有 NTP 服务器均不可达")
    offsets.sort()
    median = offsets[len(offsets) // 2]
    logger.info(f"NTP 采样 {len(offsets)} 次，范围 {offsets[0]*1000:.1f}~{offsets[-1]*1000:.1f}ms，中位数 {median*1000:.1f}ms")
    return median


def corrected_time(ntp_offset: float) -> float:
    """返回经过 NTP 校准后的本机时间"""
    return time.time() + ntp_offset


def hms_to_next_ts(hms: str) -> float:
    """将 HH:MM:SS 转换为距今最近一次该时刻的 Unix 时间戳"""
    h, m, s = map(int, hms.split(":"))
    now = datetime.datetime.now()
    t = now.replace(hour=h, minute=m, second=s, microsecond=0)
    if t.timestamp() <= now.timestamp():
        t += datetime.timedelta(days=1)
    return t.timestamp()


async def wait_until_sale_time(sale_timestamp: float, ntp_offset: float) -> None:
    while True:
        now = time.time() + ntp_offset
        remaining = sale_timestamp - now
        if remaining <= 0:
            break
        if remaining > 1:
            await asyncio.sleep(remaining - 0.5)
        else:
            await asyncio.sleep(0.001)
