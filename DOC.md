# fetch-tickets — 多平台演唱会抢票系统

## 架构概览

```
main.py                    # 协调器：NTP 同步 → 平台初始化 → 并发抢票 → 通知
├── platforms/
│   ├── base.py            # PlatformGrabber 抽象基类（wait_for_sale, stop）
│   ├── piaoxingqiu.py     # 票星球：HTTP API 抢票（burst-fire）
│   ├── maoyan.py          # 猫眼：ADB 自动化（盲点/扫描两种模式）
│   └── damai.py           # 大麦：ADB 坐标点击
├── utils/
│   ├── adb.py             # ADB 工具层（AdbSession 持久 shell + 常规命令）
│   ├── ntp_sync.py        # NTP 多服务器多采样中位数同步
│   └── notify.py          # Bark + ServerChan 推送通知
├── tools/
│   ├── pxq_login.py       # 票星球 SMS 登录，获取 Token
│   ├── pxq_show.py        # 票星球演出查询，获取 show/session/seatPlan ID
│   ├── maoyan_calibrate.py  # 猫眼 UI 坐标校准
│   ├── damai_calibrate.py   # 大麦坐标校准
│   └── taobao_checkout.py   # 淘宝购物车毫秒级结算（独立脚本）
├── tests/
│   ├── test_main.py       # 协调器单元测试
│   ├── test_integration.py # 集成测试
│   ├── test_piaoxingqiu.py # PXQ 单元测试
│   ├── test_maoyan.py     # 猫眼单元测试
│   └── test_damai.py      # 大麦单元测试
└── config.yaml            # 运行配置（每平台独立段）
```

## 核心流程

```
1. NTP 同步 → 获取时间偏差（多服务器、多采样取中位数）
2. 按 config 启用平台 → 各平台接收自己的配置段 + ntp_offset
3. warmup() → 各平台预热（刷 Token / ADB 建连 / 连接池预热）
4. grab() → 各平台并发抢票，各自等待自己的 sale_time
5. FIRST_COMPLETED → 第一个成功即 stop() 其余平台
6. 推送通知（Bark / ServerChan）
```

## 平台实现

### 票星球（PiaoxingqiuGrabber）— HTTP API

| 项目 | 说明 |
|------|------|
| 方式 | HTTP API 直接下单 |
| 预热 | 刷新 Token → 获取观演人 → TCP+TLS 连接池预热 |
| 抢票 | burst-fire：`concurrent_requests * 10` 个请求一次性发出 |
| 速度 | 30 请求 376ms（~13ms/请求），连接复用，零轮次间隔 |
| 配置 | access_token, refresh_token, show_id, session_id, seat_plan_id |

**关键优化：**
- `TCPConnector(limit=20, limit_per_host=20, ttl_dns_cache=300)` 连接池
- warmup 阶段发 N 个 `get_show_detail` 请求预建连接
- `asyncio.as_completed` 扁平流，任一成功立即返回

### 猫眼（MaoyanController）— ADB 自动化

| 项目 | 说明 |
|------|------|
| 方式 | ADB 持久 shell + UI 自动化 |
| 两种模式 | **盲点模式**（config 预设坐标，零 UI dump）/ **扫描模式**（实时 UI dump） |
| 预热 | 建立 AdbSession → 校准按钮坐标 |
| 速度 | 盲点模式 ~200ms 完成全流程 |
| 配置 | device_id, viewer_name, price, price_btn/viewer_btn/submit_btn（可选） |

**盲点模式流程：**
1. Phase 1：高频点击购买按钮（30 次，50ms 间隔）
2. Phase 2：盲点序列 3 轮（选票价 → 选观演人 → 提交，每步 50ms）
3. Phase 3：持续点击提交按钮 10 次

**扫描模式流程：**
1. Phase 1：高频点击购买按钮
2. Phase 2：UI dump 查找票价/观演人/提交按钮，最多 8 次扫描
3. Phase 3：反复查找并点击提交，最多 15 次

**AdbSession：** 持久 `adb shell` 子进程，~16ms/tap（普通 adb tap 需 41ms）。

### 大麦（DamaiController）— ADB 坐标点击

| 项目 | 说明 |
|------|------|
| 方式 | ADB 坐标点击（大麦自定义渲染，uiautomator 无法工作） |
| 预热 | 启动 App |
| 抢票 | 交替点击购买/确认按钮，60 次循环 |
| 配置 | device_id, buy_btn, confirm_btn |

## 配置说明

每个平台独立配置段，互不干扰：

