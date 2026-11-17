"""PROMOTION - HTML of the tab «Обзор» (prepared view and table specs only: no calculation, no Streamlit call here).

The look is the accepted look of MONTH: the head band and the KPI bands of Block 1 (core classes of ``month_block1.PAGE_CSS``) and the
tables of Block 2 (sticky header, groups «Текущий / Сравнение / Изменение», horizontal scroll). A value that does not exist is «—» with
its reason in the tooltip - never a zero. Every cell carries ``data-cell="<table>|<row>|<column>"`` (Web / Excel parity tests).
"""

from __future__ import annotations

from html import escape

PAGE_CSS = '<style>\ndiv[data-testid="stHorizontalBlock"]:has(.st-key-month_block1_year) {gap:.9rem;align-items:center;}\ndiv[data-testid="stHorizontalBlock"]:has(.st-key-month_block1_year) > div[data-testid="stColumn"]:first-child {flex:0 0 auto;width:auto;min-width:0;}\ndiv[data-testid="stHorizontalBlock"]:has(.st-key-month_block1_year) > div[data-testid="stColumn"]:last-child {flex:1 1 0;min-width:0;}\ndiv[data-testid="stHorizontalBlock"]:has(.st-key-month_block1_view) {gap:.4rem .7rem;align-items:center;flex-wrap:wrap;}\ndiv[data-testid="stHorizontalBlock"]:has(.st-key-month_block1_view) > div[data-testid="stColumn"] {flex:0 0 auto;width:auto;min-width:0;}\ndiv[data-testid="stHorizontalBlock"]:has(.st-key-month_block1_view) > div[data-testid="stColumn"]:first-child {flex:1 0 auto;min-width:max-content;}\n.st-key-month_block1_editor {display:none;}\n#mfh{border-collapse:collapse;font-size:12.5px;color:#1F2A44;margin:.2rem 0 .5rem 0}\n#mfh th,#mfh td{padding:3px 10px;border:1px solid #E1E7ED;white-space:nowrap;text-align:left}\n#mfh th{background:#F3F6FA} #mfh td.t{font-family:Consolas,"Courier New",monospace}\n.mb1-head {display:flex;flex-wrap:wrap;gap:.2rem 1rem;align-items:center;padding:5px 12px;border-radius:8px;margin:0 0 .4rem 0;background:#F3F7FC;border:1px solid #D9E4F0;color:#1F2A44;position:relative;}\n.mb1-head.st-OPEN {border-left:4px solid #4A78C2;} .mb1-head.st-CLOSED {border-left:4px solid #4B9B67;} .mb1-head.st-FUTURE {border-left:4px solid #AAB4C3;}\n.mb1-head .h-title {font-size:1.15rem;font-weight:700;} .mb1-head .h-item {font-size:.86rem;color:#485468;} .mb1-head .h-item b {color:#1F2A44;}\n.mb1-head .h-legend {margin-left:auto;font-size:.76rem;color:#7A8597;white-space:nowrap;}\n.mb1-chip {display:inline-block;padding:0 8px;border-radius:999px;font-size:.72rem;font-weight:700;letter-spacing:.03em;border:1px solid #C9D3DE;background:#fff;color:#3D4A5F;white-space:nowrap;}\n.mb1-chip.st-OPEN {background:#E3EEFB;border-color:#4A78C2;color:#2C5596;} .mb1-chip.st-CLOSED {background:#E4F3E9;border-color:#4B9B67;color:#2C6B43;}\n.mb1-chip.st-FUTURE {background:#F1F2F4;border-color:#B8BEC8;color:#5B6573;} .mb1-chip.warn {background:#FFF3DC;border-color:#E3B25A;color:#8A5600;}\n.mb1-chip.mute {background:#F1F2F4;border-color:#CBD2DB;color:#5B6573;}\n.mb1-alert {padding:6px 12px;border-radius:8px;margin:0 0 .4rem 0;background:#FFF6E3;border:1px solid #EBCB8B;color:#6F4700;font-size:.88rem;line-height:1.4;}\n.mb1-alert b {color:#5A3900;} .mb1-quiet {font-size:.82rem;color:#677386;margin:0 0 .35rem 0;}\n.mb1-band {display:grid;background:#fff;border:1px solid #D8E0E8;border-radius:8px;margin:0 0 .4rem 0;}\n.mb1-band.kpi {grid-template-columns:1.15fr 1.15fr .55fr 1.35fr;} .mb1-band.ads {grid-template-columns:1.4fr 1fr 1fr 1fr .8fr 1fr .8fr;}\n.mb1-band .b-cell {padding:5px 12px 6px 12px;min-width:0;border-left:1px solid #E7ECF2;} .mb1-band .b-cell:first-child {border-left:none;}\n.mb1-band .b-cell.drr {background:#FAF9F6;} .mb1-band .b-cell.drr.first {border-left:2px solid #D5DCE5;}\n.b-label {font-size:.72rem;font-weight:700;color:#5B6779;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}\n.b-cell.orders .b-label {color:#3B68B0;} .b-cell.revenue .b-label {color:#3A8556;} .b-cell.buyout .b-label {color:#75629F;} .mb1-band.ads .b-cell.main .b-label {color:#9A6E2E;}\n.b-value {font-size:1.5rem;font-weight:700;color:#1F2A44;line-height:1.2;white-space:nowrap;} .b-value small {font-size:.9rem;font-weight:600;color:#5B6779;}\n.b-value.none {font-size:.95rem;font-weight:600;color:#8A93A0;white-space:normal;line-height:1.9;}\n.mb1-band.ads .b-value {font-size:1.12rem;line-height:1.3;} .mb1-band.ads .b-value small {font-size:.78rem;} .mb1-band.ads .b-cell.main .b-value {font-size:1.25rem;}\n.mb1-band.ads .b-value.none {font-size:.88rem;line-height:1.65;} .mb1-band.ads .b-cell.zero .b-value {color:#7A8597;}\n.b-sub {display:flex;flex-wrap:wrap;gap:0 .9rem;font-size:.78rem;color:#5B6779;line-height:1.35;white-space:nowrap;overflow:hidden;} .b-sub b {color:#1F2A44;font-weight:600;}\n.x-row {display:flex;align-items:baseline;gap:.5rem;font-size:.8rem;color:#5B6779;line-height:1.3;white-space:nowrap;}\n.x-row .x-name {font-weight:600;color:#1F2A44;min-width:4.1rem;} .x-row .x-pct {font-size:1.02rem;font-weight:700;color:#1F2A44;} .x-row .x-pct.none {font-size:.8rem;font-weight:600;color:#8A93A0;}\n.x-row .x-rest {margin-left:auto;}\n.x-track {height:6px;border-radius:4px;background:#E6EBF1;overflow:hidden;margin:1px 0 4px 0;} .x-fill {height:6px;border-radius:4px;}\n.x-fill.orders {background:linear-gradient(90deg,#6C93D3,#4A78C2);} .x-fill.revenue {background:linear-gradient(90deg,#6FB487,#4B9B67);}\n.mb1-more {grid-column:1 / -1;border-top:1px solid #E7ECF2;padding:1px 12px 2px 12px;font-size:.82rem;color:#485468;}\n.mb1-more summary {cursor:pointer;color:#2C5596;font-weight:600;font-size:.78rem;} .mb1-more .more-body {padding:.3rem 0 .3rem 0;line-height:1.5;}\n.mb1-more .more-row {display:flex;flex-wrap:wrap;gap:.1rem .9rem;padding:2px 0;border-top:1px dashed #E6EBF1;} .mb1-more .more-row:first-child {border-top:none;}\n.mb1-more .more-row .r-name {min-width:230px;font-weight:600;color:#1F2A44;} .mb1-more .more-row b {color:#1F2A44;font-weight:600;white-space:nowrap;}\n.mb1-more .more-note {margin-top:.35rem;color:#677386;font-size:.8rem;}\n.mb1-cmp {display:flex;flex-wrap:wrap;gap:.1rem 1.5rem;align-items:baseline;font-size:.82rem;color:#485468;margin:0 0 .1rem 0;position:relative;}\n.mb1-cmp .c-name {font-weight:700;color:#1F2A44;} .mb1-cmp b {color:#1F2A44;white-space:nowrap;}\n.mb1-sk-title {display:flex;align-items:center;gap:.45rem;font-size:1.12rem;font-weight:700;color:#1F2A44;margin:0;white-space:nowrap;position:relative;}\n.mb1-hint {display:inline-block;font-weight:400;line-height:1;}\n.mb1-hint > summary {list-style:none;cursor:pointer;font-size:1.02rem;color:#4A78C2;padding:0 2px;border-radius:50%;user-select:none;}\n.mb1-hint > summary::-webkit-details-marker {display:none;} .mb1-hint > summary:hover, .mb1-hint[open] > summary {color:#1F5FBF;background:#E3EEFB;}\n.mb1-hint .hint-body {position:absolute;left:0;top:calc(100% + 4px);z-index:60;width:min(600px,calc(100vw - 7rem));padding:9px 14px 10px 14px;border:1px solid #C9D3DE;border-radius:8px;\n  background:#fff;box-shadow:0 8px 24px rgba(31,42,68,.18);font-size:.8rem;line-height:1.5;color:#3D4A5F;white-space:normal;}\n.mb1-hint .hint-body b {color:#1F2A44;} .mb1-hint .hint-head {font-weight:700;color:#1F2A44;margin:.35rem 0 .1rem 0;} .mb1-hint .hint-head:first-child {margin-top:0;}\n.mb1-hint .hint-body .mb1-legend {display:block;margin:0;} .mb1-hint .hint-body .mb1-legend > span {display:block;}\n.mb1-cmp .mb1-chip {cursor:help;}\n.mb1-hint.chip > summary {font-size:.72rem;font-weight:700;letter-spacing:.03em;padding:0 8px;border-radius:999px;border:1px solid #CBD2DB;background:#F1F2F4;\n  color:#5B6573;white-space:nowrap;line-height:1.5;}\n.mb1-hint.chip > summary:hover, .mb1-hint.chip[open] > summary {background:#E3EEFB;border-color:#4A78C2;color:#2C5596;}\n.mb1-head .mb1-hint .hint-body, .mb1-cmp .mb1-hint .hint-body {width:min(520px,calc(100vw - 7rem));font-weight:400;}\n.mb1-alert {cursor:help;}\n.mb1-legend {display:flex;flex-wrap:wrap;gap:.2rem 1.1rem;font-size:.78rem;color:#536174;margin:0 0 .3rem 0;}\n.mb1-legend .sw {display:inline-block;width:20px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px;border:1px solid rgba(31,42,68,.12);}\n.mb1-legend .sw.fc {background-image:repeating-linear-gradient(135deg,rgba(140,150,165,.35) 0 4px,#fff 4px 8px);}\n.mb1-legend i {color:#7A8597;}\n.mb1-list {font-size:.88rem;color:#3D4A5F;line-height:1.5;margin:.1rem 0 .2rem 1.1rem;} .mb1-list b {color:#1F2A44;}\n.mb1-empty {padding:16px 16px;border-radius:10px;border:1px dashed #C3CDD8;background:#FAFBFD;color:#485468;font-size:.98rem;line-height:1.5;margin:.2rem 0 1rem 0;}\n.mb1-empty b {color:#1F2A44;}\n@media (max-width:1150px) {.mb1-band.kpi {grid-template-columns:1fr 1fr;} .mb1-band.ads {grid-template-columns:repeat(4,1fr);} .mb1-band .b-cell {border-top:1px solid #E7ECF2;}}\n</style>'

