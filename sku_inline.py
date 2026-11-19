"""Project accepted metrics into child rows; no intake, allocation or publication."""
from copy import copy
from collections import defaultdict
from decimal import Decimal as D
from html import escape
from datetime import date,timedelta

import streamlit as st
import sku_data
import sku_view
import inline_tree as UI


def stock_through(model,period):
    end=(date.fromisoformat(period[0])+timedelta(days=6)).isoformat()
    return max((day for day,_ in model.stock if period[1]<=day<=end),default=period[1])


def filtered(model, articles, memo):
    selected=set(articles)
    scoped=copy(model)
    def get(a,b,metric,stock_through=None):
        key=a,b,metric,stock_through
        if key not in memo:
            memo[key]=model.get(a,b,metric,stock_through)
        values=memo[key]
        return {k:v for k,v in values.items() if k in selected} if values is not None else None
    scoped.get=get
    if isinstance(model.stock,dict):
        scoped.stock={k:{variant:qty for variant,qty in values.items() if variant[0] in selected}
                      for k,values in model.stock.items()}
    else:
        scoped.sku_counts={k:{a:q for a,q in values.items() if a in selected} for k,values in model.sku_counts.items()}
    return scoped


@st.cache_data(show_spinner=False,max_entries=96)
def group_rows(generation,period,prior,paths,allowed,campaign,_model):
    import week_adapter
    model=_model
    cards=[]
    for path in paths:
        cards.extend(sku_data.cards(model,period,path,lambda _:True,campaign,allowed))
    by_nm=defaultdict(list)
    for card in cards:
        by_nm[card[sku_data.NM] or ('unmatched',card[sku_data.SELLER])].append(card)
    memo={}
    result=[]
    for nm,items in by_nm.items():
        articles={a for item in items for a in item[sku_data.SELLER].split(', ')}
        scoped=filtered(model,articles,memo)
        adapted=week_adapter.read_scope(scoped,*period,prior,lambda p:tuple(p) in paths,stock_through(model,period))
        record=adapted[1][-1][0][()]
        # Published card facts explicitly distinguish an unobserved XWAY metric.
        record['week']['XWAY, ₽']=sum((r['Расход XWAY, ₽'] for r in items),D(0)) if all(r['Расход XWAY, ₽'] is not None for r in items) else None
        row=dict(items[0])
        for label in (*sku_data.LABELS.values(),sku_data.FBW,sku_data.FBS,'Заказы H7, шт.'):
            vals=[r[label] for r in items]
            row[label]=sum(vals,D(0)) if all(v is not None for v in vals) else None
        row[sku_data.SELLER]=', '.join(sorted(articles))
        if campaign is not None:
            row['WB ID кампании']=str(campaign)
        row['H7 по FBW, дней']=sku_data.divide(row[sku_data.FBW],row['Заказы H7, шт.'],7)
        result.append({'nm':str(nm) if isinstance(nm,str) else None,'card':row,'record':record,'articles':tuple(sorted(articles))})
    return result


def load(model,period,prior,paths,allowed=None,campaign=None):
    generation=tuple(sorted(model.wb_detail['source_snapshots'].items()))
    return group_rows(generation,tuple(period),tuple(prior),tuple(paths),tuple(allowed) if allowed is not None else None,campaign,model)


def register(key,book,model,items):
    cards=[r['card'] for r in items]
    st.session_state.setdefault('_wb_sku_exports',{})[key]={'book':book,'cards':cards,'variants':sku_data.variants(model,cards)}


def child_week(item,totals):
    import week_detail as detail
    row=dict(item['record']['week'])
    for numerator,label in detail.SHARES.items():
        row[label]=sku_data.divide(row.get(numerator),totals.get(numerator))
    return row


def tree_children(model,period,prior,paths,key,scope,book,kind,totals=None,metric=None,scheme=None,unit=None):
    out={}
    loaded=UI.requested(key,scope)
    for path in paths:
        if UI.node_id(path) not in loaded:
            continue
        items=load(model,period,prior,[path])
        register(key+UI.node_id(path),book,model,items)
        values=[]
        for item in items:
            if kind=='week':
                row=child_week(item,totals)
            elif kind=='dynamic':
                row=item['record']['dynamic'][metric]
            else:
                row=item['record']['stocks'].get((scheme,unit),{})
            values.append((item['nm'],row))
        out[path]=values
    return out,loaded


