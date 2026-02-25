# Piaoxingqiu (票星球) API Research

> Research date: 2026-02-25
> Sources: GitHub repos (senseek/piaoxingqiu, itsharex/pxq_ticket, fuyinkai/PXQ, 417261937/pxq-dm), CSDN blog posts

---

## 1. Base URLs

| Environment | Base URL | Usage |
|---|---|---|
| **Web / WeChat Mini-Program** | `https://m.piaoxingqiu.com` | Primary web API gateway |
| **Android / APP** | `https://appapi.caiyicloud.com` | APP-side API gateway (caiyicloud = 彩翼云) |

All API paths share the prefix: `/cyy_gatewayapi/`

---

## 2. Common Request Headers

All requests must include these headers:

```
User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1
Content-Type: application/json
Host: m.piaoxingqiu.com                    (or appapi.caiyicloud.com for APP)
access-token: <JWT access token>           (required for authenticated endpoints)
terminal-src: WEB                          (or ANDROID for APP)
src: WEB                                   (or android for APP, weixin_mini for WeChat)
ver: 4.1.2-20240305183007                  (API version string, changes with updates)
origin: https://m.piaoxingqiu.com
referer: https://m.piaoxingqiu.com
```

**Additional headers for order creation:**
```
Blackbox: <tongdun device fingerprint string>    (ONLY on create_order requests)
```

**WeChat Mini-Program specific query params:**
```
src=weixin_mini
appId=wxad60dd8123a62329
merchantId=<optional>
```

---

## 3. Authentication Flow (SMS Login)

### Step 1: Generate Photo Code (optional, triggers on rate limit)

```
POST /cyy_gatewayapi/user/pub/v3/generate_photo_code
```

**Request:**
```json
{
  "src": "WEB",
  "ver": "4.1.2-20240305183007",
  "cellphone": "13812345678",
  "verifyCodeUseType": "USER_LOGIN",
  "messageType": "MOBILE"
}
```

**Response:**
```json
{
  "statusCode": 200,
  "comments": "",
  "data": {
    "baseCode": "<base64 encoded image>"
  }
}
```

### Step 2: Send SMS Verification Code

```
POST /cyy_gatewayapi/user/pub/v3/send_verify_code
```

**Request:**
```json
{
  "src": "WEB",
  "ver": "4.1.2-20240305183007",
  "verifyCodeUseType": "USER_LOGIN",
  "cellphone": "13812345678",
  "messageType": "MOBILE",
  "token": "<photo code token, empty string if not required>"
}
```

**Response:**
```json
{
  "statusCode": 200,
  "comments": "",
  "data": true
}
```

### Step 3: Login / Register

```
POST /cyy_gatewayapi/user/pub/v3/login_or_register
```

**Request:**
```json
{
  "src": "WEB",
  "ver": "4.1.2-20240305183007",
  "cellphone": "13812345678",
  "verifyCode": "123456"
}
```

**Response:**
```json
{
  "statusCode": 200,
  "comments": "",
  "data": {
    "accessToken": "<JWT access token>",
    "refreshToken": "<JWT refresh token>"
  }
}
```

### Step 4: Refresh Token

```
GET /cyy_gatewayapi/user/pub/v3/refresh_token?refreshToken=<token>
```

**Query params:** `src`, `ver`, `refreshToken`

**Response:**
```json
{
  "statusCode": 200,
  "comments": "",
  "data": {
    "accessToken": "<new access token>",
    "refreshToken": "<new refresh token>"
  }
}
```

**Token notes:**
- `accessToken` is sent in the `access-token` header for all authenticated requests
- `refreshToken` is used to renew the accessToken when it expires
- Token format is opaque string (not standard JWT with dots), server-side validated
- Typical access token lifetime: ~2 hours; refresh token: ~30 days

---

## 4. Show & Session Endpoints

### 4.1 Search Shows

```
GET /cyy_gatewayapi/home/pub/v3/show_list/search
```

