import pytest
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


def test_build_push_command(config):
    m = MaoyanController(config)
    cmd = m._build_push_command()
    assert "adb" in cmd
    assert "push" in cmd
    assert "maoyan_grab.js" in cmd
