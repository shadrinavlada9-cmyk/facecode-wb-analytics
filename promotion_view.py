"""FACE CODE facts for the four accepted promotion sections."""
from collections import defaultdict
from decimal import Decimal
from math import factorial, prod
from fractions import Fraction
from datetime import date
from analytics_calendar import START, AD_START, dates
from wb_format import semantic_direction
from week_detail import integer
from fc_format import format_value
import management as M
from promotion_overview import GROUPS, LABELS as WB_LABELS, overview_tables
from itertools import combinations

import pandas as pd
import streamlit as st
from session_download import excel_download
import promotion_table as H
from promotion_excel import excel
from model import ADS, FUNNEL, FINANCE, confirmed_sum, ratio

NAMES = {
    "wb_spend":"Товарные списания WB, ₽","media_spend":"Медиа, ₽","xway_spend":"Расход XWAY, ₽",
    "ad_orders_rub":"Рекламные заказы XWAY, ₽","ad_orders_qty":"Рекламные заказы XWAY, шт.",
    "ad_shows":"Показы XWAY","ad_clicks":"Клики XWAY","ad_carts":"Корзины XWAY",
    "actual":"Рекламные расходы итого, ₽","ctr":"CTR XWAY, %","cr":"Клик → корзина, %",
    "drr":"Общий ДРР к заказам, %","ad_drr":"ДРР XWAY, %","roas":"ROAS XWAY, ×",
    "cpc":"CPC, ₽","cpo":"CPO, ₽","funnel_orders_rub":"Все заказы WB, ₽","funnel_orders_qty":"Все заказы WB, шт.",
    "revenue_rub":"Финансовая выручка, ₽","revenue_qty":"Финансовая выручка, шт.",
}
SECTIONS = ("Обзор","Решения и ЦУ")


def metrics(row):
    data = dict(row)
    data["actual"] = confirmed_sum(row.get(k) for k in ADS[:2])
    data["drr"] = ratio(data["actual"],row.get(FUNNEL[0]))
    data["ad_drr"] = ratio(row.get("xway_spend"),row.get("ad_orders_rub"))
    data["ctr"] = ratio(row.get("ad_clicks"),row.get("ad_shows"))
    data["cr"] = ratio(row.get("ad_carts"),row.get("ad_clicks"))
    roas = ratio(row.get("ad_orders_rub"),row.get("xway_spend"))
    data["cpc"] = M.divide(row.get("xway_spend"),row.get("ad_clicks"))
    data["cpo"] = M.divide(row.get("xway_spend"),row.get("ad_orders_qty"))
    data["roas"] = roas/100 if roas is not None else None
    return data


def frame(rows):
    return pd.DataFrame(rows).rename(columns=NAMES).map(lambda x:float(x) if isinstance(x,Decimal) else x)


