# 周杰伦2026杭州演唱会抢票系统 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建多平台并发抢票系统，在开售瞬间同时从票星球、猫眼、大麦三个平台抢购2380元档位门票。

**Architecture:** Mac 作为控制中心运行 Python 协调器，票星球走纯 API，猫眼用 AutoX.js 安卓自动化 + 小程序 API 双路，大麦用 Appium 辅助型自动化。三平台 asyncio 并发，任一成功即停止其他。

**Tech Stack:** Python 3.11+, asyncio, aiohttp, Appium, AutoX.js, ADB, ntplib, PyYAML, Bark API

---

### Task 1: 项目脚手架 + 基础工具模块

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `platforms/__init__.py`
- Create: `platforms/base.py`
- Create: `utils/__init__.py`
- Create: `utils/ntp_sync.py`
- Create: `utils/notify.py`
- Test: `tests/test_utils.py`

**Step 1: 创建 requirements.txt**

```txt
aiohttp>=3.9.0
requests>=2.31.0
PyYAML>=6.0
ntplib>=0.4.0
Appium-Python-Client>=3.0.0
```

**Step 2: 创建配置文件 config.yaml**

```yaml
concert:
  name: "周杰伦2026杭州演唱会"
  price: 2380
  weekday_preference: [saturday, sunday]

sale_time: "2026-04-01 10:00:00"  # 待确认具体日期

damai:
  device_id: ""
  appium_port: 4723
  show_id: ""
  sku_id: ""
  viewer_name: ""

maoyan:
  device_id: ""
  autoxjs_script: "maoyan_grab.js"

piaoxingqiu:
  phone: ""
  access_token: ""
  refresh_token: ""
  show_id: ""
  session_id: ""
  seat_plan_id: ""
  concurrent_requests: 3

notification:
  bark_key: ""
  serverchan_key: ""
```

**Step 3: 创建平台基类 platforms/base.py**

```python
import asyncio
from abc import ABC, abstractmethod


class PlatformGrabber(ABC):
    """所有平台抢票模块的基类"""

    def __init__(self, config: dict):
        self.config = config
        self._stop_event = asyncio.Event()

    @property
    @abstractmethod
    def name(self) -> str:
        """平台名称"""

    @abstractmethod
    async def warmup(self) -> None:
        """开售前预热：检查登录状态、预加载数据"""

    @abstractmethod
    async def grab(self) -> dict:
        """
        执行抢票。
        成功返回 {"success": True, "platform": self.name, "order_id": "..."}
        失败抛出异常。
        """

    def stop(self) -> None:
        """被协调器调用，通知停止抢票"""
        self._stop_event.set()

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()
```

**Step 4: 创建 NTP 时间同步 utils/ntp_sync.py**

```python
import time
import ntplib


def get_ntp_offset(server: str = "ntp.aliyun.com") -> float:
    """获取本地时间与 NTP 服务器的偏差（秒）"""
    client = ntplib.NTPClient()
    response = client.request(server, version=3)
    return response.offset


async def wait_until_sale_time(sale_timestamp: float, ntp_offset: float) -> None:
    """精确等待到开售时刻"""
    import asyncio

    while True:
        now = time.time() + ntp_offset
        remaining = sale_timestamp - now
        if remaining <= 0:
            break
        if remaining > 1:
            await asyncio.sleep(remaining - 0.5)
        else:
            await asyncio.sleep(0.001)  # 最后1秒用毫秒级轮询
```

**Step 5: 创建通知推送 utils/notify.py**

```python
import aiohttp
import logging

logger = logging.getLogger(__name__)


async def send_bark(key: str, title: str, body: str) -> None:
    """Bark iOS 推送"""
    if not key:
        return
    url = f"https://api.day.app/{key}/{title}/{body}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                logger.info("Bark 通知发送成功")


async def send_serverchan(key: str, title: str, body: str) -> None:
    """Server酱微信推送"""
    if not key:
        return
    url = f"https://sctapi.ftqq.com/{key}.send"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={"title": title, "desp": body}) as resp:
            if resp.status == 200:
                logger.info("Server酱通知发送成功")


async def notify(config: dict, title: str, body: str) -> None:
    """统一通知入口"""
    nc = config.get("notification", {})
    await send_bark(nc.get("bark_key", ""), title, body)
    await send_serverchan(nc.get("serverchan_key", ""), title, body)
```

**Step 6: 写测试 tests/test_utils.py**

```python
import time
from unittest.mock import patch, AsyncMock
import pytest

from utils.ntp_sync import get_ntp_offset
from utils.notify import send_bark


def test_ntp_offset_returns_float():
    """NTP offset should be a float within reasonable range"""
    with patch("utils.ntp_sync.ntplib.NTPClient") as mock:
        mock_response = type("R", (), {"offset": 0.05})()
        mock.return_value.request.return_value = mock_response
        offset = get_ntp_offset()
        assert isinstance(offset, float)
        assert abs(offset) < 10  # should be less than 10 seconds


@pytest.mark.asyncio
async def test_send_bark_skips_when_no_key():
    """Bark should skip silently when key is empty"""
    await send_bark("", "test", "body")  # should not raise
```

**Step 7: 运行测试验证**

Run: `cd /Users/andrianlee/proj/fetch-tickets && python -m pytest tests/test_utils.py -v`
Expected: PASS