GROUP_TINT = {"Текущий": "#EAF1FB", "Сравнение": "#F4F5F7", "Изменение": "#FBF5E8", "Остаток": "#EEF7F0"}

CSS = PAGE_CSS + """<style>
.prm-band {display:grid;grid-template-columns:repeat(5,minmax(0,1fr));background:#fff;border:1px solid #D8E0E8;border-radius:8px;margin:0 0 .45rem 0;}
.prm-band .b-cell {padding:5px 12px 6px 12px;min-width:0;border-left:1px solid #E7ECF2;border-top:1px solid #E7ECF2;}
.prm-band .b-cell:nth-child(5n+1) {border-left:none;} .prm-band .b-cell:nth-child(-n+5) {border-top:none;}
.prm-band .b-value {font-size:1.18rem;} .prm-band .b-cell.derived .b-label {color:#75629F;} .prm-band .b-cell.main .b-label {color:#9A6E2E;}
.prm-band .b-cell.main .b-value {font-size:1.32rem;}
.prm-sub {font-size:.76rem;color:#5B6779;line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.prm-sub b {color:#1F2A44;font-weight:600;} .prm-sub .pos {color:#1E7A41;} .prm-sub .neg {color:#B3261E;}
.prm-title {display:flex;align-items:baseline;gap:.6rem;font-size:1.05rem;font-weight:700;color:#1F2A44;margin:.8rem 0 .2rem 0;}
.prm-title small {font-size:12px;font-weight:400;color:#5B6779;}
.prm-wrap {overflow:auto;max-height:520px;border:1px solid #C9D3DE;border-radius:8px;margin-bottom:.35rem;}
table.prm {border-collapse:separate;border-spacing:0;width:max-content;font-size:12.5px;line-height:1.25;margin:0;color:#1F2A44;}
table.prm th, table.prm td {padding:4px 9px;border-right:1px solid #E3E8EE;border-bottom:1px solid #E3E8EE;white-space:nowrap;}
table.prm thead th {position:sticky;z-index:2;text-align:center;font-weight:700;background:#EEF2F7;}
table.prm thead tr.grp th {top:0;height:24px;box-sizing:border-box;font-size:12px;}
table.prm thead tr.col th {top:24px;font-size:12px;font-weight:600;color:#3D4A5F;border-bottom:2px solid rgba(31,42,68,.22);}
table.prm td {text-align:right;} table.prm td.t {text-align:left;max-width:280px;overflow:hidden;text-overflow:ellipsis;}
table.prm td.first, table.prm th.first {position:sticky;left:0;z-index:1;background:#fff;border-right:2px solid #AEBBC9;text-align:left;font-weight:600;}
table.prm thead th.first {z-index:4;background:#EEF2F7;}
table.prm td.none {color:#B4BAC4;} table.prm td.pos {color:#1E7A41;} table.prm td.neg {color:#B3261E;}
table.prm tr.top td {background-image:linear-gradient(90deg,rgba(227,178,90,.10),rgba(227,178,90,0));}
table.prm tr.lvl0 td {background:#EEF3FA;font-weight:700;} table.prm tr.lvl1 td {font-weight:600;background:#F8FAFD;}
table.prm tr.lvl0 td.first {background:#E3EBF6;} table.prm tr.lvl1 td.first {background:#F1F5FA;}
table.prm thead th[title] {cursor:help;} table.prm td[title] {cursor:help;}
.prm-note {font-size:12px;color:#5B6779;margin:.1rem 0 .4rem 0;white-space:normal;} .prm-note b {color:#1F2A44;}
.prm-note .w {color:#8A5600;background:#FFF3DC;border-radius:4px;padding:0 5px;}
.prm-legend {font-size:.76rem;color:#677386;margin:0 0 .35rem 0;}
.prm-legend .k {display:inline-block;padding:0 6px;border-radius:999px;border:1px solid #CBD2DB;margin-right:4px;font-weight:700;font-size:.68rem;}
.prm-legend .k.fact {border-color:#4B9B67;color:#2C6B43;background:#E4F3E9;} .prm-legend .k.derived {border-color:#8C7BB8;color:#5B4A8F;background:#EFEAF8;}
.prm-cov {border-collapse:collapse;font-size:12px;color:#1F2A44;margin:.2rem 0 .5rem 0;}
.prm-cov th, .prm-cov td {padding:3px 9px;border:1px solid #E1E7ED;text-align:left;white-space:nowrap;} .prm-cov th {background:#F3F6FA;}
.prm-cov td.OK {color:#2C6B43;font-weight:700;} .prm-cov td.bad {color:#A32417;font-weight:700;}
.prm-next {padding:14px 16px;border-radius:10px;border:1px dashed #C3CDD8;background:#FAFBFD;color:#485468;font-size:.95rem;line-height:1.5;}
@media (max-width:1150px) {.prm-band {grid-template-columns:repeat(2,minmax(0,1fr));}}
/* C02: the efficiency colours of the dynamics, the compact O'STIN band, the chart, the empty states, the decision panel */
table.prm td.good {color:#1E7A41;} table.prm td.bad {color:#B3261E;} table.prm td.neu {color:#6B7685;}
table.prm {font-size:13px;} table.prm th, table.prm td {padding:5px 10px;}
#prm-r8_summary, #prm-r8_collection, #prm-r8_gender, #prm-r8_cm, #prm-r8_sku, #prm-queue {min-width:100%;}   /* C02: the main tables use the whole width */
.prm-band.ov {grid-template-columns:repeat(8,minmax(0,1fr));} .prm-band.ov .b-cell:nth-child(5n+1) {border-left:1px solid #E7ECF2;}
.prm-band.ov .b-cell:nth-child(8n+1) {border-left:none;} .prm-band.ov .b-cell:nth-child(-n+8) {border-top:none;} .prm-band.ov .b-value {font-size:1.08rem;}
.prm-cmp {display:inline-block;font-size:12.5px;color:#8A5600;background:#FFF3DC;border:1px solid #F0D9A8;border-radius:6px;padding:3px 9px;margin:.15rem 0 .35rem 0;}
.prm-ok {display:inline-block;font-size:12.5px;color:#2C6B43;background:#E9F5EE;border:1px solid #BFE0CB;border-radius:6px;padding:3px 9px;margin:.15rem 0 .35rem 0;}
.prm-empty {font-size:13px;color:#485468;background:#F7F9FC;border:1px dashed #C9D3DE;border-radius:8px;padding:8px 12px;margin:.2rem 0 .5rem 0;}
.prm-h2 {font-size:1.12rem;font-weight:700;color:#1F2A44;margin:1.0rem 0 .25rem 0;padding-top:.35rem;border-top:1px solid #E3E8EE;}
.prm-h2 small {font-size:12.5px;font-weight:400;color:#5B6779;margin-left:.5rem;}
.prm-chart {border:1px solid #D8E0E8;border-radius:8px;background:#fff;padding:6px 10px 2px 10px;margin:.2rem 0 .5rem 0;}
.prm-chart .bars {display:flex;align-items:flex-end;gap:14px;height:160px;padding:2px 6px 0 6px;}
.prm-chart .bar {flex:1 1 0;max-width:140px;min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;}
.prm-chart .b {width:64%;border-radius:4px 4px 0 0;} .prm-chart .b.full {background:#5B7DB8;} .prm-chart .b.part {background:#B7C6E0;}
.prm-chart .v {font-size:11.5px;color:#1F2A44;margin-bottom:2px;white-space:nowrap;} .prm-chart .l {font-size:11.5px;color:#5B6779;margin-top:3px;white-space:nowrap;}
.prq {display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;margin:.2rem 0 .4rem 0;}
.prq .c {border:1px solid #D8E0E8;border-radius:8px;background:#fff;padding:6px 10px;} .prq .c .l {font-size:.74rem;color:#5B6779;}
.prq .c .v {font-size:1.3rem;font-weight:700;color:#1F2A44;} .prq .c .s {font-size:.72rem;color:#6B7685;line-height:1.3;}
.prq .c.stop .v {color:#B3261E;} .prq .c.go .v {color:#1E7A41;} .prq .c.lim .v {color:#8A5600;} .prq .c.chk .v {color:#3D5A99;}
.prq .c.on {border:2px solid #1F2A44;}
.prf {display:flex;flex-wrap:wrap;gap:4px;align-items:center;font-size:12.5px;color:#3D4A5F;margin:.1rem 0 .45rem 0;}
.prf .st {background:#F1F4F8;border-radius:5px;padding:2px 7px;} .prf .st b {color:#1F2A44;} .prf .ar {color:#9AA6B6;} .prf .st.ok {background:#E4F3E9;}
.prf .st.cut {background:#FBECEA;}
/* C04: values and dynamics stacked - the sub-headings; every R8 table (values, dynamics, media) uses the whole width */
.prm-subh {display:flex;align-items:baseline;flex-wrap:wrap;gap:.2rem .6rem;font-size:.95rem;font-weight:700;color:#1F2A44;margin:.55rem 0 .2rem 0;}
.prm-subh small {font-size:12.5px;font-weight:400;color:#5B6779;}
[id^="prm-r8_"] {min-width:100%;}
.prm-daychart .pair {display:flex;align-items:flex-end;gap:3px;width:70%;justify-content:center;height:112px;}
.prm-daychart .pair .b {width:46%;}
@media (max-width:1150px) {.prm-band.ov {grid-template-columns:repeat(4,minmax(0,1fr));} .prq {grid-template-columns:repeat(4,minmax(0,1fr));}}
</style>"""

