from decimal import Decimal, ROUND_HALF_UP
from typing import Any
import pandas as pd
CORE_PERCENT = {'ad_drr','drr_orders','drr_revenue','ctr','cr'}

WEEKDAY_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

FUTURE = "FUTURE_NOT_LOADED"

USER_DASH = "-"

DIMENSION_METRICS = [
    "orders_rub", "orders_qty", "order_price",
    "revenue_rub", "revenue_qty", "revenue_price",
    "ad_spend", "ad_drr", "drr_orders", "drr_revenue",
    "shows", "visits", "ctr", "carts", "cart_cr",
    "ad_shows", "ad_clicks", "ad_ctr", "cpc", "stock",
    "turn_orders", "turn_sales",
    "order_share_qty", "order_share_rub", "ad_share", "stock_share", "stock_value_proxy", "stock_value_share",
]

DIMENSION_LABELS = {
    "orders_rub": "Заказы, ₽",
    "orders_qty": "Заказы, шт",
    "order_price": "ССТ заказов, ₽",
    "revenue_rub": "Выручка, ₽",
    "revenue_qty": "Выручка, шт",
    "revenue_price": "ССТ выручки, ₽",
    "ad_spend": "Продвижение, ₽",
    "ad_drr": "ДРР продвижения, %",
    "drr_orders": "ДРР заказы, %",
    "drr_revenue": "ДРР выручка, %",
    "shows": "Показы",
    "visits": "Переходы",
    "ctr": "CTR",
    "carts": "Корзина",
    "cart_cr": "CR",
    "ad_shows": "РК показы",
    "ad_clicks": "РК клики",
    "ad_ctr": "CTR РК",
    "cpc": "CPC",
    "stock": "Остаток, шт",
    "turn_orders": "Оборачиваемость в заказах, дней",
    "turn_sales": "Оборачиваемость в продажах, дней",
    "order_share_qty": "Доля заказов, шт",
    "order_share_rub": "Доля заказов, ₽",
    "ad_share": "Доля продвижения",
    "stock_share": "Доля остатка, шт",
    "stock_value_proxy": "Остаток по ССТ заказа, ₽",
    "stock_value_share": "Доля остатка в ₽ (по ССТ заказа), %",
}

PERCENT_KEYS = set(CORE_PERCENT) | {
    "drr_orders", "drr_revenue",
    "order_share_qty", "order_share_rub", "ad_share", "stock_share", "stock_value_share",
}

VISUAL_COLORS = {
    # Visual Acceptance V2: still pastel, but intentionally visible on a normal monitor.
    "positive": "#DFF2E5",
    "negative": "#F8DCDC",
    "neutral_up": "#E3F0FA",
    "neutral_down": "#FCEBCF",
    "missing": "#F2F4F7",
    "proxy1": "#FFF3C4",
    "proxy2": "#FFE1C2",
    "total": "#DDEAF6",
    "zebra": "#FBFCFD",
}

def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return Decimal(str(value))

def _number(value: Any) -> float | int | None:
    d = _decimal(value)
    if d is None:
        return None
    if d == d.to_integral_value():
        return int(d)
    return float(d)

def _fmt_decimal(value: Any, max_decimals: int = 2) -> str:
    d = _decimal(value)
    if d is None:
        return USER_DASH
    quant = Decimal("1") if max_decimals == 0 else Decimal("1." + ("0" * max_decimals))
    d = d.quantize(quant, rounding=ROUND_HALF_UP)
    sign = "-" if d < 0 else ""
    d = abs(d)
    raw = format(d, "f")
    whole, dot, frac = raw.partition(".")
    grouped = f"{int(whole):,}".replace(",", " ")
    frac = frac.rstrip("0")
    return sign + grouped + (("," + frac) if frac else "")

def format_number(value: Any) -> str:
    return _fmt_decimal(value, 2)

def format_percent(value: Any) -> str:
    d = _decimal(value)
    if d is None:
        return USER_DASH
    return f"{_fmt_decimal(d * 100, 2)}%"

def format_metric(metric: str, value: Any) -> str:
    if value == FUTURE:
        return USER_DASH
    if value is None:
        return USER_DASH
    if metric=='orders_stock_ratio':
        d=_decimal(value)
        return USER_DASH if d is None else f'{d*100:.2f}'.replace('.',',')+'%'
    return format_percent(value) if metric in PERCENT_KEYS else format_number(value)

