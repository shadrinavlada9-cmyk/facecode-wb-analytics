"""Complete, deferred Excel projections, independent of browser expansion state."""
from collections import defaultdict
from copy import copy
from decimal import Decimal as D
import json

import streamlit as st
import sku_data as S
import sku_inline as I

NM='Номер WB'
LIMIT=1048573
DIMS=('Коллекция','Гендер','Тип товара')


def generation(model):
    return tuple(sorted(model.wb_detail['source_snapshots'].items()))


@st.cache_data(show_spinner=False,max_entries=12)
def bundle(revision,period,prior,paths,_model):
    """Run accepted report/read_scope once for all cards instead of per card."""
    import week_adapter as A
    model=_model; memo={};source=copy(model)
    def original(a,b,metric,through=None):
        key=a,b,metric,through
        if key not in memo:memo[key]=model.get(a,b,metric,through)
        return memo[key]
    source.get=original
    cards=[]
    for path in paths:
        cards.extend(S.cards(source,period,path,lambda _:True))
    by_uid={};article_uid={}
    for card in cards:
        uid=card[S.NM] or 'seller:'+card[S.SELLER]
        if uid in by_uid:
            raise ValueError('У карточки WB конфликт товарных разрезов. Выгрузка остановлена.')
        by_uid[uid]=card
        for article in card[S.SELLER].split(', '):article_uid[article]=uid
    batch=copy(model)
    batch.mapping={uid:('_WB',uid,'_') for uid in by_uid}
    grouped={}
    def get(a,b,metric,through=None):
        key=a,b,metric,through
        if key not in grouped:
            values=original(a,b,metric,through)
            if values is None:grouped[key]=None
            else:
                sums=defaultdict(D)
                for article,value in values.items():
                    if article in article_uid:sums[article_uid[article]]+=value
                # Match accepted path_values: zero only for a covered metric.
                for uid in by_uid:sums.setdefault(uid,D(0))
                grouped[key]=dict(sums)
        return grouped[key]
    batch.get=get
    if isinstance(model.stock,dict):
        batch.stock={key:{(article_uid[a],(a,size)):q for (a,size),q in values.items() if a in article_uid}
                     for key,values in model.stock.items()}
    else:
        batch.sku_counts={key:{uid:sum(q for a,q in values.items() if article_uid.get(a)==uid)
                              for uid in by_uid} for key,values in model.sku_counts.items()}
    adapted=A.read_scope(batch,*period,prior,lambda _:True,I.stock_through(model,period))
    records=adapted[1][-1][0]
    report=batch.report(*period,A.METRICS,lambda _:True,I.stock_through(model,period))
    total=model.report(*period,A.METRICS,lambda p:tuple(p) in paths,I.stock_through(model,period))[()]
    items=[]
    for uid,card in by_uid.items():
        rec=records[('_WB',uid,'_')]
        rec['week']['XWAY, ₽']=card['Расход XWAY, ₽']
        metrics=A.metrics(report[('_WB',uid,'_')],total)
        # TABLE 6 preserves the accepted screen's report and sparse overrides.
        # The flat card sheet retains its separately confirmed XWAY facts.
        from wb_format import DIMENSION_LABELS
        visible = {DIMENSION_LABELS.get(metric, metric) for metric in metrics}
        for metric, label in (('xway_spend', 'Расход XWAY, ₽'),
                              ('ad_shows', 'РК показы'), ('ad_clicks', 'РК клики')):
            if label in visible:
                metrics[metric] = card.get(S.LABELS[metric])
        items.append({'nm':card[S.NM],'card':card,'record':rec,'week6':metrics})
    return items


def load(model,period,prior,paths):
    return bundle(generation(model),tuple(period),tuple(prior),tuple(paths),model)


def path_of(item):return tuple(item['card'][k] for k in DIMS)


def dimensions(item):
    from management import gender
    return {**{k:gender(item['card'][k]) if k=='Гендер' else item['card'][k] for k in DIMS},NM:item['nm'] or '—'}


def missing_fbs(row):
    return {k:'—' if v is None and 'FBS' in k and ('шт' in k or k==S.FBS) else v for k,v in row.items()}


def flat(item,totals=None):
    card=item['card']
    row={**dimensions(item),**{k:v/100 if k.endswith('%') and v is not None else v for k,v in card.items() if k not in (*DIMS,S.NM)}}
    row.update(I.child_week({'record':item['record']},totals) if totals is not None else item['record']['week'])
    # Both names are retained: card-level XWAY is explicitly observed.
    row.pop('XWAY, ₽',None)
    row.pop('Дата остатков FBW/FBS',None)
    first=(*DIMS,NM,'Заказы, ₽','Заказы, шт.','Выручка, ₽','Выручка, шт.','Продвижение WB, ₽',
           'Расход XWAY, ₽',S.FBW,S.FBS,'Дата снимка','Статус FBS','H7 по FBW, дней')
    return missing_fbs({**{k:row[k] for k in first if k in row},**{k:v for k,v in row.items() if k not in first}})


