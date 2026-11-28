"""Accepted WB overview metric order projected from the FACE CODE fact layer."""
from datetime import date, timedelta
from decimal import Decimal as D

from management import divide
from model import confirmed_sum
from analytics_calendar import AD_START, START, dates
from wb_format import day_label

BRAND = ("total_spend","wb_spend","media_spend","other_spend","orders_rub","orders_qty",
         "revenue_rub","drr_orders","drr_revenue","ad_share","control")
PRODUCT = ("wb_spend","xway_spend","shows","clicks","ctr","cpc","cpm","carts",
           "cart_conversion","units_per_100_clicks","ad_orders_qty","ad_orders_rub","cpo",
           "ad_drr","orders_rub","orders_qty","model_drr")
GROUPS = {"Все":PRODUCT, "Расходы":PRODUCT[:2], "Воронка":PRODUCT[2:10],
          "Заказы":("ad_orders_qty","ad_orders_rub","orders_rub","orders_qty"),
          "Эффективность":("cpo","ad_drr","roas","model_drr")}
LABELS = dict(zip(BRAND,("Рекламные расходы итого, ₽","Товарное продвижение WB, ₽","Баннерная реклама, ₽",
                        "Другие расходы, ₽","Общие заказы WB, ₽","Общие заказы WB, шт.","Финансовая выручка, ₽",
                        "Общий ДРР к заказам, %","Общий ДРР к финансовой выручке, %",
                        "Атрибутированные заказы / все заказы, %","CONTROL R3.1, ₽ — сверка")))
LABELS.update(dict(zip(PRODUCT[1:14],("Расход XWAY, ₽ — сверка","Показы XWAY","Клики XWAY",
    "CTR XWAY, %","CPC XWAY, ₽","CPM XWAY, ₽","Корзины XWAY","Конверсия XWAY: корзины / клики, %",
    "Заказано шт. / 100 кликов","Рекламные заказы XWAY, шт.","Рекламные заказы XWAY, ₽","CPO XWAY, ₽","ДРР XWAY, %"))))
LABELS.update(model_drr="Общий ДРР: WB / все заказы, %",roas="ROAS XWAY, ×")
FACTS = {"wb_spend":"wb_spend","media_spend":"media_spend","xway_spend":"xway_spend","shows":"ad_shows",
         "clicks":"ad_clicks","carts":"ad_carts","orders_rub":"funnel_orders_rub","orders_qty":"funnel_orders_qty",
         "ad_orders_rub":"ad_orders_rub","ad_orders_qty":"ad_orders_qty","revenue_rub":"revenue_rub"}
RATIOS = {
    "drr_orders":("total_spend","orders_rub",100),"drr_revenue":("total_spend","revenue_rub",100),
    "ad_share":("ad_orders_rub","orders_rub",100),"ctr":("clicks","shows",100),"cpc":("xway_spend","clicks",1),
    "cpm":("xway_spend","shows",1000),"cart_conversion":("carts","clicks",100),
    "units_per_100_clicks":("ad_orders_qty","clicks",100),"cpo":("xway_spend","ad_orders_qty",1),
    "ad_drr":("xway_spend","ad_orders_rub",100),"model_drr":("wb_spend","orders_rub",100),"roas":("ad_orders_rub","xway_spend",1)
}


def values(model,period,matches):
    model=model.for_period(*period) if hasattr(model,"for_period") else model
    a,b=period
    result=dict.fromkeys(BRAND+PRODUCT)
    for key,field in FACTS.items():
        raw=model.get(a,b,field) if a>=START else None
        result[key]=None if raw is None else sum((v for art,v in raw.items() if matches(model.attributes(art,field))),D(0))
    # Additional expenses and CONTROL are unavailable in the accepted FACE CODE layer.
    result["total_spend"]=confirmed_sum(result[k] for k in ("wb_spend","media_spend"))
    result.update({k:divide(result[num],result[den],factor) for k,(num,den,factor) in RATIOS.items()})
    return result


def changes(left,right,keys,comparable):
    for key in keys:
        a,b=left.get(key),right.get(key)
        change=a-b if comparable and a is not None and b is not None else None
        yield key,change,divide(change,b,100)


def overview_tables(model,a,b,matches,product_keys=PRODUCT):
    from functools import lru_cache

    @lru_cache(maxsize=None)
    def view(period,brand=False):
        return values(model,period,(lambda path:True) if brand else matches)

    def comparable(p,q,product=False):
        if p[0]<START or q[0]<START or len(dates(*p))!=len(dates(*q)):
            return False
        fields=("funnel_orders_rub","wb_spend") + (("xway_spend",) if product else ("media_spend",))
        return all(model.get(*per,m) is not None for per in (p,q) for m in fields) and (
            not product or min(p[0],q[0])>=AD_START)

    daily=dates(*a)
    sa,sb=view(a,True),view(b,True)
    brand=[{"Показатель":LABELS[k],"A":sa[k],"B":sb[k],"Δ":delta,"Δ, %":pct,
            **{day_label(d):view((d,d),True)[k] for d in daily}}
           for k,delta,pct in changes(sa,sb,BRAND,comparable(a,b))]
    def value_row(label,scope):
        return {"Период":label,**{LABELS[k]:scope[k] for k in product_keys}}
    product=[value_row("ИТОГО A",view(a)),value_row("ИТОГО B",view(b))]
    product.extend(value_row(day_label(d),view((d,d))) for d in daily)

    def delta_row(label,p,q):
        row={"Период":label,"База сравнения":" — ".join(q)}
        for k,delta,pct in changes(view(p),view(q),product_keys,comparable(p,q,True)):
            row[LABELS[k]+" · Δ"+(", п.п." if "%" in LABELS[k] else "")]=delta
            row[LABELS[k]+" · Δ, %"]=pct
        return row
    wow=[delta_row("ИТОГО A",a,b)]
    dod=[]
    for d in daily:
        lag1,lag7=((date.fromisoformat(d)-timedelta(days=i)).isoformat() for i in (1,7))
        wow.append(delta_row(day_label(d),(d,d),(lag7,lag7)))
        dod.append(delta_row(day_label(d),(d,d),(lag1,lag1)))
    return brand,product,dod,wow