**Step 8: 创建 __init__.py 文件**

```python
# platforms/__init__.py
# utils/__init__.py
```

**Step 9: Commit**

```bash
git add requirements.txt config.yaml platforms/ utils/ tests/
git commit -m "feat: add project scaffold with base class, NTP sync, and notifications"
```

---

### Task 2: 票星球 API 模块（核心 — 成功率最高）

**Files:**
- Create: `platforms/piaoxingqiu.py`
- Test: `tests/test_piaoxingqiu.py`

**Step 1: 写测试 tests/test_piaoxingqiu.py**

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from platforms.piaoxingqiu import PiaoxingqiuGrabber


@pytest.fixture
def config():
    return {
        "piaoxingqiu": {
            "phone": "13800138000",
            "access_token": "test_token",
            "refresh_token": "test_refresh",
            "show_id": "show_123",
            "session_id": "session_456",
            "seat_plan_id": "seat_789",
            "concurrent_requests": 2,
        }
    }


def test_grabber_name(config):
    g = PiaoxingqiuGrabber(config)
    assert g.name == "票星球"


def test_build_headers(config):
    g = PiaoxingqiuGrabber(config)
    headers = g._build_headers()
    assert headers["access-token"] == "test_token"
    assert "src" in headers
    assert "ver" in headers


def test_build_blackbox():
    g = PiaoxingqiuGrabber({"piaoxingqiu": {"access_token": "t"}})
    bb = g._build_blackbox()
    assert isinstance(bb, str)
    assert len(bb) > 10


@pytest.mark.asyncio
async def test_create_order_payload(config):
    g = PiaoxingqiuGrabber(config)
    payload = g._build_order_payload(
        audience_ids=["aud_1"],
        deliver_method="E_TICKET",
    )
    assert "seatPlanId" in payload
    assert payload["seatPlanId"] == "seat_789"
    assert "audienceIds" in payload
```

**Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_piaoxingqiu.py -v`
Expected: FAIL (module not found)

**Step 3: 实现 platforms/piaoxingqiu.py**

```python
import asyncio
import random
import string
import time
import logging

import aiohttp

from platforms.base import PlatformGrabber

logger = logging.getLogger(__name__)

API_HOST = "m.piaoxingqiu.com"
APP_API_HOST = "appapi.caiyicloud.com"
API_VER = "4.1.2-20240305183007"
API_SRC = "WEB"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 "
    "Mobile/15E148 Safari/604.1"
)


class PiaoxingqiuGrabber(PlatformGrabber):
    @property
    def name(self) -> str:
        return "票星球"

    def __init__(self, config: dict):
        super().__init__(config)
        self.cfg = config.get("piaoxingqiu", {})
        self.access_token = self.cfg.get("access_token", "")
        self.refresh_token_str = self.cfg.get("refresh_token", "")

    def _build_headers(self) -> dict:
        return {
            "User-Agent": UA,
            "access-token": self.access_token,
            "host": API_HOST,
            "terminal-src": API_SRC,
            "src": API_SRC,
            "ver": API_VER,
            "origin": f"https://{API_HOST}",
            "referer": f"https://{API_HOST}",
            "content-type": "application/json",
        }

    @staticmethod
    def _random_str(length: int) -> str:
        chars = string.ascii_letters + string.digits
        return "".join(random.choices(chars, k=length))

    def _build_blackbox(self) -> str:
        """生成 Blackbox 请求头（同盾设备指纹模拟）"""
        ts = str(int(time.time()))
        raw = self._random_str(4) + ts + self._random_str(9)
        chars = list(raw)
        chars[0] = self._random_str(1)
        chars.insert(4, self._random_str(1))
        chars.insert(15, self._random_str(1))
        chars.insert(len(chars) - 1, self._random_str(1))
        return "".join(chars)

    def _build_order_payload(
        self, audience_ids: list[str], deliver_method: str = "E_TICKET"
    ) -> dict:
        return {
            "showId": self.cfg.get("show_id", ""),
            "sessionId": self.cfg.get("session_id", ""),
            "seatPlanId": self.cfg.get("seat_plan_id", ""),
            "audienceIds": audience_ids,
            "deliverMethod": deliver_method,
        }

    async def _api_get(
        self, session: aiohttp.ClientSession, path: str
    ) -> dict:
        url = f"https://{API_HOST}/{path}"
        async with session.get(url, headers=self._build_headers()) as resp:
            return await resp.json()

    async def _api_post(
        self, session: aiohttp.ClientSession, path: str, json_data: dict
    ) -> dict:
        url = f"https://{API_HOST}/{path}"
        headers = self._build_headers()
        if "create_order" in path:
            headers["Blackbox"] = self._build_blackbox()
        async with session.post(url, json=json_data, headers=headers) as resp:
            return await resp.json()

    async def refresh_token(self, session: aiohttp.ClientSession) -> None:
        """刷新 access_token"""
        path = (
            f"cyy_gatewayapi/user/pub/v3/refresh_token"
            f"?refreshToken={self.refresh_token_str}"
        )
        data = await self._api_post(
            session, path, {"src": API_SRC, "ver": API_VER,
                            "refreshToken": self.refresh_token_str}
        )
        if data.get("statusCode") == 200 and data.get("data"):
            self.access_token = data["data"]["accessToken"]
            self.refresh_token_str = data["data"]["refreshToken"]
            logger.info("票星球 Token 刷新成功")

    async def get_show_detail(self, session: aiohttp.ClientSession) -> dict:
        """获取演出详情"""
        show_id = self.cfg.get("show_id", "")
        path = (
            f"cyy_gatewayapi/show/pub/v3/show/{show_id}"
            f"?src={API_SRC}&ver={API_VER}"
        )
        return await self._api_get(session, path)

    async def get_audiences(self, session: aiohttp.ClientSession) -> list:
        """获取观演人列表"""
        path = (
            f"cyy_gatewayapi/user/buyer/v3/user_audiences"
            f"?length=500&offset=0&src={API_SRC}&ver={API_VER}"
        )
        data = await self._api_get(session, path)
        return data.get("data", []) or []

    async def create_order(
        self, session: aiohttp.ClientSession, audience_ids: list[str]
    ) -> dict:
        """提交订单"""
        path = (
            "cyy_gatewayapi/trade/buyer/order/v3/create_order"
            "?bizCode=FHL_M&src=WEB"
        )
        payload = self._build_order_payload(audience_ids)
        return await self._api_post(session, path, payload)

    async def warmup(self) -> None:
        """预热：刷新 Token + 获取观演人"""
        async with aiohttp.ClientSession() as session:
            await self.refresh_token(session)
            audiences = await self.get_audiences(session)
            if audiences:
                self._audience_ids = [a["id"] for a in audiences[:1]]
                logger.info(f"票星球预热完成，观演人: {audiences[0].get('name')}")
            else:
                raise RuntimeError("票星球: 未找到观演人，请先在 App 中添加")

    async def _single_grab(
        self, session: aiohttp.ClientSession, attempt: int
    ) -> dict:
        """单次抢票尝试"""
        logger.info(f"票星球 尝试 #{attempt}")
        result = await self.create_order(session, self._audience_ids)
        status = result.get("statusCode")
        if status == 200:
            order_id = result.get("data", {}).get("orderId", "unknown")
            return {"success": True, "platform": self.name,
                    "order_id": order_id}
        raise RuntimeError(
            f"票星球下单失败: {result.get('comments', status)}"
        )

    async def grab(self) -> dict:
        """并发抢票"""
        concurrent = self.cfg.get("concurrent_requests", 3)
        max_retries = 10
        async with aiohttp.ClientSession() as session:
            for retry in range(max_retries):
                if self.stopped:
                    raise asyncio.CancelledError("被协调器停止")
                tasks = [
                    self._single_grab(session, retry * concurrent + i)
                    for i in range(concurrent)
                ]
                results = await asyncio.gather(
                    *tasks, return_exceptions=True
                )
                for r in results:
                    if isinstance(r, dict) and r.get("success"):
                        return r
                logger.warning(f"票星球 第{retry+1}轮全部失败，0.2秒后重试")
                await asyncio.sleep(0.2)
        raise RuntimeError("票星球: 达到最大重试次数")
```

**Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_piaoxingqiu.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add platforms/piaoxingqiu.py tests/test_piaoxingqiu.py
git commit -m "feat: add Piaoxingqiu API grabber module"
```

---

### Task 3: 猫眼 AutoX.js 脚本

**Files:**
- Create: `autoxjs/maoyan_grab.js`

**Step 1: 编写 AutoX.js 猫眼抢票脚本**

```javascript
// maoyan_grab.js — 猫眼抢票 AutoX.js 脚本
// 使用前：安卓设备安装猫眼 App + AutoX.js
// 手动登录猫眼，进入目标演出详情页，再运行此脚本

"auto";

// ==================== 配置区 ====================
var CONFIG = {
    targetPrice: "2380",        // 目标票价关键字
    targetSession: "周六",      // 目标场次关键字（周六/周日）
    viewerName: "",             // 观演人姓名（留空则选第一个）
    saleTime: "2026-04-01 10:00:00", // 开售时间
    maxRetry: 50,               // 最大重试次数
    clickInterval: 80,          // 点击间隔(ms)
};

// ==================== 工具函数 ====================
function log(msg) {
    console.log("[猫眼抢票] " + msg);
    toast(msg);
}

function clickElement(selector, timeout) {
    timeout = timeout || 3000;
    var el = selector.findOne(timeout);
    if (el) {
        var b = el.bounds();
        click(b.centerX(), b.centerY());
        log("点击: " + el.text() || el.desc());
        return true;
    }
    return false;
}

function waitAndClick(textStr, timeout) {
    timeout = timeout || 5000;
    return clickElement(textContains(textStr), timeout);
}

function getSaleTimestamp() {
    var parts = CONFIG.saleTime.split(/[- :]/);
    var d = new Date(parts[0], parts[1] - 1, parts[2],
                     parts[3], parts[4], parts[5]);
    return d.getTime();
}