def split(name,rows):
    return [(name if offset==0 else name[:24]+f' ч.{offset//LIMIT+1}',rows[offset:offset+LIMIT]) for offset in range(0,len(rows),LIMIT)] or [(name,[])]


def variant_sheets(model,items):
    from management import gender
    rows=[]
    for row in S.variants(model,[item['card'] for item in items]):
        rows.append({**{k:v for k,v in row.items() if k!=S.NM},NM:row[S.NM] or '—','Гендер':gender(row['Гендер'])})
    return split('Варианты WB',rows) if rows else []


def capture_table7(value):
    if not value:return []
    tables=[]
    for name,key in (('Артикулы WB','cards'),('Варианты WB','variants')):
        rows=[{k:v/100 if k.endswith('%') and v is not None else v for k,v in row.items()} for row in value[key]]
        if rows:tables.extend(split(name,rows))
    return tables


def bounded(tables,outlines):
    result=[];levels={}
    for name,rows in tables:
        for part,(title,chunk) in enumerate(split(name,rows)):
            result.append((title,chunk))
            if name in outlines:levels[title]=outlines[name][part*LIMIT:part*LIMIT+len(chunk)]
    return result,levels


def decorate(row,nm=None):
    out={}
    for key,value in row.items():
        out[key]=value
        if key=='Тип товара':out[NM]=nm
    if NM not in out:out={NM:nm,**out}
    return missing_fbs(out)


def detail_tables(model,period,prior,paths,records,calendar,analysis):
    import week_detail as W
    import week_adapter as A
    if not model.wb_detail["catalog"]:
        return W._excel_tables(records,calendar,analysis),{}
    items=load(model,period,prior,paths);by_path=defaultdict(list)
    for item in items:by_path[path_of(item)].append(item)
    # UI intentionally omits some zero-activity unknown groups. Excel must
    # still contain every confirmed card, with its accepted group aggregate.
    records=dict(records);memo={}
    for path in sorted({p[:depth] for p in by_path for depth in (1,2,3)}):
        if path in records:continue
        articles={a for p,rows in by_path.items() if p[:len(path)]==path for item in rows for a in item['card'][S.SELLER].split(', ')}
        scoped=I.filtered(model,articles,memo)
        record=A.read_scope(scoped,*period,prior,lambda p:tuple(p)[:len(path)]==path,I.stock_through(model,period))[1][-1][0][()]
        record['week']=I.child_week({'record':record},records[()]['week'])
        records[path]=record
    originals=W._excel_tables(records,calendar,analysis)
    tables=[];outlines={}
    for name,rows in originals:
        if name=='На что обратить внимание':
            expanded=[];levels=[]
            for parent in rows:
                expanded.append({**parent,NM:None});levels.append(0)
                raw={k:v*100 if k.endswith('%') and isinstance(v,(D,float,int)) else v for k,v in parent.items()}
                for item in matching_items(model,items,parent,period):
                    values=advice_values(item,raw,list(parent))
                    child={**{k:None for k in parent},**dimensions(item),'Раздел':parent.get('Раздел'),'Объект':item['nm'] or '—',
                           **{k:v/100 if k.endswith('%') and isinstance(v,(D,float,int)) else v for k,v in values.items()}}
                    child.update(dimensions(item));child['Объект']=item['nm'] or '—';child['Раздел']=parent.get('Раздел')
                    expanded.append(missing_fbs(child));levels.append(1)
            tables.append((name,expanded));outlines[name]=levels
            continue
        if name not in ('Недельные итоги','Заказы по дням','Остатки по дням','Детальные данные'):
            tables.append((name,rows));continue
        expanded=[];levels=[]
        for parent in rows:
            expanded.append(decorate(parent));level={'Итого':0,'Коллекция':1,'Гендер':2,'Тип товара':3}.get(parent.get('Уровень'),3);levels.append(level)
            if parent.get('Уровень')!='Тип товара':continue
            from management import gender
            group=next((p for p in by_path if p[0]==parent.get('Коллекция') and gender(p[1])==parent.get('Гендер') and p[2]==parent.get('Тип товара')),None)
            for item in by_path.get(group,[]):
                dims={**dimensions(item),'Уровень':'Номер WB'}
                if name=='Недельные итоги':
                    child={**dims,**I.child_week(item,records[()]['week'])}
                elif name=='Заказы по дням':
                    metric=parent['Показатель'];child={**dims,'Показатель':metric,**item['record']['dynamic'][metric]}
                elif name=='Остатки по дням':
                    child=dict(dims)
                    for (scheme,unit),series in item['record']['stocks'].items():
                        child.update(W._flatten(series,series,f'{W.SCHEMES[scheme]} {unit} · '))
                else:
                    child={**dims,**I.child_week(item,records[()]['week'])}
                    for metric,series in item['record']['dynamic'].items():child.update(W._flatten(calendar,series,metric+' · '))
                    for (scheme,unit),series in item['record']['stocks'].items():child.update(W._flatten(series,series,f'{W.SCHEMES[scheme]} {unit} · '))
                expanded.append(missing_fbs(child));levels.append(4)
        tables.append((name,expanded));outlines[name]=levels
    tables.extend(split('Артикулы WB',[flat(item,records[()]['week']) for item in items]))
    dynamic=[];stocks=[]
    for item in items:
        dims=dimensions(item)
        for metric,series in item['record']['dynamic'].items():dynamic.append({**dims,'Показатель':metric,**series})
        for (scheme,unit),series in item['record']['stocks'].items():stocks.append(missing_fbs({**dims,'Схема':W.SCHEMES[scheme],'Единица':unit,**series}))
    tables.extend(split('Динамика WB',dynamic));tables.extend(split('Запасы WB',stocks))
    tables.extend(variant_sheets(model,items))
    return tables,outlines


