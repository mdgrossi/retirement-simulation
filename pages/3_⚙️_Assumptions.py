"""Page 3 — Assumptions"""

import streamlit as st
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.calculations import _correlated_returns
from utils.charts import _add_crosshair
import plotly.graph_objects as go

st.set_page_config(page_title="Assumptions", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:18px 22px;margin-bottom:14px;}
.sh{font-size:1.05rem;font-weight:600;color:#e6edf3;border-bottom:1px solid #21262d;padding-bottom:8px;margin:18px 0 12px 0;}
.tip{background:rgba(0,212,170,0.07);border:1px solid rgba(0,212,170,0.2);border-radius:8px;
     padding:10px 14px;font-size:.85rem;color:#8b949e;margin-bottom:14px;}
</style>""", unsafe_allow_html=True)

st.markdown("## ⚙️ Assumptions")
st.markdown("<p style='color:#8b949e;'>Market return and inflation assumptions used across all "
            "Monte Carlo projections. The return distribution preview updates live as you "
            "adjust the sliders.</p>", unsafe_allow_html=True)

a = st.session_state.setdefault("assumptions", {
    "stock_return": 7.0, "stock_volatility": 15.0,
    "bond_return": 3.5,  "bond_volatility": 6.0,
    "cash_return": 2.0,  "stock_bond_correlation": -0.20,
    "inflation_rate": 3.0, "n_simulations": 1000,
    "show_real_dollars": False,
    "retirement_age_you": 62, "retirement_age_spouse": 60,
    "confidence_level": "p50",
})
persons = st.session_state.get("persons", [{}, {}])

# ── Retirement ages ────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Retirement Ages</div>", unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "These are the ages used throughout the app as your target retirement dates. "
            "They also appear on the Pension &amp; Income page. Use the Three Scenarios page "
            "to compare different retirement ages side by side.</div>", unsafe_allow_html=True)

rc1, rc2 = st.columns(2)
a["retirement_age_you"] = rc1.slider(
    f"Your Retirement Age ({persons[0].get('name','You') if persons else 'You'})",
    50, 70, a.get("retirement_age_you", 62), key="ra_you",
    help="The age at which you stop working and begin drawing from your portfolio. "
         "Each additional year worked adds salary contributions, allows more portfolio growth, "
         "and shortens the spend-down horizon — a powerful combination.")
a["retirement_age_spouse"] = rc2.slider(
    f"Spouse Retirement Age ({persons[1].get('name','Spouse') if len(persons)>1 else 'Spouse'})",
    50, 70, a.get("retirement_age_spouse", 60), key="ra_sp",
    help="Your spouse's planned retirement age. Their contributions stop and their "
         "accounts shift to distribution mode at this age in the simulation.")

# ── Life expectancy ────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Life Expectancy</div>", unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "Spend-down projections run until the <b>later</b> of the two life expectancies. "
            "Social Security Administration (SSA) tables suggest a 65-year-old "
            "today has a 50% chance of living past 85 (men) or 87 (women). "
            "Setting this higher (e.g., 95) is the conservative choice — "
            "it's much better to have money left over than to run short.</div>",
            unsafe_allow_html=True)

lc1, lc2 = st.columns(2)
if persons:
    persons[0]["life_expectancy"] = lc1.slider(
        f"Life Expectancy — {persons[0].get('name','You')}",
        70, 110, persons[0].get("life_expectancy", 87), key="le_you",
        help="The age used as the end of your spend-down projection. This is not a prediction "
             "of when you will die — it's the age you are planning your finances around. "
             "Using 90–95 adds a safety buffer against longevity risk.")
if len(persons) > 1:
    persons[1]["life_expectancy"] = lc2.slider(
        f"Life Expectancy — {persons[1].get('name','Spouse')}",
        70, 110, persons[1].get("life_expectancy", 90), key="le_sp",
        help="Same as above for your spouse. The simulation continues until the last "
             "survivor's life expectancy, modeling the full dual-life horizon.")

# ── Expected returns ───────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Expected Returns (Annual, Nominal)</div>", unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "These are your expected <b>pre-expense, pre-tax</b> returns. Historical references: "
            "US large-cap stocks ~10% nominal / ~7% real since 1926 (Damodaran). "
            "US aggregate bonds ~4–5% nominal. Cash/stable value ~1–3%. "
            "Adjust down ~0.05–0.15% to account for fund expense ratios. "
            "Returns are simulated using a <b>log-normal distribution</b> so that annual "
            "returns can never fall below −100%.</div>", unsafe_allow_html=True)

mc1, mc2, mc3 = st.columns(3)
with mc1:
    st.markdown("**Stocks**")
    a["stock_return"] = st.slider(
        "Mean Return (%)", 3.0, 14.0, a.get("stock_return", 7.0), 0.25, key="sr",
        help="The expected average annual return for equities. 7% is a commonly cited "
             "long-run real return; 10% is the historical nominal average. "
             "Be conservative — optimistic return assumptions are the #1 cause of "
             "retirement planning failures.")
    a["stock_volatility"] = st.slider(
        "Volatility / Standard Deviation (%)", 5.0, 25.0, a.get("stock_volatility", 15.0), 0.5, key="sv",
        help="How much stock returns vary year to year. Historically ~15–17% for US large-cap. "
             "Higher volatility increases sequence-of-returns risk in early retirement years. "
             "This is the standard deviation of the log-normal return distribution.")
with mc2:
    st.markdown("**Bonds**")
    a["bond_return"] = st.slider(
        "Mean Return (%)", 0.5, 8.0, a.get("bond_return", 3.5), 0.25, key="br",
        help="Expected annual return for fixed income. Current yields are a better predictor "
             "of near-term bond returns than historical averages. The 10-year Treasury yield "
             "is a useful anchor.")
    a["bond_volatility"] = st.slider(
        "Volatility / Standard Deviation (%)", 1.0, 15.0, a.get("bond_volatility", 6.0), 0.5, key="bv",
        help="Year-to-year variability in bond returns. Historically ~5–8% for intermediate "
             "bond funds. Longer-duration bonds have higher volatility.")
with mc3:
    st.markdown("**Cash / Stable Value**")
    a["cash_return"] = st.slider(
        "Return (%)", 0.0, 6.0, a.get("cash_return", 2.0), 0.25, key="cr",
        help="Return on cash equivalents: money market funds, savings accounts, TSP G fund, "
             "CDs. The TSP G fund has historically returned ~2–3%. No volatility is modeled "
             "for cash — it earns this rate deterministically each year.")
    a["stock_bond_correlation"] = st.slider(
        "Stock/Bond Correlation", -0.8, 0.5,
        a.get("stock_bond_correlation", -0.20), 0.05, key="corr",
        help="How stock and bond returns move relative to each other. Negative correlation "
             "(e.g., −0.20) means bonds tend to rise when stocks fall — the classic "
             "'flight to safety.' This diversification benefit is baked into every simulation "
             "via Cholesky decomposition. The 2022 environment (both fell together) represents "
             "a positive correlation regime, which you can model here.")

# ── Inflation ──────────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Inflation</div>", unsafe_allow_html=True)
ic1, ic2 = st.columns([2, 2])
with ic1:
    a["inflation_rate"] = st.slider(
        "Annual Inflation Rate (%)", 1.0, 6.0, a.get("inflation_rate", 3.0), 0.25, key="inf",
        help="The assumed long-run average inflation rate. Used to inflate spending targets "
             "each year, deflate projections into today's dollars, calculate FERS COLA, "
             "and adjust tax brackets. The Fed targets 2%; long-run US average is ~3%. "
             "Using 3–3.5% is a reasonable conservative assumption.")
with ic2:
    a["show_real_dollars"] = st.toggle(
        "Show inflation-adjusted (today's dollar) on charts by default",
        a.get("show_real_dollars", False), key="real_toggle",
        help="When on, all portfolio value charts are divided by the cumulative inflation "
             "factor to show purchasing power in today's dollars rather than future nominal "
             "dollars. You can also toggle this individually on each chart page.")
    real_stock = a["stock_return"] - a["inflation_rate"]
    st.markdown(f"""<div class='card' style='margin-top:6px;'>
        <div style='color:#8b949e;font-size:.82rem;text-transform:uppercase;'>Real Stock Return</div>
        <div style='font-size:1.6rem;font-weight:700;color:#00d4aa;'>{real_stock:.2f}%</div>
        <div style='color:#8b949e;font-size:.82rem;'>
            {a['stock_return']}% nominal − {a['inflation_rate']}% inflation<br>
            This is your true inflation-adjusted purchasing power growth.</div>
    </div>""", unsafe_allow_html=True)

# ── Simulation settings ────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Monte Carlo Settings</div>", unsafe_allow_html=True)
sc1, sc2 = st.columns(2)
with sc1:
    a["n_simulations"] = st.select_slider(
        "Number of Simulations",
        options=[200, 500, 1000, 2000, 5000],
        value=a.get("n_simulations", 1000), key="nsims",
        help="How many independent future scenarios to simulate. More simulations produce "
             "smoother, more stable percentile bands but take longer to compute. "
             "200–500: fast, slightly noisy. 1,000: good balance (recommended). "
             "2,000–5,000: publication quality, noticeably slower.")
with sc2:
    st.markdown("<div class='tip' style='margin-top:6px;'>"
                "Each simulation draws a unique sequence of annual returns from the "
                "log-normal distribution. The fan charts show the 5th, 10th, 25th, 50th, "
                "75th, 90th, and 95th percentile outcomes. The wider the fan, the more "
                "uncertainty in the projection.</div>", unsafe_allow_html=True)

# ── Planning Confidence Level ─────────────────────────────────────────────────
st.markdown("<div class='sh'>Planning Confidence Level</div>", unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "Controls which percentile is used as the <b>headline planning number</b> on "
            "the Accumulation and Scenarios pages. A higher confidence level means you are "
            "planning against a worse market scenario — your portfolio must be large enough "
            "to succeed even in that scenario. Fidelity defaults to 90% (significantly below "
            "average markets). The fan charts always show all percentile bands regardless of "
            "this setting.</div>", unsafe_allow_html=True)

CL_OPTIONS = {
    "p50": "50% — Median (average market conditions)",
    "p25": "75% — Conservative (below average markets)",
    "p10": "90% — Very Conservative (significantly below average, like Fidelity)",
}
cl_keys   = list(CL_OPTIONS.keys())
cl_labels = list(CL_OPTIONS.values())
cur_cl    = a.get("confidence_level", "p50")
cur_idx   = cl_keys.index(cur_cl) if cur_cl in cl_keys else 0

chosen_cl = st.radio(
    "Headline confidence level", cl_labels, index=cur_idx,
    key="conf_level",
    help="This changes which percentile line is shown as your 'expected' portfolio value "
         "in KPI cards and the savings optimizer. It does not change the fan chart bands.")
a["confidence_level"] = cl_keys[cl_labels.index(chosen_cl)]

cl_desc = {
    "p50": "In 50% of simulations, your portfolio will be **at or above** this value. "
           "This is the median — an optimistic planning number.",
    "p25": "In 75% of simulations, your portfolio will be **at or above** this value. "
           "Markets underperform average 25% of the time historically.",
    "p10": "In 90% of simulations, your portfolio will be **at or above** this value. "
           "This is Fidelity's default — conservative planning against bad market sequences.",
}
st.caption(cl_desc[a["confidence_level"]])

# ── Return distribution preview ────────────────────────────────────────────────
st.markdown("<div class='sh'>Return Distribution Preview</div>", unsafe_allow_html=True)

rng = np.random.default_rng(1)
stocks, bonds = _correlated_returns(
    10_000, 1,
    a["stock_return"]/100, a["stock_volatility"]/100,
    a["bond_return"]/100,  a["bond_volatility"]/100,
    a["stock_bond_correlation"], rng)
port = 0.70 * stocks[:, 0] + 0.25 * bonds[:, 0] + 0.05 * (a["cash_return"]/100)

p5, p50, p95 = np.percentile(port, 5), np.median(port), np.percentile(port, 95)

fig = go.Figure()
fig.add_trace(go.Histogram(
    x=port * 100, nbinsx=80,
    marker_color="rgba(0,212,170,0.6)",
    marker_line_color="#00d4aa", marker_line_width=0.25))
fig.add_vline(x=p50*100,  line_color="#e6edf3", line_dash="dash",
              annotation_text=f"Median: {p50*100:.1f}%",
              annotation_font_color="#e6edf3")
fig.add_vline(x=p5*100,   line_color="#f85149", line_dash="dot",
              annotation_text=f"P5: {p5*100:.1f}%",
              annotation_font_color="#f85149")
fig.add_vline(x=p95*100,  line_color="#3fb950", line_dash="dot",
              annotation_text=f"P95: {p95*100:.1f}%",
              annotation_font_color="#3fb950")
fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e6edf3"), height=300,
    xaxis=dict(title="Annual Portfolio Return (%)", gridcolor="#21262d"),
    yaxis=dict(title="Number of Simulations", gridcolor="#21262d"),
    showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
_add_crosshair(fig)
st.plotly_chart(fig, width='stretch')
st.caption(
    f"Distribution of single-year returns for a 70% stock / 25% bond / 5% cash portfolio "
    f"across 10,000 simulations using your current assumptions. "
    f"**Green dashed line (P95):** a great year ({p95*100:.1f}%). "
    f"**White dashed line (median):** the most likely outcome ({p50*100:.1f}%). "
    f"**Red dotted line (P5):** a bad year ({p5*100:.1f}%). "
    f"The spread of this histogram drives the width of the fan charts on later pages — "
    f"higher volatility leads to wider fan, which means more uncertainty."
)
