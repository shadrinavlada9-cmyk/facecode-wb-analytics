"""Presentation-only weekly attention view over the admitted FACE CODE facts."""
from collections import defaultdict
from decimal import Decimal as D
from statistics import median
from html import escape

import pandas as pd
import streamlit as st

import management as M
from fc_format import format_value
from promotion_excel import excel

DOWN = "Снижение заказов"
UP = "Возможности роста"
STOCK = "Остатки и оборачиваемость"
ADS = "Реклама и ДРР"
CATEGORIES = (DOWN, UP, STOCK, ADS)


def title(path):
    return " / ".join(M.gender(x) if i==1 else x for i,x in enumerate(path))


def model_rows(model, records, current, previous, matches, settings=(None,)*5):
    groups = {label:[] for label in CATEGORIES}
    start,end,stamp,items = M.inventory(model)
    a = current[0],current[-1]
    b = (previous[0],previous[-1]) if previous else a
    xway,warning = M.xway(model,a,matches)
    by_path = defaultdict(list)
    for article, item in items.items():
        path = model.attributes(article)
        if matches(path):
            by_path[path].append(item)
    ad_path = defaultdict(list)
    for row in xway.values():
        ad_path[model.attributes(row["Артикул продавца"])].append(row)

    def complete(rows,key):
        values = [r.get(key) for r in rows]
        return sum(values,D(0)) if values and all(x is not None for x in values) else None

    comparable = bool(previous) and len(current)==len(previous)
    for path, record in records.items():
        if not comparable or len(path)!=3 or path[0]=="Не распределено":
            continue
        row=record["week"]
        order=record["dynamic"]["Заказы, ₽"]
        ad=record["dynamic"]["Продвижение WB, ₽"]
        before,now=order["Прошлая неделя"],order["За период"]
        delta=order["Изменение"]
        if delta is None or delta==0 or before is None or now is None:
            continue
        stock=complete(by_path[path],"FBW, шт.")
        orders7=complete(by_path[path],"Заказы за 7 дней, шт.")
        ads=ad_path[path]
        active=sorted({r["WB ID кампании"] for r in ads if r.get("Статус XWAY")=="Активна" and r.get("Дата XWAY")==a[-1]})
        xspend,xorders=(complete(ads,key) for key in ("Расход XWAY, ₽","Рекламные заказы XWAY, ₽"))
        group=DOWN if delta<0 else UP
        groups[group].append({
            "Объект":title(path),"Группа":title(path),"Заказы за период A, ₽":now,"Заказы за период B, ₽":before,
            "Δ Заказы, ₽":delta,"Δ Заказы, %":M.divide(delta,before,100),
            "Продвижение WB за период A, ₽":ad["За период"],"Продвижение WB за период B, ₽":ad["Прошлая неделя"],
            "Δ Продвижение WB, ₽":ad["Изменение"],"ДРР WB к заказам, %":M.divide(row.get("Продвижение WB, ₽"),now,100),
            "Расход XWAY, ₽":xspend,"Рекламные заказы XWAY, ₽":xorders,"ДРР XWAY, %":M.divide(xspend,xorders,100),
            "FBW, шт.":stock,"Заказы за 7 дней, шт.":orders7,"H7 по FBW, дней":M.divide(stock,orders7,7),
            "Активные РК в снимке XWAY на конец A":", ".join(active) if active else None,
            "Что проверить":("Сопоставить показы, переходы, конверсию и цену. Причина снижения требует проверки."
                 if delta<0 else "Проверить запас, маржу и эффективность кампаний перед расширением охвата.")})
    groups[DOWN].sort(key=lambda row:row["Δ Заказы, ₽"])
    groups[UP].sort(key=lambda row:-row["Δ Заказы, ₽"])

    inventory_rows=[]
    for article,item in items.items():
        path=model.attributes(article)
        qty,stock=item["Заказы за 7 дней, шт."],item["FBW, шт."]
        if not matches(path) or stock is None or qty is None or (not qty and not stock):
            continue
        inventory_rows.append({"Объект":article,"Группа":title(path),"Артикул продавца":article,
                               **{k:v for k,v in item.items() if k not in ("Снимок склада","FBS, шт.","H7 по FBW + FBS, дней")}})
    available=[r for r in inventory_rows if r["Заказы за 7 дней, шт."]>0]
    med=median(r["Заказы за 7 дней, шт."] for r in available) if available else None
    zero=sorted((r for r in inventory_rows if r["Заказы за 7 дней, шт."]==0),key=lambda r:-r["FBW, шт."])
    long=sorted((r for r in available if r["FBW, шт."]>0),key=lambda r:-r["H7 по FBW, дней"])
    demand=sorted((r for r in available if r["Заказы за 7 дней, шт."]>=med),
                  key=lambda r:(r["H7 по FBW, дней"],-r["Заказы за 7 дней, шт."]))
    queues=[
        [{**r,"Сигнал":"Нет заказов за 7 дней","Что проверить":"Проверить видимость, цену и карточку товара."} for r in zero],
        [{**r,"Сигнал":"Высокий H7 в выборке","Что проверить":"Сопоставить темп заказов с поставками и сезонностью."} for r in long],
        [{**r,"Сигнал":"Проверка обеспеченности при высоком спросе","Что проверить":"Проверить дату следующей поставки и доступный остаток."} for r in demand]]
    from itertools import zip_longest
    seen_stock=set()
    for items_by_rank in zip_longest(*queues):
        for row in items_by_rank:
            if row is not None and row["Объект"] not in seen_stock:
                groups[STOCK].append(row)
                seen_stock.add(row["Объект"])

    if xway:
        signals,_=M.signals(model,a,b,matches,settings)
        comparison_ok=bool(previous) and len(current)==len(previous) and a[0]!=b[0]
        conversions = [r for r in xway.values() if r["Клик → заказ, %"] and r["Клики"]]
        growth = []
        if conversions:
            typical_rate = median(r["Клик → заказ, %"] for r in conversions)
            typical_clicks = median(r["Клики"] for r in conversions)
            growth = sorted((r for r in conversions if r["Клик → заказ, %"]>typical_rate and r["Клики"]>=typical_clicks),
                            key=lambda row:-row["Клик → заказ, %"])
            growth = [{**r,"Причина":"Конверсия из клика в заказ выше медианы наблюдаемых карточек с заказами.",
                        "Предлагаемое действие":"Сверить ДРР, маржу и запас перед проверкой возможности усиления."} for r in growth]
        candidates=signals[M.GROUPS[0]]+signals[M.GROUPS[2]]+growth+signals[M.GROUPS[3]]
        if not comparison_ok:
            candidates=[r for r in candidates if not r.get("Период B")]
        seen=set()
        for row in candidates:
            key=row.get("WB ID кампании"),row.get("Артикул WB")
            if key in seen or not key[0]:
                continue
            seen.add(key)
            fields=("WB ID кампании","Артикул WB","Артикул продавца","Расход XWAY, ₽","Списания WB кампании, ₽",
                    "Рекламные заказы XWAY, ₽","ДРР XWAY, %","CTR, %","CPC, ₽","Клики","Дней с расходом без заказов",
                    "Клик → заказ, %","Превышение цели, п.п.","Δ CPC, ₽","Δ CTR, %","Δ ДРР XWAY, %","Δ Клик → заказ, %",
                    "Δ Рекламные заказы XWAY, ₽")
            path=(row.get("Коллекция"),row.get("Гендер"),row.get("Тип товара"))
            groups[ADS].append({
                "Объект":"РК "+str(key[0])+(" · WB "+str(key[1]) if key[1] else ""),
                "Группа":title(path) if all(path) else None,**{k:row.get(k) for k in fields},
                "Сигнал":row["Причина"],"Что проверить":row["Предлагаемое действие"]})
    return groups,(a,b if previous else None,start,end,stamp),warning