def detail_export(model,period,prior,paths,records,calendar,analysis,title,coverage):
    from week_detail import _excel
    tables,outlines=detail_tables(model,period,prior,paths,records,calendar,analysis)
    tables,outlines=bounded(tables,outlines)
    return _excel(tables,title,coverage,outlines=outlines)


def week_export(model,period,prior,paths,base_tables,title,coverage,table7_sheets=()):
    import week_detail as W
    import week_adapter as A
    from wb_format import DIMENSION_LABELS
    if not model.wb_detail["catalog"]:
        return W._excel(base_tables,title,coverage)
    items=load(model,period,prior,paths);by_type=defaultdict(list)
    for item in items:by_type[item['card']['Тип товара']].append(item)
    tables=[];outlines={}
    for name,rows in base_tables:
        if name!='TABLE 6':tables.append((name,rows));continue
        result=[];levels=[]
        for parent in rows:
            result.append({'Тип товара':parent.get('Тип товара'),NM:None,**{k:v for k,v in parent.items() if k!='Тип товара'}});levels.append(0 if parent.get('Тип товара')=='ИТОГО' else 3)
            if parent.get('Тип товара')=='ИТОГО':continue
            for item in by_type.get(parent['Тип товара'],[]):
                values={DIMENSION_LABELS.get(k,k):v for k,v in item['week6'].items()}
                result.append(missing_fbs({**{c:values.get(c) for c in parent},**dimensions(item)}));levels.append(4)
        tables.append((name,result));outlines[name]=levels
    tables.extend(split('Артикулы WB',[flat(item) for item in items]))
    report=model.report(*period,A.METRICS,lambda p:tuple(p) in paths,I.stock_through(model,period))
    hierarchy=[];levels=[];by_path=defaultdict(list)
    for item in items:by_path[path_of(item)].append(item)
    for path,values in sorted(report.items()):
        if path and path[0]=='Не распределено':continue
        row={**W._unpack(path),'Уровень':('Итого','Коллекция','Гендер','Тип товара')[len(path)],
             **{DIMENSION_LABELS.get(k,k):v for k,v in A.metrics(values,report[()]).items()}}
        hierarchy.append(decorate(row));levels.append(len(path))
        if len(path)==3:
            for item in by_path[path]:
                hierarchy.append(missing_fbs({**dimensions(item),'Уровень':'Номер WB',**{DIMENSION_LABELS.get(k,k):v for k,v in item['week6'].items()}}));levels.append(4)
    tables.append(('Иерархия TABLE 6',hierarchy));outlines['Иерархия TABLE 6']=levels
    tables.extend(variant_sheets(model,items))
    # Existing TABLE 7 selected-context sheets are captured without changes.
    for name,rows in table7_sheets:
        tables.append(('TABLE 7 · '+name,rows))
    tables,outlines=bounded(tables,outlines)
    return W._excel(tables,title,coverage,outlines=outlines)


def matching_items(model,items,parent,period=None):
    from management import gender
    group=parent.get('Группа') or ''
    nm=str(parent.get('Артикул WB') or '')
    seller=parent.get('Артикул продавца')
    allowed=None
    if parent.get('WB ID кампании') and not nm:
        linked={r['Артикул'] for r in model.ad_rows if str(r['Кампания'])==str(parent['WB ID кампании'])
                and (period is None or period[0]<=r['Дата']<=period[1])}
        allowed={nm for a in linked for nm in model.wb_detail['catalog'].get(a,{}).get('nm_ids',[])}
    return [item for item in items if (not group or ' / '.join(gender(v) if i==1 else v for i,v in enumerate(path_of(item))).startswith(group))
            and (not nm or item['nm']==nm) and (not seller or seller in item['card'][S.SELLER].split(', '))
            and (allowed is None or item['nm'] in allowed)]


