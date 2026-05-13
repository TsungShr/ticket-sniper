# ticket-sniper — 多平台演唱会抢票系统

三平台并发抢票：票星球 / 猫眼 / 大麦，开售即启动，先到先得。

**仅供学习交流与技术研究使用，请遵守各平台服务条款。**

---

## 功能特性

| 平台 | 抢票方式 | 特点 |
|------|----------|------|
| 票星球 | HTTP API 直连 | burst-fire 并发请求，连接池预热，~13ms/请求 |
| 猫眼 | ADB 自动化 | 盲点模式（零 UI dump，~200ms）/ 扫描模式 |
| 大麦 | ADB 坐标点击 | 纯坐标点击，适配大麦自定义渲染框架 |
| 淘宝购物车 | ADB 持久 shell | NTP 校时，精确到 T-55ms 发射，像素检测确认 |

- **NTP 多服务器同步**：阿里 / 腾讯 / cn.ntp.org.cn 多采样中位数
- **智能设备管理**：支持 Android 设备 / 模拟器，自动识别
- **Bark / ServerChan 推送**：抢票成功 / 失败实时通知
- **独立工具链**：登录、演出查询、坐标校准等辅助脚本

---

## 环境要求

- Python 3.10+
- Android 设备（猫眼 / 大麦 / 淘宝模式需要，票星球无需设备）
- ADB 已配置到系统 PATH

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/TsungShr/ticket-sniper.git
cd ticket-sniper
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 复制配置模板

```bash
cp config.yaml.example config.yaml
```

### 4. 配置各平台

根据 `config.yaml` 中的说明，填写各平台所需参数。配置方法参见[配置说明](#配置说明)章节。

### 5. 运行

```bash
python main.py
```

---

## 项目结构

```
ticket-sniper/
├── main.py                      # 协调器：NTP 同步 → 平台初始化 → 并发抢票 → 通知
├── config.yaml                  # 运行配置（各平台独立配置段）
├── config.yaml.example          # 配置模板
├── requirements.txt             # Python 依赖
│
├── platforms/                   # 各平台抢票实现
│   ├── base.py                 # PlatformGrabber 抽象基类
│   ├── piaoxingqiu.py          # 票星球 HTTP API
│   ├── maoyan.py               # 猫眼 ADB 自动化（盲点 / 扫描模式）
│   └── damai.py                # 大麦 ADB 坐标点击
│
├── utils/                      # 通用工具
│   ├── adb.py                  # ADB 工具层（持久 shell + 常规命令）
│   ├── ntp_sync.py             # NTP 多服务器多采样同步
│   ├── notify.py               # Bark + ServerChan 推送
│   └── http_retry.py           # HTTP 指数退避重试
│
├── tools/                      # 辅助工具
│   ├── pxq_login.py            # 票星球短信登录（获取 Token）
│   ├── pxq_show.py             # 票星球演出查询（获取 ID）
│   ├── maoyan_calibrate.py     # 猫眼 UI 坐标校准
│   ├── damai_calibrate.py      # 大麦坐标校准
│   └── taobao_checkout.py      # 淘宝购物车毫秒结算（独立脚本）
│
└── tests/                      # 单元测试 + 集成测试
```

---

## 配置说明

每个平台独立配置段，互不干扰。只需填写你要使用的平台配置，空或留默认值则该平台不启用。

```yaml
notification:
  bark_key: ""
  serverchan_key: ""

# ── 票星球 ──────────────────────────────
piaoxingqiu:
  access_token: ""              # 通过 tools/pxq_login.py 获取
  refresh_token: ""
  phone: ""
  sale_time: "2026-04-01 12:00:00"
  concert_name: "演唱会名称"
  price: 380
  show_id: ""                   # 通过 tools/pxq_show.py 获取
  session_id: ""
  seat_plan_id: ""
  concurrent_requests: 10        # 并发请求数

# ── 猫眼 ─────────────────────────────────
maoyan:
  device_id: ""                 # ADB 设备号（空则禁用）
  viewer_name: ""
  sale_time: "2026-04-01 10:00:00"
  concert_name: "演唱会名称"
  price: 1280
  # 盲点模式坐标（可选，通过 tools/maoyan_calibrate.py 获取）
  # price_btn: [540, 800]
  # viewer_btn: [540, 1200]
  # submit_btn: [540, 1600]

# ── 大麦 ─────────────────────────────────
damai:
  device_id: ""
  sale_time: "2026-04-01 10:00:00"
  concert_name: "演唱会名称"
  price: 1280
  buy_btn: [1600, 2650]         # 购买按钮坐标
  confirm_btn: [920, 2500]      # 确认按钮坐标

# ── 淘宝购物车 ───────────────────────────
taobao:
  device_id: ""                 # 优先读取 ADB_DEVICES 环境变量
  sale_time: "2026-04-01 12:00:00"
  concert_name: "演唱会名称"
  checkout_btn: [1655, 2628]
  pay_btn: [918, 2743]
  daily_times: ["14:00:00", "20:00:00"]
  tap_lead_ms: 55
  tap_burst: 30
  tap_gap_ms: 8
  max_seconds: 12
```

**启用规则：**
- 票星球：`access_token` 非空即启用
- 猫眼 / 大麦 / 淘宝：`device_id` 非空即启用

---

## 工具使用

### 票星球登录（获取 Token）

```bash
python tools/pxq_login.py
```

### 票星球演出查询（获取 show/session/seatPlan ID）

```bash
python tools/pxq_show.py
```

### 猫眼坐标校准

```bash
python tools/maoyan_calibrate.py
# 前提：手机在猫眼已开售演出的选座页面
```

### 大麦坐标校准

```bash
python tools/damai_calibrate.py
# 前提：设备在大麦演出详情页
```

### 淘宝购物车抢购（独立脚本）

```bash
# 通过 ADB_DEVICES 环境变量指定设备
export ADB_DEVICES=your_device_id
python tools/taobao_checkout.py
# 前提：平板淘宝 App 停在购物车页面，目标商品已勾选
```

---

## 核心流程

```
1. NTP 同步          → 多服务器多采样取中位数，精确到毫秒
2. 平台预热          → 各平台 warmup（刷 Token / ADB 建连 / 连接池预热）
3. 并发抢票          → 各平台各自等待 sale_time 后同时启动
4. FIRST_COMPLETED  → 第一个平台成功即停止其余平台
5. 推送通知          → Bark / ServerChan
```

---

## 关键设计决策

1. **per-platform 配置隔离**：各平台只接收自己的配置段 `cfg`，避免配置交叉污染
2. **独立 sale_time**：各平台各自等待开售时间，支持不同演出不同时间
3. **NTP busy-wait 精度**：粗等到开售前 200ms，然后 1ms 精度忙等
4. **协调器 stop() 机制**：第一个平台成功后，其余平台通过 `_stop_event` 优雅停止
5. **ADB 持久 shell**：避免每次 tap 都 fork 新进程，延迟从 ~41ms 降到 ~16ms
6. **连接池预热**：PXQ 在 warmup 阶段预建 TCP+TLS 连接，消除冷启动延迟
7. **burst-fire 策略**：PXQ 一次性发出所有请求，不分轮次等待，最大化并发

---

## 运行测试

```bash
pytest tests/ -v
```

---

## License

MIT License
