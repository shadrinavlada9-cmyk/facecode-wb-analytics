"""Presentation formatting. Internal values remain numeric."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from numbers import Real
import pandas as pd

DASH = "—"
GENDER = {"Men":"Мужчины","Wmn":"Женщины"}


def missing(value):
    return value is None or bool(pd.isna(value))


def rate(label):
    return "%" in label or "п.п." in label or "ROAS" in label


def format_value(value,label=""):
    if missing(value):
        return DASH
    if isinstance(value,str):
        return GENDER.get(value,value) if value.strip().lower() not in {"none","nan","null","nat",""} else DASH
    if isinstance(value,bool):
        return "Да" if value else "Нет"
    if isinstance(value,(Decimal,Real)):
        places=2 if rate(label) or label.startswith("H7 ") else 0
        try:
            value=Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        except InvalidOperation:
            return DASH
        return f"{value:,.{places}f}".replace(","," ").replace(".",",")
    return str(value)


DEMO_LABEL = 'Демо — тестовые данные'
