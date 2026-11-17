from html import escape
import pandas as pd
import streamlit as st
import week_detail
from wb_format import USER_DASH
DISPLAY_HEADERS = {'Δ к прошлой неделе, ₽ / шт.': 'К прошлой неделе · ₽ / шт.', 'Δ к прошлой неделе, %': 'К прошлой неделе · %'}
from wb_format import VISUAL_COLORS as WB_COLORS, DIMENSION_LABELS
VISUAL_COLORS = {**WB_COLORS, "zebra":"#FAFAFA", "total":"#F0F0F0", "missing":"#FAFAFA"}
DIMENSION_METRICS = {label: key for key,label in DIMENSION_LABELS.items()}

format_metric = week_detail.integer_metric

format_number = week_detail.integer

_DIMENSION_IDENTIFIERS = {"Коллекция", "Гендер", "Тип товара"}

_TURNOVER_VISIBILITY_COLUMNS = (
    "Оборачиваемость в заказах, дней",
    "Оборачиваемость в продажах, дней",
)

_DIMENSION_ORDER_COLUMNS = (
    # Orders
    "Заказы, ₽", "Заказы, шт", "ССТ заказов, ₽",
    # Revenue
    "Выручка, ₽", "Выручка, шт", "ССТ выручки, ₽",
    # Ads / efficiency / funnel
    "Продвижение, ₽", "ДРР продвижения, %", "ДРР заказы, %", "ДРР выручка, %",
    "Показы", "Переходы", "CTR", "Корзина", "CR",
    "РК показы", "РК клики", "CTR РК", "CPC",
    # Shares
    "Доля заказов, шт", "Доля заказов, ₽", "Доля продвижения",
    "Доля остатка, шт", "Остаток по ССТ заказа, ₽", "Доля остатка в ₽ (по ССТ заказа), %",
    # Stock
    "Остаток, шт",
)

_DIMENSION_SHARE_COLUMNS = {
    "Доля заказов, шт", "Доля заказов, ₽", "Доля продвижения",
    "Доля остатка, шт", "Доля остатка в ₽ (по ССТ заказа), %",
}

_DIMENSION_MONEY_COLUMNS = {
    "Заказы, ₽", "Выручка, ₽", "Продвижение, ₽", "Остаток по ССТ заказа, ₽",
}

_DIMENSION_AVERAGE_COLUMNS = {"ССТ заказов, ₽", "ССТ выручки, ₽", "CPC"}

_DIMENSION_RATE_COLUMNS = {"ДРР продвижения, %", "ДРР заказы, %", "ДРР выручка, %", "CTR", "CR", "CTR РК"}

_DIMENSION_COUNT_COLUMNS = {
    "Заказы, шт", "Выручка, шт", "Показы", "Переходы", "Корзина",
    "РК показы", "РК клики",
}

_DIMENSION_IDENTIFIER_WIDTHS = {
    "Коллекция": 165,
    "Гендер": 130,
    "Тип товара": 190,
}

_DIMENSION_WIDTHS = {
    "money": 115,
    "count": 90,
    "rate": 90,
    "share": 90,
    "average": 95,
    "stock": 95,
    "turnover": 110,
    "other_numeric": 90,
}

def _dimension_column_order(frame: pd.DataFrame, first_col: str) -> list[str]:
    """Physical display order for shared WEEK dimension summary tables.

    Unknown future KPI columns stay before turnover. Turnover is always the
    final two columns and never used as a pin/freeze anchor.
    """
    if first_col not in _DIMENSION_IDENTIFIERS:
        return list(frame.columns)

    body = [c for c in _DIMENSION_ORDER_COLUMNS if c in frame.columns]
    reserved = {first_col, *body, *_TURNOVER_VISIBILITY_COLUMNS}
    extras = [c for c in frame.columns if c not in reserved]
    turnover = [c for c in _TURNOVER_VISIBILITY_COLUMNS if c in frame.columns]
    return [first_col, *body, *extras, *turnover]

def _dimension_display_frame(frame: pd.DataFrame, first_col: str) -> pd.DataFrame:
    if first_col not in _DIMENSION_IDENTIFIERS:
        return frame
    return frame.loc[:, _dimension_column_order(frame, first_col)]

