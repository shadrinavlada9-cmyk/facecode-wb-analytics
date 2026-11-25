from collections import defaultdict
from decimal import Decimal as D

from analytics_calendar import AD_START, STOCK_START, UNKNOWN, dates

ZERO = D(0)
FUNNEL = ("funnel_orders_rub", "funnel_orders_qty", "shows", "visits", "carts",
          "wishlist", "funnel_buyout_qty", "funnel_buyout_rub", "funnel_cancel_qty", "funnel_cancel_rub")
FINANCE = ("revenue_rub", "revenue_qty")
ADS = ("wb_spend", "media_spend", "xway_spend", "ad_orders_rub", "ad_orders_qty",
       "ad_shows", "ad_clicks", "ad_carts")
STOCK = ("fbw_stock", "fbs_stock")
MEDIA_SOURCES = {"media_shows": "views", "media_clicks": "clicks",
                 "media_orders_rub": "orders_sum_pc", "media_orders_qty": "orders_qty_pc"}
MEDIA = tuple(MEDIA_SOURCES)


def number(value):
    return D(str(value)) if value is not None else None


def ratio(value, base):
    return value / base * 100 if value is not None and base is not None and base > 0 else None


def confirmed_sum(values):
    values = list(values)
    return sum(values, ZERO) if values and all(v is not None for v in values) else None


class Analytics:



    def get(self, a, b, metric, stock_through=None):
        scope = (a,b)
        daily = dates(a,b)
        if metric in STOCK:
            if metric == "fbs_stock":
                return None  # Numeric coverage is not an FBS confirmation.
            b = stock_through or b
            eligible = [s for s in self.cover if s[0] == s[1] and s[0] == b and metric in self.cover[s]]
            if not eligible or b < STOCK_START:
                return None
            return dict(self.values[max(eligible), metric])
        if metric in FUNNEL + FINANCE and self.accepted(a,b):
            return dict(self.values[scope, metric])
        if metric in ("media_spend", *MEDIA) and a >= AD_START and metric in self.cover[scope]:
            return dict(self.values[scope, metric])
        if b < AD_START and metric in ADS[3:] + MEDIA:
            return None
        out = defaultdict(lambda: ZERO)
        for day in daily:
            if day < AD_START and metric in ADS + MEDIA:
                continue
            if metric not in self.cover[day,day]:
                return None
            for art, value in self.values[(day,day), metric].items():
                out[art] += value
        return dict(out)

    def attributes(self, article, metric=None):
        if not article and metric in ADS + MEDIA:
            return ("Не распределено",)*3
        return tuple(self.mapping.get(article, (UNKNOWN,)*3))

    def path_values(self, data, metric, paths, matches):
        if data is None:
            return dict.fromkeys(paths)
        grouped = defaultdict(lambda: ZERO)
        for article, value in data.items():
            path = self.attributes(article, metric)
            if matches(path):
                for level in range(4):
                    grouped[path[:level]] += value
        return {path: grouped[path] for path in paths}

    def report(self, a, b, metrics, matches=lambda path: True, stock_through=None):
        inputs = {m: self.get(a,b,m,stock_through) for m in metrics}
        leaves = {self.attributes(art, m) for m, rows in inputs.items() for art in (rows or {})}
        leaves = {p for p in leaves if matches(p)}
        paths = [()] + sorted({p[:n] for p in leaves for n in range(1,4)})
        grouped = {m: self.path_values(rows, m, paths, matches) for m,rows in inputs.items()}
        result = {p: {m: values[p] for m,values in grouped.items()} for p in paths}
        for path, row in result.items():
            if set(STOCK) <= row.keys():
                row["stock_total"] = confirmed_sum(row[k] for k in STOCK)
            for m, label in (("funnel_orders_rub","order_share"), ("wb_spend","ad_share")):
                if m in row:
                    row[label] = ratio(row[m], result[()][m])
        if set(STOCK + FUNNEL[:2]) <= grouped.keys():
            self.value_stock(result, leaves, stock_through or b, matches)
        return result

    def value_stock(self, result, leaves, through, matches):
        values = defaultdict(list)
        known = defaultdict(lambda: ZERO)
        units = defaultdict(lambda: ZERO)
        sku = defaultdict(int)
        base = STOCK if result[()]["stock_total"] is not None else ("fbw_stock",)
        snapshots = {scheme: max((d for d,k in self.stock if k == scheme and d == through), default=None)
                     for scheme in STOCK}
        valid = all(snapshots[k] for k in base) and len({snapshots[k] for k in base}) == 1
        if valid:
            for article, count in self.sku_counts[through, base[0]].items():
                path = self.attributes(article)
                if matches(path):
                    for level in range(4):
                        sku[path[:level]] += count
        for p in leaves:
            row = result[p]
            qty = confirmed_sum(row[k] for k in base)
            orders, ordered = row["funnel_orders_rub"], row["funnel_orders_qty"]
            price = orders/ordered if orders is not None and ordered else None
            for n in range(4):
                parent = p[:n]
                if qty is not None:
                    units[parent] += qty
                    if price is not None or qty == 0:
                        known[parent] += qty
                        values[parent].append(qty * (price or ZERO))
        total = sum(values[()], ZERO)
        for path, row in result.items():
            row["stock_value"] = sum(values[path], ZERO) if values[path] else None
            row["stock_value_share"] = ratio(row["stock_value"], total)
            row["stock_price_coverage"] = ratio(known[path], units[path])
            row["sku_gt10"] = (sku[path] if valid and through not in
                               getattr(self, "unverified_fbw_sku_dates", set()) else None)