// ==================== 主流程 ====================
function main() {
    auto.waitFor();
    log("无障碍服务已启用");

    // 等待到开售时间
    var saleTs = getSaleTimestamp();
    var now = new Date().getTime();
    var waitMs = saleTs - now - 2000; // 提前2秒开始
    if (waitMs > 0) {
        log("等待开售，还有 " + Math.round(waitMs / 1000) + " 秒");
        sleep(waitMs);
        log("进入抢票倒计时！");
    }

    // 精确等待到开售时刻
    while (new Date().getTime() < saleTs) {
        sleep(10);
    }
    log("开售！开始抢票！");

    for (var i = 0; i < CONFIG.maxRetry; i++) {
        // Step 1: 点击"立即购票"或"选座购买"
        if (clickElement(textContains("立即购票"), 500) ||
            clickElement(textContains("选座购买"), 500) ||
            clickElement(textContains("立即预订"), 500)) {
            log("已点击购票按钮");
            sleep(CONFIG.clickInterval);
        }

        // Step 2: 选择目标票价档位
        if (clickElement(textContains(CONFIG.targetPrice), 500)) {
            log("已选择票价: " + CONFIG.targetPrice);
            sleep(CONFIG.clickInterval);
        }

        // Step 3: 选择场次
        if (CONFIG.targetSession &&
            clickElement(textContains(CONFIG.targetSession), 300)) {
            log("已选择场次: " + CONFIG.targetSession);
            sleep(CONFIG.clickInterval);
        }

        // Step 4: 确认选座 / 选好了
        if (clickElement(textContains("选好了"), 500) ||
            clickElement(textContains("确认"), 500)) {
            log("已确认选座");
            sleep(CONFIG.clickInterval);
        }

        // Step 5: 选择观演人（如果出现）
        if (CONFIG.viewerName) {
            clickElement(textContains(CONFIG.viewerName), 300);
        } else {
            // 点击第一个可选的观演人
            var viewer = className("android.widget.CheckBox").findOne(500);
            if (viewer && !viewer.checked()) {
                var vb = viewer.bounds();
                click(vb.centerX(), vb.centerY());
                log("已选择观演人");
            }
        }

        // Step 6: 提交订单
        if (clickElement(textContains("提交订单"), 500) ||
            clickElement(textContains("确认订单"), 500)) {
            log("已提交订单！");
            sleep(CONFIG.clickInterval);
        }

        // Step 7: 检查是否到了支付页面
        if (textContains("去支付").findOne(300) ||
            textContains("待支付").findOne(300) ||
            textContains("支付").findOne(300)) {
            log("=== 抢票成功！请手动完成支付 ===");
            // 发送通知
            var intent = new android.content.Intent(
                android.content.Intent.ACTION_VIEW,
                android.net.Uri.parse("bark://notification?title=猫眼抢票成功&body=请立即支付")
            );
            break;
        }

        // Step 8: 处理失败情况 — 返回重试
        if (textContains("已售罄").findOne(200) ||
            textContains("暂无").findOne(200) ||
            textContains("缺货").findOne(200)) {
            log("暂时无票，返回重试 #" + (i + 1));
            back();
            sleep(200);
        }

        sleep(CONFIG.clickInterval);
    }
}

// ==================== 启动 ====================
try {
    main();
} catch (e) {
    log("异常: " + e);
}
```

**Step 2: Commit**

```bash
git add autoxjs/maoyan_grab.js
git commit -m "feat: add AutoX.js Maoyan ticket grabbing script"
```

---

### Task 4: 猫眼 Python 控制模块

**Files:**
- Create: `platforms/maoyan.py`
- Create: `utils/adb.py`
- Test: `tests/test_maoyan.py`

**Step 1: 写测试 tests/test_maoyan.py**

```python
import pytest
from unittest.mock import patch, AsyncMock
from platforms.maoyan import MaoyanController


@pytest.fixture
def config():
    return {
        "maoyan": {
            "device_id": "emulator-5554",
            "autoxjs_script": "maoyan_grab.js",
        }
    }


def test_maoyan_name(config):
    m = MaoyanController(config)
    assert m.name == "猫眼"


def test_build_adb_push_command(config):
    m = MaoyanController(config)
    cmd = m._build_push_command()
    assert "adb" in cmd
    assert "push" in cmd
    assert "maoyan_grab.js" in cmd
```

**Step 2: 创建 ADB 工具 utils/adb.py**

```python
import asyncio
import logging

logger = logging.getLogger(__name__)


async def adb_command(device_id: str, *args: str) -> str:
    """执行 ADB 命令并返回输出"""
    cmd = ["adb", "-s", device_id] + list(args)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode().strip()
    if proc.returncode != 0:
        err = stderr.decode().strip()
        logger.error(f"ADB error: {err}")
        raise RuntimeError(f"ADB command failed: {err}")
    return output


async def adb_push(device_id: str, local_path: str, remote_path: str) -> str:
    return await adb_command(device_id, "push", local_path, remote_path)


async def adb_shell(device_id: str, shell_cmd: str) -> str:
    return await adb_command(device_id, "shell", shell_cmd)
```

**Step 3: 实现 platforms/maoyan.py**

```python
import asyncio
import os
import logging

from platforms.base import PlatformGrabber
from utils.adb import adb_push, adb_shell, adb_command

logger = logging.getLogger(__name__)

AUTOXJS_REMOTE_DIR = "/sdcard/Scripts/"


