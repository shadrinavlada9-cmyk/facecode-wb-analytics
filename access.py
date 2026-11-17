"""Server-side password gate for this Streamlit session."""
from hashlib import sha256
from secrets import compare_digest
from time import sleep

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

_GRANT = "_facecode_session_grant"
_INPUT = "_facecode_password_input"
_FAILED = "_facecode_login_failed"


def _password():
    try:
        value = st.secrets["auth"]["password"]
    except (KeyError, TypeError, StreamlitSecretNotFoundError):
        return None
    return value.encode("utf-8") if isinstance(value, str) and value.strip() else None


def _valid_grant(password):
    grant = st.session_state.get(_GRANT)
    return password is not None and isinstance(grant, bytes) and compare_digest(grant, sha256(password).digest())


def _submit():
    submitted = st.session_state.pop(_INPUT, "")
    password = _password()
    if password is not None and compare_digest(submitted.encode("utf-8"), password):
        st.session_state[_GRANT] = sha256(password).digest()
        st.session_state.pop(_FAILED, None)
    else:
        st.session_state.pop(_GRANT, None)
        st.session_state[_FAILED] = True
        sleep(0.75)


def require_access():
    password = _password()
    if _valid_grant(password):
        return
    st.session_state.pop(_GRANT, None)
    if password is None:
        st.error("Вход недоступен. Обратитесь к владельцу приложения.")
        st.stop()
    st.subheader("Вход")
    with st.form("facecode_login", clear_on_submit=True):
        st.text_input("Пароль", type="password", key=_INPUT)
        st.form_submit_button("Войти", on_click=_submit)
    if st.session_state.get(_FAILED):
        st.error("Неверный пароль.")
    st.stop()


def _logout():
    st.session_state.clear()


def logout_button():
    st.button("Выйти", on_click=_logout)
