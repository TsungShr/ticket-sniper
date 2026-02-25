import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class AdbSession:
    """Persistent ADB shell — one long-lived connection, ~50ms per tap."""

    def __init__(self, device_id: str):
        self.device_id = device_id
        self._proc: asyncio.subprocess.Process | None = None

    async def start(self):
        self._proc = await asyncio.create_subprocess_exec(
            "adb", "-s", self.device_id, "shell",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info("ADB 持久 shell 已建立")

    async def run(self, cmd: str) -> str:
        """Run a command and wait for output using an echo marker."""
        marker = f"__DONE_{id(cmd)}_{time.monotonic_ns()}__"
        full = f"{cmd}; echo {marker}\n"
        self._proc.stdin.write(full.encode())
        await self._proc.stdin.drain()
        lines = []
        while True:
            line = await self._proc.stdout.readline()
            text = line.decode().rstrip("\r\n")
            if marker in text:
                break
            lines.append(text)
        return "\n".join(lines)

    async def tap(self, x: int, y: int):
        """Fire-and-forget tap — don't wait for output."""
        self._proc.stdin.write(f"input tap {x} {y}\n".encode())
        await self._proc.stdin.drain()

    async def tap_wait(self, x: int, y: int):
        """Tap and wait for completion (~50ms)."""
        await self.run(f"input tap {x} {y}")

    async def close(self):
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()
            self._proc = None


async def adb_command(device_id: str, *args: str) -> str:
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
    """Dump current UI hierarchy and return XML string."""
    await adb_shell(device_id, "uiautomator dump /sdcard/ui_dump.xml")
    return await adb_shell(device_id, "cat /sdcard/ui_dump.xml")


async def adb_find_and_tap(device_id: str, text: str, timeout: float = 5.0) -> bool:
    """Find a UI element containing text and tap its center. Returns True if found."""
    import xml.etree.ElementTree as ET
    import time
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
                    # bounds format: [x1,y1][x2,y2]
                    parts = bounds.replace("][", ",").strip("[]").split(",")
                    if len(parts) == 4:
                        x1, y1, x2, y2 = map(int, parts)
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                        await adb_tap(device_id, cx, cy)
                        return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


async def adb_find_all(device_id: str, texts: list[str]) -> dict[str, tuple[int, int]]:
    """One dump, find coordinates for multiple texts. Returns {text: (cx, cy)}."""
    import xml.etree.ElementTree as ET
    found = {}
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
    except Exception:
        pass
    return found


async def adb_screencap(device_id: str, local_path: str) -> str:
    """Take a screenshot and pull to local path."""
    await adb_shell(device_id, "screencap -p /sdcard/screen_tmp.png")
    await adb_command(device_id, "pull", "/sdcard/screen_tmp.png", local_path)
    return local_path


async def adb_swipe(
    device_id: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300
) -> None:
    await adb_shell(device_id, f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")