class MaoyanController(PlatformGrabber):
    @property
    def name(self) -> str:
        return "猫眼"

    def __init__(self, config: dict):
        super().__init__(config)
        self.cfg = config.get("maoyan", {})
        self.device_id = self.cfg.get("device_id", "")
        self.script_name = self.cfg.get("autoxjs_script", "maoyan_grab.js")

    def _build_push_command(self) -> str:
        local = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "autoxjs", self.script_name,
        )
        return f"adb -s {self.device_id} push {local} {AUTOXJS_REMOTE_DIR}"

    async def _push_script(self) -> None:
        """将 AutoX.js 脚本推送到安卓设备"""
        local = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "autoxjs", self.script_name,
        )
        await adb_push(
            self.device_id, local,
            f"{AUTOXJS_REMOTE_DIR}{self.script_name}",
        )
        logger.info(f"猫眼脚本已推送到设备 {self.device_id}")

    async def _start_autoxjs(self) -> None:
        """通过 ADB 启动 AutoX.js 并运行脚本"""
        # 启动 AutoX.js App
        await adb_shell(
            self.device_id,
            "am start -n org.autojs.autoxjs.v6/org.autojs.autojs.ui.main.MainActivity",
        )
        await asyncio.sleep(2)
        # 通过 AutoX.js 的命令行接口运行脚本
        await adb_shell(
            self.device_id,
            f"am broadcast -a org.autojs.autoxjs.v6.action.RUN_SCRIPT "
            f"-e path {AUTOXJS_REMOTE_DIR}{self.script_name}",
        )
        logger.info("猫眼 AutoX.js 脚本已启动")

    async def _monitor_logcat(self) -> dict:
        """监控 logcat 输出，检测抢票结果"""
        proc = await asyncio.create_subprocess_exec(
            "adb", "-s", self.device_id,
            "logcat", "-s", "AutoX.js:I",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            while not self.stopped:
                line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=1.0
                )
                if not line:
                    continue
                text = line.decode(errors="replace")
                if "抢票成功" in text:
                    return {"success": True, "platform": self.name,
                            "order_id": "maoyan_autoxjs"}
                if "异常" in text or "失败" in text:
                    logger.warning(f"猫眼 AutoX.js: {text.strip()}")
        except asyncio.TimeoutError:
            pass
        finally:
            proc.terminate()
        raise RuntimeError("猫眼: AutoX.js 脚本未成功抢票")

    async def warmup(self) -> None:
        """预热：推送脚本到设备"""
        await self._push_script()
        logger.info("猫眼预热完成")

    async def grab(self) -> dict:
        """启动 AutoX.js 抢票并监控结果"""
        await self._start_autoxjs()
        return await asyncio.wait_for(
            self._monitor_logcat(), timeout=120
        )
```

**Step 4: 运行测试**

Run: `python -m pytest tests/test_maoyan.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add platforms/maoyan.py utils/adb.py tests/test_maoyan.py
git commit -m "feat: add Maoyan AutoX.js controller with ADB integration"
```

---

### Task 5: 大麦 Appium 辅助模块

**Files:**
- Create: `platforms/damai.py`
- Test: `tests/test_damai.py`

**Step 1: 写测试 tests/test_damai.py**

```python
import pytest
from platforms.damai import DamaiController


@pytest.fixture
def config():
    return {
        "damai": {
            "device_id": "emulator-5554",
            "appium_port": 4723,
            "show_id": "show_123",
            "sku_id": "sku_456",
            "viewer_name": "张三",
        }
    }


def test_damai_name(config):
    d = DamaiController(config)
    assert d.name == "大麦"


def test_desired_caps(config):
    d = DamaiController(config)
    caps = d._build_caps()
    assert caps["platformName"] == "Android"
    assert caps["appPackage"] == "cn.damai"
    assert caps["noReset"] is True
```

**Step 2: 实现 platforms/damai.py**

```python
import asyncio
import logging

from platforms.base import PlatformGrabber

logger = logging.getLogger(__name__)


