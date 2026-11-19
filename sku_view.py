"""Compact, opt-in card drilldowns and the matching Excel tables."""
from decimal import Decimal
import json

import pandas as pd
import streamlit as st

from fc_format import format_value
import sku_data as data

EXCEL_DATA_LIMIT = 1048573

def start_run():
    st.session_state["_wb_sku_exports"] = {}


def frame(rows):
    return pd.DataFrame(rows).map(lambda value: float(value) if isinstance(value, Decimal) else value)


@st.cache_data(show_spinner=False, max_entries=64)
def detail_tables(generation, period, path, campaign, allowed_articles, _model):
    rows = data.cards(_model, period, path, lambda attrs: tuple(attrs) == tuple(path), campaign, allowed_articles)
    return rows, data.variants(_model, rows)


def available_paths(model, matches, rows=None):
    options = data.paths(model, matches)
    if rows is None:
        return options
    direct = {tuple(r.get(key) for key in ("Коллекция", "Гендер", "Тип товара")) for r in rows}
    groups = {r.get("Группа") for r in rows}
    return [path for path in options if path in direct or " / ".join(path) in groups]


def render(model, period, matches, key, book, *, rows=None, daily=False, title="Артикулы WB", campaign=None):
    if not model.wb_detail["catalog"]:
        return
    exports = st.session_state.setdefault("_wb_sku_exports", {})
    exports.pop(key, None)
    choices = available_paths(model, matches, rows)
    if not choices:
        return
    with st.expander(title):
        labels = {" / ".join(path): path for path in choices}
        selected_label = st.selectbox(
            "Тип товара", list(labels), index=None, placeholder="Выберите тип товара", key="sku_path_" + key,
        )
        if selected_label is None:
            return
        selected = labels[selected_label]
        picked = period
        if daily:
            days = tuple(pd.date_range(period[0], period[1]).strftime("%Y-%m-%d"))
            day = st.selectbox("День", [None, *days], key="sku_day_" + key,
                               format_func=lambda value: value or "За весь период")
            if day is not None:
                picked = day, day
        search = st.text_input("Артикул WB, артикул продавца или ЦМ", key="sku_search_" + key).strip().casefold()
        generation = tuple(sorted(model.wb_detail["source_snapshots"].items()))
        allowed = None
        if rows and all(row.get("Артикул продавца") or row.get("Артикул WB") for row in rows):
            chosen_ids = {str(row["Артикул WB"]) for row in rows if row.get("Артикул WB")}
            chosen_articles = {row["Артикул продавца"] for row in rows if row.get("Артикул продавца")}
            catalog = model.wb_detail["catalog"]
            chosen_ids.update(nm for article in chosen_articles for nm in catalog.get(article, {}).get("nm_ids", []))
            allowed = tuple(sorted(article for article, info in catalog.items() if article in chosen_articles
                                   or any(nm in chosen_ids for nm in info["nm_ids"])))
        cards, variants = detail_tables(generation, tuple(picked), tuple(selected), campaign, allowed, model)
        if search:
            cards = [row for row in cards if any(search in str(row.get(k) or "").casefold()
                     for k in (data.NM, data.SELLER, "ЦМ"))]
            variants = data.variants(model, cards)
        stamp = data.stock_date(model)
        start7, end7 = data.horizon(model)
        st.caption(f"Период {' — '.join(picked)} · остатки на {stamp} · H7 {start7} — {end7}.")
        st.caption("Заказы, выручка и реклама относятся к карточке. Размерные остатки приведены отдельно.")
        if model.get(stamp, stamp, "fbs_stock") is None:
            st.caption("FBS не подтверждён.")
        if not cards:
            st.info("Нет артикулов по выбранным условиям.")
            return
        shown = frame(cards)
        numeric = [column for column in shown if pd.api.types.is_numeric_dtype(shown[column])]
        formats = {column: (lambda value, label=column: format_value(value, label)) for column in numeric}
        formats.update({column: (lambda value: "—" if pd.isna(value) else f"{value:,.2f}".replace(",", " ").replace(".", ","))
                        for column in numeric if column.endswith("₽")})
        st.dataframe(shown.style.format(formats, na_rep="—"), hide_index=True, width="stretch",
                     height=min(420, 45 + 35 * len(shown)))
        if any(row["Сопоставление"] == data.UNMATCHED for row in cards):
            st.caption("Несопоставленные артикулы сохранены в итогах. Суммы между предполагаемыми nmID не распределялись.")
        if variants:
            st.caption("Размеры и баркоды · только подтверждённые остатки")
            detail = frame(variants)
            st.dataframe(detail.style.format({"Остаток, шт.": "{:,.0f}"}, na_rep="—"), hide_index=True,
                         width="stretch", height=min(320, 45 + 35 * len(detail)))
        exports[key] = {"book": book, "cards": cards, "variants": variants}


def extra_sheets(book):
    selected = [value for value in st.session_state.get("_wb_sku_exports", {}).values() if value["book"] == book]
    result = []
    seen = set()
    for item in selected:
        signature = json.dumps([item["cards"], item["variants"]], sort_keys=True, default=str)
        if signature in seen:
            continue
        seen.add(signature)
        number = len(seen)
        for label, rows in (("Артикулы WB", item["cards"]), ("Варианты WB", item["variants"])):
            if not rows:
                continue
            # Both existing writers reserve up to three rows for metadata/header.
            for offset in range(0, len(rows), EXCEL_DATA_LIMIT):
                suffix = f" {number}" if number > 1 else ""
                suffix += f" ч.{offset // EXCEL_DATA_LIMIT + 1}" if offset else ""
                exported = [{column: value / 100 if column.endswith("%") and value is not None else value
                             for column,value in row.items()} for row in rows[offset:offset + EXCEL_DATA_LIMIT]]
                result.append((label + suffix, exported))
    return result


def promotion(rows, key):
    context = st.session_state.get("_wb_sku_promotion")
    if context is None or not rows or not any("Тип товара" in row for row in rows):
        return
    model, period, matches = context
    book = ("promotion_recs" if key.startswith("signals") else
            "promotion_overview" if key.startswith("overview") else "promotion_campaigns")
    campaign = st.session_state.get("_wb_sku_campaign") if key.startswith("overview") else None
    render(model, period, matches, key, book, rows=rows, title="Артикулы WB", campaign=campaign)
