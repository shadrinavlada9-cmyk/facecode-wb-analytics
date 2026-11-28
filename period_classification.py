"""Read-side weekly classification views; accepted facts and business formulas stay shared."""
from copy import copy
from collections import defaultdict
from datetime import date

CONTEXT_KEY='_classification_context'

def reject_conflicted_payload(payload,context):
    import re
    policy=context.get('brand_conflicts',{'items':[]})
    norm=lambda x:re.sub(r'[^A-ZА-Я0-9]','',str(x or '').upper())
    blocked={norm(i['nm_id']) for i in policy['items']}|{norm(k) for i in policy['items'] for k in i['keys']}
    def walk(x):
        if isinstance(x,dict):
            return any(norm(k) in blocked or walk(v) for k,v in x.items())
        if isinstance(x,(list,tuple)):return any(walk(v) for v in x)
        return norm(x) in blocked
    if walk(payload):raise ValueError('BRAND CONFLICT / NOT VERIFIED: publication contains disputed fact identity')

def validate(context):
    if context is None:return
    if not isinstance(context,dict) or set(context) not in ({'format','cutover','history','weeks'},{'format','cutover','history','weeks','brand_conflicts'}) or context['format']!=1:
        raise ValueError('Некорректная версия классификации по неделям')
    if 'brand_conflicts' in context:
        policy=context['brand_conflicts']
        if policy.get('status')!='BRAND CONFLICT / NOT VERIFIED' or not isinstance(policy.get('items'),list):raise ValueError('Invalid isolated brand conflict')
        blocked={str(x['nm_id']) for x in policy['items']}
        if any(blocked.intersection(item.get('nm_ids',[])) for e in context['weeks'] for item in e['catalog'].values()):raise ValueError('Brand conflict entered confirmed catalog')
    date.fromisoformat(context['cutover'])
    history=context['history']
    required={'fact_end','stock_end','mapping_published','catalog_local','catalog_published','sources_local','sources_published'}
    if set(history)!=required:raise ValueError('Неполная историческая версия классификации')
    date.fromisoformat(history['fact_end']);date.fromisoformat(history['stock_end'])
    previous=None
    for epoch in context['weeks']:
        if set(epoch)!={'from','through','mapping','catalog','qa'}:raise ValueError('Неполная недельная классификация')
        start=date.fromisoformat(epoch['from']);end=date.fromisoformat(epoch['through'])
        if start.weekday()!=0 or (end-start).days!=6 or epoch['from']<context['cutover'] or (previous and epoch['from']<=previous):
            raise ValueError('Пересекающиеся или некорректные недели классификации')
        previous=epoch['through']
        if not isinstance(epoch['mapping'],dict) or any(not isinstance(v,list) or len(v)!=3 or not all(isinstance(x,str) for x in v) for v in epoch['mapping'].values()):
            raise ValueError('Некорректные справочные признаки')
        for item in epoch['catalog'].values():
            if not isinstance(item,dict) or set(item)!={'nm_ids','cm','gender2','collection_original'}:
                raise ValueError('Некорректный каталог nmID')
            if any(not isinstance(v,list) or not all(isinstance(x,str) for x in v) or len(v)!=len(set(v)) for v in item.values()):
                raise ValueError('Дубли или некорректные ключи nmID')

def view(model,a,b=None):
    context=getattr(model,'classification_context',None)
    if not context:return model
    # An old displayed week also keeps its accepted stock/H7/catalog context.
    display=getattr(model,'_display_start',a)
    effective=min(display,a)
    if getattr(model,'_view_start',None)==effective:return model
    epoch=next((e for e in context['weeks'] if e['from']<=effective<=e['through']),None)
    result=copy(model);result._view_start=effective;result._display_start=display
    published=getattr(model,'_published_model',False)
    legacy_mapping=getattr(model,'_legacy_mapping',model.mapping)
    legacy_qa=getattr(model,'_legacy_source_qa',model.source_qa)
    result._legacy_mapping=legacy_mapping;result._legacy_source_qa=legacy_qa
    history=context['history']
    if epoch:
        from fc_format import GENDER
        result.mapping={art:(v[0],GENDER.get(v[1],v[1]),v[2]) for art,v in epoch['mapping'].items()}
    else:result.mapping=history['mapping_published'] if published else legacy_mapping
    result.source_qa=epoch['qa'] if epoch else legacy_qa
    detail=dict(getattr(model,'wb_detail',{}))
    detail['catalog']=epoch['catalog'] if epoch else history['catalog_published' if published else 'catalog_local']
    if not epoch:detail['source_snapshots']=history['sources_published' if published else 'sources_local']
    result.wb_detail=detail
    if effective<context['cutover']:
        fact_end,stock_end=history['fact_end'],history['stock_end']
        def retained(scope,metric):return scope[1]<=fact_end or (metric=='fbw_stock' and scope[0]==scope[1] and scope[0]<=stock_end)
        result.cover=defaultdict(set,{scope:{m for m in metrics if retained(scope,m)} for scope,metrics in model.cover.items()})
        result.values=defaultdict(dict,{key:values for key,values in model.values.items() if retained(*key)})
        if isinstance(model.stock,dict):result.stock={k:v for k,v in model.stock.items() if k[0]<=stock_end}
        else:result.stock={k for k in model.stock if k[0]<=stock_end}
        if hasattr(model,'sku_counts'):result.sku_counts={k:v for k,v in model.sku_counts.items() if k[0]<=stock_end}
        result.records=[r for r in model.records if (r.get('snapshot_date','')<=stock_end if r['kind'] in {'fbw_stock','fbs_stock'} else r.get('period_end',r.get('period_start',''))<=fact_end)]
        result.ad_rows=[r for r in model.ad_rows if r['Дата']<=fact_end]
        if hasattr(model,'layers'):result.layers={k:v for k,v in model.layers.items() if k[1]<=fact_end}
        if 'variants' in detail:detail['variants']=[row for row in detail['variants'] if row[0]<=stock_end]
    return result
