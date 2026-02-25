import time
import asyncio
import ntplib


def get_ntp_offset(server: str = "ntp.aliyun.com") -> float:
    client = ntplib.NTPClient()
    response = client.request(server, version=3)
    return response.offset


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
