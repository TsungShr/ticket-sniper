#!/usr/bin/env python3
"""票星球演出查询工具 — 获取 show_id, session_id, seat_plan_id"""
import requests
import sys
import yaml

API_HOST = "https://m.piaoxingqiu.com"
API_VER = "4.1.2-20240305183007"
API_SRC = "WEB"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 "
    "Mobile/15E148 Safari/604.1"
)


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_headers(token: str) -> dict:
    return {
        "User-Agent": UA,
        "access-token": token,
        "host": "m.piaoxingqiu.com",
        "terminal-src": API_SRC,
        "src": API_SRC,
        "ver": API_VER,
        "content-type": "application/json",
        "origin": API_HOST,
        "referer": API_HOST,
    }


def search_shows(token: str, keyword: str) -> list:
    resp = requests.get(
        f"{API_HOST}/cyy_gatewayapi/home/pub/v3/show_list/search",
        params={
            "keyword": keyword,
            "src": API_SRC, "ver": API_VER,
            "length": 20, "offset": 0,
            "pageType": "SEARCH_PAGE",
            "sortType": "RECOMMEND",
        },
        headers=get_headers(token),
    )
    data = resp.json()
    if data.get("statusCode") != 200:
        print(f"搜索失败: {data.get('comments', '未知错误')}")
        return []
    return data.get("data", {}).get("searchData", [])


def get_sessions(token: str, show_id: str) -> list:
    resp = requests.get(
        f"{API_HOST}/cyy_gatewayapi/show/pub/v5/show/{show_id}/sessions",
        headers=get_headers(token),
    )
    data = resp.json()
    return data.get("data", []) if data.get("statusCode") == 200 else []


def get_seat_plans(token: str, show_id: str, session_id: str) -> list:
    resp = requests.get(
        f"{API_HOST}/cyy_gatewayapi/show/pub/v5/show/{show_id}/session/{session_id}/seat_plans",
        headers=get_headers(token),
    )
    data = resp.json()
    result = data.get("data", []) if data.get("statusCode") == 200 else []
    if isinstance(result, dict):
        return result.get("seatPlans", [])
    return result


def main():
    config = load_config()
    token = config["piaoxingqiu"]["access_token"]
    if not token:
        print("请先运行 tools/pxq_login.py 登录")
        sys.exit(1)

    keyword = input("搜索演出关键词 (歌手/演出名): ").strip()
    if not keyword:
        print("请输入搜索关键词")
        sys.exit(1)
    shows = search_shows(token, keyword)
    if not shows:
        print("未找到相关演出")
        sys.exit(1)

    print("\n找到以下演出:")
    for i, s in enumerate(shows):
        print(f"  [{i}] {s.get('showName', '')} - {s.get('cityName', '')}")

    idx = int(input("\n选择演出编号: ").strip())
    show = shows[idx]
    show_id = show["showId"]
    print(f"\n选择: {show.get('showName')} (ID: {show_id})")

    sessions = get_sessions(token, show_id)
    if sessions:
        print("\n场次列表:")
        for i, s in enumerate(sessions):
            print(f"  [{i}] {s.get('sessionName', '')} {s.get('bizShowSessionId', '')}")
        sidx = int(input("选择场次编号: ").strip())
        session = sessions[sidx]
        session_id = session["bizShowSessionId"]

        plans = get_seat_plans(token, show_id, session_id)
        if plans:
            print("\n票档列表:")
            for i, p in enumerate(plans):
                print(f"  [{i}] ¥{p.get('originalPrice', '')} - {p.get('seatPlanName', '')} (ID: {p.get('seatPlanId', '')})")
            pidx = int(input("选择票档编号: ").strip())
            seat_plan_id = plans[pidx]["seatPlanId"]
        else:
            seat_plan_id = input("手动输入 seat_plan_id: ").strip()
    else:
        session_id = input("手动输入 session_id: ").strip()
        seat_plan_id = input("手动输入 seat_plan_id: ").strip()

    config["piaoxingqiu"]["show_id"] = show_id
    config["piaoxingqiu"]["session_id"] = session_id
    config["piaoxingqiu"]["seat_plan_id"] = seat_plan_id
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    print(f"\n配置已保存! show_id={show_id}, session_id={session_id}, seat_plan_id={seat_plan_id}")


if __name__ == "__main__":
    main()