class DamaiController(PlatformGrabber):
    """大麦 Appium 辅助型自动化（半自动 — 最终提交需人工点击）"""

    @property
    def name(self) -> str:
        return "大麦"

    def __init__(self, config: dict):
        super().__init__(config)
        self.cfg = config.get("damai", {})
        self.device_id = self.cfg.get("device_id", "")
        self.appium_port = self.cfg.get("appium_port", 4723)
        self.driver = None

    def _build_caps(self) -> dict:
        return {
            "platformName": "Android",
            "automationName": "UiAutomator2",
            "deviceName": self.device_id,
            "appPackage": "cn.damai",
            "appActivity": "cn.damai.homepage.MainActivity",
            "noReset": True,
            "autoGrantPermissions": True,
            "newCommandTimeout": 300,
        }

    async def _connect_appium(self) -> None:
        """连接 Appium Server"""
        from appium import webdriver
        from appium.options.android import UiAutomator2Options

        options = UiAutomator2Options()
        for k, v in self._build_caps().items():
            options.set_capability(k, v)

        loop = asyncio.get_event_loop()
        self.driver = await loop.run_in_executor(
            None,
            lambda: webdriver.Remote(
                f"http://127.0.0.1:{self.appium_port}",
                options=options,
            ),
        )
        logger.info(f"大麦 Appium 已连接设备 {self.device_id}")

    def _find_and_click(self, text: str, timeout: int = 5) -> bool:
        """查找包含指定文本的元素并点击"""
        from appium.webdriver.common.appiumby import AppiumBy
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            el = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(
                    (AppiumBy.XPATH,
                     f'//*[contains(@text, "{text}")]')
                )
            )
            el.click()
            logger.info(f"大麦: 点击 [{text}]")
            return True
        except Exception:
            return False

    async def _run_grab_flow(self) -> dict:
        """在 executor 中运行 Appium 自动化流程"""
        import time

        loop = asyncio.get_event_loop()

        def _flow():
            max_retries = 30
            for i in range(max_retries):
                if self.stopped:
                    raise RuntimeError("被协调器停止")

                # Step 1: 点击"立即购买"/"立即预约"
                if (self._find_and_click("立即购买", 1) or
                        self._find_and_click("立即抢购", 1)):
                    time.sleep(0.3)

                # Step 2: 选择 2380 元档
                self._find_and_click("2380", 1)
                time.sleep(0.1)

                # Step 3: 选择观演人
                viewer = self.cfg.get("viewer_name", "")
                if viewer:
                    self._find_and_click(viewer, 1)
                    time.sleep(0.1)

                # Step 4: 辅助到此为止 — 等待人工提交
                # 检查是否已经到了确认订单页
                if self._find_and_click("同意以上协议并提交订单", 1):
                    logger.info("=== 大麦: 已自动提交订单 ===")
                    time.sleep(1)
                    # 检查支付页面
                    from appium.webdriver.common.appiumby import AppiumBy
                    try:
                        self.driver.find_element(
                            AppiumBy.XPATH,
                            '//*[contains(@text, "支付")]'
                        )
                        return {
                            "success": True,
                            "platform": "大麦",
                            "order_id": "damai_appium",
                        }
                    except Exception:
                        pass

                # 处理失败
                time.sleep(0.3)

            raise RuntimeError("大麦: 达到最大重试次数")

        return await loop.run_in_executor(None, _flow)

    async def warmup(self) -> None:
        """预热：连接 Appium"""
        await self._connect_appium()
        logger.info("大麦预热完成 — 请确保已手动登录并进入演出详情页")

    async def grab(self) -> dict:
        """执行抢票"""
        return await asyncio.wait_for(
            self._run_grab_flow(), timeout=120
        )
```

**Step 3: 运行测试**

Run: `python -m pytest tests/test_damai.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add platforms/damai.py tests/test_damai.py
git commit -m "feat: add Damai Appium semi-auto controller"
```

---

### Task 6: 协调器主入口 + 集成测试

**Files:**
- Create: `main.py`
- Test: `tests/test_main.py`

**Step 1: 写测试 tests/test_main.py**

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio


@pytest.mark.asyncio
async def test_orchestrator_stops_on_first_success():
    """验证任一平台成功后停止其他"""
    from main import run_orchestrator

    mock_pxq = AsyncMock()
    mock_pxq.grab.return_value = {
        "success": True, "platform": "票星球", "order_id": "123"
    }
    mock_pxq.warmup = AsyncMock()
    mock_pxq.stop = MagicMock()

    mock_my = AsyncMock()
    mock_my.grab = AsyncMock(side_effect=asyncio.sleep(999))
    mock_my.warmup = AsyncMock()
    mock_my.stop = MagicMock()

    mock_dm = AsyncMock()
    mock_dm.grab = AsyncMock(side_effect=asyncio.sleep(999))
    mock_dm.warmup = AsyncMock()
    mock_dm.stop = MagicMock()

    result = await run_orchestrator(
        grabbers=[mock_pxq, mock_my, mock_dm],
        sale_timestamp=0,  # 立即开始
        ntp_offset=0,
        notify_config={},
    )
    assert result["success"] is True
    assert result["platform"] == "票星球"
```

**Step 2: 实现 main.py**

