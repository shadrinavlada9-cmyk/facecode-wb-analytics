from collections import defaultdict
from decimal import Decimal
from html import escape
from numbers import Real
import pandas as pd
import streamlit as st
from session_download import excel_download
import wb_format as presentation
from fc_format import DEMO_LABEL
UNKNOWN = 'Не определено'

D = Decimal

SKU_COLUMN = 'SKU с остатком > 10 шт.'

VALUE = 'Остаток по ССТ заказа, ₽'

SHARE = 'Доля остатка в ₽ (по ССТ заказа), %'

TOTAL = 'ИТОГО'

DETAIL_FROM = '2026-11-01'

def integer(value):
    return '—' if value is None or pd.isna(value) else presentation._fmt_decimal(value, 0)

def integer_metric(metric, value):
    if metric in presentation.PERCENT_KEYS or metric == 'orders_stock_ratio':
        return presentation.format_metric(metric, value)
    return integer(value)

def round_styler(styler):
    """Preserve existing percentage and percentage-point display functions."""
    if styler is None:
        return None
    for i, row in enumerate(styler.data.itertuples(index=False, name=None)):
        for j, value in enumerate(row):
            if not isinstance(value, (Real, Decimal)) or pd.isna(value):
                continue
            original = styler._display_funcs[i, j]
            rendered = str(original(value))
            if '%' not in rendered and 'п.п.' not in rendered and rendered.strip() not in ('—', '-'):
                styler._display_funcs[i, j] = integer
    return styler

ORDERS_RUB = 'Заказы, ₽'

ORDERS_QTY = 'Заказы, шт.'

REVENUE_RUB = 'Выручка, ₽'

REVENUE_QTY = 'Выручка, шт.'

PROMO = 'Продвижение WB, ₽'

XWAY = 'XWAY, ₽'

UNALLOCATED = ('Не распределено',) * 3

COLLECTIONS = ('AW27', 'SS27', 'OLD', 'Не определено', 'Не распределено')

BRAND = 'ИТОГО FACE CODE'

SCHEMES = {'fbs': 'FBS', 'fbw': 'FBW РФ', 'total': 'Всего'}

CHANNEL_STOCK = {'ALL': ('fbs', 'fbw'), 'FBS': ('fbs',), 'FBW_RF': ('fbw',)}

DIMENSIONS = ('Коллекция', 'Гендер', 'Тип товара')

DELTA = 'Изменение'

RELATIVE = 'Изменение, %'

WEEK_PREV = 'Прошлая неделя'

WEEK_NOW = 'За период'

WEEK_PRIOR_DAY = 'Прошлая · '

COVERAGE = 'Оценено запаса, %'

SHARES = {ORDERS_QTY: 'Доля заказов, шт., %', ORDERS_RUB: 'Доля заказов, ₽, %',
          PROMO: 'Доля продвижения WB, %', 'Средний запас · шт.': 'Доля остатка, шт., %',
          'Средний запас · ₽': SHARE}

def _dated(start):
    from datetime import date, timedelta
    return tuple((date.fromisoformat(start) + timedelta(days=i)).isoformat() for i in range(7))

def _stock_metrics(scheme, unit):
    title = SCHEMES[scheme] if scheme != 'total' else 'запас'
    return f'Средний {title} · {unit}'

def _stock_change(scheme):
    return f'Δ запас {SCHEMES[scheme]}'

def _change(value, base):
    return value - base if value is not None and base is not None else None

