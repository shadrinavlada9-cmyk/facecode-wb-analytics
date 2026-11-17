"""Deliver Excel in the authenticated Streamlit session, without a media URL."""
from base64 import b64encode
from html import escape

import streamlit as st

from access import require_access


def excel_download(label, workbook, filename, *, primary=False):
    require_access()
    contents = b64encode(workbook).decode("ascii")
    theme = "background:#171717;color:white;" if primary else "background:white;color:#1b1b1b;"
    st.iframe(
        '<style>body{margin:0;font:16px system-ui,sans-serif}'
        'a{display:inline-block;border:1px solid #ddd;border-radius:.5rem;padding:.4rem .75rem;'
        f'text-decoration:none;{theme}}}'
        'a:hover,a:focus-visible{border-color:#171717}</style>'
        '<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,'
        f'{contents}" download="{escape(filename, quote=True)}">{escape(label)}</a>',
        height=44,
    )