**Query params:**
- `backendCategoryCode=ALL`
- `cityId=4455` (city code)
- `keyword=<url-encoded search term>`
- `length=10`
- `offset=0`
- `pageType=SEARCH_PAGE`
- `sortType=<RELEVANCE|TIME|PRICE>`
- `src=WEB`
- `ver=<version>`

### 4.2 Get Show Detail (v5)

```
GET /cyy_gatewayapi/show/pub/v5/show/{showId}/static
```

**Query params:** `src`, `ver`, `cityId`, `source=FROM_QUICK_ORDER`, `siteId`

**Response contains:**
- `rsCode` - result code
- `noteInfos[]` - purchase rules, delivery info, etc.
- `basicInfo` - show name, dates, venue, prices, poster

### 4.3 Get Show Sessions (v5 - recommended)

```
GET /cyy_gatewayapi/show/pub/v5/show/{showId}/sessions
```

**Query params:** `src`, `ver`, `source=FROM_QUICK_ORDER`, `isQueryShowBasicInfo=true`

**Response:**
```json
{
  "statusCode": 200,
  "data": [
    {
      "showLimit": 4,
      "showId": "644fcb2aca916100017dcfef",
      "stdShowId": "...",
      "supportSeatPicking": false,
      "originalSeatPickType": "...",
      "showName": "...",
      "bizShowSessionId": "644fcb7dca916100017dda3d",
      "stdShowSessionId": "...",
      "sessionName": "2024-06-15 19:30",
      "hasActivity": false,
      "hasSessionSoldOut": false,
      "seatPlans": [...],
      "sessionStatus": "ON_SALE",
      "sessionSaleTime": 1718438400000
    }
  ]
}
```

**Session statuses:** `ON_SALE`, `SOLD_OUT`, `PENDING_SALE`, `OFF_SALE`

### 4.4 Get Sessions Dynamic Data (v3 - legacy)

```
GET /cyy_gatewayapi/show/pub/v3/show/{showId}/sessions_dynamic_data
```

Returns `sessionVOs[]` with `sessionStatus` and `bizShowSessionId`.

### 4.5 Get Seat Plans (v5)

```
GET /cyy_gatewayapi/show/pub/v5/show/{showId}/session/{sessionId}/seat_plans
```

**Query params:** `source=FROM_QUICK_ORDER`, `src`, `ver`

**Response:**
```json
{
  "statusCode": 200,
  "data": {
    "seatPlans": [
      {
        "seatPlanId": "644fcf080f4f4e0001f1519d",
        "stdSeatPlanId": "...",
        "originalPrice": 2380,
        "seatPlanName": "2380元",
        "hasActivity": false,
        "canBuyCount": 4
      }
    ]
  }
}
```

### 4.6 Get Seat Plans Static Data (v3 - legacy)

```
GET /cyy_gatewayapi/show/pub/v3/show/{showId}/show_session/{sessionId}/seat_plans_static_data
```

Returns `seatPlans[]` with `seatPlanId`, `originalPrice`, etc.

### 4.7 Get Seat Plans Dynamic Data (v3 - stock/availability)

```
GET /cyy_gatewayapi/show/pub/v3/show/{showId}/show_session/{sessionId}/seat_plans_dynamic_data
```

Returns `seatPlans[]` with `canBuyCount` (remaining ticket count per price tier).

---

## 5. User Data Endpoints

### 5.1 Get User Profile

```
GET /cyy_gatewayapi/user/buyer/v3/profile
```

**Response:**
```json
{
  "statusCode": 200,
  "data": {
    "nickname": "...",
    "avatar": "https://...",
    "bizUserId": "..."
  }
}
```

### 5.2 Get User Audiences (Real-name Attendees)

```
GET /cyy_gatewayapi/user/buyer/v3/user_audiences?length=500&offset=0&src=WEB&ver=<version>
```

**Response:**
```json
{
  "statusCode": 200,
  "data": [
    {
      "id": "audience-id-123",
      "idNo": "3301**********1234",
      "idType": "ID_CARD",
      "description": "张三 3301****1234",
      "name": "张三"
    }
  ]
}
```

