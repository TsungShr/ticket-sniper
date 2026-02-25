# 周杰伦2026杭州演唱会抢票系统设计文档

## 目标

抢购周杰伦2026年4月杭州演唱会 **2380元** 档位门票，周六/周日均可。

三平台同时抢：大麦、猫眼、票星球，任一平台成功即停止其他。

## 策略：开售瞬间竞抢

优先级排序（按成功率）：**票星球 > 猫眼 > 大麦**

## 整体架构

```
┌─────────────────────────────────────────────────────┐
│                   Mac 控制中心                        │
│  ┌──────────────────────────────────────────────┐   │
│  │           Orchestrator (Python)               │   │
│  │  - NTP 时间同步，精确到毫秒级开售倒计时          │   │
│  │  - 三平台并发调度                               │   │
│  │  - 成功/失败通知推送（Bark/Server酱）            │   │
│  └──────┬──────────────┬──────────────┬─────────┘   │
│         │              │              │              │
│  ┌──────▼─────┐ ┌──────▼──────┐ ┌────▼──────────┐  │
│  │ 大麦模块    │ │ 票星球模块   │ │ 猫眼控制器    │  │
│  │ Appium     │ │ Requests    │ │ ADB → Android │  │
│  │ 辅助型     │ │ (纯 API)    │ │ + 小程序API   │  │
│  └──────┬─────┘ └─────────────┘ └────┬──────────┘  │
│         │                             │              │
└─────────┼─────────────────────────────┼──────────────┘
          │                             │
   ┌──────▼──────┐              ┌───────▼───────┐
   │ 安卓设备 A   │              │ 安卓设备 B    │
   │ 大麦 App    │              │ 猫眼 App     │
   │ + Appium    │              │ + AutoX.js   │
   └─────────────┘              └───────────────┘
```

## 各平台模块设计

### 1. 票星球（优先级最高 — 同盾风控较弱）

- **技术栈：** Python + aiohttp + Requests
- **登录：** SMS 验证码 → 保存 Token
- **破盾策略：** 同盾滑块破解（有开源方案），激进并发 3-5 路请求
- **流程：**
  1. SMS 登录获取 Auth Token
  2. 查询演出详情 API，获取场次 ID + 2380 元票档 SKU ID
  3. 开售倒计时 → 并发发送 `createOrder` 请求
  4. 成功 → 推送通知 + 停止信号

### 2. 猫眼（优先级中 — 双路并发）

#### 路线 A：AutoX.js 安卓 App 自动化
- **技术栈：** AutoX.js (JavaScript) 运行在安卓设备
- **控制：** Mac 通过 ADB push 脚本 + ADB shell 启动
- **流程：**
  1. 安卓设备安装猫眼 App + AutoX.js
  2. 手动登录进入演出详情页
  3. 脚本监听开售 → 自动点击购买 → 选档 → 选观演人 → 提交

#### 路线 B：微信小程序 API 通道（风控较弱的突破口）
- **技术栈：** Python + Requests
- **原理：** 小程序通道风控弱于原生 App
- **流程：** 提取微信登录 Cookie → 调用小程序接口下单

两条路线并发运行，任一成功即可。

### 3. 大麦（优先级低 — 阿里八卦盾极难破）

- **技术栈：** Python + Appium + uiautomator2
- **策略调整：** 辅助型自动化，不做全自动化（避免被盾到4级永久封禁）
  - 自动完成：页面预加载、选票档、填观演人信息
  - 人工完成：最终提交按钮（降低被检测风险）
- **养号策略：** 开售前用账号买几次免费/低价活动，提升账号信誉
- **流程：**
  1. Appium 连接安卓设备
  2. 手动登录进入演出详情页
  3. 开售 → 自动选档+填信息 → **提示人工点击提交**

## 协调器设计

```python
async def main():
    config = load_config("config.yaml")
    ntp_offset = sync_ntp_time()

    pxq = PiaoxingqiuGrabber(config)      # 票星球 API
    maoyan = MaoyanController(config)      # 猫眼双路
    damai = DamaiController(config)        # 大麦辅助

    await warmup_all([pxq, maoyan, damai])
    await wait_until(config.sale_time, ntp_offset)

    # 三平台并发，任一成功即停
    done, pending = await asyncio.wait(
        [pxq.grab(), maoyan.grab(), damai.grab()],
        return_when=FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
    notify_result(done)
```

## 通知推送

| 方式 | 用途 |
|------|------|
| Bark（iOS 推送） | 抢票成功/失败即时推送到 iPhone |
| Server 酱 | 微信推送备用 |
| 终端日志 | 实时显示三个平台状态 |

## 配置 (`config.yaml`)

```yaml
concert:
  name: "周杰伦2026杭州演唱会"
  price: 2380
  weekday_preference: [saturday, sunday]

sale_time: "2026-03-XX 10:00:00"  # 待确认

damai:
  device_id: ""
  appium_port: 4723
  show_id: ""
  sku_id: ""
  viewer_name: ""

maoyan:
  device_id: ""
  autoxjs_script: "maoyan_grab.js"
  wechat_cookie: ""
  miniprogram_api: true

piaoxingqiu:
  phone: ""
  token: ""
  show_id: ""
  sku_id: ""
  concurrent_requests: 5

notification:
  bark_key: ""
  serverchan_key: ""
```

## 项目目录结构

```
fetch-tickets/
├── config.yaml
├── main.py                  # 协调器入口
├── requirements.txt
├── platforms/
│   ├── __init__.py
│   ├── base.py              # 平台基类（grab/warmup/stop 接口）
│   ├── piaoxingqiu.py       # 票星球 API 模块
│   ├── damai.py             # 大麦 Appium 辅助模块
│   └── maoyan.py            # 猫眼 ADB + 小程序 API 模块
├── autoxjs/
│   └── maoyan_grab.js       # AutoX.js 猫眼抢票脚本
├── utils/
│   ├── ntp_sync.py          # NTP 时间同步
│   ├── notify.py            # 通知推送（Bark/Server酱）
│   ├── adb.py               # ADB 工具函数
│   └── tongdun.py           # 同盾滑块破解
└── docs/
    └── plans/
        └── 2026-02-25-ticket-grabber-design.md
```

## 破盾策略总结

| 平台 | 盾类型 | 破盾策略 |
|------|--------|---------|
| 票星球 | 同盾(Tongdun) | 滑块破解 + 激进并发，有开源方案 |
| 猫眼 | 自研加密 | 小程序通道绕过 + App 自动化双路 |
| 大麦 | 阿里八卦盾 | 不硬破 → 辅助型自动化 + 养号，避免触发4级封禁 |

## 技术栈总览

| 组件 | 技术 |
|------|------|
| 主语言 | Python 3.11+ |
| 异步框架 | asyncio + aiohttp |
| HTTP 客户端 | Requests + aiohttp |
| 安卓自动化 | Appium (大麦) + AutoX.js (猫眼) |
| 设备控制 | ADB (Android Debug Bridge) |
| 时间同步 | ntplib |
| 通知 | Bark API / Server酱 API |
| 配置 | PyYAML |
