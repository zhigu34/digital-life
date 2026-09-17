from datetime import UTC, date, datetime
import subprocess
import sys

from app.shows.service import user_today


def test_user_today_respects_profile_timezone():
    now = datetime(2026, 9, 17, 6, 30, tzinfo=UTC)
    assert user_today("America/Los_Angeles", now) == date(2026, 9, 16)
    assert user_today("Asia/Shanghai", now) == date(2026, 9, 17)


def test_show_schema_import_order_preserves_legacy_exports():
    code = (
        "from app.shows.schemas import ShowPayload; "
        "from app.schemas import ShowPayload as LegacyShowPayload; "
        "assert ShowPayload is LegacyShowPayload"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