_ABSOLUTE_DYNAMICS_PREFIXES = ("Δ к пред. дню, ", "Тренд недели, ", "Δ к прошлой неделе, ")

_DELTA_DAY_HELP = "Последний день с фактом к предыдущему календарному дню"

_WEEK_TREND_HELP = "Последний день с фактом к первому дню недели с фактом (это не сравнение с прошлой неделей)"

_FBS_HELP = {                                       # WB: the stock slots of the Ozon page with WB meaning (wb.ui_stock_presentation)
    "Остаток FBS, шт": "Остаток FBS (отчёт остатков «Свой склад РФ») на дату снимка. «—» — снимка этой даты нет (это не ноль)",
    "Остаток FBW РФ + FBS, шт": "Сумма снимков FBW РФ и FBS одной даты; склады OTHER в отчётах остатков нет и не добавляются",
    "Оборачиваемость в заказах FBW РФ + FBS, дней": "Оборачиваемость для WB не утверждена: слот сохранён, значение «—»",
    "Оборачиваемость в продажах FBW РФ + FBS, дней": "Оборачиваемость для WB не утверждена: слот сохранён, значение «—»",
}

def _column_help(col: str) -> str:
    if col == "Δ к прошлой неделе, %":
        return "(Текущий сопоставимый период / предыдущий − 1) × 100%. Нет данных или предыдущий период = 0 — «—». CTR/CR/ДРР: п.п. только в соседней абсолютной колонке."
    if col.startswith("Δ к прошлой неделе"):
        return "Одинаковые дни недели, DAILY обеих недель. Абсолютная разница: ₽, шт., п.п. или дни. Остатки — последние сопоставимые снимки. Нет данных — «—»."
    if col == "Товары в пути, шт":
        return "FBW O’STIN: В пути до получателей + В пути возвраты на склад WB. Самостоятельный снимок; в складские остатки FBS/FBW не включается."
    if col in _TURNOVER_VISIBILITY_COLUMNS:
        return "Остаток FBW на последний день факта / (заказы или финансовые продажи минус возвраты, шт / подтверждённые дни); за день — остаток FBW / шт дня. Нет снимка или нулевой спрос — «—»."
    if col in _FBS_HELP:
        return _FBS_HELP[col]
    if col == "Δ к пред. дню":
        return f"{_DELTA_DAY_HELP}: изменение в % (для показателей в % — в п.п.)"
    if col == "Тренд недели":
        return f"{_WEEK_TREND_HELP}: изменение в % (для показателей в % — в п.п.)"
    if col.startswith("Δ к пред. дню, "):
        return f"{_DELTA_DAY_HELP}: разница тех же двух значений в ₽ / шт. «—» — сравнить не с чем"
    if col.startswith("Тренд недели, "):
        return f"{_WEEK_TREND_HELP}: разница тех же двух значений в ₽ / шт. «—» — сравнить не с чем"
    return str(col)

def _dimension_width(col: str, first_col: str) -> int:
    if col.startswith("Δ к прошлой неделе"):
        return 215 if col.endswith("₽ / шт.") else 190
    if col == first_col:
        return _DIMENSION_IDENTIFIER_WIDTHS[first_col]
    if col in _TURNOVER_VISIBILITY_COLUMNS:
        return _DIMENSION_WIDTHS["turnover"]
    if col in _DIMENSION_SHARE_COLUMNS:
        return _DIMENSION_WIDTHS["share"]
    if col in _DIMENSION_MONEY_COLUMNS:
        return _DIMENSION_WIDTHS["money"]
    if col in _DIMENSION_AVERAGE_COLUMNS:
        return _DIMENSION_WIDTHS["average"]
    if col in _DIMENSION_RATE_COLUMNS:
        return _DIMENSION_WIDTHS["rate"]
    if str(col).startswith("Оборачиваемость в ") and "FBW РФ + FBS" in str(col):
        return _DIMENSION_WIDTHS["turnover"]
    if col in ("Остаток, шт", "Остаток FBS, шт", "Остаток FBW РФ + FBS, шт"):
        return _DIMENSION_WIDTHS["stock"]
    if col in _DIMENSION_COUNT_COLUMNS:
        return _DIMENSION_WIDTHS["count"]
    if col in ("Δ к пред. дню", "Тренд недели"):
        return 115
    if col.startswith(_ABSOLUTE_DYNAMICS_PREFIXES):
        return 145
    if col == "Динамика":
        return 125
    if col.startswith(("Пн ", "Вт ", "Ср ", "Чт ", "Пт ", "Сб ", "Вс ")):
        return 95
    return _DIMENSION_WIDTHS["other_numeric"]

