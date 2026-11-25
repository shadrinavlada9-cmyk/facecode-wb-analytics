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
    names=('model.py','runtime_model.py','protected_store.py','release_contract.py')
    return {'format':1,'contract':CONTRACT,'payload_sha256':checksum(canonical(payload)),
        'reader_files':{name:checksum((public/name).read_bytes()) for name in names},
        'producer_files':{name:checksum((root/name).read_bytes()) for name in ('update.py','prepare_publish.py','accepted_state.py')},
        # Bind fact snapshots and registry, not mutable QA/journal metadata.
        # A QA-only adoption must not create a different generation at the same release time.
        'source_files':{name:source_hashes[name] for name in ('daily.json','weekly.json','finance_registry.json')}}
def verify(manifest,payload):
    value=manifest.get('controls',{}).get('_compatibility')
    if value is None:return 'LEGACY_COMPATIBLE'  # Current admitted schema-2 generation stays readable.
    if (not isinstance(value,dict) or set(value)!={'format','contract','payload_sha256','reader_files','producer_files','source_files'}
        or value['format']!=1 or value['contract']!=CONTRACT
        or value['payload_sha256']!=manifest['payload_sha256']
        or value['payload_sha256']!=checksum(canonical(payload))):
        raise ValueError('Несовместимая версия кода и данных')
    if set(value['reader_files'])!={'model.py','runtime_model.py','protected_store.py','release_contract.py'}:
        raise ValueError('Неполный контроль версии reader')
    if set(value['producer_files'])!={'update.py','prepare_publish.py','accepted_state.py'}:
        raise ValueError('Неполный контроль версии producer')
    allowed={'daily.json','weekly.json','finance_registry.json','classification_active.json','classification_previous.json',
             'qa_daily.json','qa_weekly.json','operations/last_daily.json','operations/last_weekly.json','operations/accepted_state.json'}
    if not set(value['source_files'])<=allowed or not {'daily.json','weekly.json','finance_registry.json'}<=set(value['source_files']):
        raise ValueError('Неполный контроль принятых данных')
    if any(not isinstance(v,str) or not HASH.fullmatch(v) for group in ('reader_files','producer_files','source_files') for v in value[group].values()):
        raise ValueError('Некорректная контрольная сумма версии')
    return 'COMPATIBLE'
def cache_namespace(directory):
    return CONTRACT+':'+checksum((Path(directory)/'model.py').read_bytes())
