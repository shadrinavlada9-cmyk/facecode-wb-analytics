from datetime import date, timedelta

START = "2026-11-01"

AD_START = "2026-11-13"

STOCK_START = "2026-11-17"

UNKNOWN = "Не определено"

def dates(a, b):
    start, end = date.fromisoformat(a), date.fromisoformat(b)
    return [(start + timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