def _analysis(records, current, previous):
    """Direction signals based on consistent observed quantities and comparable orders."""
    if not previous:
        return []
    comparison = f'{current[0]}–{current[-1]} / {previous[0]}–{previous[-1]}'
    stock_period = f'{current[0]}–{current[-1]}'
    rows = []
    for path, rec in records.items():
        if len(path) != 3 or path[0] not in COLLECTIONS:
            continue
        orders = rec['dynamic'][ORDERS_RUB]
        units = rec['dynamic'][ORDERS_QTY]
        promo = rec['dynamic'][PROMO]
        fbs = rec['stocks'].get(('fbs', 'шт.'), {})
        fbw = rec['stocks'].get(('fbw', 'шт.'), {})
        stock = rec['stocks'].get(('total', 'шт.'), fbs or fbw)
        ds = stock.get(DELTA)
        delta = orders[DELTA]
        has_new_fbs = len(current) > 1 and fbs.get(current[0]) == 0 and (fbs.get(current[-1]) or 0) >= 10
        base = {'Новый запас FBS': 'Да' if has_new_fbs else '—', 'Группа': ' / '.join(path), 'Период заказов': comparison, 'Период остатков': stock_period,
                'Прошлые заказы, ₽': orders[WEEK_PREV], ORDERS_RUB: orders[WEEK_NOW],
                'Δ заказы, ₽': delta, 'Δ заказы, %': orders[RELATIVE],
                'Δ заказы, шт.': units[DELTA], PROMO: promo[WEEK_NOW],
                'Прошлое продвижение WB, ₽': promo[WEEK_PREV], 'Δ продвижение WB, ₽': promo[DELTA],
                'Δ продвижение WB, %': promo[RELATIVE], 'Средний FBS, шт.': fbs.get('Среднее'),
                'Средний FBW, шт.': fbw.get('Среднее'), 'Средний запас, шт.': stock.get('Среднее'),
                'Δ запас, шт.': ds, 'Δ запас, %': stock.get(RELATIVE),
                'Δ FBS, шт.': fbs.get(DELTA), 'Δ FBW, шт.': fbw.get(DELTA),
                'Δ FBS, %': fbs.get(RELATIVE), 'Δ FBW, %': fbw.get(RELATIVE)}
        rows.append(base)
    rankings = []
    for label, sign in (('Снижение', -1), ('Рост', 1)):
        ranked = sorted((row for row in rows if row['Δ заказы, ₽'] is not None and sign * row['Δ заказы, ₽'] > 0),
                        key=lambda row: -sign * row['Δ заказы, ₽'])[:5]
        rankings.extend({'Сигнал': label, **row} for row in ranked)
    signals = []
    for row in rows:
        order = row['Δ заказы, ₽']
        stock = row['Δ запас, шт.']
        promo = row['Δ продвижение WB, ₽']
        units = row['Средний запас, шт.']
        fbs, fbw = row['Δ FBS, шт.'], row['Δ FBW, шт.']
        now = row[ORDERS_RUB]
        flags = [
            ('А · Возможное накопление', order is not None and order <= -50000 and stock is not None and stock >= 100),
            ('Б · Возможный дефицит', order is not None and order >= 50000 and stock is not None and stock <= -100),
            ('В · Проверить эффективность рекламы', order is not None and order <= -50000 and promo is not None and promo >= 10000),
            ('Г · Мало заказов при высоком запасе', units is not None and units >= 500 and now is not None and 0 <= now <= 10000),
            ('Д · Появился запас FBS при малых заказах', row['Новый запас FBS'] == 'Да' and now is not None and 0 <= now <= 10000),
            ('Е · Разнонаправленная динамика FBS и FBW', fbs is not None and fbw is not None and fbs * fbw < 0 and
             abs(fbs) >= 100 and abs(fbw) >= 100 and
             row['Δ FBS, %'] is not None and row['Δ FBW, %'] is not None and
             abs(row['Δ FBS, %']) >= D('.1') and abs(row['Δ FBW, %']) >= D('.1')),
        ]
        signals.extend({'Сигнал': label, **row} for label, show in flags if show)
    return rankings + signals

def _days_headers(calendar):
    return {day: presentation.day_label(day) for day in calendar}

def _cell_text(column, value):
    if value is None:
        return '—'
    if column.endswith('%'):
        return presentation.format_percent(value)
    return integer(value)

def _sign(value):
    return 'up' if value is not None and value > 0 else 'down' if value is not None and value < 0 else ''

def _tree_sort_key(row, path, sort_column):
    name = (path[-1].casefold(), path[-1])
    if sort_column is not None and len(path) > 1:
        value = row.get(sort_column)
        if sort_column == ORDERS_RUB:
            return value is None, value == 0, -value if value is not None else 0, name
        return value is None, -value if value is not None else 0, name
    if len(path) == 1:
        return COLLECTIONS.index(path[0]), name
    return path[-1] == UNKNOWN, name

