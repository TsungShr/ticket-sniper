import asyncio
import os
import logging

from platforms.base import PlatformGrabber
from utils.adb import adb_push, adb_shell

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
        await adb_shell(
            self.device_id,
            "am start -n org.autojs.autoxjs.v6/org.autojs.autojs.ui.main.MainActivity",
        )
        await asyncio.sleep(2)
        await adb_shell(
            self.device_id,
            f"am broadcast -a org.autojs.autoxjs.v6.action.RUN_SCRIPT "
            f"-e path {AUTOXJS_REMOTE_DIR}{self.script_name}",
        )
        logger.info("猫眼 AutoX.js 脚本已启动")

    async def _monitor_logcat(self) -> dict:
        proc = await asyncio.create_subprocess_exec(
            "adb", "-s", self.device_id,
            "logcat", "-s", "AutoX.js:I",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            while not self.stopped:
                try:
                    line = await asyncio.wait_for(
                        proc.stdout.readline(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                if not line:
                    continue
                text = line.decode(errors="replace")
                if "抢票成功" in text:
                    return {"success": True, "platform": self.name,
                            "order_id": "maoyan_autoxjs"}
                if "异常" in text or "失败" in text:
                    logger.warning(f"猫眼 AutoX.js: {text.strip()}")
        finally:
            proc.terminate()
        raise RuntimeError("猫眼: AutoX.js 脚本未成功抢票")

    async def warmup(self) -> None:
        await self._push_script()
        logger.info("猫眼预热完成")

    async def grab(self) -> dict:
        await self._start_autoxjs()
        return await asyncio.wait_for(
            self._monitor_logcat(), timeout=120
        )
