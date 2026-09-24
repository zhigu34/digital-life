from datetime import UTC, date, datetime

from app.shows.service import user_today


def test_user_today_respects_profile_timezone():
    now = datetime(2026, 9, 17, 6, 30, tzinfo=UTC)
    assert user_today("America/Los_Angeles", now) == date(2026, 9, 16)
    assert user_today("Asia/Shanghai", now) == date(2026, 9, 17)