STATE_CHIP = {"OPEN": ("st-OPEN", "идёт"), "CLOSED": ("st-CLOSED", "закрыт"), "PARTIAL": ("warn", "не вся неделя"), "CUSTOM": ("mute", "произвольный")}

def _tip(text: str) -> str:
    return f' title="{escape(text)}"' if text else ""

def _kpi_cell(k: dict, main: bool = False, missing: str = "") -> str:
    classes = ["b-cell"] + (["main"] if main else []) + (["derived"] if k["nature"] == "DERIVED" else [])
    value = (f'<div class="b-value">{escape(k["cur_text"])}</div>' if k["cur"] is not None
             else f'<div class="b-value none">—</div>')
    delta_class = "" if k["delta"] in (None, 0) else ("pos" if k["delta"] > 0 else "neg")
    sub = (f'<div class="prm-sub">было <b>{escape(k["prev_text"])}</b> · Δ <b class="{delta_class}">{escape(k["delta_text"])}</b>'
           + (f' (<span class="{delta_class}">{escape(k["relative_text"])}</span>)' if k["relative"] is not None else "") + '</div>')
    hint = " · ".join(part for part in (k["nature"], k["note"], missing) if part)
    return f'<div class="{" ".join(classes)}"{_tip(hint)}><div class="b-label">{escape(k["title"])}</div>{value}{sub}</div>'

