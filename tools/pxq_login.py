#!/usr/bin/env python3
"""票星球 SMS 登录工具 — 获取 Token 并写入 config.yaml"""
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
    resp = requests.post(
        f"{API_HOST}/cyy_gatewayapi/user/pub/v3/generate_photo_code",
        json={
            "src": API_SRC, "ver": API_VER,
            "cellphone": phone,
            "verifyCodeUseType": "USER_LOGIN",
            "messageType": "MOBILE",
        },
        headers=HEADERS,
    )
    resp = requests.post(
        f"{API_HOST}/cyy_gatewayapi/user/pub/v3/send_verify_code",
        json={
            "src": API_SRC, "ver": API_VER,
            "verifyCodeUseType": "USER_LOGIN",
            "cellphone": phone,
            "messageType": "MOBILE",
            "token": "",
        },
        headers=HEADERS,
    )
    return resp.json().get("statusCode") == 200


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