def week6(model,period,prior,matches,rows,columns):
    import week_adapter as adapter
    from wb_format import DIMENSION_LABELS,format_metric,format_percent
    from week_controls import DIMENSION_METRICS,_DIMENSION_DRR
    from fc_format import format_value
    key='week_table6_inline'
    paths=sku_data.paths(model,matches)
    scope=UI.scope_id(model,period,paths)
    loaded=UI.requested(key,scope)
    total=model.report(*period,adapter.METRICS,matches,stock_through(model,period))[()]
    header='<div class="wb-tree-row wb-tree-head">'+''.join('<span>'+escape(c)+'</span>' for c in columns)+'</div>'
    def line(label,values,tag='div',nm=False):
        cells=[]
        for column in columns[1:]:
            value=values.get(column)
            metric=DIMENSION_METRICS.get(column)
            text=format_percent(value) if metric in _DIMENSION_DRR else format_metric(metric,value) if metric else format_value(value,column)
            cells.append('<span>'+escape(text)+'</span>')
        return f'<{tag} class="wb-tree-row"'+(' data-nm="'+escape(label)+'"' if nm else '')+'><span>'+escape(label)+'</span>'+''.join(cells)+f'</{tag}>'
    body=[]
    for row in rows:
        label=row[columns[0]]
        if label=='ИТОГО':
            body.append(line(label,row));continue
        node=(label,)
        children=[]
        if UI.node_id(node) in loaded:
            selected=[p for p in paths if p[2]==label]
            items=load(model,period,prior,selected)
            register(key+label,'week',model,items)
            memo={}
            for item in items:
                scoped=filtered(model,item['articles'],memo)
                original=scoped.report(*period,adapter.METRICS,lambda _:True,stock_through(model,period))[()]
                values={DIMENSION_LABELS.get(k,k):v for k,v in adapter.metrics(original,total).items()}
                # The sparse card-level XWAY values take priority over inferred zero.
                for metric,label2 in (('xway_spend','Расход XWAY, ₽'),('ad_shows','РК показы'),('ad_clicks','РК клики')):
                    if label2 in values: values[label2]=item['card'].get(sku_data.LABELS[metric])
                children.append(line(item['nm'] or '—',values,nm=True))
        attr=UI.attributes(node,UI.node_id(node) in loaded)
        body.append(f'<details {attr}>'+line(label,row,'summary')+(''.join(children) or '<div class="pending">Показатели загружаются при раскрытии.</div>')+'</details>')
    from week_detail import INLINE_CSS
    html=f'<style>{INLINE_CSS}</style><div class="wb-tree" style="--wb-columns:{len(columns)-1}">{header}{"".join(body)}</div>'
    UI.mount(html,key,scope,loaded)


def attention(model,period,prior,matches,rows,articles,fields,section,key,css):
    from management import gender
    from fc_format import format_value
    paths=sku_data.paths(model,matches)
    nodes=[('advice',str(r.get('Объект')),str(r.get('WB ID кампании') or ''),str(r.get('Артикул WB') or '')) for r in rows]
    scope=UI.scope_id(model,period,paths,[list(n) for n in nodes])
    loaded=UI.requested(key,scope)
    body=[]
    for row,article,node in zip(rows,articles,nodes):
        children=[]
        if UI.node_id(node) in loaded:
            group=row.get('Группа') or ''
            selected=[p for p in paths if ' / '.join(gender(v) if i==1 else v for i,v in enumerate(p)).startswith(group)]
            allowed=None
            if row.get('Артикул продавца'):
                allowed=tuple(row['Артикул продавца'].split(', '))
            if row.get('Артикул WB'):
                allowed=tuple(a for a,info in model.wb_detail['catalog'].items() if str(row['Артикул WB']) in info['nm_ids'])
            items=load(model,period,prior,selected,allowed,str(row['WB ID кампании']) if row.get('WB ID кампании') else None)
            register(key+UI.node_id(node),'attention_'+section,model,items)
            for item in items:
                card=item['card'];rec=item['record'];week=rec['week'];orders=rec['dynamic']['Заказы, ₽'];ads=rec['dynamic']['Продвижение WB, ₽']
                values={'Заказы за период A, ₽':orders['За период'],'Заказы за период B, ₽':orders['Прошлая неделя'],
                        'Δ Заказы, ₽':orders['Изменение'],'Δ Заказы, %':orders['Изменение, %']*100 if orders['Изменение, %'] is not None else None,
                        'Δ Продвижение WB, ₽':ads['Изменение'],'ДРР WB к заказам, %':sku_data.divide(week['Продвижение WB, ₽'],week['Заказы, ₽'],100),
                        'FBW, шт.':card[sku_data.FBW],'Заказы за 7 дней, шт.':card['Заказы H7, шт.'],'H7 по FBW, дней':card['H7 по FBW, дней'],
                        'Расход XWAY, ₽':card['Расход XWAY, ₽'],'Рекламные заказы XWAY, ₽':card['Рекламные заказы XWAY, ₽'],
                        'ДРР XWAY, %':sku_data.divide(card['Расход XWAY, ₽'],card['Рекламные заказы XWAY, ₽'],100)}
                if row.get('Артикул WB') and str(row['Артикул WB'])==item['nm']:
                    values.update({k:row.get(k) for k in fields})
                cells=''.join('<span>'+escape(format_value(values.get(k),k))+(' %' if '%' in k and values.get(k) is not None else '')+'</span>' for k in fields)
                children.append('<div class="wb-tree-row" data-nm="'+escape(item['nm'] or '')+'"><span>'+escape(item['nm'] or '—')+'</span>'+cells+'</div>')
        header='<div class="wb-tree-row wb-tree-head"><span>Номер WB</span>'+''.join('<span>'+escape(k)+'</span>' for k in fields)+'</div>'
        child_html=f'<div class="wb-tree" style="--wb-columns:{len(fields)}">{header}{"".join(children)}</div>' if children else '<div class="pending">'+('Нет подтверждённых товаров.' if UI.node_id(node) in loaded else 'Показатели загружаются при раскрытии.')+'</div>'
        body.append('<details class="fc-att-item" '+UI.attributes(node,UI.node_id(node) in loaded)+'><summary>'+article+'</summary>'+child_html+'</details>')
    from week_detail import INLINE_CSS
    extra='<style>.fc-att-item[open]{grid-column:1/-1}.fc-att-item>summary{list-style:none;cursor:pointer}.fc-att-item>summary::-webkit-details-marker{display:none}.fc-att-item>summary:before{content:"▸";float:left;padding:10px 5px}.fc-att-item[open]>summary:before{content:"▾"}.fc-att-item>.wb-tree{margin-top:4px}</style>'
    UI.mount(css+'<style>'+INLINE_CSS+'</style>'+extra+'<div class="fc-att-grid">'+''.join(body)+'</div>',key,scope,loaded)
