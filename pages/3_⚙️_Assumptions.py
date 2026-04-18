"""
Page 3 — Assumptions
Market returns, inflation, retirement ages, Monte Carlo settings.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="Assumptions", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.card  { background:#161b22; border:1px solid #21262d; border-radius:12px; padding:18px 22px; margin-bottom:14px; }
.sh { font-size:1.05rem; font-weight:600; color:#e6edf3; border-bottom:1px solid #21262d;
     padding-bottom:8px; margin:18px 0 12px 0; }
</style>""", unsafe_allow_html=True)

st.markdown("## ⚙️ Assumptions")
st.markdown("<p style='color:#8b949e;'>Market return assumptions and simulation settings. "
            "These drive all Monte Carlo projections.</p>", unsafe_allow_html=True)

a = st.session_state.setdefault("assumptions", {
    "stock_return": 7.0, "stock_volatility": 15.0,
    "bond_return": 3.5,  "bond_volatility": 6.0,
    "cash_return": 2.0,  "stock_bond_correlation": -0.20,
    "inflation_rate": 3.0, "n_simulations": 1000,
    "show_real_dollars": False,
    "retirement_age_you": 62, "retirement_age_spouse": 60,
})

# ─── Retirement ages ──────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Retirement Ages</div>", unsafe_allow_html=True)
persons = st.session_state.get("persons", [{}, {}])

rc1, rc2 = st.columns(2)
with rc1:
    a["retirement_age_you"] = st.slider(
        f"Your Retirement Age ({persons[0].get('name','You') if persons else 'You'})",
        50, 70, a.get("retirement_age_you", 62), key="ra_you")
with rc2:
    a["retirement_age_spouse"] = st.slider(
        f"Spouse Retirement Age ({persons[1].get('name','Spouse') if len(persons)>1 else 'Spouse'})",
        50, 70, a.get("retirement_age_spouse", 60), key="ra_sp")

# ─── Life expectancy
st.markdown("<div class='sh'>Life Expectancy</div>", unsafe_allow_html=True)
lc1, lc2 = st.columns(2)
with lc1:
    if persons:
        persons[0]["life_expectancy"] = st.slider(
            f"Life Expectancy — {persons[0].get('name','You')}",
            70, 110, persons[0].get("life_expectancy", 87), key="le_you")
with lc2:
    if len(persons) > 1:
        persons[1]["life_expectancy"] = st.slider(
            f"Life Expectancy — {persons[1].get('name','Spouse')}",
            70, 110, persons[1].get("life_expectancy", 90), key="le_sp")

# ─── Returns ──────────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Expected Returns (Annual, Nominal)</div>", unsafe_allow_html=True)
st.caption("Historical references: US stocks ~10% nominal / ~7% real since 1926; "
           "US bonds ~4–5% nominal. These are *pre-expense* estimates — adjust down ~0.05–0.15% for fund fees.")

mc1, mc2, mc3 = st.columns(3)
with mc1:
    st.markdown("**Stocks**")
    a["stock_return"]     = st.slider("Mean Return (%)",     3.0, 14.0, a.get("stock_return", 7.0), 0.25, key="sr")
    a["stock_volatility"] = st.slider("Volatility / Std Dev (%)", 5.0, 25.0, a.get("stock_volatility", 15.0), 0.5, key="sv")
with mc2:
    st.markdown("**Bonds**")
    a["bond_return"]     = st.slider("Mean Return (%)",    0.5, 8.0, a.get("bond_return", 3.5), 0.25, key="br")
    a["bond_volatility"] = st.slider("Volatility / Std Dev (%)", 1.0, 15.0, a.get("bond_volatility", 6.0), 0.5, key="bv")
