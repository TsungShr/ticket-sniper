import pytest
from platforms.damai import DamaiController


@pytest.fixture
def cfg():
    return {
        "device_id": "emulator-5554",
        "viewer_name": "张三",
        "buy_btn": [1600, 2650],
        "confirm_btn": [920, 2500],
    }


def test_damai_name(cfg):
    d = DamaiController(cfg)
    assert d.name == "大麦"


def test_damai_coords(cfg):
    d = DamaiController(cfg)
    assert d.buy_btn == [1600, 2650]
    assert d.confirm_btn == [920, 2500]
    assert d.device_id == "emulator-5554"
