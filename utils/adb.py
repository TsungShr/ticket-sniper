import asyncio
import logging

logger = logging.getLogger(__name__)


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