def _col_width(col: str, first_col: str) -> int:
    if col.startswith("Δ к прошлой неделе"):
        return 215 if col.endswith("₽ / шт.") else 190
    if first_col in _DIMENSION_IDENTIFIERS:
        return _dimension_width(col, first_col)
    # TABLE 1 and non-dimension tables keep the exact accepted baseline sizing.
    if col == first_col:
        return 260
    if col in ("Δ к пред. дню", "Тренд недели"):
        return 125
    if col.startswith(_ABSOLUTE_DYNAMICS_PREFIXES):
        return 175
    if col == "Динамика":
        return 150
    if col.startswith(("Пн ", "Вт ", "Ср ", "Чт ", "Пт ", "Сб ", "Вс ")):
        return 120
    if "₽" in col or "руб" in col or "ССТ" in col or col in ("Продвижение, ₽",):
        return 145
    if "%" in col or "CTR" in col or "CR" in col or "ДРР" in col or "Доля" in col:
        return 105
    return 115

_STYLER_NULL_NUMERIC_COLUMNS = {
    "CPC",
    *_TURNOVER_VISIBILITY_COLUMNS,
}

def _table_columns(frame: pd.DataFrame, first_col: str):
    config = {}
    dimension_table = first_col in _DIMENSION_IDENTIFIERS
    metrics = DIMENSION_METRICS if dimension_table else {}
    for col in frame.columns:
        width = _col_width(col, first_col)
        tip = _column_help(col)
        from week_controls import DISPLAY_HEADERS
        if col in DISPLAY_HEADERS:
            config[col]=st.column_config.NumberColumn(DISPLAY_HEADERS[col],width=width,pinned=False,help=col+". "+tip)
            continue
        if col == first_col:
            # The identifier/metric column stays visible during horizontal scrolling.
            config[col] = st.column_config.TextColumn(col, width=width, pinned=True, help=tip)
        elif col == "Динамика" and hasattr(st.column_config, "LineChartColumn"):
            config[col] = st.column_config.LineChartColumn(col, width=width, help=tip)
        elif not pd.api.types.is_numeric_dtype(frame[col]):
            config[col] = st.column_config.TextColumn(col, width=width, help=tip)
        elif metrics.get(col) in _DIMENSION_DRR:
            config[col] = st.column_config.NumberColumn(
                col, width=width, format="percent", pinned=False, help=tip
            )
        elif col in _TURNOVER_VISIBILITY_COLUMNS:
            # Explicitly unpinned; generic Column preserves inferred numeric type
            # and leaves Styler in control of unavailable-value formatting.
            if hasattr(st.column_config, "Column"):
                config[col] = st.column_config.Column(col, width=width, pinned=False, help=tip)
            else:
                continue
        elif col in _STYLER_NULL_NUMERIC_COLUMNS:
            # CPC keeps inferred numeric semantics while receiving the canonical
            # compact width. Generic Column preserves Styler/null ownership.
            if hasattr(st.column_config, "Column"):
                config[col] = st.column_config.Column(
                    col, width=width, pinned=False if dimension_table else None, help=tip
                )
            else:
                continue
        else:
            config[col] = st.column_config.NumberColumn(
                col, width=width, pinned=False if dimension_table else None, help=tip
            )
    return config

_WEEK_CONTRAST = {
    # Presentation-only contrast polish: intentionally dark navy/graphite rather
    # than pure black, so the grid is clearer without becoming visually harsh.
    "body": "#1B2638",
    "header": "#0F172A",
    "identifier": "#111827",
    "missing": "#4B5563",
    "header_bg": "#E8EEF5",
}

