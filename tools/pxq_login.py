#!/usr/bin/env python3
"""票星球 SMS 登录工具 — 获取 Token 并写入 config.yaml"""
import os
import requests
import yaml
import sys

API_HOST = "https://m.piaoxingqiu.com"
API_VER = "4.1.2-20240305183007"
API_SRC = "WEB"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 "
    "Mobile/15E148 Safari/604.1"
)
HEADERS = {
    "User-Agent": UA,
    "host": "m.piaoxingqiu.com",
    "terminal-src": API_SRC,
    "src": API_SRC,
    "ver": API_VER,
    "content-type": "application/json",
    "origin": API_HOST,
    "referer": API_HOST,
}


def send_sms(phone: str) -> bool:
    # Step 1: 获取图形验证 token（有些场景不需要图形验证，但 API 要求先调用）
    resp1 = requests.post(
        f"{API_HOST}/cyy_gatewayapi/user/pub/v3/generate_photo_code",
        json={
            "src": API_SRC, "ver": API_VER,
            "cellphone": phone,
            "verifyCodeUseType": "USER_LOGIN",
            "messageType": "MOBILE",
        },
        headers=HEADERS,
    )
    data1 = resp1.json()
    print(f"[debug] generate_photo_code 响应: statusCode={data1.get('statusCode')}, "
          f"comments={data1.get('comments', '')}")

    if data1.get("statusCode") != 200 or not data1.get("data"):
        print("获取图形验证码失败")
        return False

    photo_data = data1["data"]
    unique_id = photo_data.get("uniqueIdentity", "")
    base_code = photo_data.get("baseCode", "")

    if not base_code:
        print("未获取到图形验证码图片")
        return False

    # 保存验证码图片到本地
    import base64
    import subprocess
    img_b64 = base_code.split(",")[1] if "," in base_code else base_code
    img_bytes = base64.b64decode(img_b64)
    captcha_path = os.path.join(os.path.dirname(__file__), "..", "captcha.jpg")
    captcha_path = os.path.abspath(captcha_path)
    with open(captcha_path, "wb") as f:
        f.write(img_bytes)

    # macOS 自动打开图片
    subprocess.Popen(["open", captcha_path])
    print(f"图形验证码已打开（也保存在 {captcha_path}）")
    captcha_code = input("请输入图中的字符: ").strip()

    # Step 2: 发送短信验证码（token 字段放验证码答案，不是 uniqueIdentity）
    resp2 = requests.post(
        f"{API_HOST}/cyy_gatewayapi/user/pub/v3/send_verify_code",
        json={
            "src": API_SRC, "ver": API_VER,
            "verifyCodeUseType": "USER_LOGIN",
            "cellphone": phone,
            "messageType": "MOBILE",
            "token": captcha_code,
        },
        headers=HEADERS,
    )
    data2 = resp2.json()
    if data2.get("statusCode") != 200:
        print(f"发送失败: {data2.get('comments', '未知错误')}")
    return data2.get("statusCode") == 200


def login(phone: str, code: str) -> dict:
    resp = requests.post(
        f"{API_HOST}/cyy_gatewayapi/user/pub/v3/login_or_register",
        json={
            "src": API_SRC, "ver": API_VER,
            "cellphone": phone,
            "verifyCode": code,
        },
        headers=HEADERS,
    )
    result = resp.json()
    if result.get("statusCode") == 200 and result.get("data"):
        return result["data"]
    print(f"登录失败: {result.get('comments', 'unknown error')}")
    sys.exit(1)


def update_config(phone: str, tokens: dict):
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    config["piaoxingqiu"]["phone"] = phone
    config["piaoxingqiu"]["access_token"] = tokens["accessToken"]
    config["piaoxingqiu"]["refresh_token"] = tokens["refreshToken"]
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    print("Token 已保存到 config.yaml")


def main():
    phone = input("请输入手机号: ").strip()
    print(f"正在向 {phone} 发送验证码...")
    if send_sms(phone):
        print("验证码已发送！")
    else:
        print("发送失败，请稍后重试")
        sys.exit(1)
    code = input("请输入验证码: ").strip()
    tokens = login(phone, code)
    print(f"登录成功！accessToken: {tokens['accessToken'][:20]}...")
    update_config(phone, tokens)


if __name__ == "__main__":
    main()
