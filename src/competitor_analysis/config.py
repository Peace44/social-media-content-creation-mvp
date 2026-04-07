from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_ROOT = Path(__file__).parent.parent.parent
load_dotenv(_ROOT / ".env")


def _from_streamlit(key: str) -> str | None:
    """Try to read a key from st.secrets (only available when running on Streamlit Cloud)."""
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None


def get(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key) or _from_streamlit(key) or default


def require(key: str) -> str:
    value = os.environ.get(key) or _from_streamlit(key)
    if not value:
        raise RuntimeError(
            f"Missing required secret: {key}\n"
            f"Local: set it in your .env file.\n"
            f"Streamlit Cloud: add it under App settings → Secrets."
        )
    return value