def _tree(rows, columns, headings=None, changes=None, sort_column=None, trend=False, daily_note="К предыдущему дню"):
    """Expandable rows are native HTML details; opening them never reruns Streamlit."""
    children = defaultdict(list)
    for path in rows:
        if path and path[0] in COLLECTIONS and path[0] != UNALLOCATED[0]:
            children[path[:-1]].append(path)
    scope = len(columns) + trend
    head = '<div class="wb-tree-row wb-tree-head"><span>Коллекция / Гендер / Тип товара</span>'
    head += ''.join(f'<span>{escape((headings or {}).get(c, c))}</span>' for c in columns)
    head += ('<span>Тренд</span>' if trend else '') + '</div>'

    def line(path, tag='div'):
        row = rows[path]
        from management import gender, UNATTRIBUTED
        label = (UNATTRIBUTED if path == UNALLOCATED[:1] else gender(path[-1]) if len(path)==2 else path[-1]) if path else BRAND
        values = []
        for col in columns:
            value = row.get(col)
            movement = (changes or {}).get(path, {}).get(col)
            title = f' title="{escape(daily_note)}: {escape(integer(movement))}"' if movement is not None and col[:4].isdigit() else ''
            values.append(f'<span class="{_sign(movement)}"{title}>{escape(_cell_text(col, value))}</span>')
        if trend:
            value = row.get(RELATIVE)
            amount = row.get(DELTA)
            if value is None:
                bar = 'Новые продажи' if amount and amount > 0 and row.get(WEEK_PREV) == 0 else '—'
            else:
                width = max(3, min(100, abs(float(value)) * 100)) if value else 0
                bar = f'<i class="{_sign(amount)}" style="width:{width:.1f}%"></i>'
            values.append(f'<span class="wb-bar">{bar}</span>')
        return f'<{tag} class="wb-tree-row"><span>{escape(label)}</span>{"".join(values)}</{tag}>'

    def nested(parent):
        paths = sorted(children[parent], key=lambda p: _tree_sort_key(rows[p], p, sort_column))
        for path in paths:
            if path in children:
                yield '<details>' + line(path, 'summary') + ''.join(nested(path)) + '</details>'
            else:
                yield line(path)

    css = """
    .wb-tree{position:relative;isolation:isolate;overflow:auto;max-height:56vh;scrollbar-gutter:stable;border:1px solid #ccd8e4;border-radius:6px;margin-bottom:1rem}
    .wb-tree-row{color:#172b3e;display:grid;grid-template-columns:205px repeat(COLUMN_COUNT,120px);width:max-content;
      border-bottom:1px solid #dce5ee;background:#fff;font-size:.82rem}
    .wb-tree-row span{padding:7px 8px;text-align:right;min-width:0}
    .wb-tree-row span:first-child{text-align:left;position:sticky;left:0;background:inherit;z-index:1}
    .wb-tree details details summary span:first-child{padding-left:25px}
    .wb-tree details details div span:first-child{padding-left:43px}
    .wb-tree summary{background:#f4f7fa;cursor:pointer}
    .wb-tree > details > summary{background:#e7eff6;font-weight:600;border-top:1px solid #d2dfea}
    .wb-tree details details > summary > span:first-child{font-weight:600}
    .wb-tree details details > div:nth-child(odd){background:#fafbfd}
    .wb-tree summary span:first-child:before{content:"▸ ";color:#4980a7}
    .wb-tree details[open]>summary span:first-child:before{content:"▾ "}
    .wb-tree-head,.wb-total{background:#d5e4f1;color:#162b41;font-weight:700}
    .wb-tree .wb-tree-head{position:sticky;top:0;z-index:10;align-items:stretch;
      background:#ebf2f8;box-shadow:0 1px 0 #ccd8e4}
    .wb-tree .wb-tree-head span{display:flex;align-items:center;justify-content:flex-end;
      min-height:2.8rem;white-space:normal;overflow-wrap:anywhere;line-height:1.25}
    .wb-tree .wb-tree-head span:first-child{justify-content:flex-start;z-index:11}
    .wb-tree-row .up{color:#187848;background-color:#e2f4e9}
    .wb-tree-row .down{color:#ae2b31;background-color:#ffeded}
    .wb-bar i{display:block;border-radius:2px;height:7px;margin-top:6px}
    .wb-bar i.up{background:#27905a}.wb-bar i.down{background:#cc454a}
    """.replace('COLUMN_COUNT', str(scope))
    st.html(f'<style>{css}</style><div class="wb-tree">{head}{line(()).replace("wb-tree-row", "wb-tree-row wb-total", 1)}'
            f'{"".join(nested(()))}</div>')

