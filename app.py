"""Streamlit web UI for the Competitor Analysis tool."""
from __future__ import annotations

import io
import csv
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import tempfile

import streamlit as st


@st.cache_resource
def _install_playwright_browser() -> None:
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
    )


_install_playwright_browser()

from competitor_analysis.models import AnalysisRecord, CompetitorRow, TargetAnalysis
from competitor_analysis.storage.history import save_analysis, load_analysis, list_analyses, delete_analysis

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Competitor Analysis — Kolif Agency",
    page_icon="🔍",
    layout="wide",
)

# ── Brand colours ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    :root {
        --primary: #09084c;
        --accent:  #ff7300;
    }
    /* Top bar accent line */
    [data-testid="stAppViewContainer"]::before {
        content: "";
        display: block;
        height: 4px;
        background: linear-gradient(90deg, #09084c 0%, #ff7300 100%);
    }
    /* Primary button */
    div.stButton > button[kind="primary"] {
        background-color: #ff7300;
        border: none;
        color: white;
        font-weight: 600;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #e06600;
        border: none;
        color: white;
    }
    /* Download buttons */
    div.stDownloadButton > button {
        background-color: #09084c;
        color: white;
        border: none;
        font-weight: 500;
    }
    div.stDownloadButton > button:hover {
        background-color: #1a1870;
        color: white;
        border: none;
    }
    /* Metric labels */
    [data-testid="stMetricLabel"] { font-size: 0.8rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state ─────────────────────────────────────────────────────────────
if "rows" not in st.session_state:
    st.session_state.rows = []
    st.session_state.profile = None
    st.session_state.current_analysis_id = None
    st.session_state.profile_debug = None
    st.session_state.raw_profile = None
    st.session_state.target_analysis = None
    st.session_state.marketing_strategy = None
    st.session_state.objective = ""

# ── Sidebar – Cronologia ──────────────────────────────────────────────────────
with st.sidebar:
    st.title("📋 Cronologia")
    st.divider()
    metas = list_analyses()
    if not metas:
        st.caption("Nessuna analisi salvata.")
    else:
        for meta in metas:
            c1, c2 = st.columns([5, 1])
            with c1:
                btn_label = f"**{meta.profile_name}**  \n{meta.created_at[:16].replace('T', ' ')} · {meta.competitor_count} competitor"
                if st.button(btn_label, key=f"load_{meta.id}", use_container_width=True):
                    record = load_analysis(meta.id)
                    st.session_state.rows = record.rows
                    st.session_state.profile = record.profile
                    st.session_state.current_analysis_id = meta.id
                    st.session_state.profile_debug = None
                    st.session_state.raw_profile = None
                    st.session_state.target_analysis = record.target_analysis
                    st.session_state.marketing_strategy = record.marketing_strategy
                    st.session_state.objective = record.objective or ""
                    st.rerun()
            with c2:
                if st.button("🗑", key=f"del_{meta.id}", help="Elimina questa analisi"):
                    delete_analysis(meta.id)
                    if st.session_state.current_analysis_id == meta.id:
                        st.session_state.rows = []
                        st.session_state.profile = None
                        st.session_state.current_analysis_id = None
                        st.session_state.target_analysis = None
                        st.session_state.marketing_strategy = None
                        st.session_state.objective = ""
                    st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 8])
with col_title:
    st.title("🔍 Competitor Analysis")
    st.caption("Powered by Claude AI · Kolif Agency")

st.divider()

# ── Input form ────────────────────────────────────────────────────────────────
with st.form("analysis_form"):
    profile_url = st.text_input(
        "Social media profile URL",
        placeholder="https://www.instagram.com/example/",
        help="Paste any public social media profile link (Instagram, LinkedIn, Facebook, etc.)",
    )
    col_n, col_fmt, _ = st.columns([2, 2, 6])
    with col_n:
        max_competitors = st.number_input(
            "Max competitors", min_value=1, max_value=20, value=10, step=1
        )
    with col_fmt:
        use_cache = st.toggle("Use cache", value=True, help="Skip repeated web searches for 24 hours")

    submitted = st.form_submit_button("Analyze", type="primary", use_container_width=False)

