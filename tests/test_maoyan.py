import pytest
from platforms.maoyan import MaoyanController


@pytest.fixture
def cfg():
    return {
        "device_id": "emulator-5554",
        "viewer_name": "张三",
        "price": 2380,
        "sale_time": "2026-04-01 10:00:00",
        "concert_name": "测试演唱会",
    }


def test_maoyan_name(cfg):
    m = MaoyanController(cfg)
    assert m.name == "猫眼"


def test_maoyan_config(cfg):
    m = MaoyanController(cfg)
    assert m.device_id == "emulator-5554"
