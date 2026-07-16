from html import escape

import streamlit as st


APP_CSS = """
<style>
    :root {
        --spa-primary: #0f766e;
        --spa-primary-dark: #115e59;
        --spa-ink: #172033;
        --spa-muted: #667085;
        --spa-border: #dce4ec;
        --spa-surface: #ffffff;
    }

    .block-container {
        max-width: 1480px;
        padding-top: 2.2rem;
        padding-bottom: 4rem;
    }

    [data-testid="stSidebar"] {
        border-right: 1px solid var(--spa-border);
    }

    [data-testid="stSidebarNav"] span,
    [data-testid="stSidebarNav"] a {
        font-size: 0.94rem;
    }

    .spa-brand {
        padding: .45rem .15rem .9rem;
    }

    .spa-brand__mark {
        align-items: center;
        background: linear-gradient(135deg, #0f766e, #2563eb);
        border-radius: 14px;
        color: #fff;
        display: inline-flex;
        font-size: 1.2rem;
        height: 42px;
        justify-content: center;
        margin-bottom: .65rem;
        width: 42px;
    }

    .spa-brand__name {
        color: var(--spa-ink);
        font-size: 1rem;
        font-weight: 750;
        line-height: 1.25;
    }

    .spa-brand__tagline {
        color: var(--spa-muted);
        font-size: .78rem;
        line-height: 1.45;
        margin-top: .25rem;
    }

    .spa-page-header {
        background:
            radial-gradient(circle at 94% 8%, rgba(15, 118, 110, .15), transparent 26%),
            linear-gradient(135deg, #ffffff 0%, #f3f8fa 100%);
        border: 1px solid var(--spa-border);
        border-radius: 18px;
        box-shadow: 0 8px 24px rgba(23, 32, 51, .045);
        margin: 0 0 1.35rem;
        overflow: hidden;
        padding: 1.45rem 1.6rem;
        position: relative;
    }

    .spa-page-header__section {
        color: var(--spa-primary);
        font-size: .72rem;
        font-weight: 750;
        letter-spacing: .09em;
        margin-bottom: .45rem;
        text-transform: uppercase;
    }

    .spa-page-header h1 {
        color: var(--spa-ink);
        font-size: clamp(1.7rem, 3vw, 2.35rem);
        letter-spacing: -.035em;
        line-height: 1.08;
        margin: 0;
        padding: 0;
    }

    .spa-page-header p {
        color: var(--spa-muted);
        font-size: .98rem;
        line-height: 1.55;
        margin: .65rem 0 0;
        max-width: 820px;
    }

    [data-testid="stMetric"] {
        background: var(--spa-surface);
        border: 1px solid var(--spa-border);
        border-radius: 14px;
        box-shadow: 0 4px 16px rgba(23, 32, 51, .035);
        min-height: 112px;
        padding: 1rem 1.1rem;
    }

    [data-testid="stMetricLabel"] {
        color: var(--spa-muted);
    }

    [data-testid="stMetricValue"] {
        color: var(--spa-ink);
        font-weight: 720;
    }

    .stTabs [data-baseweb="tab-list"] {
        background: #eef3f7;
        border-radius: 12px;
        gap: .25rem;
        padding: .3rem;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 9px;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .stTabs [aria-selected="true"] {
        background: #ffffff;
        box-shadow: 0 2px 8px rgba(23, 32, 51, .08);
    }

    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        box-shadow: 0 5px 14px rgba(15, 118, 110, .2);
        font-weight: 650;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--spa-border);
        border-radius: 12px;
        overflow: hidden;
    }

    .spa-guide-card {
        background: #ffffff;
        border: 1px solid var(--spa-border);
        border-radius: 14px;
        min-height: 150px;
        padding: 1rem 1.1rem;
    }

    .spa-guide-card strong {
        color: var(--spa-ink);
        display: block;
        margin-bottom: .35rem;
    }

    .spa-guide-card span {
        color: var(--spa-muted);
        font-size: .9rem;
        line-height: 1.5;
    }

    @media (max-width: 760px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
            padding-top: 1rem;
        }

        .spa-page-header {
            border-radius: 14px;
            padding: 1.1rem;
        }

        [data-testid="stMetric"] {
            min-height: auto;
        }
    }
</style>
"""


def apply_app_style() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)


def render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="spa-brand">
            <div class="spa-brand__mark">📈</div>
            <div class="spa-brand__name">Pilotage prédictif des ventes</div>
            <div class="spa-brand__tagline">
                Des données fiables aux décisions de stock.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(
    *,
    title: str,
    description: str,
    icon: str,
    section: str,
) -> None:
    apply_app_style()
    st.markdown(
        f"""
        <div class="spa-page-header">
            <div class="spa-page-header__section">{escape(section)}</div>
            <h1>{escape(icon)}&nbsp; {escape(title)}</h1>
            <p>{escape(description)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def guide_card(title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="spa-guide-card">
            <strong>{escape(title)}</strong>
            <span>{escape(description)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