```yaml
notification:
  bark_key: ''        # Bark 推送 key
  serverchan_key: ''  # ServerChan key

maoyan:
  device_id: '3KQYD25227201783'   # ADB 设备号
  viewer_name: '张三'              # 观演人姓名（用于 UI 匹配）
  sale_time: '2026-03-01 10:00:00' # 开售时间
  concert_name: 演唱会名称
  price: 1280                      # 目标票价
  # 以下为盲点模式坐标（可选，通过 maoyan_calibrate.py 获取）
  # price_btn: [540, 800]
  # viewer_btn: [540, 1200]
  # submit_btn: [540, 1600]

damai:
  device_id: ''                    # ADB 设备号（空则禁用）
  sale_time: '2026-03-01 10:00:00'
  concert_name: 演唱会名称
  price: 1280
  buy_btn: [1600, 2650]           # 购买按钮坐标
  confirm_btn: [920, 2500]        # 确认按钮坐标

piaoxingqiu:
  access_token: ''                 # 通过 pxq_login.py 获取
  refresh_token: ''
  phone: '13800138000'
  sale_time: '2026-03-01 12:00:00'
  concert_name: 演唱会名称
  price: 380
  show_id: ''                     # 通过 pxq_show.py 获取
  session_id: ''
  seat_plan_id: ''
  concurrent_requests: 10         # 并发请求数
```

**启用/禁用规则：**
- 票星球：`access_token` 非空即启用
- 猫眼：`device_id` 非空即启用
- 大麦：`device_id` 非空即启用

**每平台独立 sale_time：** 各平台在 `grab()` 中调用 `wait_for_sale()` 自行等待，互不影响。

## 工具使用

### 票星球登录

```bash
python tools/pxq_login.py
# 1. 输入手机号
# 2. 打开验证码图片，输入图中字符
# 3. 输入短信验证码
# → Token 自动写入 config.yaml
```

### 票星球演出查询

```bash
python tools/pxq_show.py
# 1. 输入关键词搜索
# 2. 选择演出 → 场次 → 票档
# → show_id / session_id / seat_plan_id 写入 config.yaml
```

### 猫眼坐标校准

```bash
python tools/maoyan_calibrate.py
# 前提：手机在猫眼已开售演出的选座页面
# → 自动识别票价/观演人/提交按钮坐标
# → 确认后写入 config.yaml
```

### 大麦坐标校准

```bash
python tools/damai_calibrate.py
# 前提：平板在大麦演出详情页
# → 截图 + 交互式坐标测试
# → 手动写入 config.yaml
```

### 淘宝购物车抢购

```bash
python tools/taobao_checkout.py
# 前提：平板淘宝 App 停在购物车页面，目标商品已勾选
# 支持每日定时（14:00 / 20:00）或指定单次时间
```

独立于主协调器，不走 `main.py` 流程。

## 淘宝抢购脚本（taobao_checkout.py）

独立的淘宝购物车毫秒级结算工具，不经过主协调器。

| 项目 | 说明 |
|------|------|
| 方式 | ADB 持久 shell + 像素检测（PIL + numpy） |
| 定时 | NTP 校时，精确到 T - 55ms 开始发射 |
| 速度 | 8ms 间隔连射 30 次，持久 shell fire-and-forget |
| 检测 | 后台线程截图检测底部区域暖色像素（橙色支付按钮），120ms 轮询 |
| 支付 | 检测到订单页后自动连点「立即支付」5 次 + 振动提醒 |

**流程：**
1. NTP 校时 → 精确等待到开售前 55ms
2. 持久 shell 连射结算按钮 `(1655, 2628)` 30 次，8ms 间隔
3. 后台线程截图检测：底部区域 `y=2690~2790` 是否出现亮橙色像素（RGB≈238,96,44）
4. 检测到订单页 → 自动点击「立即支付」`(918, 2743)` → 振动提醒
5. 未检测到则持续补射最多 12 秒

**硬编码配置（脚本顶部修改）：**
```python
DEVICE   = "3KQYD25227201783"     # ADB 设备号
CX, CY   = 1655, 2628            # 结算按钮坐标
PAY_X, PAY_Y = 918, 2743         # 立即支付按钮坐标
DAILY_TIMES = ["14:00:00", "20:00:00"]  # 每日定时
SINGLE_TIME = ""                  # 单次时间（留空用 DAILY_TIMES）
TAP_LEAD_MS  = 55                 # 提前发射毫秒数
TAP_BURST    = 30                 # 连射次数
TAP_GAP_MS   = 8                  # 连射间隔
```

## 运行

```bash
# 正式抢票（三平台协调器）
python main.py

# 系统会：
# 1. NTP 同步
# 2. 启用已配置的平台
# 3. 各平台预热
# 4. 等待各自开售时间
# 5. 并发抢票
# 6. 推送通知
```

## 关键设计决策

1. **per-platform config 隔离**：每个平台只接收自己的配置段 `cfg`，避免配置交叉污染
2. **独立 sale_time**：各平台各自等待开售时间，支持不同演出不同时间
3. **NTP busy-wait 精度**：粗等到 200ms 前，然后 1ms 精度 busy-wait
4. **协调器 stop() 机制**：第一个平台成功后，其余平台通过 `_stop_event` 优雅停止
5. **ADB 持久 shell**：避免每次 tap 都 fork 新进程，延迟从 41ms 降到 16ms
6. **连接池预热**：PXQ 在 warmup 阶段预建 TCP+TLS 连接，避免首次请求冷启动
7. **burst-fire 策略**：PXQ 一次性发出所有请求，不分轮次等待，最大化并发