```python
#!/usr/bin/env python3
"""
周杰伦2026杭州演唱会抢票系统 — 协调器主入口
三平台并发抢票：票星球 > 猫眼 > 大麦
"""
import asyncio
import logging
import sys
import time
from datetime import datetime

import yaml

from platforms.base import PlatformGrabber
from platforms.piaoxingqiu import PiaoxingqiuGrabber
from platforms.maoyan import MaoyanController
from platforms.damai import DamaiController
from utils.ntp_sync import get_ntp_offset, wait_until_sale_time
from utils.notify import notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S.%f",
)
logger = logging.getLogger("orchestrator")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def run_orchestrator(
    grabbers: list[PlatformGrabber],
    sale_timestamp: float,
    ntp_offset: float,
    notify_config: dict,
) -> dict:
    """核心协调器：并发抢票，任一成功即停止其他"""

    # 预热所有平台
    for g in grabbers:
        try:
            await g.warmup()
            logger.info(f"[{g.name}] 预热完成")
        except Exception as e:
            logger.error(f"[{g.name}] 预热失败: {e}")

    # 等待开售时刻
    if sale_timestamp > 0:
        remaining = sale_timestamp - (time.time() + ntp_offset)
        if remaining > 0:
            logger.info(f"等待开售，还有 {remaining:.1f} 秒")
            await wait_until_sale_time(sale_timestamp, ntp_offset)

    logger.info("=== 开售！三平台并发抢票 ===")

    # 并发执行
    tasks = {
        asyncio.create_task(g.grab(), name=g.name): g
        for g in grabbers
    }

    result = None
    done, pending = await asyncio.wait(
        tasks.keys(), return_when=asyncio.FIRST_COMPLETED
    )

    # 检查完成的任务
    for task in done:
        try:
            r = task.result()
            if isinstance(r, dict) and r.get("success"):
                result = r
                logger.info(
                    f"=== 抢票成功！平台: {r['platform']}，"
                    f"订单号: {r.get('order_id')} ==="
                )
                break
        except Exception as e:
            logger.error(f"[{task.get_name()}] 失败: {e}")

    # 停止所有还在运行的
    for task in pending:
        grabber = tasks[task]
        grabber.stop()
        task.cancel()
    # 等待取消完成
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    # 发送通知
    if result:
        await notify(
            {"notification": notify_config},
            "抢票成功！",
            f"平台: {result['platform']}，订单号: {result.get('order_id')}",
        )
    else:
        await notify(
            {"notification": notify_config},
            "抢票失败",
            "三个平台均未成功",
        )
        result = {"success": False, "platform": "none", "order_id": ""}

    return result


async def main():
    config = load_config()

    # NTP 时间同步
    try:
        ntp_offset = get_ntp_offset()
        logger.info(f"NTP 时间偏差: {ntp_offset*1000:.1f}ms")
    except Exception as e:
        logger.warning(f"NTP 同步失败，使用本地时间: {e}")
        ntp_offset = 0.0

    # 解析开售时间
    sale_time_str = config.get("sale_time", "")
    if sale_time_str:
        sale_dt = datetime.strptime(sale_time_str, "%Y-%m-%d %H:%M:%S")
        sale_timestamp = sale_dt.timestamp()
    else:
        logger.warning("未设置开售时间，立即开始")
        sale_timestamp = 0

    # 初始化三个平台
    grabbers: list[PlatformGrabber] = []

    # 票星球（优先级最高）
    if config.get("piaoxingqiu", {}).get("access_token"):
        grabbers.append(PiaoxingqiuGrabber(config))
        logger.info("票星球模块: 已启用")

    # 猫眼
    if config.get("maoyan", {}).get("device_id"):
        grabbers.append(MaoyanController(config))
        logger.info("猫眼模块: 已启用")

    # 大麦
    if config.get("damai", {}).get("device_id"):
        grabbers.append(DamaiController(config))
        logger.info("大麦模块: 已启用")

    if not grabbers:
        logger.error("没有启用任何平台！请检查 config.yaml")
        sys.exit(1)

    logger.info(f"已启用 {len(grabbers)} 个平台: "
                + ", ".join(g.name for g in grabbers))

    # 开始抢票
    result = await run_orchestrator(
        grabbers=grabbers,
        sale_timestamp=sale_timestamp,
        ntp_offset=ntp_offset,
        notify_config=config.get("notification", {}),
    )

    if result["success"]:
        logger.info("请立即完成支付！")
    else:
        logger.info("本次抢票未成功，可以等待回流票或下一轮")


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 3: 运行测试**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add orchestrator with concurrent multi-platform grabbing"
```

---

### Task 7: 票星球登录工具（交互式 SMS 登录）

**Files:**
- Create: `tools/pxq_login.py`

**Step 1: 实现登录工具**

```python
#!/usr/bin/env python3
"""
票星球 SMS 登录工具
运行后输入手机号和验证码，自动获取 Token 并写入 config.yaml
"""
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
    """发送短信验证码"""
    # Step 1: 生成图形验证码（可能需要）
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
    photo_data = resp.json()
    token = ""
    if photo_data.get("statusCode") == 200:
        print("图形验证码已生成（如需要请在浏览器中完成）")

    # Step 2: 发送短信
    resp = requests.post(
        f"{API_HOST}/cyy_gatewayapi/user/pub/v3/send_verify_code",
        json={
            "src": API_SRC, "ver": API_VER,
            "verifyCodeUseType": "USER_LOGIN",
            "cellphone": phone,
            "messageType": "MOBILE",
            "token": token,
        },
        headers=HEADERS,
    )
    result = resp.json()
    return result.get("statusCode") == 200


def login(phone: str, code: str) -> dict:
    """使用验证码登录"""
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
    """将 Token 写入 config.yaml"""
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
```

**Step 2: Commit**

```bash
git add tools/pxq_login.py
git commit -m "feat: add Piaoxingqiu SMS login tool"
```

---

### Task 8: 票星球演出查询工具

**Files:**
- Create: `tools/pxq_show.py`

**Step 1: 实现演出查询工具**

