"""Load the published analytical facts. Scope selection and UI use the accepted model."""
from collections import defaultdict

from model import Analytics, number


class PublishedAnalytics(Analytics):
    def __init__(self, payload):
        from hashlib import sha256
        import json
        canonical = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf8")
        checksum = lambda value: sha256(value).hexdigest()
        self.wb_detail = {"catalog": {a: {"nm_ids": ids} for a,ids in payload.get("sku_catalog",{}).items()},
                          "variants": [], "source_snapshots": {"generation": checksum(canonical(payload))}}
        self.classification_context = payload.get("_classification_context")
        from period_classification import validate
        validate(self.classification_context)
        self._published_model = True
        self.mapping = payload["products"]
        self.source_qa = {}
        # Old projection counted FBW+FBS before tagging its per-article SKU counts.
        self.unverified_fbw_sku_dates = (
            {a for a,b,metrics in payload["coverage_by_scope"] if "fbs_stock" in metrics}
            | {a for a,b,metric,values in payload["values"] if metric == "fbs_stock"}
            | {day for day,metric,counts in payload["sku_gt10_by_article"] if metric == "fbs_stock"})
        self.accepted_weeks = set(map(tuple, payload["accepted_weeks"]))
        self.cover = defaultdict(set, {(a, b): set(metrics) - {"fbs_stock"} for a, b, metrics in payload["coverage_by_scope"]})
        self.values = defaultdict(dict, {
            ((a, b), metric): {article: number(value) for article, value in values.items()}
            for a, b, metric, values in payload["values"] if metric != "fbs_stock"
        })
        self.stock = {(day, metric) for day, metric, counts in payload["sku_gt10_by_article"] if metric != "fbs_stock"}
        self.sku_counts = {(day, metric): counts for day, metric, counts in payload["sku_gt10_by_article"] if metric != "fbs_stock"}
        self.records = [
            {"kind": "funnel", "period_start": day, "period_end": day, "facts": {"articles": True}}
            for day in payload["funnel_days"]
        ]
        self.records.extend(
            {"kind": "xway", "period_start": day,
             "facts": {"rows": [dict(row, brand_key="FACECODE") for row in rows]}}
            for day, rows in payload["xway_detail"]
        )
        self.ad_rows = [
            {**row, **{key: number(row[key]) for key in row.keys() - {"Дата", "Кампания", "Артикул"}}}
            for row in payload["ad_history"]
        ]

    def accepted(self, a, b):
        return (a, b) in self.accepted_weeks
