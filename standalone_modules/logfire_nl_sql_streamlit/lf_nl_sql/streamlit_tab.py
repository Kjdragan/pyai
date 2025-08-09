from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import streamlit as st
import logging

from .config import Settings, get_env_source_path
from .logfire_client import LogfireQueryClient
from .nl_to_sql import generate_sql
from .saved_queries import SavedQuery, load_queries, upsert_query
from .sql_safety import ensure_safe_select


_TIME_PRESETS = {
    "Last 1 hour": timedelta(hours=1),
    "Last 6 hours": timedelta(hours=6),
    "Last 24 hours": timedelta(hours=24),
    "Last 7 days": timedelta(days=7),
}


def _get_time_bounds(preset: str) -> tuple[Optional[datetime], Optional[datetime]]:
    delta = _TIME_PRESETS.get(preset)
    if not delta:
        return None, None
    now = datetime.utcnow()
    return now - delta, now


def render_nl_sql_tab(state=None, config: Optional[Settings] = None) -> None:
    log = logging.getLogger(__name__)
    st.title("Logfire NL→SQL")

    cfg = config or Settings()
    try:
        cfg.validate()
    except Exception as e:
        log.exception("Configuration validation failed")
        st.error(str(e))
        return

    # Diagnostics: show what env file was used (if any)
    env_src = get_env_source_path()
    st.caption(
        f"Env source: {env_src if env_src else 'process env (no module .env found)'}"
    )

    log.info(
        "Render NL→SQL tab start | api_base=%s accept=%s default_limit=%s llm_provider=%s model=%s token_present=%s",
        cfg.logfire_api_base,
        cfg.accept_format,
        cfg.default_row_limit,
        cfg.llm_provider,
        cfg.llm_model,
        bool(cfg.logfire_read_token),
    )

    if "sql_text" not in st.session_state:
        st.session_state.sql_text = (
            "SELECT timestamp, service_name, span_name, trace_id, span_id\n"
            "FROM records\nORDER BY timestamp DESC\nLIMIT 100;"
        )
    if "nl_prompt" not in st.session_state:
        st.session_state.nl_prompt = ""

    cols = st.columns([2, 3])

    with cols[0]:
        st.subheader("Natural Language")
        st.session_state.nl_prompt = st.text_area("Ask a question", value=st.session_state.nl_prompt, height=180)
        gen_mode = st.radio("Generation mode", options=["new", "modify"], horizontal=True)
        if st.button("Generate SQL", type="primary"):
            log.info("Generate SQL clicked | mode=%s prompt_len=%s", gen_mode, len(st.session_state.nl_prompt or ""))
            st.session_state.sql_text = generate_sql(
                st.session_state.nl_prompt,
                provider=cfg.llm_provider,
                model=cfg.llm_model,
                api_key=cfg.openai_api_key,
                mode=gen_mode,
                existing_sql=st.session_state.sql_text if gen_mode == "modify" else None,
            )
            log.info("Generated SQL (truncated): %s", (st.session_state.sql_text or "").strip().replace("\n", " ")[:300])

        st.divider()
        st.subheader("Saved Queries")
        saved = load_queries(cfg.saved_queries_path)
        if saved:
            opts = [q.name for q in saved]
            sel = st.selectbox("Load", options=[""] + opts, index=0)
            if sel:
                q = next(q for q in saved if q.name == sel)
                st.session_state.nl_prompt = q.prompt
                st.session_state.sql_text = q.sql
                log.info("Loaded saved query '%s'", sel)
        name = st.text_input("Save current as", value="")
        if st.button("Save Query") and name.strip():
            new_q = SavedQuery(name=name.strip(), prompt=st.session_state.nl_prompt, sql=st.session_state.sql_text)
            upsert_query(cfg.saved_queries_path, new_q)
            st.success(f"Saved '{name}'.")
            log.info("Saved query '%s'", name.strip())

    with cols[1]:
        st.subheader("SQL & Run")
        st.session_state.sql_text = st.text_area("SQL", value=st.session_state.sql_text, height=220)

        with st.expander("Connection", expanded=False):
            st.text("API base:")
            st.code(cfg.logfire_api_base, language="text")
            st.text("Env source:")
            st.code(str(env_src) if env_src else "<process env>", language="text")
            override = st.text_input("Override read token (session only)", value="", type="password", help="Paste a valid Logfire READ token to use for this session only. Not saved.")
            if override:
                st.session_state["lf_read_token_override"] = override.strip()
                log.info("Using session token override: True")
            else:
                st.session_state["lf_read_token_override"] = ""
                log.info("Using session token override: False")

        c1, c2, c3 = st.columns(3)
        with c1:
            preset = st.selectbox("Time range", list(_TIME_PRESETS.keys()), index=2)
        with c2:
            row_limit = st.number_input("Row limit", min_value=1, max_value=100000, value=int(cfg.default_row_limit), step=100)
        with c3:
            fmt = st.selectbox("Format", options=["csv", "json", "arrow"], index=["csv", "json", "arrow"].index(cfg.accept_format))

        run = st.button("Run Query", type="primary")

        if run:
            with st.spinner("Querying Logfire..."):
                token = st.session_state.get("lf_read_token_override") or cfg.logfire_read_token
                client = LogfireQueryClient(cfg.logfire_api_base, token, default_accept=fmt)
                try:
                    # Safety: allow only single, read-only SELECT
                    safe_sql = ensure_safe_select(st.session_state.sql_text)
                except Exception as e:
                    log.warning("Unsafe SQL rejected: %s", e)
                    st.error(f"Unsafe SQL: {e}")
                    client.close()
                    return
                try:
                    min_ts, max_ts = _get_time_bounds(preset)
                    log.info("Run query | preset=%s min_ts=%s max_ts=%s limit=%s fmt=%s", preset, min_ts, max_ts, row_limit, fmt)
                    df, meta = client.query(safe_sql, accept=fmt, min_ts=min_ts, max_ts=max_ts, limit=row_limit)
                except Exception as e:
                    log.exception("Query failed")
                    st.error(f"Query failed: {e}")
                    client.close()
                    return
                finally:
                    client.close()

                st.caption(f"Status: {meta['status_code']} | Format: {meta['accept']}")
                if df is None or df.empty:
                    log.info("No results returned")
                    st.info("No results.")
                else:
                    log.info("Results returned: %s rows", len(df.index))  # type: ignore[arg-type]
                    st.dataframe(df, use_container_width=True)

                st.divider()
                st.subheader("Trace Drill‑down")
                if df is not None and "trace_id" in df.columns:
                    trace_id = st.text_input("Enter a trace_id from the results")
                    if st.button("Fetch Trace Spans") and trace_id.strip():
                        q = (
                            "SELECT timestamp, service_name, span_name, trace_id, span_id, attributes "
                            "FROM records WHERE trace_id = '" + trace_id.replace("'", "''") + "' "
                            "ORDER BY timestamp ASC LIMIT 200;"
                        )
                        try:
                            tq = ensure_safe_select(q)
                        except Exception as e:
                            log.warning("Unsafe trace lookup SQL: %s", e)
                            st.error(f"Unsafe SQL for trace lookup: {e}")
                        else:
                            t_token = st.session_state.get("lf_read_token_override") or cfg.logfire_read_token
                            tclient = LogfireQueryClient(cfg.logfire_api_base, t_token, default_accept=fmt)
                            try:
                                log.info("Trace lookup start trace_id=%s", trace_id.strip())
                                tdf, _ = tclient.query(tq, accept=fmt)
                                st.dataframe(tdf, use_container_width=True)
                                log.info("Trace lookup rows=%s", 0 if tdf is None else len(tdf.index))  # type: ignore[arg-type]
                            except Exception as e:  # pragma: no cover
                                log.exception("Trace lookup failed")
                                st.error(f"Trace lookup failed: {e}")
                            finally:
                                tclient.close()
