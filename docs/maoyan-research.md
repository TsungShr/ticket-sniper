# Maoyan (猫眼) Ticketing Platform Automation Research

## Table of Contents
1. [Overview of Technical Approaches](#1-overview-of-technical-approaches)
2. [AutoX.js UI Automation (Approach 1)](#2-autoxjs-ui-automation-approach-1)
3. [Protocol Reverse Engineering (Approach 2)](#3-protocol-reverse-engineering-approach-2)
4. [WeChat Mini-Program API (Approach 3)](#4-wechat-mini-program-api-approach-3)
5. [Known API Endpoints](#5-known-api-endpoints)
6. [Encryption and Authentication Details](#6-encryption-and-authentication-details)
7. [Anti-Bot Measures and Rate Limiting](#7-anti-bot-measures-and-rate-limiting)
8. [Source Repositories](#8-source-repositories)

---

## 1. Overview of Technical Approaches

Maoyan ticket automation currently follows three primary technical routes, all centered around **automation + protocol reversal**. Ordered by investment cost -> success rate -> risk:

| Approach | Tech Stack | Pros | Cons | Risk Level |
|----------|-----------|------|------|------------|
| **AutoX.js UI Automation** | AutoX.js on Android | No HTTPS involved; risk control only detects human-machine behavior; low ban rate | 1 account per phone; must pre-fill viewer/ticket info | Low |
| **Protocol Reverse Engineering** | Python/Java + Frida + libmtguard.so | Multi-threaded/coroutine concurrency; highest speed | Complex; encryption changes frequently; high ban risk | High |
| **WeChat Mini-Program API** | Python + requests + Cloud Functions | Lightweight; cheap (0.01 CNY/10k requests); moderate concurrency | accessToken expires every 2 hours; strict User-Agent check | Medium |

---

## 2. AutoX.js UI Automation (Approach 1)

### 2.1 Repository Structure

**Primary repo: [Pactum7/ticket-grabbing](https://github.com/Pactum7/ticket-grabbing)**

```
ticket-grabbing/
├── MaoYan/
│   ├── MaoYanDraft.js      # Draft/experimental version
│   ├── MaoYanGo.js          # Original time-based ticket grab
│   ├── MaoYanGoNew.js       # Improved time-based ticket grab (卡点抢票)
│   └── MaoYanMonitor.js     # Residual ticket monitoring (余票监控)
├── FenWanDao/
│   └── FenWanDaoGo.js
├── PiaoXingQiu/
├── Test/
├── ticket-notice/
├── LICENSE (Apache-2.0)
└── README.md
```

**Fork/variant: [yd-coder/ticket-helper](https://github.com/yd-coder/ticket-helper)** - Same structure, 34 commits, 100% JavaScript.

### 2.2 Script Descriptions

| Script | Purpose | Key Features |
|--------|---------|--------------|
| `MaoYanGoNew.js` | Time-based ticket grab at exact moment | Waits for target timestamp, then auto-clicks through purchase flow |
| `MaoYanMonitor.js` | Monitors remaining inventory | Auto viewer selection, auto-refresh, webhook notifications, audio alerts, target price threshold |
| `MaoYanGo.js` | Original grab script | Simpler version of GoNew |
| `MaoYanDraft.js` | Experimental/draft | Testing new approaches |

### 2.3 Core AutoX.js Script Pattern

The fundamental automation flow (~150 lines of core code):

```javascript
// Step 1: Enable accessibility service
auto.waitFor();

// Step 2: Launch Maoyan app
app.launchApp("猫眼");

// Step 3: Open console for logging
openConsole();
console.setTitle("猫眼 go!", "#ff11ee00", 30);

// Step 4: Input configuration
function getPlayEtc() {
    var playEtc = rawInput("请输入场次关键字", "周六");
    // validation logic
    return playEtc;
}

function getTicketPrice() {
    var ticketPrice = rawInput("请输入票价关键字", "788");
    // validation logic
    return ticketPrice;
}

function getSellTime() {
    // Get target grab timestamp
    // Uses server time from: https://mtop.damai.cn/gw/... (Damai time API)
    return JSON.parse(http.get("https://mtop.damai.cn/gw/..."));
}

// Step 5: Main automation loop
function main() {
    // Wait until target time
    while (currentTime < targetTime) {
        sleep(10);
    }

    // Find and click "立即购票" (Buy Now) button
    var buyBtn = textContains("立即购票").findOne(5000);
    if (buyBtn) {
        click(buyBtn.bounds().centerX(), buyBtn.bounds().centerY());
    }

    // Select session (场次)
    var session = textContains(playEtc).findOne(3000);
    if (session) {
        click(session.bounds().centerX(), session.bounds().centerY());
    }

    // Select ticket price tier
    var price = textContains(ticketPrice).findOne(3000);
    if (price) {
        click(price.bounds().centerX(), price.bounds().centerY());
    }

    // Click through confirmation steps
    // "选好了" -> "确认" -> "提交订单" -> "去付款"/"立即支付"
    while (true) {
        var confirmBtn = textContains("选好了").findOne(1000)
            || textContains("确认").findOne(1000)
            || textContains("提交订单").findOne(1000)
            || textContains("去付款").findOne(1000)
            || textContains("立即支付").findOne(1000);
        if (confirmBtn) {
            click(confirmBtn.bounds().centerX(), confirmBtn.bounds().centerY());
        }
    }
}
```

### 2.4 Key UI Element Identifiers (Button Text Patterns)

These are the Chinese text strings that appear on Maoyan's Android app UI and are used by AutoX.js `textContains()` / `text()` selectors:

| Stage | Button Text (Chinese) | English Translation | AutoX.js Selector |
|-------|----------------------|---------------------|-------------------|
| Show detail page | `"立即购票"` | "Buy Now" | `textContains("立即购票").findOne(5000)` |
| Show detail page | `"即将开抢"` | "Coming Soon" | `textContains("即将开抢")` |
| Session selection | Session keyword (e.g., `"周六"`) | User-configured | `textContains(playEtc).findOne(3000)` |
| Price tier selection | Price keyword (e.g., `"788"`) | User-configured | `textContains(ticketPrice).findOne(3000)` |
| Viewer selection | `"选好了"` | "Done Selecting" | `textContains("选好了").findOne(1000)` |
| Seat confirmation | `"确认选座"` | "Confirm Seats" | `textContains("确认选座")` |
| Order confirmation | `"确认"` / `"确定"` | "Confirm" | `textContains("确认")` |
| Order submission | `"提交订单"` | "Submit Order" | `textContains("提交订单")` |
| Payment | `"去付款"` / `"立即支付"` | "Go Pay" / "Pay Now" | `textContains("去付款")` |
| Out of stock | `"缺货登记"` | "Out of Stock Registration" | `textContains("缺货登记")` |
| Purchase button alt | `"立即购买"` | "Buy Immediately" | `textContains("立即购买")` |

### 2.5 AutoX.js API Methods Used

```javascript
// Finding elements
textContains("text").findOne(timeout_ms)   // Find element containing text
text("exact text").findOne(timeout_ms)      // Find element with exact text
className("android.widget.Button").findOne() // Find by class name
id("resource_id").findOne()                 // Find by resource ID
desc("description").findOne()               // Find by content description

// Getting coordinates for click
element.bounds().centerX()                  // Center X coordinate
element.bounds().centerY()                  // Center Y coordinate

// Clicking
click(x, y)                                // Click at coordinates
element.click()                            // Click the element directly

// Existence check
textContains("text").exists()              // Check if element exists

// Combined selectors
classNameContains("Button").textContains("立即开始").findOne(2000).click()

// Waiting and timing
sleep(ms)                                  // Delay
auto.waitFor()                             // Wait for accessibility service

// App control
app.launchApp("猫眼")                      // Launch Maoyan app
```

### 2.6 Important Notes on UI Automation

- Scripts run on **Android only** via AutoX.js accessibility services
- One phone = one account (no multi-account capability per device)
- All viewer info and ticket preferences must be **pre-filled** before running the script
- AutoX.js control IDs may change with Maoyan app updates; `textContains` is more stable than `id()`
- The `className` and `packageName` can be inspected using MT Manager's "Activity Record" feature
- DOM may require manual interaction to refresh ticket category regions before automation resumes
- `click()` on popup controls sometimes requires a forced `sleep()` before the click event fires

---

## 3. Protocol Reverse Engineering (Approach 2)

### 3.1 Five Core Interfaces

The protocol-based approach recreates Maoyan's HTTPS protocol from the App/WeChat Mini-program. There are five core interfaces:

| Step | Interface | Description |
|------|-----------|-------------|
| 1 | **Login** | Integrated with Meituan's wind control (slider + device fingerprint). As of Oct 2024, encryption logic moved to `libmtguard.so`. Can be invoked through Frida or have signature verification patched. |
| 2 | **Query Sessions** | `/cinema/shows` - Query available show sessions. Has `antiToken` field. |
| 3 | **Lock Seats** | `/seat/lock` - Lock selected seats. Has `antiToken` field calculated from timestamp + device info. |
| 4 | **Create Order** | Submit purchase order after seat lock |
| 5 | **Payment** | Complete payment flow |

### 3.2 antiToken Field

The query interface `/cinema/shows` and seat-locking interface `/seat/lock` added an `antiToken` field:
- Calculated based on **timestamps** and **device information**
- Can be obtained in real-time via **RPC methods** (e.g., Frida RPC)
- The encryption logic resides in `libmtguard.so` (a native shared library)

### 3.3 Login Interface Details

- Integrated with **Meituan advanced verification** (美团高级验证)
- Includes slider CAPTCHA + device fingerprint
- Once logged in, sessions can last approximately **1 year** without dropping
- Multi-threaded login with memo functionality supported
- Separate proxy IPs recommended for queries vs purchases

### 3.4 Technical Stack

- **Languages**: Python / Java
- **Concurrency**: Multi-threaded or coroutine-based
- **Tools**: Frida for hooking `libmtguard.so`, or direct SO patching
- **Proxy**: Residential proxy pools required
- **Performance**: ~20 concurrent orders per device (high CPU requirement)

### 3.5 Features of Production Implementations

- Bypass mechanisms described as "回流无盾免滑块" (return flow without shield/slider)
- Separate proxy IPs for queries and purchases
- Network delay automation
- "No-query purchase mode" for maximum speed
- Order notifications and QR code payment
- High-concurrency support for presale tickets

---

## 4. WeChat Mini-Program API (Approach 3)

### 4.1 Overview

The WeChat Mini-Program approach extracts the login Cookie from Maoyan's WeChat mini-program and places it in cloud functions to repeatedly call the mini-program purchase interface.

### 4.2 Key Endpoint

```
/wx/buy
```

This is the mini-program's purchase endpoint, called in a loop from cloud functions.

### 4.3 Technical Stack

| Component | Detail |
|-----------|--------|
| Language | Python + requests |
| Hosting | Alibaba Cloud FC (Function Compute), 0.5 vCPU, 128 MB |
| Cost | 0.01 CNY per 10,000 requests |
| Concurrency | ~100 concurrent instances documented |

### 4.4 Authentication

- **accessToken**: Expires every **2 hours**, must be periodically refreshed
- **Cookie**: Extracted from WeChat mini-program via packet capture
- **User-Agent**: Strict checking; must include:
  ```
  Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15
  ```

### 4.5 Cookie Extraction from WeChat Mini-Program

WeChat mini-program requests use HTTPS with **SSL Pinning** (SSL certificate binding), making standard proxy tools like Burp Suite insufficient. Special methods required:

1. **Tool preparation**: Fiddler/Charles + decryption tool packages + WeChat developer tools
2. **Clear mini-program cache** in WeChat
3. **Trigger mini-program events** to capture data packets
4. **Decrypt and decompile** the captured data packets
5. **Extract Cookie** from the decrypted request headers
6. **Import into cloud function** for automated calling

Since WeChat mini-programs don't natively support cookies via `wx.request()`, custom cookie storage implementations are used.

### 4.6 Performance Reference

Per a February 2025 case study: Using this method for a premiere screening, **100 concurrent instances produced 42 orders in 2 minutes**.

---

## 5. Known API Endpoints

### 5.1 Maoyan Performance/Show APIs (yanchu.maoyan.com)

**Ticket Availability / Sales Plans Query:**
```
GET https://yanchu.maoyan.com/myshow/ajax/performance/show/{showId}/ticket/{ticketId}/salesplans
```

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `showId` | path | Performance/show identifier | `1608623` |
| `ticketId` | path | Ticket type identifier | `19847277` |
| `optimus_risk_level` | query | Security parameter | `71` |
| `optimus_code` | query | Verification code | `10` |
| `uuid` | query | User device identifier | (dynamic) |
| `se` | query | Additional security token | (dynamic) |

**Request Headers:**
```
Host: yanchu.maoyan.com
Accept-Encoding: gzip, deflate, br
Connection: keep-alive
Accept: application/json, text/plain, */*
User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_3_1 like Mac OS X)...
```

**Response Fields:**
- `data[0].currentAmount` - Current ticket availability count
- `attrMaps.serverTime` - Server timestamp (milliseconds)

### 5.2 Maoyan Movie APIs (m.maoyan.com) - Reference

These are the movie-side APIs which share similar patterns with the show/performance APIs:

| Endpoint | Description | Key Parameters |
|----------|-------------|----------------|
| `GET /ajax/movieOnInfoList` | Currently showing movies | - |
| `GET /ajax/comingList` | Upcoming movies | `ci` (city ID), `token`, `limit` |
| `GET /ajax/detailmovie` | Movie detail | `movieId` |
| `GET /ajax/filterCinemas` | Filter cinemas | `ci` (city ID) |
| `GET /ajax/cinemaDetail` | Cinema detail | `cinemaId` |
| `GET /showtime/wrap.json` | Showtime info | `cinemaid`, `movieid` |
| `GET /show/seats` | Seat map | `showId`, `showDate` |

### 5.3 Maoyan Box Office API (piaofang.maoyan.com)

```
GET https://piaofang.maoyan.com/dashboard-ajax
```
Requires `signKey` authentication (see Section 6).

### 5.4 Other Domain References

| Domain | Purpose |
|--------|---------|
| `yanchu.maoyan.com` | Performance/show ticketing |
| `show.maoyan.com` | Show listings/browsing |
| `show-e.maoyan.com` | Business backend (merchant) |
| `m.maoyan.com` | Mobile web (movie focused) |
| `piaofang.maoyan.com` | Box office data |
| `fantasy.maoyan.com` | Special events |

---

## 6. Encryption and Authentication Details

### 6.1 signKey Generation (Box Office API)

The `signKey` for the box office API (`piaofang.maoyan.com/dashboard-ajax`) is generated via MD5 encryption:

**Step 1: Generate Index**
```python
def getIndex(self):
    return math.floor(1000 * random.random() + 1)
```

**Step 2: Construct Parameter String (d)**
```python
def getD(self):
    self.pay_loads['index'] = self.getIndex()
    self.pay_loads['timeStamp'] = int(time.time() * 1000)
    d = 'method=GET&timeStamp=' + str(self.pay_loads['timeStamp']) + \
        '&User-Agent=' + self.pay_loads['User-Agent'] + \
        '&index=' + str(self.pay_loads['index']) + \
        '&channelId=' + str(self.pay_loads['channelId']) + \
        '&sVersion=' + str(self.pay_loads['sVersion']) + \
        '&key=' + self.key
    d = d.replace(r'/\s+/g', " ")
    return d
```

**Step 3: MD5 Hash**
```python
def getSignKey(self):
    md5 = hashlib.md5()
    d = self.getD()
    md5.update(d.encode('utf-8'))
    signKey = md5.hexdigest()
    self.pay_loads['signKey'] = signKey
```

**Required Parameters:**
| Parameter | Description |
|-----------|-------------|
| `timeStamp` | Current timestamp in milliseconds |
| `User-Agent` | Browser user agent string |
| `index` | Random value (1-1000 range) |
| `channelId` | Channel identifier |
| `sVersion` | Version number |
| `key` | Constant value from `veri.js` file |

**Important**: String replacements are applied to `d` before passing to the encryption function.

### 6.2 antiToken (Show/Performance APIs)

- Present on `/cinema/shows` and `/seat/lock` endpoints
- Calculated from **timestamps + device information**
- Can be obtained via **Frida RPC** at runtime
- Encryption logic in native library: `libmtguard.so`

### 6.3 Meituan Login Verification

- Slider CAPTCHA + device fingerprint
- Logic moved to `libmtguard.so` (native shared library) as of October 2024
- Can be bypassed via:
  - Frida hooking to invoke signing functions directly
  - Patching the SO file to disable signature verification

---

## 7. Anti-Bot Measures and Rate Limiting

| Measure | Detail |
|---------|--------|
| **IP Rate Limiting** | >8 requests from single IP within 3 seconds triggers HTTP 429 |
| **Proxy Requirement** | Residential proxy pools with random User-Agents required |
| **SSL Pinning** | WeChat mini-program uses SSL certificate binding |
| **antiToken** | Dynamic token on query and seat-lock endpoints |
| **Device Fingerprint** | Required for login and order creation |
| **CAPTCHA** | Slider verification on login (Meituan advanced verification) |
| **Account Ban** | High-frequency abnormal orders result in device + account ban |
| **User-Agent Check** | Strict UA validation on mini-program endpoints |

---

## 8. Source Repositories

### Primary Repositories Examined

| Repository | Type | Notes |
|------------|------|-------|
| [Pactum7/ticket-grabbing](https://github.com/Pactum7/ticket-grabbing) | AutoX.js scripts | 1.6k stars, 208 forks. Contains MaoYanGoNew.js, MaoYanMonitor.js. Apache-2.0. 86.2% JS, 13.8% Java |
| [yd-coder/ticket-helper](https://github.com/yd-coder/ticket-helper) | AutoX.js scripts | Fork/variant. 8 stars, 2 forks, 34 commits, 100% JS |
| [fuyinkai/maoyanbuy](https://github.com/fuyinkai/maoyanbuy) | Compiled Windows exe | **No source code available** - contains only .exe, .dll, and config files. Desktop app for refund ticket monitoring. |
| [xhconceit/MaoYanApi](https://github.com/xhconceit/MaoYanApi) | Node.js API wrapper | Movie API endpoints. Requires cookie.txt from browser. Port 3000. |

### Related Resources

| Resource | URL |
|----------|-----|
| Maoyan Movie API Documentation | https://apis.netstart.cn/maoyan/ |
| AutoX.js Framework | https://github.com/kkevsekk1/AutoX |
| AutoX.js Documentation | http://doc.autoxjs.com/ |
| Gitee Mirror of ticket-grabbing | https://gitee.com/yanghao99/ticket-grabbing |

### CSDN Blog References

| Title | URL |
|-------|-----|
| AutoX.js抢票(猫眼) - Java_wucao | https://blog.csdn.net/Java_wucao/article/details/134012918 |
| Auto.js猫眼抢票助手 | https://blog.csdn.net/m0_61239576/article/details/139250805 |
| 最新猫眼抢票脚本 | https://blog.csdn.net/m0_63289473/article/details/138091962 |
| 猫眼三种技术路线 | https://blog.csdn.net/xintai1999/article/details/149453753 |
| 猫眼signKey解密 | https://blog.csdn.net/qq_41234663/article/details/129300490 |
| 猫眼余票查询示例 | https://blog.csdn.net/hackermengzhi/article/details/139064850 |
| 猫眼协议购票方案 | https://blog.csdn.net/xuanzizhang1/article/details/138807306 |
| 利用autox.js自动抢票(猫眼) | https://www.iotword.com/22126.html |
| 基于autox.js的抢票(猫眼) - 前端哥 | https://www.qianduange.cn/article/1168.html |