### 5.3 Get User Location

```
GET /cyy_gatewayapi/home/pub/v5/citys/current_location?src=WEB&ver=<version>
```

**Response:**
```json
{
  "statusCode": 200,
  "data": {
    "cityId": "4401",
    "cityName": "广州",
    "provinceId": "44",
    "provinceName": "广东",
    "siteId": "..."
  }
}
```

### 5.4 Get User Default Address

```
GET /cyy_gatewayapi/user/buyer/v3/user/addresses/default
```

**Response contains:** `addressId`, `username`, `cellphone`, `detailAddress`, `locationId`

### 5.5 Get All User Addresses

```
GET /cyy_gatewayapi/user/buyer/v3/user/addresses?src=WEB&ver=<version>
```

**Response:**
```json
{
  "statusCode": 200,
  "data": [
    {
      "addressId": "...",
      "username": "张三",
      "cellphone": "13812345678",
      "detailAddress": "XX路XX号",
      "isDefault": true,
      "location": {
        "locationId": "460102",
        "province": "46",
        "city": "01",
        "district": "02"
      }
    }
  ]
}
```

---

## 6. Order Flow

### 6.1 Pre-Order (Get Delivery Methods & Pricing)

**Web endpoint:**
```
POST /cyy_gatewayapi/trade/buyer/order/v3/pre_order
```

**APP endpoint (v5):**
```
POST https://appapi.caiyicloud.com/cyy_gatewayapi/trade/buyer/order/v5/pre_order?bizCode=FHL_M&src=android
```

**Request:**
```json
{
  "items": [
    {
      "skus": [
        {
          "seatPlanId": "644fcf080f4f4e0001f1519d",
          "sessionId": "644fcb7dca916100017dda3d",
          "showId": "644fcb2aca916100017dcfef",
          "skuId": "644fcf080f4f4e0001f1519d",
          "skuType": "SINGLE",
          "ticketPrice": 2380,
          "qty": 2
        }
      ],
      "spu": {
        "id": "644fcb2aca916100017dcfef",
        "spuType": "SINGLE"
      }
    }
  ]
}
```

**Response:**
```json
{
  "statusCode": 200,
  "data": {
    "supportDeliveries": [
      { "name": "EXPRESS" },
      { "name": "E_TICKET" }
    ],
    "priceItems": [
      {
        "priceItemName": "票款总额",
        "priceItemVal": 4760,
        "priceItemType": "TICKET_FEE",
        "direction": "INCREASE",
        "priceItemSpecies": "SEAT_PLAN"
      }
    ]
  }
}
```

### 6.2 Get Express Price Items (for EXPRESS delivery)

**Web endpoint:**
```
POST /cyy_gatewayapi/trade/buyer/order/v3/price_items
```

**APP endpoint (v5):**
```
POST https://appapi.caiyicloud.com/cyy_gatewayapi/trade/buyer/order/v5/price_items
```

**Request:**
```json
{
  "items": [
    {
      "skus": [
        {
          "seatPlanId": "...",
          "sessionId": "...",
          "showId": "...",
          "skuId": "...",
          "skuType": "SINGLE",
          "ticketPrice": 2380,
          "qty": 2,
          "deliverMethod": "EXPRESS"
        }
      ],
      "spu": {
        "id": "...",
        "spuType": "SINGLE"
      }
    }
  ],
  "locationCityId": "460102"
}
```

**Response:**
```json
{
  "statusCode": 200,
  "data": [
    {
      "priceItemName": "快递费",
      "priceItemVal": 20,
      "priceItemType": "EXPRESS_FEE",
      "direction": "INCREASE",
      "priceItemSpecies": "SEAT_PLAN"
    }
  ]
}
```

### 6.3 Create Order

**Web endpoint:**
```
POST /cyy_gatewayapi/trade/buyer/order/v3/create_order
```

