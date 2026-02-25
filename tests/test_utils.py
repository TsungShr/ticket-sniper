from unittest.mock import patch
import pytest
from utils.ntp_sync import get_ntp_offset
from utils.notify import send_bark


def test_ntp_offset_returns_float():
    with patch("utils.ntp_sync.ntplib.NTPClient") as mock:
        mock_response = type("R", (), {"offset": 0.05})()
        mock.return_value.request.return_value = mock_response
        offset = get_ntp_offset()
        assert isinstance(offset, float)
        assert abs(offset) < 10


@pytest.mark.asyncio
async def test_send_bark_skips_when_no_key():
    await send_bark("", "test", "body")
