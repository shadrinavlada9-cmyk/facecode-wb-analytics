"""Bind the selected FACE CODE facts to the accepted WB week renderers."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal as D
from io import BytesIO

import pandas as pd
import streamlit as st

from model import FUNNEL, FINANCE, STOCK, confirmed_sum
from management import UNATTRIBUTED, gender
from analytics_calendar import dates, START
import week_detail as detail
import week_controls as controls
from wb_format import day_label, DIMENSION_LABELS, WB_PERCENT, WB_TABLE1, delta_semantic_style, format_percent

AD = ("wb_spend", "xway_spend", "ad_orders_rub", "ad_shows", "ad_clicks", "media_spend")
METRICS = FUNNEL + FINANCE + AD + STOCK
ORDER_FIELDS = dict(zip((detail.ORDERS_RUB, detail.ORDERS_QTY, detail.PROMO),
                        (*FUNNEL[:2], "wb_spend")))


def share(a, b):
    return a/b if a is not None and b else None


def diff(a, b):
    return a-b if a is not None and b is not None else None


def mean(series):
    values = [v for v in series if v is not None]
    return sum(values,D(0))/len(values) if values else None


def has_activity(rows, *, empty_is_activity=True):
    numeric = [v for row in rows for v in row.values() if isinstance(v,(int,D,float)) and pd.notna(v)]
    return any(v != 0 for v in numeric) if numeric else empty_is_activity


def visible_paths(report, history):
    detailed_metrics = (*FUNNEL[:2],*FINANCE,"wb_spend","xway_spend",*STOCK,"stock_total","stock_value","sku_gt10")
    for path in report:
        if not path or not any(v in ("Не определено","Не распределено") for v in path):
            yield path
            continue
        evidence = [{metric:row.get(metric) for metric in detailed_metrics}
                    for r in (report,*history) for key,row in r.items() if key[:len(path)]==path]
        if has_activity(evidence,empty_is_activity=path[0]!="Не распределено"):
            yield path

def read_scope(model, a, b, prior, matches, stock_through):
    current = dates(a,b)
    previous = dates(*prior) if prior[0] >= START else []
    calendar = detail._dated(a)
    now = model.report(a,b,METRICS,matches,stock_through)
    old = model.report(*prior,METRICS,matches) if previous else {}
    daily = {day:model.report(day,day,METRICS,matches) for day in set(current+previous+list(calendar))}
    schemes = {"fbw":"fbw_stock", "fbs":"fbs_stock", "total":"stock_total"}
    stock_days = {k:[d for d in calendar if daily[d][()].get(metric) is not None] for k,metric in schemes.items()}
    stock_days = {key:days for key,days in stock_days.items() if days}

    def item(report, path, metric):
        if path in report:
            return report[path].get(metric)
        return D(0) if report.get((),{}).get(metric) is not None else None

    records = {}
    for path in visible_paths(now,(old,*daily.values())):
        row = now[path]
        rec = {title: row.get(key) for title,key in ORDER_FIELDS.items()}
        rec.update({detail.REVENUE_RUB:row["revenue_rub"], detail.REVENUE_QTY:row["revenue_qty"],
                    detail.XWAY:row["xway_spend"], detail.SKU_COLUMN:row["sku_gt10"]})
        dynamic = {}
        for title,key in ORDER_FIELDS.items():
            value, earlier = row[key], item(old,path,key)
            change = diff(value,earlier)
            series = {d:item(daily[d],path,key) if d in current else None for d in calendar}
            series.update({detail.WEEK_NOW:value, detail.WEEK_PREV:earlier, detail.DELTA:change,
                           detail.RELATIVE:share(change,earlier)})
            series.update({detail.WEEK_PRIOR_DAY+d:item(daily[earlier_day],path,key)
                           for d,earlier_day in zip(current,previous)})
            dynamic[title] = series
        rec["Прошлая неделя · заказы, ₽"] = dynamic[detail.ORDERS_RUB][detail.WEEK_PREV]
        rec["Заказы · к прошлой неделе, %"] = dynamic[detail.ORDERS_RUB][detail.RELATIVE]
        stocks = {}
        for scheme, days in stock_days.items():
            for unit in ("шт.","₽"):
                stock_series = {}
                for d in calendar:
                    qty = item(daily[d],path,schemes[scheme]) if d in days else None
                    price = share(row[FUNNEL[0]],row[FUNNEL[1]])
                    stock_series[d] = qty if unit == "шт." or qty is None or not qty else (qty*price if price is not None else None)
                avg = mean(stock_series.values())
                delta = diff(stock_series[current[-1]],stock_series[current[0]])
                stocks[scheme,unit] = {**stock_series,"Среднее":avg,detail.DELTA:delta,
                    detail.RELATIVE:share(delta,stock_series[current[0]]),
                    detail.COVERAGE:share(row["stock_price_coverage"],D(100)) if unit=="₽" else None}
                rec[detail._stock_metrics(scheme,unit)] = avg
                if unit == "шт.":
                    rec[detail._stock_change(scheme)+", шт."] = delta
                    rec[detail._stock_change(scheme)+", %"] = stocks[scheme,unit][detail.RELATIVE]
        scheme = next((s for s in ("total","fbw","fbs") if s in stock_days),None)
        for unit in ("шт.","₽"):
            rec[f"Средний запас · {unit}"] = rec.get(detail._stock_metrics(scheme,unit)) if scheme else None
        rec[detail.COVERAGE] = share(row["stock_price_coverage"],D(100))
        records[path] = {"week":rec,"dynamic":dynamic,"stocks":stocks}
    for record in records.values():
        row = record["week"]
        for numerator, label in detail.SHARES.items():
            row[label] = share(row.get(numerator),records[()]["week"].get(numerator))
    records[()]["unknown_count"] = sum(p[0]=="Не определено" for p in records if len(p)==3)
    overview = {dest:now[()].get(src) for dest,src in
                {"orders_rub":FUNNEL[0], "orders_qty":FUNNEL[1], "revenue_rub":"revenue_rub",
                 "revenue_qty":"revenue_qty","ad_spend":"wb_spend"}.items()}
    result = {"period_meta":{"period_start":a,"period_end":b},"totals":overview}
    return result, (a,b,current,previous,"FACE_CODE","ALL",(records,stock_days,{},[])), now, old, daily


FACT_MAP = {
    "orders_rub":FUNNEL[0],"orders_qty":FUNNEL[1],"revenue_rub":"revenue_rub","revenue_qty":"revenue_qty",
    "ad_spend":"wb_spend","shows":"shows","visits":"visits","carts":"carts","ad_shows":"ad_shows",
    "ad_clicks":"ad_clicks","ad_orders_rub":"ad_orders_rub","ad_orders_qty":"ad_orders_qty","media_spend":"media_spend","xway_spend":"xway_spend","stock":"fbw_stock","stock_value_proxy":"stock_value",
    "Остаток FBS, шт":"fbs_stock","Остаток FBW РФ + FBS, шт":"stock_total",detail.SKU_COLUMN:"sku_gt10",
}
RATIOS = {
    "order_price":(FUNNEL[0],FUNNEL[1]),"revenue_price":("revenue_rub","revenue_qty"),
    "ad_drr":("xway_spend","ad_orders_rub"),"drr_orders":("wb_spend",FUNNEL[0]),
    "drr_revenue":("wb_spend","revenue_rub"),"ctr":("visits","shows"),"cart_cr":("carts","visits"),
    "ad_ctr":("ad_clicks","ad_shows"),"order_cr":(FUNNEL[1],"visits"),"ad_cr":("ad_orders_qty","ad_clicks"),"ad_cpo":("xway_spend","ad_orders_qty"),"cpc":("xway_spend","ad_clicks"),
}
SHARES = {"order_share_qty":FUNNEL[1],"order_share_rub":FUNNEL[0],"ad_share":"wb_spend",
          "stock_share":"fbw_stock","stock_value_share":"stock_value"}


def metrics(row, total):
    result = {k:row.get(v) for k,v in FACT_MAP.items()}
    result.update({k:share(row.get(num),row.get(den)) for k,(num,den) in RATIOS.items()})
    result["total_spend"] = confirmed_sum(row.get(k) for k in ("wb_spend","media_spend"))
    result["total_drr"] = share(result["total_spend"],row.get(FUNNEL[0]))
    result.update({k:share(row.get(v),total.get(v)) for k,v in SHARES.items()})
    return result


def group(report, index):
    rows = defaultdict(list)
    for path, row in report.items():
        if len(path)==3:
            label = gender(path[index]) if index==1 else path[index]
            rows[label].append(row)
    result = {label:{m:confirmed_sum(r.get(m) for r in leaves) for m in (*METRICS,*STOCK,"stock_total","stock_value","sku_gt10")}
              for label,leaves in rows.items()}
    if () in report:
        result["ИТОГО"] = report[()]
    return result


def numeric(records):
    return pd.DataFrame(records).map(lambda v: float(v) if isinstance(v,D) else v)


def movement(frame, first, metric_for, enabled):
    columns = list(frame)
    def shades(row):
        metric = metric_for(row)
        cells = [""] * len(columns)
        if enabled:
            previous = None
            for i, column in enumerate(columns[1:], 1):
                value = row[column]
                if column.startswith("Δ"):
                    cells[i] = delta_semantic_style(metric, value) if pd.notna(value) and value else ""
                elif column[:3] in ("Пн ","Вт ","Ср ","Чт ","Пт ","Сб ","Вс "):
                    if pd.notna(value) and previous is not None and value != previous:
                        cells[i] = delta_semantic_style(metric,value-previous)
                    previous = value if pd.notna(value) else None
        return cells
    styler = controls._apply_week_contrast(frame.style.format(detail.integer,na_rep="—"),first).apply(shades,axis=1)
    for i, (_, row) in enumerate(frame.iterrows()):
        metric = metric_for(row)
        for j, col in enumerate(columns[1:],1):
            if col.endswith(", %"):
                styler._display_funcs[i,j] = format_percent
            elif metric in WB_PERCENT:
                styler._display_funcs[i,j] = (lambda v:"—" if pd.isna(v) else f"{v*100:+.2f} п.п.") if col.startswith("Δ") else format_percent
    return styler

def render_week(model, adapted):
    result, scope, now, old, daily = adapted
    a,b,current,previous,_,_,_ = scope
    status = "WEEKLY принят" if model.accepted(a,b) else "OPEN · дневной слой"
    st.markdown(f'<div class="week-status status-{"closed" if model.accepted(a,b) else "open"}">{status}</div>',
                unsafe_allow_html=True)
    download_slot = st.empty()
    cards = [(detail.ORDERS_RUB,FUNNEL[0],"orders"),(detail.ORDERS_QTY,FUNNEL[1],"orders"),
             ("Доступно к продаже, шт","fbw_stock","stock"),(detail.REVENUE_RUB,"revenue_rub","revenue"),
             (detail.REVENUE_QTY,"revenue_qty","revenue"),("События","events","events")]
    st.markdown('<div class="kpi-grid">'+"".join(controls._kpi_card(title,now[()].get(key),cls)
                                                   for title,key,cls in cards)+'</div>',unsafe_allow_html=True)
    top = now[()]
    actual = confirmed_sum(top[k] for k in ("wb_spend","media_spend"))
    ad_cards = [("Продвижение WB, ₽",top["wb_spend"]),("Медиа, ₽",top["media_spend"]),
                ("Общий рекламный расход, ₽",actual),
                ("ДРР общий от заказов, %",share(actual,top[FUNNEL[0]])),
                ("ДРР общий от выручки, %",share(actual,top["revenue_rub"])),
                ("Контрольный расход WB × XWAY, ₽",None),
                ("Остаток FBS, шт",top["fbs_stock"]),("Остаток FBW РФ + FBS, шт",top["stock_total"])]
    from wb_format import format_percent
    band = [controls._kpi_card(label,value,"events") if not label.endswith("%") else
            f'<div class="kpi-card events"><div class="kpi-label">{label}</div><div class="kpi-value">{format_percent(value)}</div></div>'
            for label,value in ad_cards]
    st.markdown('<div class="kpi-grid">'+"".join(band)+'</div>',unsafe_allow_html=True)
    highlight = st.toggle("Подсветка динамики", value=True)
    cal = detail._dated(a)
    labels = {**DIMENSION_LABELS, **{k:k for k in FACT_MAP if k not in DIMENSION_LABELS}}
    st.subheader("TABLE 1 — Общие показатели")
    total = metrics(now[()],now[()])
    old_total = metrics(old.get((),{}), old.get((),{}))
    one = []
    table1_labels = dict(WB_TABLE1) | {k:labels[k] for k in FACT_MAP if k not in dict(WB_TABLE1)}
    for m,title in table1_labels.items():
        if m in SHARES:
            continue
        values = {day_label(d):metrics(daily[d][()],daily[d][()]).get(m) if d in current else None for d in cal}
        change = diff(total.get(m),old_total.get(m))
        day_change = diff(values[day_label(current[-1])],values.get(day_label(current[-2]))) if len(current)>1 else None
        one.append({"Показатель":title,**values,"Итого / последний":total.get(m),
                    "Δ к пред. дню, ₽ / шт.":day_change,"Прошлая неделя, ₽ / шт.":old_total.get(m),"Δ к прошлой неделе, ₽ / шт.":change,
                    "Δ к прошлой неделе, %":None if m in WB_PERCENT else share(change,old_total.get(m))})
    first = numeric(one)
    order = st.selectbox("Сортировка",("Как в отчёте","Итог ↓","Итог ↑"),key="week_table1_order")
    if order != "Как в отчёте":
        first = first.sort_values("Итого / последний",ascending=order=="Итог ↑").reset_index(drop=True)
        one = first.to_dict("records")
    inverse = {label:key for key,label in table1_labels.items()}
    style = movement(first,"Показатель", lambda row:inverse[row["Показатель"]],highlight)
    controls._render_html_table(first,"Показатель",styler=style,key="t1",max_height=620)
    sheets = {"TABLE 1":one}
    outside_export = []
    for index,(label,title) in enumerate(zip(detail.DIMENSIONS,("Коллекции","Гендеры","Типы товаров"))):
        number = 2+index*2
        st.subheader(f"TABLE {number} — {title}")
        grouped = group(now,index)
        prior_groups = group(old,index)
        per_day = {d:group(daily[d],index) for d in cal}
        def evidence(key):
            return [g[key] for g in (grouped,prior_groups,*per_day.values()) if key in g]
        unknowns = ("Не определено","Гендер не определён")
        outside_labels = ("Не распределено",UNATTRIBUTED)
        grouped = {k:v for k,v in grouped.items() if k not in (*unknowns,*outside_labels)
                   or has_activity(evidence(k),empty_is_activity=k in unknowns)}
        rows = [{label:key, **{labels[m]:v for m,v in metrics(value,now[()]).items() if m in labels}}
                for key,value in grouped.items()]
        outside = [r for r in rows if r[label] in outside_labels]
        shown = [r for r in rows if r not in outside]
        controls._render_dimension_table(controls._dimension_display_frame(numeric(shown),label),label,key=f"t{number}",cap=650 if index==2 else 420)
        if outside:
            value = outside[0].get(DIMENSION_LABELS["ad_spend"])
            st.caption(f"{UNATTRIBUTED} · {detail.integer(value)} ₽. Расход входит в итог.")
        outside_export.extend({"Таблица":f"TABLE {number}","Распределение":UNATTRIBUTED,**{k:v for k,v in r.items() if k!=label}} for r in outside)
        sheets[f"TABLE {number}"] = shown
        st.subheader(f"TABLE {number+1} — {title}: динамика по дням")
        c1,c2 = st.columns(2)
        metric = c1.selectbox("Показатель для динамики",list(labels),format_func=labels.get,key=f"metric_{number}")
        sort = c2.selectbox("Сортировка",["Как в отчёте","Итог ↓","Итог ↑"],key=f"sort_{number}")
        rows = []
        for k, value in grouped.items():
            if k in (*unknowns,*outside_labels):
                relevant = [{metric:metrics(g[k],g["ИТОГО"]).get(metric)}
                            for g in (grouped,prior_groups,*per_day.values()) if k in g]
                if not has_activity(relevant,empty_is_activity=k in unknowns):
                    continue
            current_value = metrics(value,now[()]).get(metric)
            baseline = metrics(prior_groups.get(k,{}), old.get((),{})).get(metric)
            change = diff(current_value,baseline)
            rows.append({label:k,**{day_label(d):metrics(per_day[d].get(k,{}),daily[d][()]).get(metric)
                                            if d in current else None for d in cal},
                         "Δ к пред. дню, ₽ / шт.":diff(metrics(per_day[current[-1]].get(k,{}),daily[current[-1]][()]).get(metric),metrics(per_day[current[-2]].get(k,{}),daily[current[-2]][()]).get(metric)) if len(current)>1 else None,
                         "Итого / последний":current_value,"Прошлая неделя, ₽ / шт.":baseline,
                         "Δ к прошлой неделе, ₽ / шт.":change,"Δ к прошлой неделе, %":None if metric in WB_PERCENT else share(change,baseline)})
        if sort != "Как в отчёте":
            rows[:-1] = sorted(rows[:-1],key=lambda r:r["Итого / последний"] or 0,reverse=sort=="Итог ↓")
        outside = [r for r in rows if r[label] in outside_labels]
        frame = numeric([r for r in rows if r not in outside])
        styler = movement(frame,label,lambda row:metric,highlight)
        controls._render_html_table(frame,label,styler=styler,key=f"t{number+1}",max_height=540)
        if outside and metric == "ad_spend":
            extra = numeric([{("Распределение" if k==label else k):v for k,v in r.items()} for r in outside])
            controls._render_html_table(extra,"Распределение",styler=movement(extra,"Распределение",lambda row:metric,highlight),key="ads_by_gender")
        if metric == "ad_spend":
            outside_export.extend({"Таблица":f"TABLE {number+1}","Распределение":UNATTRIBUTED,**{k:v for k,v in r.items() if k!=label}} for r in outside)
        sheets[f"TABLE {number+1}"] = [r for r in rows if r not in outside]
    if outside_export:
        sheets["Реклама вне разрезов"] = outside_export
    workbook = detail._excel(list(sheets.items()),f"FACE CODE · {a} — {b}",status)
    download_slot.download_button("⬇ Скачать Excel принятой недели",workbook,f"FACE_CODE_WEEK_{a}_{b}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",key="wb_week_export")