**APP endpoint (v5):**
```
POST https://appapi.caiyicloud.com/cyy_gatewayapi/trade/buyer/order/v5/create_order?bizCode=FHL_M&src=android
```

**IMPORTANT: The `Blackbox` header is REQUIRED for create_order requests.**

#### Payload: EXPRESS (Physical Delivery)

```json
{
  "priceItemParam": [
    {
      "applyTickets": [],
      "priceItemName": "票款总额",
      "priceItemVal": 4760,
      "priceItemType": "TICKET_FEE",
      "priceItemSpecies": "SEAT_PLAN",
      "direction": "INCREASE",
      "priceDisplay": "￥4760"
    },
    {
      "applyTickets": [],
      "priceItemName": "快递费",
      "priceItemVal": 20,
      "priceItemId": "644fcb2aca916100017dcfef",
      "priceItemSpecies": "SEAT_PLAN",
      "priceItemType": "EXPRESS_FEE",
      "direction": "INCREASE",
      "priceDisplay": "￥20"
    }
  ],
  "items": [
    {
      "skus": [
        {
          "seatPlanId": "644fcf080f4f4e0001f1519d",
          "sessionId": "644fcb7dca916100017dda3d",
          "showId": "644fcb2aca916100017dcfef",
          "skuId": "644fcf080f4f4e0001f1519d",
          "skuType": "SINGLE",
          "ticketPrice": 2380,
          "qty": 2,
          "deliverMethod": "EXPRESS"
        }
      ],
      "spu": {
        "id": "644fcb2aca916100017dcfef",
        "spuType": "SINGLE"
      }
    }
  ],
  "contactParam": {
    "receiver": "张三",
    "cellphone": "13812345678"
  },
  "one2oneAudiences": [
    { "audienceId": "audience-id-1", "sessionId": "644fcb7dca916100017dda3d" },
    { "audienceId": "audience-id-2", "sessionId": "644fcb7dca916100017dda3d" }
  ],
  "addressParam": {
    "address": "XX路XX号",
    "district": "02",
    "city": "01",
    "province": "46",
    "addressId": "address-id-123"
  }
}
```

#### Payload: E_TICKET (Electronic Ticket)

```json
{
  "priceItemParam": [
    {
      "applyTickets": [],
      "priceItemName": "票款总额",
      "priceItemVal": 4760,
      "priceItemType": "TICKET_FEE",
      "priceItemSpecies": "SEAT_PLAN",
      "direction": "INCREASE",
      "priceDisplay": "￥4760"
    }
  ],
  "items": [
    {
      "skus": [
        {
          "seatPlanId": "...",
          "sessionId": "...",
          "showId": "...",
          "skuId": "...",
          "skuType": "SINGLE",
          "ticketPrice": 2380,
          "qty": 2,
          "deliverMethod": "E_TICKET"
        }
      ],
      "spu": {
        "id": "...",
        "spuType": "SINGLE"
      }
    }
  ],
  "many2OneAudience": {
    "audienceId": "audience-id-1",
    "sessionIds": ["644fcb7dca916100017dda3d"]
  }
}
```

#### Payload: VENUE (Pick-up at Venue)

```json
{
  "priceItemParam": [
    {
      "applyTickets": [],
      "priceItemName": "票款总额",
      "priceItemVal": 4760,
      "priceItemType": "TICKET_FEE",
      "priceItemSpecies": "SEAT_PLAN",
      "direction": "INCREASE",
      "priceDisplay": "￥4760"
    }
  ],
  "items": [
    {
      "skus": [
        {
          "seatPlanId": "...",
          "sessionId": "...",
          "showId": "...",
          "skuId": "...",
          "skuType": "SINGLE",
          "ticketPrice": 2380,
          "qty": 2,
          "deliverMethod": "VENUE"
        }
      ],
      "spu": {
        "id": "...",
        "spuType": "SINGLE"
      }
    }
  ],
  "one2oneAudiences": [
    { "audienceId": "audience-id-1", "sessionId": "..." },
    { "audienceId": "audience-id-2", "sessionId": "..." }
  ]
}
```

