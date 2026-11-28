"""Refresh app-owned imports once per installed release, before the access/data gates."""
from pathlib import Path
from hashlib import sha256
from threading import RLock
import importlib,json,sys

_lock=RLock()
_versions={}

def ensure_runtime(directory):
    root=Path(directory).resolve()
    # File content is used, not timestamps or the already imported classes.
    files=sorted(root.glob('*.py'))
    fingerprint=sha256(json.dumps({p.name:sha256(p.read_bytes()).hexdigest() for p in files},sort_keys=True).encode()).hexdigest()
    key=str(root)
    with _lock:
        if _versions.get(key)==fingerprint:return fingerprint
        stale=[]
        for name,module in tuple(sys.modules.items()):
            if name in {'__main__',__name__}:continue
            filename=getattr(module,'__file__',None)
            if filename:
                try:owned=Path(filename).resolve().parent==root
                except (OSError,TypeError,ValueError):owned=False
                if owned:stale.append(name)
        for name in stale:sys.modules.pop(name,None)
        importlib.invalidate_caches()
        _versions[key]=fingerprint
        return fingerprint