def _changes(rows, calendar=(), color_delta=True, previous_week=False):
    out = {}
    for path, row in rows.items():
        sign = row.get(DELTA) if color_delta else None
        out[path] = {DELTA: sign, RELATIVE: sign}
        if previous_week:
            for day in calendar:
                out[path][day] = _change(row.get(day), row.get(WEEK_PRIOR_DAY + day)) if color_delta else None
        else:
            for prev, day in zip(calendar, calendar[1:]):
                out[path][day] = _change(row.get(day), row.get(prev))
    return out

def _unpack(path):
    labels = (path[0], None, None) if path == UNALLOCATED[:1] else (*path, *([None] * (3 - len(path))))
    from management import gender, UNATTRIBUTED
    if path and path[0] == UNALLOCATED[0]:
        labels = (UNATTRIBUTED,None,None)
    elif len(path)>1:
        labels = (labels[0],gender(labels[1]),labels[2])
    return dict(zip(DIMENSIONS, labels if path else (BRAND, None, None)))

def _flatten(columns, row, prefix=''):
    return {prefix + name: row.get(name) for name in columns}

def _discussion(rows):
    st.subheader('На что обратить внимание')
    for label, title in (('Снижение', 'Топ-5 снижений заказов'), ('Рост', 'Топ-5 роста заказов')):
        st.markdown('**' + title + '**')
        frame = pd.DataFrame([{k: v for k, v in row.items() if k in (
            'Группа', 'Прошлые заказы, ₽', ORDERS_RUB, 'Δ заказы, ₽', 'Δ заказы, %', 'Δ заказы, шт.',
            'Δ продвижение WB, ₽', 'Средний FBS, шт.', 'Средний FBW, шт.', 'Δ запас, шт.', 'Δ FBS, шт.', 'Δ FBW, шт.'
        )} for row in rows if row['Сигнал'] == label])
        if frame.empty:
            st.caption('Нет подтверждённых изменений для этого рейтинга.')
        else:
            tint = 'background-color:#fff0ef;color:#812f34' if label == 'Снижение' else 'background-color:#eaf6ef;color:#255f44'
            styler = frame.style.format({c: (presentation.format_percent if c.endswith('%') else integer)
                                         for c in frame.columns if c != 'Группа'})
            for column in ('Δ заказы, ₽', 'Δ заказы, %'):
                styler = styler.map(lambda value: tint if value is not None and not pd.isna(value) and value else '', subset=[column])
            st.dataframe(styler, hide_index=True, width='stretch')
    st.markdown('**Главное за неделю**')
    st.caption('Порог подсказок: заказы от 50 000 ₽ изменения, запас от 100 шт., продвижение от 10 000 ₽. '
               'Мало заказов: до 10 000 ₽ при среднем запасе от 500 шт. '
               'Новый запас: от 0 до 10 шт. FBS или больше за период. Разнонаправленный FBS/FBW: от 100 шт. и 10% по каждой схеме.')
    for kind in ('Снижение', 'Рост', 'Б', 'А', 'В', 'Г', 'Д', 'Е'):
        if kind in ('Б', 'А', 'В', 'Г', 'Д', 'Е'):
            options = [x for x in rows if x['Сигнал'].startswith(kind + ' ·')]
            options.sort(key=lambda x: abs(x['Δ заказы, ₽'] or 0), reverse=True)
        else:
            options = [x for x in rows if x['Сигнал'] == kind]
        if options:
            row = options[0]
            yield row

def _format_signal(row):
    from operator import itemgetter

    def movement(title, delta, relative, suffix):
        absolute, ratio = itemgetter(delta, relative)(row)
        return f'{title} {integer(absolute)} {suffix} ({_cell_text(relative, ratio)})' if absolute is not None else None

    details = [movement('заказы', 'Δ заказы, ₽', 'Δ заказы, %', '₽'),
               movement('продвижение WB', 'Δ продвижение WB, ₽', 'Δ продвижение WB, %', '₽'),
               movement('запас', 'Δ запас, шт.', 'Δ запас, %', 'шт.'),
               movement('FBS', 'Δ FBS, шт.', 'Δ FBS, %', 'шт.'),
               movement('FBW', 'Δ FBW, шт.', 'Δ FBW, %', 'шт.')]
    if row['Средний запас, шт.'] is not None:
        details.append(f"средний запас {integer(row['Средний запас, шт.'])} шт.")
    return f"**{row['Сигнал']} · {row['Группа']}**. " + ', '.join(x for x in details if x) + '. ' + row['Период заказов'] + '.'

