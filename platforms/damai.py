import asyncio
import logging

from platforms.base import PlatformGrabber

logger = logging.getLogger(__name__)


class DamaiController(PlatformGrabber):
    """大麦 Appium 辅助型自动化"""

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
        import time
        loop = asyncio.get_event_loop()

        def _flow():
            for i in range(30):
                if self.stopped:
                    raise RuntimeError("被协调器停止")

                if (self._find_and_click("立即购买", 1) or
                        self._find_and_click("立即抢购", 1)):
                    time.sleep(0.3)

                self._find_and_click("2380", 1)
                time.sleep(0.1)

                viewer = self.cfg.get("viewer_name", "")
                if viewer:
                    self._find_and_click(viewer, 1)
                    time.sleep(0.1)

                if self._find_and_click("同意以上协议并提交订单", 1):
                    logger.info("=== 大麦: 已自动提交订单 ===")
                    time.sleep(1)
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

                time.sleep(0.3)

            raise RuntimeError("大麦: 达到最大重试次数")

        return await loop.run_in_executor(None, _flow)

    async def warmup(self) -> None:
        await self._connect_appium()
        logger.info("大麦预热完成 — 请确保已手动登录并进入演出详情页")

    async def grab(self) -> dict:
        return await asyncio.wait_for(
            self._run_grab_flow(), timeout=120
        )
