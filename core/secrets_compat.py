"""Secrets 兼容层 — Streamlit secrets 优先，回退到环境变量"""

import os


def _get_secret(key: str, default: str = "") -> str:
    """Streamlit secrets 优先，回退到环境变量"""
    try:
        import streamlit as st
        val = st.secrets.get(key, "")
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(key, default)
