from datetime import date, datetime
from zoneinfo import ZoneInfo


def today_in(timezone: str, now: datetime | None = None) -> date:
    """Calendar date in the owner's timezone. Dates in the app are local; timestamps are UTC."""
    zone = ZoneInfo(timezone)
    return (now.astimezone(zone) if now else datetime.now(zone)).date()