def display(rows, key, sortable=True):
    table = frame(rows)
    if sortable and not table.empty:
        cols = st.columns([3,2,1])
        search = cols[0].text_input("Поиск",key=key+"search")
        order = cols[1].selectbox("Сортировка",list(table.columns),key=key+"sort")
        asc = cols[2].checkbox("По возр.",key=key+"asc")
        if search:
            table = table[table.astype(str).apply(lambda col:col.str.contains(search,case=False,regex=False)).any(axis=1)]
        table = table.sort_values(order,ascending=asc,na_position="last")
    page = st.number_input("Страница",1,(len(table)+49)//50,1,key=key+"page") if len(table)>50 else 1
    s = {"id":key,"columns":[{"key":k,"title":k,"group":""} for k in table], "rows":[]}
    for n,r in enumerate(table.iloc[(page-1)*50:page*50].to_dict("records")):
        cells = {}
        for k,v in r.items():
            missing = pd.isna(v)
            number = isinstance(v,(float,int)) and not missing
            places = 2 if "%" in k or "ДРР" in k or "п.п." in k or "%" in str(r.get("Показатель","")) else 0
            text = format_value(v,k if places==0 else k+" %")
            tone = None
            if number and v and (k in ("Изменение","Δ","Δ, %","Δ, п.п.") or " · Δ" in k):
                title = r.get("Показатель",k.split(" · Δ")[0])
                metric = next((key for key,label in {**NAMES,**WB_LABELS}.items() if label==title),None)
                direction = semantic_direction({"drr":"total_drr","cr":"ad_cr"}.get(metric,metric))
                if direction != "neutral":
                    tone = "pos" if (v>0)==(direction=="higher") else "neg"
            cells[k] = {"value":None if missing else v, "text":text, "tone":tone, "kind":"money2" if number or missing else "text"}
        s["rows"].append({"key":str(n),"cells":cells})
    st.html(H.table_html(s,max_height=410))
    return table


def download(name,tables):
    excel_download("Скачать Excel · "+name, excel(tables), "FACE_CODE_"+name+".xlsx")


def campaigns(model, period, matches, by_article=False):
    grouped = defaultdict(lambda: defaultdict(lambda:Decimal(0)))
    for r in model.ad_rows:
        if not period[0]<=r["Дата"]<=period[1] or not matches(model.attributes(r["Артикул"],"wb_spend")):
            continue
        key=(r["Кампания"],r["Артикул"]) if by_article else r["Кампания"]
        for field in ADS:
            if r.get(field) is not None:
                grouped[key][field] += r[field]
    rows=[]
    for key,row in sorted(grouped.items()):
        labels = {"Кампания":key[0],"Артикул":key[1]} if by_article else {"Кампания":key}
        values = metrics(row)
        rows.append({**labels,**{k:values.get(k) for k in (*ADS,"ad_drr","ctr","cr")}})
    return rows


def selection_values(model, period, matches):
    result = model.report(*period,ADS+FUNNEL[:2]+FINANCE,matches)
    return result, metrics(result[()])


def compare_rows(current, baseline, keys):
    output=[]
    for key in keys:
        a,b=current.get(key),baseline.get(key)
        output.append({"Показатель":NAMES.get(key,key),"Текущий A":a,"Сравнение B":b,
                       "Δ, п.п." if "%" in NAMES.get(key,"") else "Изменение":a-b if a is not None and b is not None else None})
    return output


def factors(model, a, b, matches):
    if (min(a[0],b[0]) < AD_START or len(dates(*a)) != len(dates(*b))
            or any(model.get(*period,"ad_orders_rub") is None for period in (a,b))):
        return [{"Фактор":"Недостаточно сопоставимых подтверждённых данных","Вклад, ₽":None}]
    fields = ("ad_shows","ad_clicks","ad_orders_qty","ad_orders_rub")
    def records(period):
        return {(row["Кампания"],row["Артикул"]):row for row in campaigns(model,period,matches,True)}
    def inputs(row):
        if not row or any(row.get(key) is None or row[key]<=0 for key in fields):
            return None
        s,c,q,v = (Fraction(row[key]) for key in fields)
        return s,c/s,q/c,v/q
    first,second = records(a),records(b)
    parts = [Fraction(0)]*4
    residual = dict.fromkeys(("Новая активность","Исчезнувшая активность","Недостаточно данных факторов"),Fraction(0))
    for key in first.keys()|second.keys():
        left,right = first.get(key),second.get(key)
        x,y = inputs(left),inputs(right)
        if x and y:
            for i in range(4):
                others = [j for j in range(4) if j!=i]
                for n in range(4):
                    weight = Fraction(factorial(n)*factorial(3-n),factorial(4))
                    for chosen in combinations(others,n):
                        parts[i] += weight*(x[i]-y[i])*prod(x[j] if j in chosen else y[j] for j in others)
        else:
            category = "Новая активность" if right is None else "Исчезнувшая активность" if left is None else "Недостаточно данных факторов"
            residual[category] += Fraction((left or {}).get("ad_orders_rub") or 0)-Fraction((right or {}).get("ad_orders_rub") or 0)
    labels = ("Показы","CTR","Заказов на клик","Средняя сумма заказа")
    return [{"Фактор":key,"Вклад, ₽":float(value)} for key,value in [*zip(labels,parts),*residual.items()]]


def period_controls(model, a, b):
    start = date.fromisoformat(START)
    latest = max((date.fromisoformat(r["period_end"]) for r in model.records if r["kind"]=="funnel"),default=start)
    left,right = st.columns(2)
    values = []
    for label, column, initial in (("Период A",left,a),("Период B",right,b)):
        default = tuple(min(latest,max(start,date.fromisoformat(d))) for d in initial)
        picked = column.date_input(label,default,min_value=start,max_value=latest,key="promo_"+label)
        if len(picked)!=2:
            st.info("Выберите начало и конец периода.")
            return None
        values.append(tuple(d.isoformat() for d in picked))
    return tuple(values)


def kpis(current, baseline):
    cards = []
    for field in ("wb_spend","media_spend","drr","ad_orders_rub","ad_drr","xway_spend","ad_shows","ad_clicks","ctr","cpc","cpo","actual"):
        now, old = current.get(field),baseline.get(field)
        delta = now-old if now is not None and old is not None else None
        rate = field in ("drr","ad_drr","ctr")
        fmt = lambda v: ("—" if v is None else f"{v:.2f}%" if rate else integer(v))
        item = dict(cur=now,cur_text=fmt(now),prev_text=fmt(old),delta=delta,delta_text=(
            f"{delta:+.2f} п.п." if rate and delta is not None else integer(delta)),relative=None,
            relative_text="",title=NAMES[field],nature="DERIVED" if rate else "",note="")
        card = H._kpi_cell(item,main=field=="actual")
        direction = "lower" if field in ("drr","ad_drr","cpc","cpo") else "higher" if field in ("ad_orders_rub","ctr") else "neutral"
        if delta and direction == "lower":
            card = card.replace('class="pos"','class="neg"') if delta>0 else card.replace('class="neg"','class="pos"')
        elif direction == "neutral":
            card = card.replace('class="pos"','class=""').replace('class="neg"','class=""')
        cards.append(card)
    st.html('<div class="prm-band">'+"".join(cards)+"</div>")

def attention(model, period, prior, matches):
    with st.expander("Настройки сигналов FACE CODE"):
        st.caption("Без заданных порогов показываются наблюдаемые факты и сравнительная диагностика.")
        columns = st.columns(5)
        settings = tuple(c.number_input(label,min_value=0.0,value=None,placeholder="Не задано",key="fc_signal_"+str(i))
                        for i,(c,label) in enumerate(zip(columns,("Цель ДРР, %","Мин. расход, ₽","Риск H7, дней",
                                                                "Избыток H7, дней","H7 для усиления, дней"))))
    groups,warning = M.signals(model,period,prior,matches,settings)
    st.subheader("Обратите внимание")
    if warning:
        st.warning(warning)
    tables = []
    campaign_ids = set()
    keys = ("Приоритет","Уровень","Кампания","WB ID кампании","Артикул WB","Артикул продавца","Коллекция","Гендер","Тип товара",
            "Расход XWAY, ₽","Рекламные заказы XWAY, ₽","ДРР XWAY, %","Клики","Дней с расходом без заказов","Период XWAY","Период заказов H7","Источник",
            "Заказы за 7 дней, шт.","FBW, шт.","H7 по FBW, дней","Причина","Предлагаемое действие")
    for i,(group,rows) in enumerate(groups.items()):
        st.markdown(f"#### {group}")
        if not rows:
            st.caption("Подтверждённых сигналов для выбранного периода нет.")
        else:
            cols = [key for key in keys if any(row.get(key) is not None for row in rows[:5])]
            display([{k:r.get(k) for k in cols} for r in rows[:5]],f"signals_{i}",False)
            campaign_ids.update(r["WB ID кампании"] for r in rows if r.get("WB ID кампании"))
            with st.expander(f"Все сигналы · {group} ({len(rows)})"):
                display(rows,f"signals_all_{i}")
        tables.append((group,frame(rows)))
    download("Рекомендации",tables)
    return campaign_ids

def render(model,period,prior,matches):
    st.html(H.CSS + "<style>.prm-band{grid-template-columns:repeat(6,minmax(0,1fr));gap:1px} .prm-wrap table{min-width:100%} .prm-table{min-width:100%} .prm-table td{font-size:14px} @media(max-width:1100px){.prm-band{grid-template-columns:repeat(3,minmax(0,1fr))}}</style>")
    picked = period_controls(model,period,prior)
    if picked is None:
        return
    period,prior = picked
    tabs=st.tabs(SECTIONS)
    _,current=selection_values(model,period,matches)
    _,baseline=selection_values(model,prior,matches) if prior[0]>=model_start() else ({},{})
    ids=campaigns(model,period,matches)
    with tabs[0]:
        st.html(H.h2("Обзор продвижения"))
        kpis(current,baseline)
        st.subheader("Расходы и общие показатели продвижения")
        st.caption("Бренд целиком. XWAY учитывается отдельно. Другие расходы и CONTROL не подтверждены.")
        brand, product, dod, wow = overview_tables(model,period,prior,matches)
        display(brand,"brand_overview",False)

        st.subheader("Рекламная воронка")
        choice = st.segmented_control("Группа показателей",tuple(GROUPS),default="Все",required=True,key="funnel_metrics")
        if choice != "Все":
            keep = {WB_LABELS[k] for k in GROUPS[choice]}
            def selected(rows):
                return [{k:v for k,v in r.items() if k in {"Период","База сравнения"} or k.split(" · Δ")[0] in keep} for r in rows]
            if choice=="Эффективность":
                _, shown, shown_dod, shown_wow = overview_tables(model,period,prior,matches,GROUPS[choice])
            else:
                shown, shown_dod, shown_wow = map(selected,(product,dod,wow))
        else:
            shown, shown_dod, shown_wow = product,dod,wow
        mode = st.segmented_control("Представление воронки",("Значения A/B и по дням","К предыдущему дню","К сопоставимой базе"),
                                    default="Значения A/B и по дням",required=True)
        display(dict(zip(("Значения A/B и по дням","К предыдущему дню","К сопоставимой базе"),
                         (shown,shown_dod,shown_wow)))[mode],"funnel_overview",False)
        st.caption("Дельты воронки требуют равных периодов и подтверждённого XWAY с обеих сторон. Итог WEEKLY берётся целиком, без распределения поправки по дням.")

        daily_rows = [{"Дата":d,**selection_values(model,(d,d),matches)[1]} for d in dates(*period)]
        st.html(H.sub("Динамика по дням"))
        daily = frame(daily_rows)
        k = st.selectbox("Показатель графика",["wb_spend","ad_orders_rub","ad_drr","ad_shows","ad_clicks","ctr","cpc","cpo"],format_func=NAMES.get)
        timeline = frame([{"Дата":d,k:selection_values(model,(d,d),matches)[1].get(k)} for d in dates(*period)])
        if timeline[NAMES[k]].notna().any():
            st.line_chart(timeline,x="Дата",y=NAMES[k],height=240)
        else:
            st.caption("Нет подтверждённых значений для выбранного показателя.")
        signal_ids = attention(model,period,prior,matches)
        st.subheader("Подробные данные WB и XWAY")
        xway_rows, _ = M.xway(model,period,matches)
        all_ids = sorted({*signal_ids,*(str(r["Кампания"]) for r in ids)})
        chosen = st.selectbox("WB ID кампании из сигнала или таблицы",["Все кампании",*all_ids])
        st.caption("История затрат WB. Списания показаны один раз на строку принятого расчёта.")
        wb_details = display([{"Дата":r["Дата"],"WB ID кампании":r["Кампания"],"Артикул продавца":r["Артикул"],"wb_spend":r["wb_spend"]}
                              for r in model.ad_rows if r.get("wb_spend") is not None and period[0]<=r["Дата"]<=period[1]
                              and matches(model.attributes(r["Артикул"],"wb_spend"))
                              and (chosen=="Все кампании" or r["Кампания"]==chosen)],"overview_campaigns")
        st.caption("XWAY. Аналитические данные по кампании и карточке, отдельно от списаний WB.")
        xway_details = display([r for r in xway_rows.values() if chosen=="Все кампании" or r["WB ID кампании"]==chosen],"overview_xway")
        download("Обзор",[("Общие расходы",frame(brand)),("Рекламная воронка",frame(product)),("К предыдущему дню",frame(dod)),("К сопоставимой базе",frame(wow)),("Динамика",daily),("Кампании WB и XWAY",wb_details),("Товары XWAY",xway_details)])
    with tabs[1]:
        st.html(H.h2("Решения и ЦУ"))
        with st.expander("Управленческие сигналы XWAY"):
            preview, _ = M.signals(model,period,prior,matches,(None,)*5)
            for i,(name,rows) in enumerate(preview.items()):
                st.markdown("**"+name+"**")
                if rows:
                    display(rows[:5],f"decisions_signals_{i}",False)
                else:
                    st.caption("Нет подтверждённых сигналов.")
        sections=st.tabs(("Рекламные кампании","Кандидаты на запуск","Возобновление / проверка расписания",
                          "Без продаж — ручная оценка","Правила и данные"))
        with sections[0]:
            content=display(ids,"promo_campaigns")
            detail=display(campaigns(model,period,matches,True),"promo_products")
            download("Кампании",[("Кампании",content),("Товары",detail)])
        for section, caption in zip(sections[1:4],(
            "Подбор кандидатов требует подтверждённой связи модели и статусов кампаний FACE CODE.",
            "Для оценки возобновления необходимы актуальные статусы и расписание FACE CODE.",
            "Для оценки товаров без продаж необходимы рейтинг, отзывы и отдельный журнал FACE CODE.")):
            with section:
                st.info(caption)
        with sections[4]:
            st.caption("Товарные расходы WB и баннеры — фактические списания. XWAY учитывается отдельно.")
def model_start():
    from analytics_calendar import START
    return START







