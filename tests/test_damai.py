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