def _excel_tables(records, calendar, analysis):
    week, orders, stocks, flat, outside = [], [], [], [], []
    for path, record in sorted(records.items(), key=lambda item: (COLLECTIONS.index(item[0][0]) if item[0] and item[0][0] in COLLECTIONS else -1, item[0])):
        if path and path[0] not in COLLECTIONS:
            continue
        if path and path[0] == UNALLOCATED[0]:
            if len(path)==1:
                outside.append({"Распределение":"Реклама без привязки к товарам",**record["week"]})
                outside.append({"Распределение":"Реклама без привязки к товарам","Показатель":PROMO,**record["dynamic"][PROMO]})
            continue
        dims = _unpack(path)
        level = {'0': 'Итого', '1': 'Коллекция', '2': 'Гендер', '3': 'Тип товара'}[str(len(path))]
        dim = {**dims, 'Уровень': level}
        weekly = {**dim, **record['week']}
        week.append(weekly)
        for metric, series in record['dynamic'].items():
            orders.append({**dim, 'Показатель': metric, **series})
        stock_row = dict(dim)
        for (scheme, unit), series in record['stocks'].items():
            stock_row.update(_flatten(series, series, f'{SCHEMES[scheme]} {unit} · '))
        stocks.append(stock_row)
        if len(path) == 3:
            flattened = dict(weekly)
            for metric, series in record['dynamic'].items():
                flattened.update(_flatten(calendar, series, metric + ' · '))
            flattened.update({k: v for k, v in stock_row.items() if k not in dim})
            flat.append(flattened)
    return [('Недельные итоги', week), ('Заказы по дням', orders), ('Остатки по дням', stocks),
            ('На что обратить внимание', analysis), ('Детальные данные', flat)] + ([('Реклама вне разрезов',outside)] if outside else [])

def _excel(tables, title, coverage):
    from io import BytesIO
    from openpyxl import Workbook as ExcelBook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils.cell import get_column_letter
    book = ExcelBook()
    book.remove(book.active)
    for name, rows in tables:
        sheet = book.create_sheet(name)
        sheet.append([f"{DEMO_LABEL} · {title}"])
        sheet.append([coverage])
        columns = list(dict.fromkeys(key for row in rows for key in row))
        if not columns:
            columns = ['Сигнал', 'Группа'] if name == 'На что обратить внимание' else list(DIMENSIONS)
        sheet.append(columns)
        for cell in sheet[3]:
            cell.fill = PatternFill('solid', fgColor='DAE9F4')
            cell.font = Font(bold=True, color='19354A')
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            sheet.column_dimensions[cell.column_letter].width = 28 if cell.value in DIMENSIONS or cell.value == 'Группа' else 18
        sheet.row_dimensions[3].height = 38
        for index, row in enumerate(rows, 4):
            for j, col in enumerate(columns, 1):
                value = row.get(col)
                if value is None:
                    continue
                cell = sheet.cell(index, j)
                if isinstance(value, (Decimal, Real)):
                    cell.value = float(value)
                    cell.number_format = '0.00%' if col.endswith('%') else '0.00' if 'п.п.' in col or col.startswith('H7 ') else '#,##0'
                    is_delta = col.startswith('Δ') or col.startswith(DELTA) or f'· {DELTA}' in col
                    # An increase in costs has no automatic positive business meaning.
                    if is_delta and 'продвижение' not in col.lower() and row.get('Показатель') != PROMO and value:
                        cell.fill = PatternFill('solid', fgColor='E2F4E9' if value > 0 else 'FFEDED')
                else:
                    cell.value = value
                    cell.data_type = 's'
        sheet.freeze_panes = 'D4' if len(columns) > 3 else 'A4'
        sheet.auto_filter.ref = f'A3:{get_column_letter(len(columns))}{sheet.max_row}'
    out = BytesIO()
    book.save(out)
    return out.getvalue()

