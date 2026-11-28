"""Read-side card and variant detail over the accepted analytical model."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from model import ADS, FINANCE, FUNNEL, STOCK, AD_START

CARD_METRICS = FUNNEL + FINANCE + ADS
LABELS = {
    "funnel_orders_rub": "Заказы, ₽", "funnel_orders_qty": "Заказы, шт.",
    "revenue_rub": "Выручка, ₽", "revenue_qty": "Выручка, шт.",
    "wb_spend": "Продвижение WB, ₽", "media_spend": "Баннеры, ₽",
    "xway_spend": "Расход XWAY, ₽", "ad_orders_rub": "Рекламные заказы XWAY, ₽",
    "ad_orders_qty": "Рекламные заказы XWAY, шт.", "ad_shows": "Показы XWAY",
    "ad_clicks": "Клики XWAY", "ad_carts": "Корзины XWAY", "shows": "Показы WB",
    "visits": "Переходы WB", "carts": "Корзины WB", "wishlist": "Отложено",
    "funnel_buyout_qty": "Выкупы, шт.", "funnel_buyout_rub": "Выкупы, ₽",
    "funnel_cancel_qty": "Отмены, шт.", "funnel_cancel_rub": "Отмены, ₽",
}
FBW = "Остаток FBW, шт."
FBS = "Остаток FBS, шт."
NM = "Артикул WB"
SELLER = "Артикул продавца"
UNMATCHED = "Артикул WB не сопоставлен"


def divide(value, base, scale=1):
    return value / base * scale if value is not None and base is not None and base > 0 else None


def stock_date(model):
    return max((day for day, _ in model.stock), default=None)


def horizon(model):
    last = max((r["period_end"] for r in model.records if r["kind"] == "funnel"), default=None)
    return ((date.fromisoformat(last) - timedelta(days=6)).isoformat(), last) if last else (None, None)


def paths(model, matches):
    return sorted({tuple(path) for path in model.mapping.values() if matches(path)})


def latest_stock(model):
    stamp = stock_date(model)
    if stamp is None:
        return None, {}
    return stamp, model.report(stamp, stamp, STOCK)


def cards(model, period, path, matches, campaign=None, allowed_articles=None):
    """One seller/card relation per row. Ambiguity is retained as unmatched."""
    model=model.for_period(*period) if hasattr(model,"for_period") else model
    catalog = model.wb_detail["catalog"]
    metrics = {metric: model.get(*period, metric) for metric in CARD_METRICS}
    stamp = stock_date(model)
    stocks = {metric: model.get(stamp, stamp, metric) if stamp else None for metric in STOCK}
    start7, end7 = horizon(model)
    orders7 = model.get(start7, end7, "funnel_orders_qty") if start7 else None
    articles = {art for values in (*metrics.values(), *stocks.values()) for art in (values or {})}
    if allowed_articles is not None:
        articles &= set(allowed_articles)
    if campaign:
        linked = {r["Артикул"] for r in model.ad_rows if str(r["Кампания"]) == str(campaign)
                  and period[0] <= r["Дата"] <= period[1]}
        linked_ids = {nm for article in linked for nm in catalog.get(article, {}).get("nm_ids", [])}
        articles &= linked | {article for article, item in catalog.items()
                              if any(nm in linked_ids for nm in item["nm_ids"])}
    xway = defaultdict(list)
    for record in model.records:
        if record["kind"] != "xway" or not max(period[0], AD_START) <= record["period_start"] <= period[1]:
            continue
        for item in record["facts"]["rows"]:
            if item["brand_key"] == "FACECODE" and item.get("nm_id") and (
                campaign is None or str(item["wb_campaign_id"]) == str(campaign)
            ):
                xway[str(item["nm_id"])].append(item)
    selected = [art for art in sorted(articles) if tuple(model.attributes(art)) == tuple(path) and matches(model.attributes(art))]
    result = []
    for article in selected:
        mapping = catalog.get(article, {})
        ids = mapping.get("nm_ids", [])
        nm = ids[0] if len(ids) == 1 else None
        row = {
            NM: nm, SELLER: article, "ЦМ": ", ".join(mapping.get("cm", [])) or None,
            "Сопоставление": "Подтверждено" if nm else UNMATCHED,
            "Коллекция": path[0], "Гендер": path[1], "Тип товара": path[2],
        }
        for metric, values in metrics.items():
            row[LABELS[metric]] = values.get(article, Decimal(0)) if values is not None else None
        for metric, label in zip(STOCK, (FBW, FBS)):
            values = stocks[metric]
            row[label] = values.get(article, Decimal(0)) if values is not None else None
        if campaign:
            for metric in ADS:
                values = [r[metric] for r in model.ad_rows if str(r["Кампания"]) == str(campaign)
                          and r["Артикул"] == article and period[0] <= r["Дата"] <= period[1] and r.get(metric) is not None]
                row[LABELS[metric]] = sum(values, Decimal(0)) if values else Decimal(0) if metrics[metric] is not None else None
        # No proportional allocation across ambiguous cards or barcode variants.
        qty7 = orders7.get(article, Decimal(0)) if orders7 is not None else None
        row.update({
            "ДРР WB, %": divide(row[LABELS["wb_spend"]], row[LABELS["funnel_orders_rub"]], 100) if nm else None,
            "ДРР XWAY, %": divide(row[LABELS["xway_spend"]], row[LABELS["ad_orders_rub"]], 100) if nm else None,
            "CTR XWAY, %": divide(row[LABELS["ad_clicks"]], row[LABELS["ad_shows"]], 100),
            "CPC XWAY, ₽": divide(row[LABELS["xway_spend"]], row[LABELS["ad_clicks"]]),
            "Доля заказов в группе, %": None,
            "Дата снимка": stamp, "Статус FBS": "Подтверждён" if stocks["fbs_stock"] is not None else "FBS не подтверждён",
            "Заказы H7, шт.": qty7, "H7 по FBW, дней": divide(row[FBW], qty7, 7),
            "Окно H7": f"{start7} — {end7}" if start7 else None,
            "Период": " — ".join(period),
        })
        if "gender2" in mapping:
            row["Гендер 2"] = ", ".join(mapping["gender2"]) or None
            row["Коллекция справочника"] = ", ".join(mapping.get("collection_original",[])) or None
        result.append(row)
    grouped = defaultdict(list)
    for row in result:
        grouped[row[NM] or ("unmatched", row[SELLER])].append(row)
    merged = []
    additive = [*LABELS.values(), FBW, FBS, "Заказы H7, шт."]
    for rows in grouped.values():
        row = dict(rows[0])
        row[SELLER] = ", ".join(sorted({item[SELLER] for item in rows}))
        row["ЦМ"] = ", ".join(sorted({value for item in rows for value in
                                     catalog.get(item[SELLER], {}).get("cm", [])})) or None
        for column in additive:
            values = [item[column] for item in rows]
            row[column] = sum(values, Decimal(0)) if all(v is not None for v in values) else None
        for metric in ADS[2:]:
            observed = [Decimal(str(item[metric])) for item in xway.get(row[NM], []) if item.get(metric) is not None]
            if metric == "xway_spend":
                observed = [value.quantize(Decimal("0.01")) for value in observed]
            if row[NM] is not None:
                row[LABELS[metric]] = sum(observed, Decimal(0)) if observed and metrics[metric] is not None else None
        if period[1] < AD_START:
            row[LABELS["xway_spend"]] = Decimal(0)
        if metrics["media_spend"] is None or any(metrics["media_spend"].values()):
            row[LABELS["media_spend"]] = None
        row["ДРР WB, %"] = divide(row[LABELS["wb_spend"]], row[LABELS["funnel_orders_rub"]], 100) if row[NM] else None
        row["ДРР XWAY, %"] = divide(row[LABELS["xway_spend"]], row[LABELS["ad_orders_rub"]], 100) if row[NM] else None
        row["CTR XWAY, %"] = divide(row[LABELS["ad_clicks"]], row[LABELS["ad_shows"]], 100)
        row["CPC XWAY, ₽"] = divide(row[LABELS["xway_spend"]], row[LABELS["ad_clicks"]])
        row["H7 по FBW, дней"] = divide(row[FBW], row["Заказы H7, шт."], 7)
        merged.append(row)
    result = merged
    total = sum((r[LABELS["funnel_orders_rub"]] or Decimal(0) for r in result), Decimal(0))
    for row in result:
        row["Доля заказов в группе, %"] = divide(row[LABELS["funnel_orders_rub"]], total, 100)
    return result


def variants(model, selected):
    stamp = stock_date(model)
    catalog = model.wb_detail["catalog"]
    selected_ids = {r[NM] for r in selected if r[NM]}
    selected_paths = {(r["Коллекция"], r["Гендер"], r["Тип товара"]) for r in selected}
    arts = {article for article, info in catalog.items() if len(info["nm_ids"]) == 1
            and info["nm_ids"][0] in selected_ids and tuple(model.attributes(article)) in selected_paths}
    arts.update(r[SELLER] for r in selected if not r[NM])
    rows = []
    for day, scheme, article, barcode, size, quantity in model.wb_detail["variants"]:
        if day != stamp or article not in arts or scheme != "fbw_stock":
            continue
        ids = catalog.get(article, {}).get("nm_ids", [])
        attrs = model.attributes(article)
        rows.append({
            NM: ids[0] if len(ids) == 1 else None, SELLER: article,
            "Коллекция": attrs[0], "Гендер": attrs[1], "Тип товара": attrs[2],
            "SKU / ШК": barcode, "Размер": size, "Схема": "FBW" if scheme == "fbw_stock" else "FBS",
            "Остаток, шт.": Decimal(str(quantity)), "Дата снимка": day,
        })
    return rows
