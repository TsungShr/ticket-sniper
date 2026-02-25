import pytest
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


def test_build_blackbox(config):
    g = PiaoxingqiuGrabber(config)
    bb = g._build_blackbox()
    assert isinstance(bb, str)
    assert len(bb) > 10


def test_build_order_payload(config):
    g = PiaoxingqiuGrabber(config)
    payload = g._build_order_payload(audience_ids=["aud_1"], deliver_method="E_TICKET")
    assert payload["seatPlanId"] == "seat_789"
    assert payload["audienceIds"] == ["aud_1"]
    assert payload["showId"] == "show_123"