#### Payload: VENUE_E (Electronic + Venue, no audience required)

```json
{
  "priceItemParam": [
    {
      "applyTickets": [],
      "priceItemName": "票款总额",
      "priceItemVal": 4760,
      "priceItemType": "TICKET_FEE",
      "priceItemSpecies": "SEAT_PLAN",
      "direction": "INCREASE",
      "priceDisplay": "￥4760"
    }
  ],
  "items": [
    {
      "skus": [
        {
          "seatPlanId": "...",
          "sessionId": "...",
          "showId": "...",
          "skuId": "...",
          "skuType": "SINGLE",
          "ticketPrice": 2380,
          "qty": 2,
          "deliverMethod": "VENUE_E"
        }
      ],
      "spu": {
        "id": "...",
        "spuType": "SINGLE"
      }
    }
  ]
}
```

#### Create Order Response (Success)

```json
{
  "statusCode": 200,
  "comments": "",
  "data": {
    "createTime": 1718438500000,
    "orderId": "order-id-123",
    "orderNumber": "PXQ2024061512345",
    "unPaidTransactionIds": ["txn-id-123"],
    "paidDeadLineTime": 1718439400000
  }
}
```

### 6.4 Delivery Methods

| Value | Description |
|---|---|
| `EXPRESS` | Physical ticket delivery via express courier |
| `E_TICKET` | Electronic ticket |
| `VENUE` | Pick up at venue |
| `VENUE_E` | Electronic ticket or venue pick-up (no audience info needed) |
| `ID_CARD` | Enter venue with ID card |

### 6.5 Audience Assignment Patterns

| Delivery Method | Audience Pattern | Notes |
|---|---|---|
| EXPRESS | `one2oneAudiences` array | Each ticket mapped to one audience |
| VENUE | `one2oneAudiences` array | Same as EXPRESS |
| E_TICKET | `many2OneAudience` object | All tickets to one audience |
| VENUE_E | None | No audience info needed |

---

## 7. Order Management Endpoints

### 7.1 Get Pending Orders

```
GET /cyy_gatewayapi/trade/buyer/order/v3/pending_orders (Web)
POST https://appapi.caiyicloud.com/cyy_gatewayapi/trade/buyer/order/v5/pending_orders (APP)
```

### 7.2 Get Terminated/Historical Orders

```
GET /cyy_gatewayapi/trade/buyer/order/v3/terminate_orders (Web)
POST https://appapi.caiyicloud.com/cyy_gatewayapi/trade/buyer/order/v5/terminate_orders (APP)
```

**Order response structure:**
```json
{
  "orderId": "...",
  "orderNumber": "...",
  "firstShowName": "...",
  "qty": 2,
  "displayPosterURL": "...",
  "payAmount": 4780,
  "orderDetailState": {
    "displayName": "待支付"
  },
  "firstSessionName": "...",
  "cityName": "杭州",
  "showTimeDesc": "2024-06-15 19:30",
  "firstVenueName": "..."
}
```

---

## 8. Show Subscription Endpoints

### 8.1 Add Sale Reminder

```
POST /cyy_gatewayapi/show/buyer/v3/shows/{showId}/subscribe?showSessionId={sessionId}
```

**Request:**
```json
{
  "src": "WEB",
  "ver": "...",
  "openId": "",
  "appId": "",
  "showId": "...",
  "subscribeTargetType": "SHOW_SESSION",
  "showSessionId": "...",
  "remindType": "SALE_REMIND"
}
```

### 8.2 Ticket Waitlist (Out-of-Stock Notification)

```
POST /cyy_gatewayapi/show/buyer/v3/shows/{showId}/subscribe?showSessionId={sessionId}
```

**Request:**
```json
{
  "src": "WEB",
  "ver": "...",
  "openId": "",
  "appId": "",
  "showId": "...",
  "subscribeTargetType": "SEAT_PLAN",
  "showSessionId": "...",
  "remindType": "OOS",
  "seatPlanId": "..."
}
```

