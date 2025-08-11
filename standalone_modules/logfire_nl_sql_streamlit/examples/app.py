import sys
from pathlib import Path

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from lf_nl_sql.config import Settings
from lf_nl_sql.streamlit_tab import render_nl_sql_tab
from lf_nl_sql.logging_setup import init_logging


def main() -> None:
    st.set_page_config(page_title="Logfire NL→SQL", layout="wide")
    log_file = init_logging()
    st.caption(f"Logging to: {log_file}")
    render_nl_sql_tab(config=Settings())


if __name__ == "__main__":
    main()