# ── Run analysis ─────────────────────────────────────────────────────────────
if submitted:
    if not profile_url.strip():
        st.error("Please enter a profile URL.")
        st.stop()

    from competitor_analysis.scraper.profile import scrape_profile
    from competitor_analysis.analysis.competitor_finder import analyze_profile, find_competitors
    from competitor_analysis.analysis.target_analyzer import analyze_target
    from competitor_analysis.analysis.kpi_analyzer import (
        _gather_competitor_data,
        _analyze_kpis,
        _build_row,
        CompetitorKPI,
    )

    progress = st.progress(0, text="Starting…")
    status = st.empty()

    try:
        # Stage 1 – scrape
        status.info("🌐 Fetching profile page…")
        raw_profile = scrape_profile(profile_url.strip())
        progress.progress(15, text="Profile fetched")

        # Stage 2 – Claude profile analysis
        status.info("🤖 Analysing profile with Claude…")
        profile, profile_debug = analyze_profile(raw_profile, profile_url.strip(), use_cache=use_cache)
        progress.progress(35, text="Profile analysed")

        # Stage 3 – find competitors
        status.info("🔎 Searching for competitors…")
        candidates = find_competitors(
            profile, max_results=int(max_competitors), use_cache=use_cache
        )
        progress.progress(60, text=f"Found {len(candidates)} candidates")

        # Stage 4 – gather KPIs
        status.info("📊 Gathering KPIs for each competitor…")
        rows: list[CompetitorRow] = []

        for i, candidate in enumerate(candidates):
            try:
                raw_data = _gather_competitor_data(candidate, use_cache=use_cache, verbose=False)
                kpis = _analyze_kpis(candidate, raw_data, profile)
                rows.append(_build_row(candidate, kpis))
            except Exception:
                rows.append(_build_row(candidate, CompetitorKPI()))

            pct = 60 + int(40 * (i + 1) / len(candidates))
            progress.progress(pct, text=f"KPIs: {i + 1}/{len(candidates)}")

        # Stage 5 – target analysis
        status.info("🎯 Analysing target audience…")
        target_analysis = analyze_target(profile)
        progress.progress(100, text="Done!")
        status.success(f"✅ Analysis complete — {len(rows)} competitors found")

        # Save to history
        url_slug = profile_url.strip().rstrip("/").split("/")[-1][:30]
        record_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{url_slug}"
        record = AnalysisRecord(
            id=record_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            input_url=profile_url.strip(),
            profile=profile,
            rows=rows,
            target_analysis=target_analysis,
        )
        save_analysis(record)
        st.session_state.rows = rows
        st.session_state.profile = profile
        st.session_state.current_analysis_id = record_id
        st.session_state.profile_debug = profile_debug
        st.session_state.raw_profile = raw_profile
        st.session_state.target_analysis = target_analysis
        st.session_state.marketing_strategy = None
        st.session_state.objective = ""

    except Exception as exc:
        progress.empty()
        status.empty()
        st.error(f"Something went wrong: {exc}")
        st.stop()