def _residual_note(count, orders, qty, fbs, fbw, promo, unallocated=None):
    notes = []
    if count or any((orders, qty, fbs, fbw, promo)):
        notes.append(f'В общем итоге отдельно учтены {count} артикулов без коллекции среди заказов и остатков периода: '
                     f'заказы {integer(orders)} ₽ / {integer(qty)} шт., '
                     f'FBS {integer(fbs)} шт., FBW РФ {integer(fbw)} шт., '
                     f'продвижение WB {integer(promo)} ₽.')
    if unallocated:
        notes.append(f'В общий итог также входят {integer(unallocated)} ₽ продвижения WB без однозначной привязки к группе.')
    return ' '.join(notes)

def coverage_note(records, day=None):
    member = records.get((UNKNOWN,), {})
    values = member.get('week', {})
    fbs, fbw = (values.get(_stock_metrics(k, 'шт.')) if day is None
                else member.get('stocks', {}).get((k, 'шт.'), {}).get(day)
                for k in ('fbs', 'fbw'))
    ads = records.get(UNALLOCATED[:1], {}).get('week', {}).get(PROMO)
    return _residual_note(records[()].get('unknown_count', 0), values.get(ORDERS_RUB),
                          values.get(ORDERS_QTY), fbs, fbw, values.get(PROMO), ads)