```python
#!/usr/bin/env python3
"""
票星球演出查询工具
查询演出详情，获取 show_id, session_id, seat_plan_id 并写入 config.yaml
"""
import requests
import yaml
import sys
import json

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
    """搜索演出"""
    resp = requests.get(
        f"{API_HOST}/cyy_gatewayapi/show/pub/v3/show/search",
        params={"keyword": keyword, "src": API_SRC, "ver": API_VER},
        headers=get_headers(token),
    )
    data = resp.json()
    return data.get("data", {}).get("list", []) if data.get("statusCode") == 200 else []


def get_show_detail(token: str, show_id: str) -> dict:
    """获取演出详情"""
    resp = requests.get(
        f"{API_HOST}/cyy_gatewayapi/show/pub/v3/show/{show_id}",
        params={"src": API_SRC, "ver": API_VER},
        headers=get_headers(token),
    )
    return resp.json()


def get_sessions(token: str, show_id: str) -> list:
    """获取场次列表"""
    resp = requests.get(
        f"{API_HOST}/cyy_gatewayapi/show/pub/v3/show/{show_id}/sessions",
        params={"src": API_SRC, "ver": API_VER},
        headers=get_headers(token),
    )
    data = resp.json()
    return data.get("data", []) if data.get("statusCode") == 200 else []


def get_seat_plans(token: str, show_id: str, session_id: str) -> list:
    """获取票档列表"""
    resp = requests.get(
        f"{API_HOST}/cyy_gatewayapi/show/pub/v3/show/{show_id}/session/{session_id}/seat_plans",
        params={"src": API_SRC, "ver": API_VER},
        headers=get_headers(token),
    )
    data = resp.json()
    return data.get("data", []) if data.get("statusCode") == 200 else []


def main():
    config = load_config()
    token = config["piaoxingqiu"]["access_token"]
    if not token:
        print("请先运行 tools/pxq_login.py 登录")
        sys.exit(1)

    keyword = input("搜索演出 (如: 周杰伦): ").strip() or "周杰伦"
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

    # 获取场次
    sessions = get_sessions(token, show_id)
    if sessions:
        print("\n场次列表:")
        for i, s in enumerate(sessions):
            print(f"  [{i}] {s.get('sessionName', '')} {s.get('bizShowSessionId', '')}")
        sidx = int(input("选择场次编号: ").strip())
        session = sessions[sidx]
        session_id = session["bizShowSessionId"]

        # 获取票档
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

    # 更新 config
    config["piaoxingqiu"]["show_id"] = show_id
    config["piaoxingqiu"]["session_id"] = session_id
    config["piaoxingqiu"]["seat_plan_id"] = seat_plan_id

    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    print(f"\n配置已保存! show_id={show_id}, session_id={session_id}, seat_plan_id={seat_plan_id}")


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add tools/pxq_show.py
git commit -m "feat: add Piaoxingqiu show search and config tool"
```

---

### Task 9: 端到端集成测试 + README

**Files:**
- Create: `tests/test_integration.py`
- Create: `conftest.py`

**Step 1: 创建 conftest.py（pytest 路径配置）**

```python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
```

**Step 2: 写集成测试 tests/test_integration.py**

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_full_flow_pxq_success():
    """端到端：票星球成功时，其他平台被取消"""
    from main import run_orchestrator
    from platforms.base import PlatformGrabber

    class MockPXQ(PlatformGrabber):
        name = "票星球"
        async def warmup(self): pass
        async def grab(self):
            await asyncio.sleep(0.1)
            return {"success": True, "platform": "票星球", "order_id": "pxq_001"}

    class MockMaoyan(PlatformGrabber):
        name = "猫眼"
        async def warmup(self): pass
        async def grab(self):
            await asyncio.sleep(999)

    class MockDamai(PlatformGrabber):
        name = "大麦"
        async def warmup(self): pass
        async def grab(self):
            await asyncio.sleep(999)

    with patch("main.notify", new_callable=AsyncMock):
        result = await run_orchestrator(
            grabbers=[MockPXQ({}), MockMaoyan({}), MockDamai({})],
            sale_timestamp=0,
            ntp_offset=0,
            notify_config={},
        )

    assert result["success"] is True
    assert result["platform"] == "票星球"
    assert result["order_id"] == "pxq_001"


@pytest.mark.asyncio
async def test_all_fail():
    """端到端：三个平台都失败"""
    from main import run_orchestrator
    from platforms.base import PlatformGrabber

    class MockFail(PlatformGrabber):
        def __init__(self, config, pname):
            super().__init__(config)
            self._name = pname
        @property
        def name(self): return self._name
        async def warmup(self): pass
        async def grab(self):
            raise RuntimeError(f"{self._name} failed")

    with patch("main.notify", new_callable=AsyncMock):
        result = await run_orchestrator(
            grabbers=[
                MockFail({}, "票星球"),
                MockFail({}, "猫眼"),
                MockFail({}, "大麦"),
            ],
            sale_timestamp=0,
            ntp_offset=0,
            notify_config={},
        )

    assert result["success"] is False
```

**Step 3: 运行全部测试**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/ conftest.py
git commit -m "feat: add integration tests for orchestrator"
```

---

### Task 10: 安装依赖 + 最终验证

**Step 1: 安装 Python 依赖**

Run: `cd /Users/andrianlee/proj/fetch-tickets && pip install -r requirements.txt`

**Step 2: 安装 pytest-asyncio**

Run: `pip install pytest-asyncio`

**Step 3: 运行全部测试套件**

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 4: 验证 main.py 可启动（dry run）**

Run: `python main.py --help 2>&1 || python -c "from main import load_config; print(load_config())"`
Expected: 能读取配置文件

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: finalize project setup and verify all tests pass"
```

---

## 使用流程（开售前准备）

```
1. pip install -r requirements.txt
2. python tools/pxq_login.py        # 票星球 SMS 登录，获取 Token
3. python tools/pxq_show.py         # 搜索演出，获取 show_id 等
4. 编辑 config.yaml 填入:
   - sale_time（开售时间）
   - damai.device_id（安卓设备序列号，adb devices 查看）
   - maoyan.device_id
   - notification.bark_key（可选）
5. 安卓设备 A: 安装大麦 App，手动登录进入演出详情页
6. 安卓设备 B: 安装猫眼 App + AutoX.js，手动登录进入演出详情页
7. Mac 启动 Appium Server: appium -p 4723
8. 开售前 5 分钟运行: python main.py
```
