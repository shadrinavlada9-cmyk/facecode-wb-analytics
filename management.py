"""Read-only management diagnostics over admitted WB and XWAY facts."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal as D
from statistics import median

from model import FUNNEL, number
from analytics_calendar import AD_START, dates

FIELDS = ("xway_spend","ad_orders_rub","ad_orders_qty","ad_shows","ad_clicks","ad_carts")
GROUPS = ("ДРР и расходы","Оборачиваемость и остатки","Рекламная воронка","Возможности роста")
UNATTRIBUTED = "Реклама без привязки к товарам"


def gender(label):
    return {"Men":"Мужчины","Wmn":"Женщины","Не определено":"Гендер не определён",
            "Не распределено":UNATTRIBUTED}.get(label,label)


def divide(a,b,factor=1):
    return a/b*factor if a is not None and b is not None and b>0 else None


def demand(model):
    end = max((r["period_start"] for r in model.records if r["kind"]=="funnel" and r["facts"]["articles"]),default=None)
    if end is None:
        return None, None, {}
    start = (date.fromisoformat(end)-timedelta(days=6)).isoformat()
    totals = defaultdict(D)
    for day in dates(start,end):
        values = model.get(day,day,FUNNEL[1])
        if values is None:
            return start,end,None
        for article, value in values.items():
            totals[article] += value
    return start,end,dict(totals)


def inventory(model):
    start,end,orders = demand(model)
    stamp = max((day for day,_ in model.stock),default=None)
    fbw = model.get(stamp,stamp,"fbw_stock") if stamp else None
    fbs = model.get(stamp,stamp,"fbs_stock") if stamp else None
    items = {}
    for article in (fbw or {}).keys() | (fbs or {}).keys() | (orders or {}).keys():
        qty = orders.get(article,D(0)) if orders is not None else None
        warehouse = fbw.get(article,D(0)) if fbw is not None else None
        seller = fbs.get(article,D(0)) if fbs is not None else None
        total = warehouse+seller if warehouse is not None and seller is not None else None
        status = ("Нет полного покрытия заказов" if qty is None else "Нет заказов за 7 дней" if qty==0
                  else "Нет подтверждённого остатка" if warehouse is None and seller is None else "Расчёт доступен")
        items[article] = {"Заказы за 7 дней, шт.":qty,"FBW, шт.":warehouse,"FBS, шт.":seller,
                          "H7 по FBW, дней":divide(warehouse,qty,7),"H7 по FBW + FBS, дней":divide(total,qty,7),
                          "Снимок склада":stamp,"Статус H7":status}
    return start,end,stamp,items


def xway(model,period,matches):
    a,b = period
    if b<AD_START:
        return {},None
    expected = set(dates(max(a,AD_START),b))
    by_day = defaultdict(list)
    for rec in model.records:
        if rec["kind"]=="xway" and rec["period_start"] in expected:
            by_day[rec["period_start"]].append(rec)
    if set(by_day)!=expected or any(len(v)!=1 for v in by_day.values()):
        return {}, "Неполное или неоднозначное покрытие XWAY."
    groups = defaultdict(list)
    for day, (rec,) in sorted(by_day.items()):
        seen = set()
        for row in rec["facts"]["rows"]:
            if row["brand_key"]!="FACECODE":
                continue
            key = row["wb_campaign_id"],str(row["nm_id"] or "")
            if not all(key) or key in seen:
                return {}, "Повтор или неполный ключ WB ID × артикул WB в XWAY."
            seen.add(key)
            if row["article"] and matches(model.attributes(row["article"])):
                groups[key].append((day,row))
    out = {}
    for (cid,nm), rows in groups.items():
        _, latest = rows[-1]
        article = latest["article"]
        # Disagreement in the seller key blocks the recommendation for the affected card.
        if any(row["article"]!=article for _,row in rows):
            continue
        attrs = model.attributes(article)
        sums = {}
        for field in FIELDS:
            values = [number(row.get(field)) for _,row in rows]
            # Workbook counters are sparse; preserve lack of any observation.
            if field == "xway_spend":
                values = [v.quantize(D("0.01")) if v is not None else None for v in values]
            sums[field] = sum((v for v in values if v is not None),D(0)) if any(v is not None for v in values) else None
        spend, revenue, qty, shows, clicks, carts = (sums[f] for f in FIELDS)
        item = {"Уровень":"Товар","Кампания":latest.get("campaign_name") or cid,"WB ID кампании":cid,"Артикул WB":nm,"Артикул продавца":article,
                "Коллекция":attrs[0],"Гендер":gender(attrs[1]),"Тип товара":attrs[2],
                "Статус XWAY":latest.get("campaign_status"),"Ставка, ₽":latest.get("bid"),"Бюджет, ₽":latest.get("budget"),
                "Остаток XWAY, шт.":latest.get("xway_stock"),"Дата XWAY":rows[-1][0],
                "Расход XWAY, ₽":spend,"Рекламные заказы XWAY, ₽":revenue,"Рекламные заказы, шт.":qty,
                "Показы":shows,"Клики":clicks,"Корзины":carts,"ДРР XWAY, %":divide(spend,revenue,100),
                "CTR, %":divide(clicks,shows,100),"CPC, ₽":divide(spend,clicks),"CPO, ₽":divide(spend,qty),
                "Клик → заказ, %":divide(qty,clicks,100),
                "Дней с расходом без заказов":sum(number(row.get("xway_spend"))>0 and number(row.get("ad_orders_rub"))==0
                    and not number(row.get("ad_orders_qty")) for _,row in rows if number(row.get("xway_spend")) is not None),
                "Период XWAY":f"{max(a,AD_START)} — {b}"}
        # The cash amount lives only in campaign totals, never on each card.
        out[cid,nm] = item
    return out,None


def signals(model,a,b,matches,settings):
    reports,warning = xway(model,a,matches)
    previous,_ = xway(model,b,matches)
    start,end,stamp,stocks = inventory(model)
    target, minimum, low, high, enough = settings
    groups = {name:[] for name in GROUPS}
    paid = [r for r in reports.values() if (r["Расход XWAY, ₽"] or 0)>0]
    spend_mid = median(r["Расход XWAY, ₽"] for r in paid) if paid else None
    demand_values = [s["Заказы за 7 дней, шт."] for s in stocks.values() if (s["Заказы за 7 дней, шт."] or 0)>0]
    demand_mid = median(demand_values) if demand_values else None
    linked_stocks = [s["FBW, шт."] for article,s in stocks.items() if matches(model.attributes(article)) and s["FBW, шт."] is not None]
    stock_mid = median(linked_stocks) if linked_stocks else None
    comparable = (min(a[0],b[0])>=AD_START and len(dates(*a))==len(dates(*b)) and bool(previous))

    def add(group,row,reason,action,rank,priority="Проверить"):
        groups[GROUPS[group]].append((rank,{"Приоритет":priority,**row,"Причина":reason,"Предлагаемое действие":action}))
    for key,row in reports.items():
        spend, revenue, drr = (row[k] for k in ("Расход XWAY, ₽","Рекламные заказы XWAY, ₽","ДРР XWAY, %"))
        clicks = row["Клики"]
        item = stocks.get(row["Артикул продавца"],{})
        h7 = item.get("H7 по FBW + FBS, дней")
        h7 = item.get("H7 по FBW, дней") if h7 is None else h7
        row = {**row,**item,"Период заказов H7":f"{start} — {end}" if start else None,"Источник":"XWAY · WB Воронка · FBW/FBS"}
        if not spend or spend<=0:
            continue
        if revenue==0 and not row["Рекламные заказы, шт."]:
            add(0,row,"Есть расход XWAY, атрибутированные заказы в ₽ равны нулю.",
                "Проверить поисковые запросы и карточку.",spend,"Высокий")
        if target is not None and minimum is not None and spend>=minimum and drr is not None and drr>target:
            add(0,{**row,"Превышение цели, п.п.":drr-D(str(target))},"ДРР выше цели FACE CODE.",
                "Проверить ставки, размещения и маржу.",spend,"Высокий")
        old = previous.get(key) if comparable else None
        if old and spend_mid is not None and spend>=spend_mid:
            bad = {}
            for metric,direction in (("CPC, ₽",1),("CTR, %",-1),("Клик → заказ, %",-1),("ДРР XWAY, %",1),("Рекламные заказы XWAY, ₽",-1)):
                cur,prev = row[metric],old[metric]
                if cur is not None and prev is not None and (cur-prev)*direction>0:
                    bad["Δ "+metric] = cur-prev
            if bad:
                add(2,{**row,**bad,"Период B":old["Период XWAY"]},"Ухудшение на равном периоде B.",
                    "Сопоставить размещения и этапы рекламной воронки.",spend)
        if clicks and revenue==0 and not row["Рекламные заказы, шт."]:
            add(2,row,"Клики есть, рекламный оборот XWAY равен нулю.",
                "Проверить карточку, цену и переход от клика к заказу.",clicks)
        if low is not None and h7 is not None and h7<D(str(low)):
            add(1,row,"H7 ниже порога FACE CODE при расходе на рекламу.",
                "Проверить поставку, остаток и ограничения рекламы.",spend,"Высокий")
        if target is not None and enough is not None and minimum is not None and spend>=minimum and drr is not None and drr<=target and revenue>0 and h7 is not None and h7>=D(str(enough)):
            add(3,row,"ДРР в пределах цели, подтверждённый запас покрывает заданный H7.",
                "Рассмотреть возможность усиления после проверки маржи и остатков.",revenue)
        elif revenue is not None and revenue>0 and h7 is not None and (row.get("Заказы за 7 дней, шт.") or 0)>=(demand_mid or 1):
            add(3,row,"Заказы за 7 дней не ниже медианы продающихся артикулов. Порог усиления требует настройки.",
                "Проверить цель ДРР, запас и маржу перед решением об усилении.",revenue,"Сравнительная диагностика")
    campaign_groups = defaultdict(list)
    for row in reports.values():
        campaign_groups[row["WB ID кампании"]].append(row)
    cash = defaultdict(D)
    if model.get(*a,"wb_spend") is not None:
        for row in model.ad_rows:
            if a[0]<=row["Дата"]<=a[1] and row.get("wb_spend") is not None:
                cash[str(row["Кампания"])] += row["wb_spend"]
    campaign_days = {day:xway(model,(day,day),matches)[0] for day in dates(max(a[0],AD_START),a[1])}
    for cid, children in campaign_groups.items():
        if len(children) == 1:
            continue
        amounts = [r["Расход XWAY, ₽"] for r in children]
        sales = [r["Рекламные заказы XWAY, ₽"] for r in children]
        if any(v is None for v in amounts+sales):
            continue
        cost, orders = sum(amounts,D(0)),sum(sales,D(0))
        drr = divide(cost,orders,100)
        row = {"Уровень":"Кампания","Кампания":children[0]["Кампания"],"WB ID кампании":cid,
               "Расход XWAY, ₽":cost,"Списания WB кампании, ₽":cash.get(cid),
               "Рекламные заказы XWAY, ₽":orders,"ДРР XWAY, %":drr,
               "Клики":sum((r["Клики"] or 0 for r in children),D(0)),
               "Период XWAY":children[0]["Период XWAY"],"Источник":"XWAY · история затрат WB"}
        if cost>0 and orders==0 and not any(r["Рекламные заказы, шт."] for r in children):
            paid_days = []
            for day,daily in campaign_days.items():
                group = [r for (key,_),r in daily.items() if key==cid]
                if group and any((r["Расход XWAY, ₽"] or 0)>0 for r in group) and all(r["Рекламные заказы XWAY, ₽"]==0 and not r["Рекламные заказы, шт."] for r in group):
                    paid_days.append(day)
            add(0,{**row,"Дней с расходом без заказов":len(paid_days)},"Кампания без рекламных заказов XWAY.",
                "Проверить товарные строки и расходы кампании.",cost,"Высокий")
        elif target is not None and minimum is not None and cost>=minimum and drr is not None and drr>target:
            add(0,{**row,"Превышение цели, п.п.":drr-D(str(target))},"ДРР кампании выше цели FACE CODE.",
                "Проверить вклад товаров, ставки и маржу.",cost,"Высокий")
    for article,item in stocks.items():
        qty,stock = item["Заказы за 7 дней, шт."],item["FBW, шт."]
        if qty is None or not stock or not matches(model.attributes(article)):
            continue
        if (qty==0 and stock_mid is not None and stock>=stock_mid) or (high is not None and item["H7 по FBW, дней"] is not None and item["H7 по FBW, дней"]>=D(str(high))):
            attrs = model.attributes(article)
            row = {"Артикул продавца":article,"Коллекция":attrs[0],"Гендер":gender(attrs[1]),"Тип товара":attrs[2],
                   **item,"Период заказов H7":f"{start} — {end}","Источник":"WB Воронка · FBW"}
            reason = "Ноль заказов за 7 дней, FBW не ниже медианы." if qty==0 else "H7 по FBW выше заданного порога."
            add(1,row,reason,"Проверить карточку, цену и возможность продвижения.",stock)
    return {k:[row for _,row in sorted(v,key=lambda pair:-pair[0])] for k,v in groups.items()},warning



