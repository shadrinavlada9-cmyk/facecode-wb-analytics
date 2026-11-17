"""Choose a dataset only after the server-side access gate."""
from hashlib import sha256
import json
from pathlib import Path
from time import monotonic

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from protected_store import Denied, GitHubStore, Invalid, Unavailable, latest

_CACHE = "_verified_generation"


def load_dataset():
    try:
        settings = st.secrets.get("data")
    except StreamlitSecretNotFoundError:
        raise Denied from None
    if settings is None:
        st.session_state.pop(_CACHE, None)
        try:
            payload = json.loads(Path(__file__).with_name("analytics.json").read_bytes())
        except (OSError, ValueError):
            raise Invalid from None
        if not isinstance(payload, dict) or payload.get("synthetic") is not True:
            raise Invalid
        return payload, False
    try:
        store = GitHubStore(settings["repository"], settings["token"])
    except (KeyError, TypeError):
        st.session_state.pop(_CACHE, None)
        raise Denied from None
    fingerprint = sha256((store.repository.casefold() + "\0" + settings["token"]).encode()).digest()
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