def day_label(day: str) -> str:
    ts = pd.Timestamp(day)
    return f"{WEEKDAY_RU[ts.weekday()]} {ts.strftime('%d.%m')}"


HIGHER_IS_BETTER = {
    "orders_rub", "orders_qty", "revenue_rub", "revenue_qty", "carts",
    "ctr", "cart_cr", "order_cr", "ad_ctr", "ad_cr",
    "ad_orders_rub", "ad_orders_qty", "media_ctr", "media_cr",
    "media_orders_rub", "media_orders_qty",
}


LOWER_IS_BETTER = {
    "total_drr", "ad_drr", "media_drr", "cpc", "ad_cpo", "unavailable",
    "turn_orders", "turn_sales", "drr_orders", "drr_revenue",
}


def semantic_direction(metric: str) -> str:
    if metric in HIGHER_IS_BETTER:
        return "higher"
    if metric in LOWER_IS_BETTER:
        return "lower"
    return "neutral"


def daily_direction_style(value: Any, previous: Any) -> str:
    """Calendar-day direction, independent of metric effectiveness and rounding."""
    current, earlier = _decimal(value), _decimal(previous)
    if current is None or earlier is None or current == earlier:
        return ""
    increased = current > earlier
    color = VISUAL_COLORS["positive" if increased else "negative"]
    text = "#20633A" if increased else "#9A3030"
    return f"background-color:{color};color:{text};font-weight:600"


def delta_semantic_style(metric: str, value: Any) -> str:
    d = _decimal(value)
    if d is None:
        return f"background-color:{VISUAL_COLORS['missing']};color:#7B8490"
    if d == 0:
        return ""
    # Delta sign always expresses current vs previous; apply the same semantic direction.
    direction = semantic_direction(metric)
    increased = d > 0
    if direction == "higher":
        good = increased
        color = VISUAL_COLORS["positive" if good else "negative"]
        text = "#20633A" if good else "#9A3030"
    elif direction == "lower":
        good = not increased
        color = VISUAL_COLORS["positive" if good else "negative"]
        text = "#20633A" if good else "#9A3030"
    else:
        color = VISUAL_COLORS["neutral_up" if increased else "neutral_down"]
        text = "#35566F" if increased else "#7B5A2B"
    return f"background-color:{color};color:{text};font-weight:600"


WB_TABLE1 = [
    ("orders_rub", "Заказы, ₽"), ("orders_qty", "Заказы, шт"), ("order_price", "ССТ заказов, ₽"),
    ("revenue_rub", "Выручка, ₽"), ("revenue_qty", "Выручка, шт"), ("revenue_price", "ССТ выручки, ₽"),
    ("total_spend", "Рекламный расход итого, ₽"), ("ad_spend", "Продвижение, ₽"), ("media_spend", "Медиа, ₽"),
    ("total_drr", "ДРР общая, %"), ("shows", "Показы"), ("visits", "Переходы"), ("ctr", "CTR,%"),
    ("carts", "Корзина"), ("cart_cr", "CR,%"), ("order_cr", "CR сквозная, %"),
    ("ad_shows", "РК показы"), ("ad_clicks", "РК клики"), ("ad_ctr", "РК CTR, %"),
    ("ad_orders_rub", "РК заказы, руб"), ("ad_orders_qty", "РК заказы, шт"), ("ad_cr", "РК CR сквозная, %"),
    ("ad_drr", "РК ДРР, %"), ("ad_cpo", "РК СРО"), ("media_shows", "Медиа показы"),
    ("media_clicks", "Медиа клики"), ("media_ctr", "Медиа CTR, %"), ("media_orders_rub", "Медиа заказы, руб"),
    ("media_orders_qty", "Медиа заказы, шт"), ("media_cr", "Медиа CR сквозная, %"),
    ("media_drr", "Медиа ДРР, %"), ("stock", "Доступно к продаже, шт"),
    ("unavailable", "Недоступно к продаже, шт"), ("transit", "Товары в пути, шт"),
    ("turn_orders", "Оборачиваемость в заказах, дней"), ("turn_sales", "Оборачиваемость в продажах, дней")]


WB_PERCENT = {"ctr", "cart_cr", "order_cr", "ad_ctr", "ad_cr", "ad_drr", "drr_orders", "drr_revenue", "media_ctr", "media_cr",
             "media_drr", "total_drr", "orders_stock_ratio"}