# ── Results (new analysis or loaded from history) ─────────────────────────────
if st.session_state.rows:
    profile = st.session_state.profile
    rows = st.session_state.rows

    # ── Profile summary card ──────────────────────────────────────────────────
    st.subheader("Profile summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Name", profile.name)
    m2.metric("Niche", profile.niche)
    m3.metric("Market", profile.geographic_scope)
    m4.metric("Competitors found", len(rows))

    with st.expander("Full profile details", expanded=True):
        st.write(f"**Bio:** {profile.bio}")
        st.write(f"**Target audience:** {profile.target_audience}")
        st.write(f"**Services:** {', '.join(profile.services)}")
        if profile.brand_values:
            st.write(f"**Brand values:** {', '.join(profile.brand_values)}")
        if profile.website:
            st.write(f"**Website:** {profile.website}")
        if profile.social_links:
            links_md = "  ·  ".join(f"[{p.capitalize()}]({u})" for p, u in profile.social_links.items())
            st.write(f"**Social links:** {links_md}")

    if st.session_state.profile_debug:
        debug = st.session_state.profile_debug
        with st.expander("🔧 Debug — raw data Claude saw", expanded=False):
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Platform", debug["platform"])
            col_b.metric("Sparse data triggered", "Yes" if debug["sparse_data"] else "No")
            col_c.metric("Handle hint triggered", "Yes" if debug["handle_hint_triggered"] else "No")

            st.write("**Scraped description (raw):**")
            st.code(debug["scraped_description"] or "(empty)", language="text")

            if debug["meta_tags_subset"]:
                st.write("**Relevant meta tags:**")
                st.json(debug["meta_tags_subset"])

            if st.session_state.raw_profile and getattr(st.session_state.raw_profile, "extra_data", None):
                st.write("**Structured data extracted:**")
                st.json(st.session_state.raw_profile.extra_data)

            if debug["visible_text_preview"]:
                st.write("**Visible page text (first 500 chars):**")
                st.code(debug["visible_text_preview"], language="text")

    st.divider()

    # ── Target analysis table ─────────────────────────────────────────────────
    target_analysis: TargetAnalysis | None = st.session_state.target_analysis
    if target_analysis:
        st.subheader("🎯 Analisi del target")
        st.caption("Clienti potenziali — non il professionista analizzato né i suoi competitor")

        col_p, col_o, col_d, col_des = st.columns(4)

        def _render_list_col(col, header: str, items: list[str], color: str) -> None:
            with col:
                st.markdown(
                    f"<div style='background:{color};padding:10px 14px 4px;border-radius:8px 8px 0 0;'>"
                    f"<strong style='color:white;font-size:0.95rem'>{header}</strong></div>",
                    unsafe_allow_html=True,
                )
                bullets = "".join(f"<li style='margin-bottom:6px'>{item}</li>" for item in items)
                st.markdown(
                    f"<div style='background:#f7f7fb;padding:12px 14px;border-radius:0 0 8px 8px;"
                    f"border:1px solid #e0e0e0;min-height:220px'><ul style='padding-left:18px;margin:0'>"
                    f"{bullets}</ul></div>",
                    unsafe_allow_html=True,
                )

        _render_list_col(col_p,   "PROBLEMI",   target_analysis.problemi,   "#09084c")
        _render_list_col(col_o,   "OBIETTIVI",  target_analysis.obiettivi,  "#ff7300")
        _render_list_col(col_d,   "DOLORE",     target_analysis.dolore,     "#c0392b")
        _render_list_col(col_des, "DESIDERI",   target_analysis.desideri,   "#2e7d32")

    st.divider()

    # ── Competitors table ─────────────────────────────────────────────────────
    st.subheader("Competitor analysis")

    _PLATFORMS = ["instagram", "facebook", "linkedin", "youtube", "tiktok", "twitter"]

    def _social_links_md(row: CompetitorRow) -> str:
        parts = []
        for p, url in row.social_profiles.items():
            parts.append(f"[{p.capitalize()}]({url})")
        return " · ".join(parts) if parts else "—"

    def _followers_str(row: CompetitorRow) -> str:
        parts = []
        for p in _PLATFORMS:
            v = row.kpis.follower_count.get(p, "N/A")
            if v and v != "N/A":
                parts.append(f"{p[:2].upper()}: {v}")
        return "  |  ".join(parts) if parts else "N/A"

    def _structure_str(row: CompetitorRow) -> str:
        icons = {
            "website": "🌐 Website",
            "landing_page": "📄 Landing",
            "ebook": "📘 E-book",
            "freebie": "🎁 Freebie",
            "multi_platform": "📱 Multi-platform",
        }
        present = [label for key, label in icons.items() if row.kpis.structure.get(key)]
        return "  ·  ".join(present) if present else "—"

    for idx, row in enumerate(rows, 1):
        with st.container(border=True):
            head_col, kpi_col = st.columns([3, 2])

            with head_col:
                st.markdown(f"### {idx}. {row.name}")
                st.write(row.description)
                st.caption(f"**Active since:** {row.active_since}  |  **Engagement:** {row.kpis.interaction_score}")
                if row.website_and_links:
                    st.markdown(" · ".join(f"[{l}]({l})" for l in row.website_and_links[:3]))

            with kpi_col:
                st.markdown(f"**Followers**  \n{_followers_str(row)}")
                st.markdown(f"**Digital presence**  \n{_structure_str(row)}")
                st.markdown(f"**Social profiles**  \n{_social_links_md(row)}")

            with st.expander("Why a competitor / Activities"):
                st.write(f"**Why a competitor:** {row.why_competitor}")
                st.write(f"**Activities:** {row.activities}")

    st.divider()

    # ── Download buttons ──────────────────────────────────────────────────────
    st.subheader("Download results")
    dl1, dl2 = st.columns(2)

    from competitor_analysis.output.export import _flatten, export_excel

    # CSV
    csv_buf = io.StringIO()
    flat_rows = [_flatten(r) for r in rows]
    writer = csv.DictWriter(csv_buf, fieldnames=list(flat_rows[0].keys()))
    writer.writeheader()
    writer.writerows(flat_rows)

    with dl1:
        st.download_button(
            label="⬇️ Download CSV",
            data=csv_buf.getvalue().encode("utf-8"),
            file_name="competitor_analysis.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Excel
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    export_excel(rows, tmp_path)
    excel_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    with dl2:
        st.download_button(
            label="⬇️ Download Excel",
            data=excel_bytes,
            file_name="competitor_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # ── Marketing strategy section ────────────────────────────────────────────
    if st.session_state.target_analysis:
        st.divider()
        st.subheader("🎯 Strategia di marketing")
        st.caption("Genera una strategia personalizzata basata sull'analisi dei competitor e del target")

        with st.form("strategy_form"):
            objective_input = st.text_area(
                "Il tuo obiettivo",
                value=st.session_state.objective,
                placeholder="Es. Acquisire 10 nuovi clienti coach in 3 mesi aumentando la visibilità su Instagram",
                height=90,
            )
            col_tf, col_pp, _ = st.columns([2, 2, 6])
            with col_tf:
                timeframe = st.selectbox(
                    "Orizzonte temporale",
                    ["1 mese", "3 mesi", "6 mesi"],
                    index=1,
                )
            with col_pp:
                priority_platform = st.selectbox(
                    "Piattaforma prioritaria",
                    ["(nessuna preferenza)", "Instagram", "LinkedIn", "Facebook", "TikTok", "YouTube"],
                )
            gen_submitted = st.form_submit_button("✨ Genera strategia", type="primary")

        if gen_submitted:
            if not objective_input.strip():
                st.error("Inserisci un obiettivo prima di generare la strategia.")
            else:
                from competitor_analysis.analysis.strategy_generator import generate_strategy

                with st.spinner("🤖 Elaborazione strategia con Claude…"):
                    try:
                        pp = None if priority_platform == "(nessuna preferenza)" else priority_platform
                        strategy = generate_strategy(
                            objective=objective_input.strip(),
                            profile=st.session_state.profile,
                            competitors=st.session_state.rows,
                            target_analysis=st.session_state.target_analysis,
                            timeframe=timeframe,
                            priority_platform=pp,
                        )
                        st.session_state.marketing_strategy = strategy
                        st.session_state.objective = objective_input.strip()

                        # Persist onto the existing analysis record
                        if st.session_state.current_analysis_id:
                            from competitor_analysis.storage.history import load_analysis, save_analysis
                            record = load_analysis(st.session_state.current_analysis_id)
                            record = record.model_copy(update={
                                "objective": objective_input.strip(),
                                "marketing_strategy": strategy,
                            })
                            save_analysis(record)

                        st.rerun()
                    except Exception as exc:
                        st.error(f"Errore durante la generazione della strategia: {exc}")

        # Render saved/generated strategy
        strategy = st.session_state.marketing_strategy
        if strategy:
            from competitor_analysis.output.export import strategy_to_markdown

            st.success(f"**Obiettivo:** {strategy.objective}")

            if strategy.summary:
                st.info(strategy.summary)

            col_pos, col_tgt = st.columns(2)
            with col_pos:
                with st.container(border=True):
                    st.markdown("**📍 Posizionamento**")
                    st.write(strategy.positioning)
            with col_tgt:
                with st.container(border=True):
                    st.markdown("**🎯 Focus sul target**")
                    st.write(strategy.target_focus)

            if strategy.differentiation:
                with st.expander("🔀 Differenziazione vs competitor", expanded=True):
                    for item in strategy.differentiation:
                        st.markdown(f"- {item}")

            if strategy.key_messages:
                with st.expander("💬 Messaggi chiave", expanded=True):
                    for msg in strategy.key_messages:
                        st.markdown(f"- {msg}")

            if strategy.content_pillars:
                st.markdown("#### 📚 Pilastri di contenuto")
                pillar_cols = st.columns(min(len(strategy.content_pillars), 3))
                for i, pillar in enumerate(strategy.content_pillars):
                    with pillar_cols[i % 3]:
                        with st.container(border=True):
                            st.markdown(f"**{pillar.title}**")
                            if pillar.description:
                                st.caption(pillar.description)
                            for topic in pillar.sample_topics:
                                st.markdown(f"• {topic}")

            col_ch, col_act = st.columns(2)
            with col_ch:
                if strategy.channel_strategy:
                    with st.expander("📱 Strategia di canale", expanded=False):
                        for item in strategy.channel_strategy:
                            st.markdown(f"- {item}")
            with col_act:
                if strategy.recommended_actions:
                    with st.expander("✅ Azioni raccomandate", expanded=False):
                        for i, action in enumerate(strategy.recommended_actions, 1):
                            st.markdown(f"{i}. {action}")

            if strategy.kpis:
                with st.expander("📊 KPI e metriche di successo", expanded=False):
                    for kpi in strategy.kpis:
                        st.markdown(f"- {kpi}")

            if strategy.editorial_plan:
                st.markdown("#### 📅 Piano editoriale")
                import pandas as pd
                plan_data = [
                    {
                        "Sett.": item.week,
                        "Giorno": item.day,
                        "Piattaforma": item.platform,
                        "Formato": item.format,
                        "Pilastro": item.pillar,
                        "Idea / Hook": item.topic,
                        "Obiettivo": item.goal,
                    }
                    for item in strategy.editorial_plan
                ]
                st.dataframe(
                    pd.DataFrame(plan_data),
                    use_container_width=True,
                    hide_index=True,
                )

            st.download_button(
                label="⬇️ Download strategia (Markdown)",
                data=strategy_to_markdown(strategy).encode("utf-8"),
                file_name="strategia.md",
                mime="text/markdown",
                use_container_width=False,
            )

# ── Empty state ───────────────────────────────────────────────────────────────
elif not submitted:
    st.info("👆 Enter a social media profile URL above and click **Analyze** to get started.")