---

## 9. Tongdun (同盾) Blackbox Device Fingerprint

### What It Is

The `Blackbox` header is a Tongdun device fingerprint value that is ONLY required on `create_order` requests. It is a lightweight anti-bot measure. The pxq_ticket Tauri app generates a fake blackbox on the client side.

### How pxq_ticket Generates It (Simplified Fake)

From the Rust source code in `client.rs`:

```rust
fn random_str(len: usize) -> String {
    let char_set = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    // generate random string of given length from char_set
}

fn box_str(td: &str) -> String {
    let mut td_chars: Vec<char> = td.chars().collect();
    td_chars[0] = random_str(1);           // replace first char
    td_chars.insert(4, random_str(1));      // insert at position 4
    td_chars.insert(15, random_str(1));     // insert at position 15
    td_chars.insert(len-1, random_str(1));  // insert near end
    td_chars.into_iter().collect()
}

fn get_black_box() -> String {
    let timestamp = Local::now().timestamp();  // unix timestamp in seconds
    box_str(&format!("{}{}{}", random_str(4), timestamp, random_str(9)))
}
```

**Resulting format:**
- Start with 4 random alphanumeric chars
- Append unix timestamp (10 digits)
- Append 9 random alphanumeric chars
- Then insert random chars at positions 0, 4, 15, and second-to-last
- Final string length: ~26 characters

**Python equivalent:**

```python
import time
import random
import string

def random_str(length):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def get_blackbox():
    timestamp = str(int(time.time()))
    base = random_str(4) + timestamp + random_str(9)
    chars = list(base)
    chars[0] = random_str(1)
    chars.insert(4, random_str(1))
    chars.insert(15, random_str(1))
    chars.insert(len(chars) - 1, random_str(1))
    return ''.join(chars)
```

### Real Tongdun Blackbox

The real Tongdun device fingerprint is much more complex - it collects hardware, software, and network information, generates a device ID, and sends it to `https://sphinx.tongdun.net/sphinx/validatecode/v1` for WASM-based encryption. However, the simple fake blackbox above has been demonstrated to work for order creation.

---

## 10. Anti-Bot / Rate Limiting Measures

### CAPTCHA Types

1. **Image CAPTCHA (Photo Code):** Generated via `generate_photo_code` endpoint; returns a base64-encoded image. Required when SMS sending is rate-limited.

2. **Icon Click CAPTCHA:** For high-traffic events, an icon-selection CAPTCHA appears where users must identify and click specific icons from a background image (~6 icons per background, ~110 icon categories, ~20 background variations).

### Rate Limiting Observations

- **SMS sending:** Rate limited; triggers photo code requirement after repeated attempts
- **API requests:** No hard rate limit documented, but aggressive concurrent requests may trigger risk control
- **IP bans:** Scripts use proxy IP pools to avoid IP-level blocking
- **Request frequency:** Recommended to add small delays between requests (not too aggressive)
- **Device fingerprint:** The Blackbox header helps bypass basic device-level rate limiting on order creation

### Risk Control Strategy (from community)

- Use dynamic User-Agent strings (rotate via `fake_useragent` or similar)
- Use proxy IP pool for IP rotation
- Control request frequency to avoid triggering anti-fraud systems
- Pre-warm sessions before sale time (query show details, load seat plans)
- The v5 APP endpoints (`appapi.caiyicloud.com`) may have different rate limits than v3 web endpoints

---

## 11. API Version History

| Version Path | Base URL | Notes |
|---|---|---|
| v3 | `m.piaoxingqiu.com` | Original web API, still works |
| v5 | `m.piaoxingqiu.com` | Newer web API (sessions, seat_plans) |
| v5 + APP | `appapi.caiyicloud.com` | Android APP endpoints with `bizCode=FHL_M&src=android` |

The v5 endpoints combine session + seat plan data in fewer calls. The APP endpoints go through a different gateway but share the same `cyy_gatewayapi` path prefix.