def render(result, scope, model=None, matches=None):


    if scope is None:
        if result['period_meta']['period_start'] < DETAIL_FROM:
            st.info('Детализация доступна с ноября 2026 года. Прежние таблицы доступны во вкладке «Обзор».')
        else:
            st.info('За выбранную неделю нет принятых данных.')
        return
    start, end, current, previous, build_id, channel, (records, stock_days, valid, problems) = scope
    if not records:
        st.info('За выбранную неделю нет подтверждённой детализации.')
        return
    calendar = _dated(start)
    headings = _days_headers(calendar)
    coverage = 'Подтверждённые снимки: ' + ' · '.join(
        f'{SCHEMES[s]} {len(days)}/7' for s, days in stock_days.items()
    )
    st.caption(coverage)
    st.caption('Поля справочника: Коллекция → Гендер_1 → Тип товара (поле «Категория» шаблона WB).')
    if problems:
        st.warning(' '.join(problems))
    note = coverage_note(records)
    if note:
        st.caption(note)
    week = {path: rec['week'] for path, rec in records.items()}
    actual = week[()]
    if records[()].get('legacy_comparison'):
        st.caption('Сравнение с октябрьской неделей показано по принятым итогам FACE CODE. Товарные разрезы за октябрь сохранены в обзоре.')
    checks = {ORDERS_RUB: 'orders_rub', ORDERS_QTY: 'orders_qty', REVENUE_RUB: 'revenue_rub',
              REVENUE_QTY: 'revenue_qty', PROMO: 'ad_spend'}
    mismatches = [col for col, field in checks.items()
                  if result['totals'].get(field) is not None
                  and (actual.get(col) is None or abs(actual[col] - D(str(result['totals'][field]))) > D('.01'))]
    if mismatches:
        st.warning('Не подтверждена сверка с обзором: ' + ', '.join(mismatches) + '.')
    else:
        st.caption('Заказы и доступные финансовые и рекламные итоги сверены с обзором.')
    st.subheader('Недельные итоги')
    summary = st.segmented_control('Колонки итогов', ['Заказы и реклама', 'Запас и доли'], default='Заказы и реклама',
                                   required=True, key='wb_detail_summary', label_visibility='collapsed')
    if summary == 'Запас и доли':
        columns = [*SHARES.values(), *[c for c in actual if c.startswith(('Средний', 'Δ запас'))], COVERAGE]
        columns = list(dict.fromkeys(columns))
        st.caption('Запас в ₽ по ССТ заказа. Денежная доля рассчитана по оценённой части запаса.')
    else:
        aliases = {REVENUE_RUB: 'Выручка, ₽ (справочно)', REVENUE_QTY: 'Выручка, шт. (справочно)'} if channel != 'ALL' else {}
        columns = [ORDERS_RUB, ORDERS_QTY, REVENUE_RUB, REVENUE_QTY, PROMO, XWAY,
                   'Прошлая неделя · заказы, ₽', 'Заказы · к прошлой неделе, %',
                   SHARES[ORDERS_RUB], SHARES[ORDERS_QTY], SHARES[PROMO]]
    _tree(week, columns, headings=aliases if summary == 'Заказы и реклама' else None, sort_column=ORDERS_RUB)

    if outside := records.get(UNALLOCATED[:1]):
        from fc_format import format_value
        with st.expander("Реклама без привязки к товарам"):
            values = outside["dynamic"][PROMO]
            row = {headings.get(key,key):values.get(key) for key in (*calendar,WEEK_NOW,WEEK_PREV,DELTA,RELATIVE)}
            st.dataframe(pd.DataFrame([row]).style.format({key:(presentation.format_percent if key.endswith("%") else format_value)
                                                          for key in row},na_rep="—"),hide_index=True,width="stretch")
    st.subheader('Заказы — динамика по дням')
    options = [ORDERS_RUB, ORDERS_QTY] + ([PROMO] if channel == 'ALL' else [])
    order_metric = st.segmented_control('Показатель заказов', options, default=ORDERS_RUB, required=True,
                                        key='wb_detail_orders', label_visibility='collapsed')
    rows = {path: rec['dynamic'][order_metric] for path, rec in records.items()}
    st.caption('Закрытая неделя: итог из принятой WEEKLY-выгрузки, дни из DAILY. '
               'Открытая неделя: сравнение по одинаковым дням. Цвет дня показывает разницу с тем же днём прошлой недели. Расходы WB без однозначной связи показаны отдельно.')
    _tree(rows, [*calendar, WEEK_NOW, WEEK_PREV, DELTA, RELATIVE], headings,
          _changes(rows, calendar, color_delta=order_metric != PROMO, previous_week=True),
          sort_column=WEEK_NOW,
          trend=order_metric != PROMO, daily_note="К тому же дню прошлой недели")

    st.subheader('Остатки — динамика по дням')
    comparable_stock_days = {scheme: days for scheme, days in stock_days.items() if len(days) >= 2}
    if comparable_stock_days:
        left, right = st.columns(2)
        with left:
            selected = st.segmented_control('Склад', [SCHEMES[s] for s in comparable_stock_days],
                default=SCHEMES['total'] if 'total' in comparable_stock_days else SCHEMES[next(iter(comparable_stock_days))],
                required=True, key='wb_detail_stock', label_visibility='collapsed')
        with right:
            unit = st.segmented_control('Единица остатков', ['Штуки', 'Рубли по ССТ заказа'], default='Штуки',
                                        required=True, key='wb_detail_unit', label_visibility='collapsed')
        scheme = next(s for s in comparable_stock_days if SCHEMES[s] == selected)
        unit = 'шт.' if unit == 'Штуки' else '₽'
        rows = {path: rec['stocks'][scheme, unit] for path, rec in records.items()}
        missing = [headings[d] for d in current if d not in stock_days[scheme]]
        details = f'{selected} · {len(stock_days[scheme])}/7 принятых снимков.'
        if missing:
            details += ' Пропущено: ' + ', '.join(missing) + '.'
        if len(current) > 1:
            details += f' Изменение за {headings[current[0]]} — {headings[current[-1]]}.'
        if unit == '₽':
            details += ' Оценка покрывает ' + _cell_text(COVERAGE, rows[()].get(COVERAGE)) + ' доступного запаса в штуках.'
        st.caption(details)
        columns = [*calendar, 'Среднее', DELTA, RELATIVE] + ([COVERAGE] if unit == '₽' else [])
        _tree(rows, columns, headings, _changes(rows, calendar), sort_column='Среднее', trend=True)

    else:
        st.caption("За выбранный период меньше двух сопоставимых снимков по одной схеме. Изменение остатка не рассчитано.")

    from week_attention import render as render_attention
    groups = render_attention(model,records,current,previous,matches)
    analysis = [{"Раздел":name,**{k:(v/100 if k.endswith("%") and isinstance(v,(Decimal,Real)) else v)
                                    for k,v in row.items()}} for name,rows in groups.items() for row in rows]
    end_label = f'{start} — {end} · FACE CODE · Канал: {'Все схемы'}'
    stock_meta = coverage + ' · Рубли по ССТ по оценённому запасу. ' + note
    def export():
        return _excel(_excel_tables(records, calendar, analysis), end_label, stock_meta)

    excel_download('Скачать Excel', export(), f'WB_Неделя_{start}_{end}_{channel}.xlsx', primary=True)






