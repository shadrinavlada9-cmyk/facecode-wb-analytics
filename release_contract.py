"""Versioned computation contract in the existing controls envelope (schema stays 2)."""
from hashlib import sha256
from pathlib import Path
import json,re
CONTRACT='facecode-accepted-v1-fbs-unconfirmed'
HASH=re.compile(r'[0-9a-f]{64}\Z')
def canonical(value):return json.dumps(value,ensure_ascii=False,default=str,sort_keys=True,separators=(',',':')).encode('utf8')
def checksum(raw):return sha256(raw).hexdigest()
def metadata(payload,root,source_hashes):
    root=Path(root);public=root/'publication/github-demo'
    if (root/'period_classification.py').read_text(encoding='utf-8-sig')!=(public/'period_classification.py').read_text(encoding='utf-8-sig'):
        raise ValueError('Локальная и публичная версии недельной классификации различаются')
    names=('model.py','runtime_model.py','protected_store.py','release_contract.py','period_classification.py')
    return {'format':1,'contract':CONTRACT,'payload_sha256':checksum(canonical({k:v for k,v in payload.items() if k!='_classification_context'})),
        'reader_files':{name:checksum((public/name).read_bytes()) for name in names},
        'producer_files':{name:checksum((root/name).read_bytes()) for name in ('update.py','prepare_publish.py','accepted_state.py','classification.py','reference_refresh.py','brand_conflicts.py')},
        # Bind fact snapshots and registry, not mutable QA/journal metadata.
        # A QA-only adoption must not create a different generation at the same release time.
        'source_files':{name:source_hashes[name] for name in ('daily.json','weekly.json','finance_registry.json')}}
def verify(manifest,payload):
    value=manifest.get('controls',{}).get('_compatibility')
    scoped=manifest.get('controls',{}).get('_classification_context') is not None
    if value is None:
        if scoped:raise ValueError('Нет контроля версии недельной классификации')
        return 'LEGACY_COMPATIBLE'
    if (not isinstance(value,dict) or set(value)!={'format','contract','payload_sha256','reader_files','producer_files','source_files'}
        or value['format']!=1 or value['contract']!=CONTRACT
        or value['payload_sha256']!=manifest['payload_sha256']
        or value['payload_sha256']!=checksum(canonical(payload))):
        raise ValueError('Несовместимая версия кода и данных')
    if set(value['reader_files']) not in ({'model.py','runtime_model.py','protected_store.py','release_contract.py'}, {'model.py','runtime_model.py','protected_store.py','release_contract.py','period_classification.py'}):
        raise ValueError('Неполный контроль версии reader')
    if set(value['producer_files']) not in ({'update.py','prepare_publish.py','accepted_state.py'}, {'update.py','prepare_publish.py','accepted_state.py','classification.py','reference_refresh.py'}, {'update.py','prepare_publish.py','accepted_state.py','classification.py','reference_refresh.py','brand_conflicts.py'}):
        raise ValueError('Неполный контроль версии producer')
    if scoped and (set(value['reader_files'])!={'model.py','runtime_model.py','protected_store.py','release_contract.py','period_classification.py'} or set(value['producer_files']) not in ({'update.py','prepare_publish.py','accepted_state.py','classification.py','reference_refresh.py'},{'update.py','prepare_publish.py','accepted_state.py','classification.py','reference_refresh.py','brand_conflicts.py'})):
        raise ValueError('Неполный контроль версии недельной классификации')
    allowed={'daily.json','weekly.json','finance_registry.json','classification_active.json','classification_previous.json',
             'qa_daily.json','qa_weekly.json','operations/last_daily.json','operations/last_weekly.json','operations/accepted_state.json'}
    if not set(value['source_files'])<=allowed or not {'daily.json','weekly.json','finance_registry.json'}<=set(value['source_files']):
        raise ValueError('Неполный контроль принятых данных')
    if any(not isinstance(v,str) or not HASH.fullmatch(v) for group in ('reader_files','producer_files','source_files') for v in value[group].values()):
        raise ValueError('Некорректная контрольная сумма версии')
    return 'COMPATIBLE'
def cache_namespace(directory):
    directory=Path(directory)
    names=('model.py','runtime_model.py','period_classification.py','protected_store.py','release_contract.py','runtime_bootstrap.py')
    return CONTRACT+':'+checksum(canonical({n:checksum((directory/n).read_bytes()) for n in names if (directory/n).is_file()}))
