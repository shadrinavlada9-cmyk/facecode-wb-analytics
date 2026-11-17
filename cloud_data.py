"""Read production data only after the server-side access gate."""
from hashlib import sha256
from time import monotonic

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from protected_store import (
    Denied, GitHubStore, Invalid, Unavailable, generation_path, latest, object_json, verify_pointer,
)

_CACHE = "_verified_generation"
DATA_REPOSITORY = "shadrinavlada9-cmyk/facecode-wb-data"
FIRST_GENERATION = "9534e857253c7adfa61439e4a31b03f47217e1856ca6dbc7b5afde1712c45367"
FIRST_GIT_BLOB = "545394a09b2bf7971f57aad7a5b4290df07a3cc8"


def _configured_store():
    try:
        settings = st.secrets["data"]
        repository, token = settings["repository"], settings["token"]
        if not isinstance(repository, str) or repository.casefold() != DATA_REPOSITORY:
            raise Denied
        store = GitHubStore(repository, token)
    except (KeyError, TypeError, StreamlitSecretNotFoundError):
        raise Denied from None
    fingerprint = sha256((repository.casefold() + "\0" + token).encode()).digest()
    return store, fingerprint


@st.cache_data(ttl=30, max_entries=2, show_spinner=False)
def _probe_source(fingerprint, _store):
    """Check the production token with Git metadata, without reading analytical rows."""
    try:
        _store.verify_private()
        pointer = verify_pointer(_store.read("current.json"))
        tree = object_json(_store.request("/git/trees/main?recursive=1"))
        if tree.get("truncated") is not False or not isinstance(tree.get("tree"), list):
            return "integrity"
        path = generation_path(pointer["current"])
        entry = next((row for row in tree["tree"] if row.get("path") == path and row.get("type") == "blob"), None)
        if not entry or not isinstance(entry.get("size"), int) or entry["size"] <= 0:
            return "integrity"
        if pointer["current"] == FIRST_GENERATION:
            return "initial-verified" if entry.get("sha") == FIRST_GIT_BLOB else "integrity"
        return "ready"
    except Denied:
        return "access"
    except Invalid:
        return "integrity"
    except Unavailable:
        return "unavailable"


def source_status():
    try:
        store, fingerprint = _configured_store()
    except Denied:
        return "configuration"
    return _probe_source(fingerprint, store)


def load_dataset():
    try:
        store, fingerprint = _configured_store()
    except Denied:
        st.session_state.pop(_CACHE, None)
        raise
    cached = st.session_state.get(_CACHE)
    if cached and cached[0] != fingerprint:
        st.session_state.pop(_CACHE, None)
        cached = None
    now = monotonic()
    if cached and now < cached[1] + 20:
        return cached[2], cached[3]
    try:
        payload, backup = latest(store)
    except Denied:
        st.session_state.pop(_CACHE, None)
        raise
    except (Unavailable, Invalid):
        if cached:
            st.session_state[_CACHE] = (fingerprint, now, cached[2], True)
            return cached[2], True
        raise
    st.session_state[_CACHE] = (fingerprint, now, payload, backup)
    return payload, backup