def render_cards(rows, section):
    if not rows:
        st.caption("Нет подтверждённых случаев по выбранному условию.")
        return
    fields = {
        DOWN:("Заказы за период A, ₽","Заказы за период B, ₽","Δ Заказы, ₽","Δ Заказы, %","Δ Продвижение WB, ₽","ДРР WB к заказам, %","H7 по FBW, дней"),
        UP:("Заказы за период A, ₽","Заказы за период B, ₽","Δ Заказы, ₽","Δ Заказы, %","Δ Продвижение WB, ₽","ДРР WB к заказам, %","ДРР XWAY, %","H7 по FBW, дней","Активные РК в снимке XWAY на конец A"),
        STOCK:("FBW, шт.","Заказы за 7 дней, шт.","H7 по FBW, дней"),
        ADS:("Артикул продавца","Расход XWAY, ₽","Списания WB кампании, ₽","Рекламные заказы XWAY, ₽","ДРР XWAY, %","CTR, %","CPC, ₽","Клики","Клик → заказ, %","Дней с расходом без заказов","Превышение цели, п.п.","Δ CPC, ₽","Δ CTR, %","Δ ДРР XWAY, %","Δ Клик → заказ, %"),
    }[section]
    cards=[]
    for row in rows:
        pieces=[]
        for key in fields:
            value=row.get(key)
            if value is None and key not in ("H7 по FBW, дней","ДРР WB к заказам, %","ДРР XWAY, %"):
                continue
            text=format_value(value,key)
            if "%" in key and value is not None:
                text+=" %"
            tone=""
            if key.startswith("Δ Заказы") and value:
                tone=" positive" if value>0 else " negative"
                text=("+" if value>0 else "")+text
            pieces.append(f'<span class="fc-att-metric{tone}">{escape(key)} <b>{escape(text)}</b></span>')
        note=escape(row.get("Сигнал") or "")
        subgroup=escape(row["Группа"]) if row.get("Группа") and row["Группа"]!=row["Объект"] else ""
        cards.append(f'<article><h5>{escape(row["Объект"])}</h5>'
                     +(f'<p>{subgroup}</p>' if subgroup else "")
                     +(f'<p>{note}</p>' if note else "")
                     +'<div class="fc-att-values">'+ "".join(pieces)+'</div>'
                     +f'<p><b>Проверить</b> · {escape(row["Что проверить"])}</p></article>')
    st.html('<div class="fc-att-grid">'+ "".join(cards)+'</div>')


