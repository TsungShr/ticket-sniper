"""ADB 工具封装 — 支持持久 shell session 和一次性命令"""
import asyncio
import logging
import time
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class AdbSession:
    """持久 ADB shell — 一条长连接，每次 tap 约 50ms"""

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self._proc: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            "adb", "-s", self.device_id, "shell",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info("ADB 持久 shell 已建立")

    async def run(self, cmd: str) -> str:
        """运行命令并等待输出（通过 echo marker 同步）"""
        if self._proc is None or self._proc.stdin.is_closing():
            raise RuntimeError("ADB session 未启动或已关闭")
        marker = f"__DONE_{id(cmd)}_{time.monotonic():.0f}__"
        full = f"{cmd}; echo {marker}\n"
        self._proc.stdin.write(full.encode())
        await self._proc.stdin.drain()
        lines: list[str] = []
        while True:
            line_bytes = await self._proc.stdout.readline()
            if not line_bytes:
                break
            text = line_bytes.decode().rstrip("\r\n")
            if marker in text:
                break
            lines.append(text)
        return "\n".join(lines)

    async def tap(self, x: int, y: int) -> None:
        """Fire-and-forget tap — 不等待输出"""
        if self._proc is None or self._proc.stdin.is_closing():
            return
        self._proc.stdin.write(f"input tap {x} {y}\n".encode())
        await self._proc.stdin.drain()

    async def tap_wait(self, x: int, y: int) -> str:
        """Tap 并等待完成（约 50ms）"""
        return await self.run(f"input tap {x} {y}")

    async def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300
    ) -> str:
        return await self.run(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    async def close(self) -> None:
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()
            self._proc = None


async def adb_command(device_id: str, *args: str) -> str:
    """执行任意 adb 命令，返回 stdout"""
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


async def adb_tap(device_id: str, x: int, y: int) -> None:
    await adb_shell(device_id, f"input tap {x} {y}")


async def adb_dump_ui(device_id: str) -> str:
    """Dump 当前 UI 层级结构并返回 XML 字符串"""
    await adb_shell(device_id, "uiautomator dump /sdcard/ui_dump.xml")
    return await adb_shell(device_id, "cat /sdcard/ui_dump.xml")


async def adb_find_and_tap(device_id: str, text: str, timeout: float = 5.0) -> bool:
    """查找包含指定文字的 UI 元素并点击中心点，找不到返回 False"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            xml_str = await adb_dump_ui(device_id)
            root = ET.fromstring(xml_str)
            for node in root.iter("node"):
                node_text = node.get("text", "")
                node_desc = node.get("content-desc", "")
                if text in node_text or text in node_desc:
                    bounds = node.get("bounds", "")
                    parts = bounds.replace("][", ",").strip("[]").split(",")
                    if len(parts) == 4:
                        x1, y1, x2, y2 = map(int, parts)
                        await adb_tap(device_id, (x1 + x2) // 2, (y1 + y2) // 2)
                        return True
        except ET.ParseError:
            pass
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


async def adb_find_all(device_id: str, texts: list[str]) -> dict[str, tuple[int, int]]:
    """一次 dump，批量查找多个文字对应的坐标，返回 {文字: (cx, cy)}"""
    found: dict[str, tuple[int, int]] = {}
    try:
        xml_str = await adb_dump_ui(device_id)
        root = ET.fromstring(xml_str)
        for node in root.iter("node"):
            node_text = node.get("text", "")
            node_desc = node.get("content-desc", "")
            for t in texts:
                if t in found:
                    continue
                if t in node_text or t in node_desc:
                    bounds = node.get("bounds", "")
                    parts = bounds.replace("][", ",").strip("[]").split(",")
                    if len(parts) == 4:
                        x1, y1, x2, y2 = map(int, parts)
                        found[t] = ((x1 + x2) // 2, (y1 + y2) // 2)
    except ET.ParseError:
        pass
    except Exception:
        pass
    return found


async def adb_screencap(device_id: str, local_path: str) -> str:
    """截图并 pull 到本地"""
    await adb_shell(device_id, "screencap -p /sdcard/screen_tmp.png")
    await adb_command(device_id, "pull", "/sdcard/screen_tmp.png", local_path)
    return local_path


async def adb_screencap_bytes(device_id: str) -> bytes:
    """直接拉取截图原始字节（不落盘）"""
    proc = await asyncio.create_subprocess_exec(
        "adb", "-s", device_id, "exec-out", "screencap", "-p",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout


async def adb_swipe(
    device_id: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300
) -> None:
    await adb_shell(device_id, f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")
