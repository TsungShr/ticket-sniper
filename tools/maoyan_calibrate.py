#!/usr/bin/env python3
"""猫眼选票页坐标校准工具

使用方法:
1. 手机打开猫眼，进入任意已开售演出的选座页面（能看到票价/观演人/提交订单）
2. 运行: python tools/maoyan_calibrate.py
3. 工具自动识别目标价格、观演人、提交订单按钮坐标
4. 确认后自动写入 config.yaml
"""
import asyncio
import sys
import os
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from utils.adb import adb_shell, adb_screencap


def parse_bounds(bounds: str) -> tuple[int, int]:
    parts = bounds.replace("][", ",").strip("[]").split(",")
    x1, y1, x2, y2 = map(int, parts)
    return (x1 + x2) // 2, (y1 + y2) // 2


async def dump_and_parse(device_id: str) -> list[dict]:
    await adb_shell(device_id, "uiautomator dump /sdcard/ui_dump.xml")
    xml_str = await adb_shell(device_id, "cat /sdcard/ui_dump.xml")
    root = ET.fromstring(xml_str)
    elements = []
    for node in root.iter("node"):
        text = node.get("text", "").strip()
        bounds = node.get("bounds", "")
        if text and bounds:
            cx, cy = parse_bounds(bounds)
            elements.append({"text": text, "x": cx, "y": cy, "bounds": bounds})
    return elements


async def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    my_cfg = config.get("maoyan", {})
    device_id = my_cfg.get("device_id", "")
    price = str(my_cfg.get("price", ""))
    viewer = my_cfg.get("viewer_name", "")

    if not device_id:
        print("错误: config.yaml 中未设置 maoyan.device_id")
        return

    print(f"设备: {device_id}")
    print(f"目标价格: ¥{price}")
    print(f"观演人: {viewer}")
    print()

    output = await adb_shell(device_id, "wm size")
    print(f"屏幕分辨率: {output}")

    await adb_screencap(device_id, "maoyan_calibrate.png")
    print("截图已保存: maoyan_calibrate.png\n")

    print("正在扫描屏幕元素...")
    elements = await dump_and_parse(device_id)

    print(f"找到 {len(elements)} 个文本元素:\n")
    for i, el in enumerate(elements):
        print(f"  [{i:2d}] ({el['x']:4d}, {el['y']:4d})  {el['text']}")

    print("\n--- 自动匹配结果 ---")
    result = {}

    for el in elements:
        if price and price in el["text"] and "price_btn" not in result:
            result["price_btn"] = [el["x"], el["y"]]
            print(f"  票价 ¥{price}: ({el['x']}, {el['y']})")

        if viewer and viewer in el["text"] and "viewer_btn" not in result:
            result["viewer_btn"] = [el["x"], el["y"]]
            print(f"  观演人 {viewer}: ({el['x']}, {el['y']})")

        if el["text"] in ("提交订单", "确认购买") and "submit_btn" not in result:
            result["submit_btn"] = [el["x"], el["y"]]
            print(f"  提交按钮: ({el['x']}, {el['y']})")

    if not result:
        print("  未自动匹配到任何目标，请检查是否在选座页面")
        print("\n你也可以手动输入坐标:")
        for field, label in [
            ("price_btn", f"票价 ¥{price}"),
            ("viewer_btn", f"观演人 {viewer}"),
            ("submit_btn", "提交订单"),
        ]:
            coord = input(f"  {label} 坐标 (x,y，留空跳过): ").strip()
            if coord:
                x, y = map(int, coord.split(","))
                result[field] = [x, y]

    if not result:
        print("未配置任何坐标，退出")
        return

    print(f"\n将写入 config.yaml maoyan 段:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    confirm = input("\n确认写入? (y/n): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return

    config["maoyan"].update(result)
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print("已写入 config.yaml ✓")


if __name__ == "__main__":
    asyncio.run(main())