def table_html(table: dict, *, highlight: int = 0, max_height: int = 520) -> str:
    columns, rows = table["columns"], table["rows"]
    groups, head_groups = [], []
    for column in columns:
        group = column.get("group", "")
        if groups and groups[-1][0] == group:
            groups[-1][1] += 1
        else:
            groups.append([group, 1])
    for position, (group, span) in enumerate(groups):
        tint = f' style="background:{GROUP_TINT[group]}"' if group in GROUP_TINT else ""
        head_groups.append(f'<th colspan="{span}"{tint}{" class=" + chr(34) + "first" + chr(34) if position == 0 else ""}>{escape(group)}</th>')
    head = "".join(f'<th{" class=" + chr(34) + "first" + chr(34) if i == 0 else ""}{_tip(c.get("help", ""))}>{escape(c["title"])}</th>' for i, c in enumerate(columns))
    body = []
    for index, row in enumerate(rows):
        cells = []
        for i, column in enumerate(columns):
            value = row["cells"][column["key"]]
            classes = ["first"] if i == 0 else []
            if value["kind"] == "text":
                classes.append("t")
            if value["value"] is None and value["kind"] != "text":
                classes.append("none")
            elif value.get("tone"):                                # C02: the colour of the efficiency, not of the sign (core.promotion_dynamics)
                classes.append(value["tone"])
            elif value["kind"].endswith("_delta") or value["kind"] in ("relative", "pp"):
                if value["value"] not in (None, 0):
                    classes.append("pos" if value["value"] > 0 else "neg")
            tip = _tip(value["text"]) if value["kind"] == "text" and len(value["text"]) > 40 else ""
            if value.get("note"):                                  # R8: the reason of a value (or of «—») in the tooltip
                tip = _tip((value["text"] + " — " if value["kind"] == "text" else "") + value["note"])
            cells.append(f'<td class="{" ".join(classes)}" data-cell="{escape(table["id"])}|{escape(str(row["key"]))}|{column["key"]}"{tip}>{escape(value["text"])}</td>')
        level = f' lvl{row["level"]}' if row.get("level") is not None and row["level"] < 2 else ""
        body.append(f'<tr class="{"top" if index < highlight else ""}{level}">{"".join(cells)}</tr>')
    if not rows:
        body.append(f'<tr><td class="t none" colspan="{len(columns)}">нет строк</td></tr>')
    return (f'<div class="prm-wrap" style="max-height:{max_height}px"><table class="prm" id="prm-{escape(table["id"])}"><thead>'
            f'<tr class="grp">{"".join(head_groups)}</tr><tr class="col">{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')