def _week_contrast_style_frame(frame: pd.DataFrame, first_col: str) -> pd.DataFrame:
    styles = pd.DataFrame("", index=frame.index, columns=frame.columns)
    for idx, row in frame.iterrows():
        is_total = str(row.get(first_col)) == "ИТОГО"
        if first_col in frame.columns and not is_total:
            styles.at[idx, first_col] = (
                f"color:{_WEEK_CONTRAST['identifier']};font-weight:600"
            )
        if is_total:
            continue
        for col in frame.columns:
            value = row.get(col)
            try:
                missing = bool(pd.isna(value))
            except Exception:
                missing = value is None
            if missing:
                styles.at[idx, col] = (
                    f"background-color:{VISUAL_COLORS['missing']};"
                    f"color:{_WEEK_CONTRAST['missing']};font-weight:600"
                )
    return styles

def _apply_week_contrast(styler, first_col: str):
    """WEEK-only contrast overlay; values, formatting and business semantics stay untouched."""
    styler = styler.set_table_styles([
        {"selector": "th", "props": [
            ("background-color", "#F3F3F3"),
            ("color", _WEEK_CONTRAST["header"]),
            ("font-weight", "700"),
            ("border-bottom", "1px solid #C9D3DE"),
        ]},
        {"selector": "td", "props": [
            ("color", _WEEK_CONTRAST["body"]),
            ("font-weight", "500"),
        ]},
    ], overwrite=False)
    return styler.apply(
        lambda data: _week_contrast_style_frame(data, first_col), axis=None
    )

MISSING_DISPLAY = "—"

_DIMENSION_DRR = {"ad_drr", "drr_orders", "drr_revenue"}

def _dimension_display_styler(frame: pd.DataFrame, first_col: str):
    """Rebuild the accepted dimension Styler on the physically reordered frame."""
    def zebra(row):
        if row.get(first_col) == "ИТОГО":
            return [""] * len(row)
        bg = f"background-color:{VISUAL_COLORS['zebra']}" if row.name % 2 else ""
        return [bg] * len(row)

    def highlight_total(row):
        if row.get(first_col) == "ИТОГО":
            return [
                f"background-color:{VISUAL_COLORS['total']};"
                f"color:{_WEEK_CONTRAST['header']};"
                "font-weight:700;border-top:2px solid #AEBFD0"
            ] * len(row)
        return [""] * len(row)

    from wb_format import format_percent
    from fc_format import format_value
    styler = frame.style.format({column:(lambda v, col=column:format_value(v,col)) for column in frame},na_rep=MISSING_DISPLAY)
    styler = styler.apply(zebra, axis=1).apply(highlight_total, axis=1)
    metrics = DIMENSION_METRICS
    for col in frame.columns:
        metric = metrics.get(col)
        if metric is None:
            continue
        formatter = format_percent if metric in _DIMENSION_DRR else lambda v, m=metric: format_metric(m, v)
        styler = styler.format(formatter, subset=[col], na_rep=MISSING_DISPLAY)
    for col in ("Остаток FBS, шт", "Остаток FBW РФ + FBS, шт", week_detail.SKU_COLUMN):   # OZON FBS: integers, «—» when not known (never 0)
        if col in frame.columns:
            styler = styler.format(lambda v: format_number(v), subset=[col], na_rep=MISSING_DISPLAY)
    for metric, col in (("turn_orders", "Оборачиваемость в заказах FBW РФ + FBS, дней"),
                        ("turn_sales", "Оборачиваемость в продажах FBW РФ + FBS, дней")):   # the accepted turnover format
        if col in frame.columns:
            styler = styler.format(lambda v, m=metric: format_metric(m, v), subset=[col], na_rep=MISSING_DISPLAY)
    return _apply_week_contrast(styler, first_col)

def _table_height(frame, *, cap: int = 680, row_px: int = 35, minimum: int = 115) -> int:
    return max(minimum, min(cap, 44 + row_px * (len(frame) + 1)))

