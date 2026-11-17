from datetime import date, timedelta
import json
from base64 import b64encode
from pathlib import Path

import streamlit as st

from access import logout_button, require_access
from wb_style import GLOBAL_CSS

st.set_page_config(page_title="FACE CODE Analytics", layout="wide", initial_sidebar_state="collapsed")
st.html(GLOBAL_CSS.replace("padding-top:1.05rem","padding-top:4.5rem"))
logo = Path(__file__).with_name("face-code.svg").read_text(encoding="utf-8-sig").replace("currentColor","#171717")
logo_uri = "data:image/svg+xml;base64," + b64encode(logo.encode()).decode("ascii")
st.html(f'<style>.fc-head{{display:flex;align-items:center;gap:1rem;margin:.25rem 0 .8rem;color:#171717}} .fc-head img{{width:10.75rem;max-width:45vw;height:auto}} .fc-head span{{border-left:1px solid #ddd;padding-left:1rem;font-size:.85rem;font-weight:600}}</style><header class="fc-head" aria-label="FACE CODE Analytics"><img src="{logo_uri}" alt="FACE CODE"><span>Analytics · Wildberries</span></header>')
require_access()

import pandas as pd

from analytics_calendar import START, dates
from fc_format import DEMO_LABEL
from model import ADS, FINANCE, FUNNEL, STOCK
from runtime_model import PublishedAnalytics
import week_adapter
import week_detail

LABELS = dict(zip(FUNNEL + FINANCE + ADS + STOCK, (
    "Заказы, ₽", "Заказы, шт.", "Показы WB", "Переходы", "Корзины WB", "Отложено",
    "Выкупы, шт.", "Выкупы, ₽", "Отмены, шт.", "Отмены, ₽", "Выручка, ₽", "Выручка, шт.",
    "Товарные списания WB, ₽", "Баннеры WB, ₽", "Расход XWAY, ₽", "Рекламные заказы, ₽",
    "Рекламные заказы, шт.", "Показы XWAY", "Клики XWAY", "Корзины XWAY",
    "FBW РФ, шт.", "FBS, шт.")))
LABELS.update(stock_total="FBW + FBS, шт.", stock_value="Оценка запаса, ₽",
              stock_value_share="Доля оценки, %", stock_price_coverage="Оценено запаса, %",
              sku_gt10="SKU с остатком > 10 шт.", order_share="Доля заказов, %",
              ad_share="Доля списаний, %", actual="Фактический расход, ₽", drr="Общий ДРР, %",
              ad_drr="ДРР XWAY, %", roas="ROAS XWAY", ctr="CTR XWAY, %", cart_cr="Клик → корзина, %", cpc="CPC XWAY, ₽")
DIMENSIONS = ("Коллекция", "Гендер", "Тип товара")


path = Path(__file__).with_name("analytics.json")
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, ValueError):
    st.error("Данные демоверсии недоступны.")
    st.stop()
if not isinstance(payload, dict) or payload.get("synthetic") is not True:
    st.error("Данные демоверсии недоступны.")
    st.stop()
model = PublishedAnalytics(payload)
logout_button()
section = st.radio("Раздел", ("Неделя", "Неделя — детализация", "Продвижение"), horizontal=True)
st.caption("Последнее принятое обновление · " + payload["released_at_utc"])
st.warning(DEMO_LABEL)
latest = max((r["period_end"] for r in model.records if r["kind"] == "funnel"), default=START)
periods = [(START, START)]
cursor = date.fromisoformat(START) + timedelta(days=1)
while cursor.isoformat() <= latest:
    periods.append((cursor.isoformat(), min((cursor+timedelta(days=6)).isoformat(),latest)))
    cursor += timedelta(days=7)
a,b = st.selectbox("Период", periods, index=len(periods)-1, format_func=lambda p: " — ".join(p))
prior = (date.fromisoformat(a)-timedelta(days=7), date.fromisoformat(b)-timedelta(days=7))
prior = tuple(d.isoformat() for d in prior)
stock_through = max((d for d,_ in model.stock if b <= d <= (date.fromisoformat(a)+timedelta(days=6)).isoformat()), default=b)
if stock_through > b:
    st.caption(f"Остатки на {stock_through}")
if model.get(a,b,"fbw_stock",stock_through) is not None and model.get(a,b,"fbs_stock",stock_through) is None:
    st.caption("FBS без подтверждения. Оценка в ₽ и счётчик SKU относятся к FBW РФ.")
covered = sum("funnel_orders_rub" in model.cover[d,d] for d in dates(a,b))
st.caption("WEEKLY принят" if model.accepted(a,b) else f"DAILY {covered}/{len(dates(a,b))} · недельное закрытие не подтверждено")
if payload["classification_stale"]:
    st.warning("Используется предыдущая принятая классификация.")
with st.expander("Покрытие источников"):
    st.dataframe(pd.DataFrame([{
        "Дата": day, **{LABELS[m]: model.get(day,day,m) is not None
                       for m in ("funnel_orders_rub","revenue_rub","wb_spend","media_spend","xway_spend",*STOCK)}
    } for day in dates(a,b if stock_through == b else stock_through)]), hide_index=True)
    st.caption(f"Конфликты с правилом нулевой рекламы: {payload['conflict_count']}. "
               f"Строки списаний с неустановленной принадлежностью: {payload['unresolved_count']}.")

selection = [st.sidebar.multiselect(label, sorted({v[i] for v in model.mapping.values()}))
             for i,label in enumerate(DIMENSIONS)]
matches = lambda p: all(not values or p[i] in values for i,values in enumerate(selection))
metrics = FUNNEL + FINANCE + ADS[:3] + STOCK


if section == "Продвижение":
    from promotion_view import render
    render(model,(a,b),prior,matches)
else:
    adapted = week_adapter.read_scope(model,a,b,prior,matches,stock_through)
    if section == "Неделя":
        week_adapter.render_week(model,adapted)
    else:
        week_detail.render(*adapted[:2],model=model,matches=matches)






