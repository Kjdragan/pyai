import streamlit as st

from lf_nl_sql.config import Settings
from lf_nl_sql.streamlit_tab import render_nl_sql_tab


def main() -> None:
    st.set_page_config(page_title="Logfire NL→SQL", layout="wide")
    render_nl_sql_tab(config=Settings())


if __name__ == "__main__":
    main()
