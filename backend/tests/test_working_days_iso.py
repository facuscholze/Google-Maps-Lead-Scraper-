"""BUG-03: queue working_days are ISO 1-7 (1=lunes … 7=domingo), never 0-6."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.services.emailing.queue import EmailQueueService


def test_validator_requires_iso_weekdays():
    with pytest.raises(ValidationError):
        Settings(working_days="0")          # 0 is NOT a valid ISO weekday
    with pytest.raises(ValidationError):
        Settings(working_days="8")
    with pytest.raises(ValidationError):
        Settings(working_days="lunes")

    ok = Settings(working_days="1,2,3,4,5")
    assert ok.working_day_set == {1, 2, 3, 4, 5}

    ok = Settings(working_days="7")         # domingo es válido
    assert ok.working_day_set == {7}


def _window_check(day: datetime) -> bool:  # helper standalone=self check w/o db
    service = EmailQueueService.__new__(EmailQueueService)
    return service._within_allowed_window(day)  # type: ignore[call-arg]


def test_queue_window_uses_isoweekday(monkeypatch):
    tz = ZoneInfo(settings.default_timezone)
    # 2026-10-14 es MIÉRCOLES → isoweekday()==3, weekday()==2
    wednesday = datetime(2026, 10, 14, 12, 0, tzinfo=tz)
    assert wednesday.isoweekday() == 3

    monkeypatch.setattr(settings, "working_days", "3")      # miércoles (ISO)
    assert _window_check(wednesday) is True

    monkeypatch.setattr(settings, "working_days", "2")      # martes (ISO)
    assert _window_check(wednesday) is False

    # domingo 2026-10-18 → ISO 7
    sunday = datetime(2026, 10, 18, 12, 0, tzinfo=tz)
    assert sunday.isoweekday() == 7
    monkeypatch.setattr(settings, "working_days", "6,7")
    assert _window_check(sunday) is True