def sub(title: str, note: str = "") -> str:
    """C04: the heading of one of the stacked tables («Значения» / «Динамика» / A-D of the media) with what it compares."""
    return f'<div class="prm-subh">{escape(title)}{f"<small>{escape(note)}</small>" if note else ""}</div>'

def h2(title: str, note: str = "") -> str:
    return f'<div class="prm-h2">{escape(title)}{f"<small>{escape(note)}</small>" if note else ""}</div>'

OV_KEYS = ("total_ads", "media", "other", "orders_total_rub", "revenue", "drr_total", "share_ad_orders")

NEXT_RELEASE = {
    "causes": "«Разбор причин» — следующий релиз: гипотезы изменений по иерархии Гендер → Коллекция → Тип → ЦМ → SKU → Кампания с явными подтверждающими фактами. "
              "В MVP 1 не реализован; показатели здесь не имитируются.",
    "decisions": "«Решения и ЦУ» — следующий релиз: рекомендации (усилить / оставить / сократить / остановить / возобновить при остатке / проверить) "
                 "после сверки действующих правил рекламы с владельцем. В MVP 1 не реализован.",
    "control": "«Контроль результата» — последующий этап: история выданных ЦУ и проверка изменений через 1, 3 и 7 дней. В MVP 1 не реализован.",
}