def _render_table(frame: pd.DataFrame, first_col: str, *, cap: int = 680, styler=None):
    future_columns = [col for col in frame.columns
                      if col.startswith(("Пн ", "Вт ", "Ср ", "Чт ", "Пт ", "Сб ", "Вс "))
                      and frame[col].isna().all()]
    columns = _table_columns(frame, first_col)
    if first_col == "Показатель" and len(frame) > 30:
        columns[first_col] = st.column_config.TextColumn(first_col, width=390, pinned=True)
    if styler is not None and future_columns:
        # Display only: retain null numeric cells and their sorting semantics.
        styler = styler.format(na_rep=MISSING_DISPLAY, subset=future_columns)
        for col in future_columns:
            columns[col] = st.column_config.Column(
                col, width=_col_width(col, first_col), help=str(col)
            )
    st.dataframe(
        week_detail.round_styler(styler) if styler is not None else frame,
        width="stretch",
        hide_index=True,
        height=_table_height(frame, cap=cap),
        column_config=columns,
        # The grid draws empty cells itself (Styler display values do not reach
        # them): show "—" for absent data / future days instead of "None".
        # Real zeros stay 0; underlying values and sorting are unchanged.
        placeholder=MISSING_DISPLAY,
    )

_HTML_COL_MIN_PX = 100

_HTML_COL_MAX_PX = 210

def _html_col_width(col: str, first_col: str) -> int:
    return 236 if col == first_col else max(_HTML_COL_MIN_PX, min(_HTML_COL_MAX_PX, _col_width(col, first_col)))

def _html_header_label(col) -> str:
    """Keep a short unit (₽, %, шт) on the same line as the word before it."""
    words = str(col).split(" ")
    if len(words) > 1 and len(words[-1]) <= 3:
        words[-2:] = [words[-2] + " " + words[-1]]
    return " ".join(words)

def _render_html_table(frame: pd.DataFrame, first_col: str, *, styler, key: str, max_height: int = 560):
    uid = f"week_{key}"
    widths = "".join(
        f"#T_{uid} .col{i}{{width:{_html_col_width(col, first_col)}px;min-width:{_html_col_width(col, first_col)}px}}"
        for i, col in enumerate(frame.columns)
    )
    table = (styler.set_uuid(uid).hide(axis="index")
             .format(escape="html", subset=[first_col])
             .format_index(_html_header_label, axis=1, escape="html").to_html())
    css = f"""<style>
/* Low-specificity default: Styler cell colours (#T_..._rowN_colM) take precedence. */
.week-html-wrap{{overflow:auto;max-height:{max_height}px;border:1px solid #D8E0E8;border-radius:6px;margin-bottom:1rem}}
#T_{uid}{{border-collapse:separate;border-spacing:0;width:max-content;font-size:14px;line-height:1.3;margin:0}}
#T_{uid} th{{position:sticky;top:0;z-index:2;white-space:normal;word-break:normal;overflow-wrap:anywhere;
  vertical-align:bottom;text-align:center;padding:8px 8px;border-right:1px solid #D8E0E8}}
.week-html-wrap td{{background:#FFFFFF}}
#T_{uid} td,#T_{uid} th{{font-size:14px;line-height:1.35}}
#T_{uid} td{{white-space:nowrap;text-align:right;padding:6px 8px;
  border-bottom:1px solid #EEF2F6;border-right:1px solid #EEF2F6}}
#T_{uid} td.col0,#T_{uid} th.col0{{position:sticky;left:0;text-align:left;border-right:1px solid #C9D3DE}}
#T_{uid} td.col0{{z-index:1;text-align:left;white-space:normal;background:#fff}}
#T_{uid} th.col0{{z-index:3}}
{widths}
</style>"""
    st.html(css + f'<div class="week-html-wrap">{table}</div>')

_VIEW_COMFORT = "Удобный вид"

_VIEW_INTERACTIVE = "Интерактивный: сортировка, поиск"

def _render_dimension_table(frame: pd.DataFrame, first_col: str, *, key: str, cap: int):
    """Two presentations of one frame and one Styler; the data are identical."""
    view = st.segmented_control(
        "Вид таблицы", [_VIEW_COMFORT, _VIEW_INTERACTIVE],
        default=_VIEW_COMFORT, required=True, key=f"week_view_{key}",
        label_visibility="collapsed",
    )
    styler = _dimension_display_styler(frame, first_col)
    if view == _VIEW_INTERACTIVE:
        _render_table(frame, first_col, cap=cap, styler=styler)
    else:
        _render_html_table(frame, first_col, styler=styler, key=key, max_height=cap + 60)

def _kpi_card(label: str, value, cls: str) -> str:
    return f'<div class="kpi-card {cls}"><div class="kpi-label">{label}</div><div class="kpi-value">{format_number(value)}</div></div>'



