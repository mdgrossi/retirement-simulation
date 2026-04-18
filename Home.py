"""
Retirement Planner — Home / Landing Page
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from utils.defaults import DEFAULT_STATE, ACCOUNT_TYPES
import copy, json

st.set_page_config(
    page_title="Retirement Planner",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.metric-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
}
.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #00d4aa;
    line-height: 1.1;
}
.metric-label {
    font-size: 0.82rem;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 4px;
}
.metric-sub {
    font-size: 0.88rem;
    color: #8b949e;
    margin-top: 6px;
}
.section-header {
    font-size: 1.1rem;
    font-weight: 600;
    color: #e6edf3;
    border-bottom: 1px solid #21262d;
    padding-bottom: 8px;
    margin: 20px 0 14px 0;
}
.nav-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 10px;
    transition: border-color 0.2s;
}
.nav-card:hover { border-color: #00d4aa; }
.pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
}
.pill-green  { background: rgba(63,185,80,0.2);  color: #3fb950; }
.pill-blue   { background: rgba(121,192,255,0.2); color: #79c0ff; }
.pill-amber  { background: rgba(240,136,62,0.2); color: #f0883e; }
.pill-teal   { background: rgba(0,212,170,0.2);  color: #00d4aa; }
.stButton > button {
    background: #00d4aa;
    color: #0d1117;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1.2rem;
}
.stButton > button:hover { background: #00b899; }
div[data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
</style>
""", unsafe_allow_html=True)

# ─── Session state init ───────────────────────────────────────────────────────
def init_state():
    defaults = copy.deepcopy(DEFAULT_STATE)
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_state()

# ─── Quick summary helpers ────────────────────────────────────────────────────
def total_portfolio() -> float:
    total = 0.0
    for person in st.session_state.persons:
        for acct in person.get("accounts", []):
            total += acct.get("balance", 0)
    return total

def total_annual_contributions() -> float:
    total = 0.0
    for person in st.session_state.persons:
        for acct in person.get("accounts", []):
            total += acct.get("annual_contribution", 0) + acct.get("employer_match", 0)
    return total

def total_salary() -> float:
    return sum(
        sum(s.get("amount", 0) for s in p.get("salaries", []))
        for p in st.session_state.persons
    )

def fmt_dollar(v: float) -> str:
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    if v >= 1e3:  return f"${v/1e3:,.0f}K"
    return f"${v:,.0f}"

# ─── Page layout ─────────────────────────────────────────────────────────────
st.markdown("## 📊 Retirement Planning Dashboard")
st.markdown(
    "<p style='color:#8b949e; margin-top:-8px;'>Household retirement projections with Monte Carlo simulation "
    "· FERS pension · Tax-aware analysis</p>",
    unsafe_allow_html=True
)

# ── KPI row
col1, col2, col3, col4 = st.columns(4)
persons = st.session_state.persons

with col1:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value">{fmt_dollar(total_portfolio())}</div>
        <div class="metric-label">Total Portfolio Today</div>
        <div class="metric-sub">{len([a for p in persons for a in p.get('accounts',[])])} accounts</div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value">{fmt_dollar(total_annual_contributions())}</div>
        <div class="metric-label">Annual Contributions</div>
        <div class="metric-sub">All accounts incl. employer match</div>
    </div>""", unsafe_allow_html=True)

with col3:
    ret_age = st.session_state.assumptions.get("retirement_age_you", 62)
    you_age = persons[0]["age"]
    yrs     = max(ret_age - you_age, 0)
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value">{yrs} yrs</div>
        <div class="metric-label">Years to Retirement</div>
        <div class="metric-sub">Target age {ret_age} · Currently {you_age}</div>
    </div>""", unsafe_allow_html=True)

with col4:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value">{fmt_dollar(total_salary())}</div>
        <div class="metric-label">Household Income</div>
        <div class="metric-sub">Combined salaries</div>
    </div>""", unsafe_allow_html=True)

st.markdown("")

# ── Navigation cards
st.markdown("<div class='section-header'>Pages</div>", unsafe_allow_html=True)

nav_cols = st.columns(2)
pages = [
    ("👥 Household Setup",     "Enter accounts, salaries, and personal details for both partners.",     "1_👥_Household_Setup",     "pill-teal"),
    ("🏛️ Pension & Income",   "FERS pension calculator, Social Security estimation, other income.",    "2_🏛️_Pension_&_Income",    "pill-blue"),
    ("⚙️ Assumptions",        "Set market return assumptions, inflation, retirement ages.",             "3_⚙️_Assumptions",         "pill-teal"),
    ("📈 Accumulation",        "Monte Carlo portfolio growth from now to retirement.",                  "4_📈_Accumulation",         "pill-blue"),
    ("🎯 Three Scenarios",     "Core feature: Grow / Sustain / Deplete scenario comparison.",          "5_🎯_Three_Scenarios",      "pill-green"),
    ("📉 Spend-Down",          "Year-by-year retirement drawdown with survivor analysis.",              "6_📉_Spend_Down",           "pill-amber"),
    ("💰 Tax Analysis",        "Roth vs Traditional, RMDs, bracket optimization, IRMAA flags.",        "7_💰_Tax_Analysis",         "pill-blue"),
]

for i, (title, desc, _, pill_cls) in enumerate(pages):
    with nav_cols[i % 2]:
        st.markdown(f"""<div class="nav-card">
            <span style="font-weight:600; color:#e6edf3;">{title}</span>
            <span class="pill {pill_cls}" style="float:right; margin-top:2px;">Page {i+1}</span>
            <div style="color:#8b949e; font-size:0.85rem; margin-top:6px;">{desc}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── Getting started / instructions
st.markdown("<div class='section-header'>Getting Started</div>", unsafe_allow_html=True)
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("""
1. **👥 Household Setup** — Enter your accounts, current balances, contributions, and salaries. Add/remove accounts freely.
2. **🏛️ Pension & Income** — Configure your FERS pension details and Social Security estimates.
3. **⚙️ Assumptions** — Adjust market return assumptions, inflation, and retirement ages.
4. **📈 Accumulation** — Run the Monte Carlo and see how your portfolio grows to retirement.
5. **🎯 Three Scenarios** — The core page: see what *Grow*, *Sustain*, and *Deplete* look like with full Monte Carlo uncertainty bands, guaranteed income breakdown, and the savings rate needed to achieve each.
6. **💰 Tax Analysis** — Compare Roth vs Traditional contributions, visualize your Roth conversion window, and see RMD projections.

> **All values are anonymized placeholders.** Replace them with your actual numbers on the Household Setup page.
""")

with c2:
    st.markdown("""
<div class="metric-card" style="text-align:center;">
    <div style="font-size:2.5rem;">🎯</div>
    <div style="color:#e6edf3; font-weight:600; margin-top:8px;">Goal</div>
    <div style="color:#8b949e; font-size:0.83rem; margin-top:6px;">
        Save enough to retire comfortably — but not so much that you over-save now.
    </div>
</div>
""", unsafe_allow_html=True)

# ── Reset button
st.markdown("---")
if st.button("🔄 Reset All Data to Defaults"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_state()
    st.success("Reset to defaults.")
    st.rerun()