def advice_values(item,parent,fields):
    card=item['card'];rec=item['record'];week=rec['week'];orders=rec['dynamic']['Заказы, ₽'];ads=rec['dynamic']['Продвижение WB, ₽']
    values={'Заказы за период A, ₽':orders['За период'],'Заказы за период B, ₽':orders['Прошлая неделя'],
            'Δ Заказы, ₽':orders['Изменение'],'Δ Заказы, %':orders['Изменение, %']*100 if orders['Изменение, %'] is not None else None,
            'Δ Продвижение WB, ₽':ads['Изменение'],'ДРР WB к заказам, %':S.divide(week['Продвижение WB, ₽'],week['Заказы, ₽'],100),
            'FBW, шт.':card[S.FBW],'Заказы за 7 дней, шт.':card['Заказы H7, шт.'],'H7 по FBW, дней':card['H7 по FBW, дней'],
            'Продвижение WB за период A, ₽':ads['За период'],'Продвижение WB за период B, ₽':ads['Прошлая неделя'],
            'Расход XWAY, ₽':card['Расход XWAY, ₽'],'Рекламные заказы XWAY, ₽':card['Рекламные заказы XWAY, ₽'],
            'ДРР XWAY, %':S.divide(card['Расход XWAY, ₽'],card['Рекламные заказы XWAY, ₽'],100)}
    if parent.get('Артикул WB') and str(parent['Артикул WB'])==item['nm']:
        values.update({k:parent.get(k) for k in fields})
    # Promotion writer retains accepted percentage-point values (0..100).
    return {k:values.get(k) for k in fields}


def attention_export(model,period,prior,paths,parents,section,metadata):
    from sku_view import frame
    from promotion_excel import excel
    if not model.wb_detail["catalog"]:
        return excel([(section,frame(parents))],metadata)
    items=load(model,period,prior,paths);selected={};expanded=[];levels=[];campaign_rows=[];campaigns=defaultdict(set)
    fields=list(dict.fromkeys(k for row in parents for k in row))
    for parent in parents:
        expanded.append({**parent,NM:None});levels.append(0)
        for item in matching_items(model,items,parent,period):
            selected[item['nm'] or item['card'][S.SELLER]]=item
            child={**{k:None for k in fields},**dimensions(item),'Объект':item['nm'] or '—',**advice_values(item,parent,fields),NM:item['nm'] or '—'}
            child.update(dimensions(item));child['Объект']=item['nm'] or '—'
            expanded.append(missing_fbs(child));levels.append(1)
            if parent.get('WB ID кампании'):
                campaigns[item['nm'] or item['card'][S.SELLER]].add(str(parent['WB ID кампании']))
                campaign_rows.append({**dimensions(item),**{k:parent.get(k) for k in fields if k not in ('Объект','Группа',S.SELLER,S.NM)},'Контекст':'Кампания'})
    flat_rows=[]
    for uid,item in selected.items():
        row=flat(item)
        if campaigns.get(uid):
            scoped=[]
            for cid in sorted(campaigns[uid]):
                scoped.extend(S.cards(model,period,path_of(item),lambda _:True,cid,tuple(item['card'][S.SELLER].split(', '))))
            row['WB ID кампаний']=', '.join(sorted(campaigns[uid]))
            for label in ('Продвижение WB, ₽','Расход XWAY, ₽','Рекламные заказы XWAY, ₽','Рекламные заказы XWAY, шт.','Показы XWAY','Клики XWAY','Корзины XWAY'):
                vals=[c[label] for c in scoped];row[label]=sum(vals,D(0)) if vals and all(v is not None for v in vals) else None
            row['ДРР XWAY, %']=S.divide(row['Расход XWAY, ₽'],row['Рекламные заказы XWAY, ₽'])
            row['ДРР WB, %']=S.divide(row['Продвижение WB, ₽'],row['Заказы, ₽'])
            row['CTR XWAY, %']=S.divide(row['Клики XWAY'],row['Показы XWAY'])
            row['CPC XWAY, ₽']=S.divide(row['Расход XWAY, ₽'],row['Клики XWAY'])
            row['Доля продвижения WB, %']=None
        flat_rows.append(row)
    sheets=[(section,frame(expanded))]
    sheets.extend((name,frame(rows)) for name,rows in split('Артикулы WB',flat_rows))
    sheets.extend((name,frame(rows)) for name,rows in variant_sheets(model,list(selected.values())))
    if campaign_rows:sheets.append(('Кампании WB',frame(campaign_rows)))
    return excel(sheets,metadata,outlines={section:levels})
