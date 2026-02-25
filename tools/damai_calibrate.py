#!/usr/bin/env python3
"""大麦坐标校准工具

使用方法:
1. 在平板上打开大麦，进入演出详情页
2. 运行: python tools/damai_calibrate.py
3. 根据截图标注的网格，找到按钮坐标
4. 写入 config.yaml
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from utils.adb import adb_screencap, adb_shell, adb_tap


async def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    device_id = config.get("damai", {}).get("device_id", "")
    if not device_id:
        print("错误: config.yaml 中未设置 damai.device_id")
        return

    # Get screen resolution
    output = await adb_shell(device_id, "wm size")
    print(f"屏幕分辨率: {output}")

    # Take screenshot
    local_path = "damai_calibrate.png"
    await adb_screencap(device_id, local_path)
    print(f"\n截图已保存: {local_path}")
    print("请打开截图查看当前页面")

    print("\n--- 坐标校准 ---")
    print("请在平板上进入演出详情页，然后输入坐标测试")
    print("输入格式: x,y (如 1600,2650)")
    print("输入 'q' 退出\n")

    while True:
        coord = input("输入坐标点击测试 (x,y): ").strip()
        if coord.lower() == "q":
            break
        try:
            x, y = map(int, coord.split(","))
            await adb_tap(device_id, x, y)
            print(f"  已点击 ({x}, {y})")
            await asyncio.sleep(1)
            await adb_screencap(device_id, local_path)
            print(f"  截图已更新: {local_path}")
        except ValueError:
            print("  格式错误，请输入 x,y")
        except Exception as e:
            print(f"  错误: {e}")

    print("\n请将坐标写入 config.yaml:")
    print("  damai:")
    print("    buy_btn: [x, y]      # 立即购买 按钮")
    print("    confirm_btn: [x, y]  # 确认/提交订单 按钮")


if __name__ == "__main__":
    asyncio.run(main())