---

## 12. Complete Ticket Purchase Flow (Step by Step)

```
1. LOGIN
   POST /cyy_gatewayapi/user/pub/v3/send_verify_code    (send SMS)
   POST /cyy_gatewayapi/user/pub/v3/login_or_register    (verify + get tokens)

2. GET SHOW INFO
   GET  /cyy_gatewayapi/show/pub/v5/show/{showId}/sessions          (get sessions)
   GET  /cyy_gatewayapi/show/pub/v5/show/{showId}/session/{sid}/seat_plans  (get price tiers)
   GET  /cyy_gatewayapi/show/pub/v3/show/{showId}/show_session/{sid}/seat_plans_dynamic_data  (check stock)

3. GET USER INFO
   GET  /cyy_gatewayapi/user/buyer/v3/user_audiences     (get attendee list)
   GET  /cyy_gatewayapi/user/buyer/v3/user/addresses      (get delivery addresses)

4. PRE-ORDER (determine delivery method)
   POST /cyy_gatewayapi/trade/buyer/order/v3/pre_order

5. GET EXPRESS FEE (if EXPRESS)
   POST /cyy_gatewayapi/trade/buyer/order/v3/price_items

6. CREATE ORDER (with Blackbox header!)
   POST /cyy_gatewayapi/trade/buyer/order/v3/create_order

7. PAY (external - user redirected to payment page)
```

---

## 13. Key ID Formats

All IDs are MongoDB ObjectId-style hex strings (24 characters):
- `showId`: `644fcb2aca916100017dcfef`
- `sessionId` (bizShowSessionId): `644fcb7dca916100017dda3d`
- `seatPlanId`: `644fcf080f4f4e0001f1519d`
- `skuId` = `seatPlanId` (they are the same value)
- `audienceId`: similar format
- `addressId`: similar format

---

## 14. Multi-Account Patterns (from fuyinkai/PXQ)

The PXQ repo indicates support for:
- Multiple account management (stored in plain text files)
- Proxy configuration per account
- Inventory monitoring (scheduled polling of seat_plans_dynamic_data)
- Auto-detection of resale/returned tickets
- Scheduled purchase timing

---

## 15. Error Handling

Common `statusCode` values:
- `200` - Success
- `401` - Token expired / unauthorized (trigger refresh_token)
- `403` - Forbidden / risk control triggered
- `429` - Rate limited
- `500` - Server error

Common `comments` messages:
- `"SUCCESS"` - Operation successful
- `"该场次已售罄"` - Session sold out
- `"超过购票上限"` - Exceeds purchase limit per person
- `"请先完成实名认证"` - Real-name verification required

---

## Sources

- [senseek/piaoxingqiu](https://github.com/senseek/piaoxingqiu) - Python ticket grabber (config.py, request.py, main.py)
- [itsharex/pxq_ticket](https://github.com/itsharex/pxq_ticket) - Tauri cross-platform client (Rust source: client.rs, user.rs, show.rs, order.rs)
- [fuyinkai/PXQ](https://github.com/fuyinkai/PXQ) - Multi-account ticket tool
- [417261937/pxq-dm](https://github.com/417261937/pxq-dm) - Python ticket monitoring script
- [票星球协议抢票APP解密 - CSDN](https://blog.csdn.net/2401_86046283/article/details/140030576)
- [爬虫笔记20-票星球抢票脚本的实现 - CSDN](https://blog.csdn.net/Yima_Dangxian/article/details/140139781)
- [票星球小程序端下单助手 - CSDN](https://blog.csdn.net/gitblog_09816/article/details/141946953)
- [票星球协议抢购与商业级授权系统全流程实战 - CSDN](https://blog.csdn.net/weixin_35770067/article/details/151140962)
- [票星球图标点选验证码YOLOV8识别 - CSDN](https://blog.csdn.net/qq_36551453/article/details/138615520)
- [同盾设备指纹 - Tongdun](https://tongdun.cn/product/bddevicefingerp)