CSS = """<style>
.fc-att-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(325px,100%),1fr));gap:10px}
.fc-att-grid article{border:1px solid #ddd;border-radius:8px;padding:10px 13px;background:#fff;color:#1c1c1c}
.fc-att-grid h5{font-size:15px;line-height:1.35;margin:0 0 4px;font-weight:650;overflow-wrap:anywhere}
.fc-att-grid p{font-size:13px;line-height:1.45;margin:4px 0;overflow-wrap:anywhere}
.fc-att-values{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:13px;line-height:1.4;font-variant-numeric:tabular-nums}
.fc-att-metric{color:#535353;overflow-wrap:anywhere}.fc-att-metric b{color:#202020}
.fc-att-metric.positive b{color:#16613a}.fc-att-metric.negative b{color:#9e2629}
</style>"""


def normalize_frame(rows):
    return pd.DataFrame(rows).dropna(axis=1,how="all").map(lambda v:float(v) if isinstance(v,D) else v)


def render(model,records,current,previous,matches=None):
    st.subheader("На что обратить внимание")
    if model is None:
        return {}
    with st.expander("Настройки проверки ДРР"):
        left,right=st.columns(2)
        target=left.number_input("Целевой ДРР XWAY, %", min_value=0.0, value=None,key="attention_target_drr")
        minimum=right.number_input("Минимальный расход XWAY, ₽",min_value=0.0,value=None,key="attention_min_spend")
    settings=(target,minimum,None,None,None)
    groups,period,warning=model_rows(model,records,current,previous,matches or (lambda p:True),settings)
    a,b,start,end,stamp=period
    analysis=f"A {' — '.join(a)} · "+(f"B {' — '.join(b)}" if b else "Сопоставимого периода B нет")
    stock_note=f"H7 · заказы {start} — {end} · снимок FBW {stamp}" if start and stamp else "H7 · недостаточно подтверждённых данных"
    st.caption(analysis+" | "+stock_note+". Статусы кампаний относятся к выгрузке XWAY.")
    st.html(CSS)
    tabs=st.tabs(CATEGORIES)
    for tab,(name,rows) in zip(tabs,groups.items()):
        with tab:
            if name==ADS and warning:
                st.caption(warning)
            render_cards(rows[:5],name)
            if rows:
                with st.expander(f"Подробности и фильтр · {len(rows)}"):
                    search=st.text_input("Группа, артикул или ID кампании",key=f"attention_filter_{name}").strip().lower()
                    selected=[r for r in rows if not search or any(search in str(r.get(k,"")).lower() for k in
                              ("Объект","Группа","Артикул продавца","WB ID кампании","Артикул WB"))]
                    if selected:
                        st.caption(f"Найдено: {len(selected)}")
                        offset=st.number_input("Страница",1,(len(selected)+9)//10,1,key=f"attention_page_{name}")
                        render_cards(selected[(offset-1)*10:offset*10],name)
                    else:
                        st.caption("Нет совпадений по фильтру.")
                payload=excel([(name,normalize_frame(rows))],{"Периоды":analysis,"Источник H7":stock_note})
                st.download_button(f"Скачать Excel · {name}",payload,f"FACE_CODE_{name}_{a[0]}_{a[1]}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",key=f"attention_excel_{name}")
    return groups




