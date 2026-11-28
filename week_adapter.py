from session_download import excel_download
"""Bind the selected FACE CODE facts to the accepted WB week renderers."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal as D
from io import BytesIO

import pandas as pd
import streamlit as st

from model import FUNNEL, FINANCE, STOCK, MEDIA, confirmed_sum
from management import UNATTRIBUTED, gender
from analytics_calendar import dates, START
import week_detail as detail
import week_controls as controls
import sku_data
import sku_view
import sku_inline
from wb_format import day_label, DIMENSION_LABELS, WB_PERCENT, WB_TABLE1, delta_semantic_style, daily_direction_style, format_percent

AD = ("wb_spend", "xway_spend", "ad_orders_rub", "ad_shows", "ad_clicks", "media_spend")
TABLE1_EXTRA = (*MEDIA, "ad_orders_qty")
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
    model=model.for_period(a,b) if hasattr(model,"for_period") else model
    current = dates(a,b)
    previous = dates(*prior) if prior[0] >= START else []
    calendar = detail._dated(a)
    now = model.report(a,b,METRICS,matches,stock_through)
    latest_stamp = sku_data.stock_date(model)
    latest_stocks = model.report(latest_stamp,latest_stamp,STOCK,matches) if latest_stamp else {}
    old = model.report(*prior,METRICS,matches) if previous else {}
    daily = {day:model.report(day,day,METRICS,matches) for day in set(current+previous+list(calendar))}
    leading_day = (date.fromisoformat(calendar[0]) - timedelta(days=1)).isoformat()
    if leading_day >= START:
        daily[leading_day] = model.report(leading_day, leading_day, METRICS, matches)
    schemes = {"fbw":"fbw_stock", "fbs":"fbs_stock", "total":"stock_total"}
    stock_days = {k:[d for d in calendar if daily[d][()].get(metric) is not None] for k,metric in schemes.items()}
    stock_days = {key:days for key,days in stock_days.items() if days}

    def item(report, path, metric):
        if path in report:
            return report[path].get(metric)
        return D(0) if report.get((),{}).get(metric) is not None else None

    records = {}
    # Latest-stock-only groups must remain visible on a historical week too.
    # Keep the original period report returned to WEEK unchanged.
    detail_now = dict(now)
    for path in latest_stocks:
        if path not in detail_now:
            detail_now[path] = {metric:D(0) if value is not None else None for metric,value in now[()].items()}
    for path in visible_paths(detail_now,(latest_stocks,old,*daily.values())):
        row = detail_now[path]
        rec = {title: row.get(key) for title,key in ORDER_FIELDS.items()}
        rec.update({detail.REVENUE_RUB:row["revenue_rub"], detail.REVENUE_QTY:row["revenue_qty"],
                    detail.XWAY:row["xway_spend"], detail.SKU_COLUMN:row["sku_gt10"]})
        rec[sku_data.FBW] = latest_stocks.get(path, {}).get("fbw_stock", D(0) if latest_stocks.get((), {}).get("fbw_stock") is not None else None)
        rec[sku_data.FBS] = latest_stocks.get(path, {}).get("fbs_stock", D(0) if latest_stocks.get((), {}).get("fbs_stock") is not None else None)
        rec["Дата остатков FBW/FBS"] = latest_stamp
        rec["Статус FBS"] = "Подтверждён" if latest_stocks.get((), {}).get("fbs_stock") is not None else "FBS не подтверждён"
        dynamic = {}
        for title,key in ORDER_FIELDS.items():
            value, earlier = row[key], item(old,path,key)
            change = diff(value,earlier)
            series = {d:item(daily[d],path,key) if d in current else None for d in calendar}
            series.update({detail.WEEK_NOW:value, detail.WEEK_PREV:earlier, detail.DELTA:change,
                           detail.RELATIVE:share(change,earlier)})
            series.update({detail.WEEK_PRIOR_DAY+d:item(daily[earlier_day],path,key)
                           for d,earlier_day in zip(current,previous)})
            series.update({detail.DAY_PRIOR+d:item(daily[prior_day],path,key) if prior_day in daily else None
                           for d in calendar
                           for prior_day in [(date.fromisoformat(d)-timedelta(days=1)).isoformat()]})
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
                price = share(row[FUNNEL[0]],row[FUNNEL[1]])
                for d in calendar:
                    prior_day = (date.fromisoformat(d)-timedelta(days=1)).isoformat()
                    qty = item(daily[prior_day],path,schemes[scheme]) if prior_day in daily else None
                    stocks[scheme,unit][detail.DAY_PRIOR+d] = qty if unit == "шт." or qty is None or not qty else (qty*price if price is not None else None)
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


def table1_metrics(row, total, media):
    """Restore brand-level media only in TABLE 1; no allocation to products."""
    result = metrics({**row,"ad_orders_qty":media.get("ad_orders_qty")}, total)
    result.update({key:media.get(key) for key in MEDIA})
    result.update(media_ctr=share(result["media_clicks"],result["media_shows"]),
                  media_cr=share(result["media_orders_qty"],result["media_shows"]),
                  media_drr=share(result.get("media_spend"),result["media_orders_rub"]))
    return result


def turnover(model, stock_day, fbw, matches=lambda path: True, daily_cache=None):
    """Use the displayed FBW and seven confirmed days ending before its snapshot.

    Financial units retain the accepted definition: sales less returns, as exposed
    by revenue_qty. Never substitute funnel buyouts, orders, or finance row counts.
    """
    cache = daily_cache if daily_cache is not None else {}
    window = [(date.fromisoformat(stock_day)-timedelta(days=i)).isoformat() for i in range(7,0,-1)]
    for day in window:
        if day not in cache:
            cache[day] = model.report(day,day,(FUNNEL[1],"revenue_qty"),matches)[()]
    result = {"stock_date":stock_day,"window":window,"fbw":fbw}
    for metric, source, noun in (("turn_orders",FUNNEL[1],"заказов"),("turn_sales","revenue_qty","продаж")):
        values = [cache[day].get(source) for day in window]
        covered = sum(value is not None for value in values)
        units = sum(values,D(0)) if covered == 7 else None
        status = ("Нет подтверждённого FBW" if fbw is None else
                  f"Нет полного окна {covered}/7" if covered != 7 else
                  f"Нет положительных {noun} за 7 дней" if units <= 0 else None)
        result[metric] = fbw*7/units if status is None else None
        result[metric+"_status"] = status
        result[metric+"_qty"] = units
        result[metric+"_coverage"] = covered
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


def movement(frame, first, metric_for, enabled, previous_for=None, exact_values=None):
    columns = list(frame)
    def shades(row):
        metric = metric_for(row)
        cells = [""] * len(columns)
        if enabled:
            previous = previous_for(row) if previous_for is not None else None
            for i, column in enumerate(columns[1:], 1):
                value = exact_values[row[first]].get(column) if exact_values is not None else row[column]
                if column.startswith("Δ к пред. дню"):
                    cells[i] = daily_direction_style(value, 0)
                elif column.startswith("Δ"):
                    cells[i] = delta_semantic_style(metric, value) if pd.notna(value) and value else ""
                elif column[:3] in ("Пн ","Вт ","Ср ","Чт ","Пт ","Сб ","Вс "):
                    cells[i] = daily_direction_style(value, previous)
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

def render_week(model, adapted, matches=lambda path: True):
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
    # The first calendar day compares with the preceding day across week boundaries.
    leading_day = (date.fromisoformat(cal[0]) - timedelta(days=1)).isoformat()
    leading_report = model.report(leading_day, leading_day, METRICS, matches) if leading_day >= START else {}
    media_days = {d:model.report(d,d,TABLE1_EXTRA,matches)[()] for d in {*cal,leading_day}}
    leading_total = table1_metrics(leading_report.get((), {}), leading_report.get((), {}), media_days[leading_day])
    last_previous_day = (date.fromisoformat(current[-1]) - timedelta(days=1)).isoformat()
    last_previous_report = daily.get(last_previous_day, leading_report)
    labels = {**DIMENSION_LABELS, **{k:k for k in FACT_MAP if k not in DIMENSION_LABELS}}
    st.subheader("TABLE 1 — Общие показатели")
    total = table1_metrics(now[()],now[()],model.report(a,b,TABLE1_EXTRA,matches)[()])
    prior_period = tuple((date.fromisoformat(day)-timedelta(days=7)).isoformat() for day in (a,b))
    old_total = table1_metrics(old.get((),{}), old.get((),{}),model.report(*prior_period,TABLE1_EXTRA,matches)[()])
    turn_cache = {}
    stock_day = sku_inline.stock_through(model,(a,b))
    turn_days = {d:turnover(model,d,daily[d][()].get("fbw_stock"),matches,turn_cache) for d in cal}
    turn_leading = turnover(model,leading_day,leading_report.get((),{}).get("fbw_stock"),matches,turn_cache)
    turn_total = turnover(model,stock_day,now[()].get("fbw_stock"),matches,turn_cache)
    turn_old = turnover(model,prior_period[1],old.get((),{}).get("fbw_stock"),matches,turn_cache)
    day_metrics = {d:{**table1_metrics(daily[d][()],daily[d][()],media_days[d]),
                      **{k:turn_days[d][k] for k in ("turn_orders","turn_sales")}} for d in cal}
    for key in ("turn_orders","turn_sales"):
        total[key],old_total[key],leading_total[key] = turn_total[key],turn_old[key],turn_leading[key]
    day_previous = day_metrics.get(last_previous_day,leading_total)
    st.caption(f"Оборачиваемость: доступный FBW соответствующей даты / средние за 7 предыдущих календарных дней. "
               f"Итого / последний: FBW на {stock_day}, окно {turn_total['window'][0]} — {turn_total['window'][-1]}. "
               "Продажи — принятые финансовые штуки за вычетом возвратов; неполное окно не рассчитывается.")
    one = []
    table1_labels = dict(WB_TABLE1) | {k:labels[k] for k in FACT_MAP if k not in dict(WB_TABLE1)}
    # TABLE 1 keeps only available FBW and the two turnover metrics. Other
    # inventory data remains available in the accepted store and other tables.
    excluded_stock = {"unavailable","transit","stock_value_proxy","Остаток FBS, шт",
                      "Остаток FBW РФ + FBS, шт",detail.SKU_COLUMN}
    table1_labels = {k:v for k,v in table1_labels.items() if k not in excluded_stock}
    for m,title in table1_labels.items():
        if m in SHARES:
            continue
        values = {day_label(d):day_metrics[d].get(m) if d in current else None for d in cal}
        change = diff(total.get(m),old_total.get(m))
        day_change = diff(values[day_label(current[-1])], day_previous.get(m))
        one.append({"Показатель":title,**values,"Итого / последний":total.get(m),
                    "Δ к пред. дню, ₽ / шт.":day_change,"Прошлая неделя, ₽ / шт.":old_total.get(m),"Δ к прошлой неделе, ₽ / шт.":change,
                    "Δ к прошлой неделе, %":None if m in WB_PERCENT else share(change,old_total.get(m))})
    exact_first = {row["Показатель"]:row for row in one}
    first = numeric(one)
    order = st.selectbox("Сортировка",("Как в отчёте","Итог ↓","Итог ↑"),key="week_table1_order")
    if order != "Как в отчёте":
        first = first.sort_values("Итого / последний",ascending=order=="Итог ↑").reset_index(drop=True)
        one = first.to_dict("records")
    inverse = {label:key for key,label in table1_labels.items()}
    style = movement(first,"Показатель", lambda row:inverse[row["Показатель"]],highlight,
                     previous_for=lambda row:leading_total.get(inverse[row["Показатель"]]),exact_values=exact_first)
    export_status = {}
    for i, row in first.iterrows():
        metric = inverse[row["Показатель"]]
        if metric not in ("turn_orders","turn_sales"):
            continue
        statuses = {day_label(d):turn_days[d][metric+"_status"] for d in current}
        statuses.update({"Итого / последний":turn_total[metric+"_status"],
                         "Прошлая неделя, ₽ / шт.":turn_old[metric+"_status"]})
        export_status[row["Показатель"]] = statuses
        for j, column in enumerate(first.columns[1:],1):
            if column.endswith(", %"):
                continue
            status_text = statuses.get(column)
            style._display_funcs[i,j] = lambda v,s=status_text: (s or "—") if pd.isna(v) else f"{v:.2f}".replace(".",",")
    controls._render_html_table(first,"Показатель",styler=style,key="t1",max_height=620)
    sheets = {"TABLE 1":[{k:(export_status.get(row["Показатель"],{}).get(k) or None) if pd.isna(v) else v
                          for k,v in row.items()} for row in one]}
    outside_export = []
    table6_sort = None
    table6_ascending = False
    for index,(label,title) in enumerate(zip(detail.DIMENSIONS,("Коллекции","Гендеры","Типы товаров"))):
        number = 2+index*2
        st.subheader(f"TABLE {number} — {title}")
        grouped = group(now,index)
        prior_groups = group(old,index)
        leading_groups = group(leading_report,index)
        last_previous_groups = group(last_previous_report,index)
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
        if index==2 and model.wb_detail["catalog"]:
            display=controls._dimension_display_frame(numeric(shown),label)
            sort_column, direction = st.columns([3,1])
            table6_sort = sort_column.selectbox("Сортировка",["Как в отчёте",*display.columns],key="week_table6_sort")
            table6_ascending = direction.checkbox("По возр.",value=False,key="week_table6_asc")
            table6_sort = None if table6_sort == "Как в отчёте" else table6_sort
            shown = sku_inline.sort_rows(shown,table6_sort,table6_ascending)
            sku_inline.week6(model,(a,b),(previous[0],previous[-1]) if previous else (a,b),matches,shown,list(display.columns),table6_sort,table6_ascending)
        else:
            controls._render_dimension_table(controls._dimension_display_frame(numeric(shown),label),label,key=f"t{number}",cap=420)
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
                         "Δ к пред. дню, ₽ / шт.":diff(metrics(per_day[current[-1]].get(k,{}),daily[current[-1]][()]).get(metric),metrics(last_previous_groups.get(k,{}),last_previous_report.get((),{})).get(metric)),
                         "Итого / последний":current_value,"Прошлая неделя, ₽ / шт.":baseline,
                         "Δ к прошлой неделе, ₽ / шт.":change,"Δ к прошлой неделе, %":None if metric in WB_PERCENT else share(change,baseline)})
        if sort != "Как в отчёте":
            rows[:-1] = sorted(rows[:-1],key=lambda r:r["Итого / последний"] or 0,reverse=sort=="Итог ↓")
        outside = [r for r in rows if r[label] in outside_labels]
        frame = numeric([r for r in rows if r not in outside])
        exact_rows = {row[label]:row for row in rows}
        preceding = lambda row:metrics(leading_groups.get(row[label], {}), leading_report.get((), {})).get(metric)
        styler = movement(frame,label,lambda row:metric,highlight,previous_for=preceding,exact_values=exact_rows)
        controls._render_html_table(frame,label,styler=styler,key=f"t{number+1}",max_height=540)
        if outside and metric == "ad_spend":
            extra = numeric([{("Распределение" if k==label else k):v for k,v in r.items()} for r in outside])
            controls._render_html_table(extra,"Распределение",styler=movement(extra,"Распределение",lambda row:metric,highlight,
                previous_for=lambda row:metrics(leading_groups.get(row["Распределение"], {}), leading_report.get((), {})).get(metric),
                exact_values={row["Распределение"]:row for row in extra.to_dict("records")}),key="ads_by_gender")
        if metric == "ad_spend":
            outside_export.extend({"Таблица":f"TABLE {number+1}","Распределение":UNATTRIBUTED,**{k:v for k,v in r.items() if k!=label}} for r in outside)
        sheets[f"TABLE {number+1}"] = [r for r in rows if r not in outside]
        if index == 2:
            sku_view.render(model, (a,b), matches, "week_table7", "week", daily=True, title="Артикулы WB · TABLE 7")
    if outside_export:
        sheets["Реклама вне разрезов"] = outside_export
    from sku_exports import week_export,capture_table7
    export_paths = tuple(sku_data.paths(model,matches))
    table7_sheets = capture_table7(st.session_state.get('_wb_sku_exports',{}).get('week_table7'))
    def workbook():
        return week_export(model,(a,b),(previous[0],previous[-1]) if previous else (a,b),export_paths,
                           list(sheets.items()),f"FACE CODE · {a} — {b}",status,table7_sheets,table6_sort,table6_ascending)
    with download_slot:
        excel_download("⬇ Скачать Excel принятой недели", workbook(), f"FACE_CODE_WEEK_{a}_{b}.xlsx")