with mc3:
    st.markdown("**Cash / Money Market**")
    a["cash_return"] = st.slider("Return (%)", 0.0, 6.0, a.get("cash_return", 2.0), 0.25, key="cr")
    a["stock_bond_correlation"] = st.slider(
        "Stock/Bond Correlation", -0.8, 0.5, a.get("stock_bond_correlation", -0.20), 0.05, key="corr",
        help="Negative correlation (typical) means bonds cushion stock losses. Historical: ~-0.20 to -0.30.")

# ─── Inflation
st.markdown("<div class='sh'>Inflation</div>", unsafe_allow_html=True)
ic1, ic2 = st.columns([2, 2])
with ic1:
    a["inflation_rate"] = st.slider("Annual Inflation Rate (%)", 1.0, 6.0, a.get("inflation_rate", 3.0), 0.25, key="inf")
with ic2:
    a["show_real_dollars"] = st.toggle("Show inflation-adjusted (today's $) on charts by default",
                                        a.get("show_real_dollars", False), key="real_toggle")
    st.caption("You can toggle this on individual pages too.")

# ─── Simulation settings
st.markdown("<div class='sh'>Monte Carlo Settings</div>", unsafe_allow_html=True)
sc1, sc2 = st.columns(2)
with sc1:
    a["n_simulations"] = st.select_slider(
        "Number of Simulations",
        options=[200, 500, 1000, 2000, 5000],
        value=a.get("n_simulations", 1000),
        key="nsims",
        help="More simulations = more accurate but slower. 1,000 is a good balance."
    )
with sc2:
    st.markdown(f"""<div class='card' style='margin-top:6px;'>
        <div style='color:#8b949e;font-size:.82rem;text-transform:uppercase;'>Real Return (Stocks)</div>
        <div style='font-size:1.6rem;font-weight:700;color:#00d4aa;'>
            {a['stock_return'] - a['inflation_rate']:.2f}%</div>
        <div style='color:#8b949e;font-size:.82rem;'>Nominal {a['stock_return']}% − Inflation {a['inflation_rate']}%</div>
    </div>""", unsafe_allow_html=True)

# ─── Return distribution preview ─────────────────────────────────────────────
st.markdown("<div class='sh'>Return Distribution Preview</div>", unsafe_allow_html=True)
st.caption("Log-normal distribution of single-year portfolio returns for a 70/25/5 stock/bond/cash mix.")

from utils.calculations import _correlated_returns
import numpy as np

rng = np.random.default_rng(1)
s_r, s_v = a["stock_return"]/100, a["stock_volatility"]/100
b_r, b_v = a["bond_return"]/100, a["bond_volatility"]/100
stocks, bonds = _correlated_returns(10_000, 1, s_r, s_v, b_r, b_v, a["stock_bond_correlation"], rng)
port = 0.70 * stocks[:, 0] + 0.25 * bonds[:, 0] + 0.05 * (a["cash_return"]/100)

fig = go.Figure()
fig.add_trace(go.Histogram(x=port * 100, nbinsx=80, name="Annual Return (%)",
                            marker_color="rgba(0,212,170,0.6)", marker_line_color="#00d4aa",
                            marker_line_width=0.5))
fig.add_vline(x=np.median(port)*100, line_color="#e6edf3", line_dash="dash",
              annotation_text=f"Median: {np.median(port)*100:.1f}%", annotation_font_color="#e6edf3")
fig.add_vline(x=np.percentile(port, 5)*100, line_color="#f85149", line_dash="dot",
              annotation_text=f"P5: {np.percentile(port,5)*100:.1f}%", annotation_font_color="#f85149")
fig.add_vline(x=np.percentile(port, 95)*100, line_color="#3fb950", line_dash="dot",
              annotation_text=f"P95: {np.percentile(port,95)*100:.1f}%", annotation_font_color="#3fb950")
fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e6edf3"), height=280,
    xaxis=dict(title="Annual Return (%)", gridcolor="#21262d"),
    yaxis=dict(title="Simulations", gridcolor="#21262d"),
    showlegend=False, margin=dict(l=10, r=10, t=10, b=10),
)
st.plotly_chart(fig, width='stretch')
