"""Page 6 — Spend-Down & Survivor Analysis"""

import streamlit as st
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.calculations import run_distribution_mc, fers_cola_rate
from utils.charts import fan_chart, income_waterfall, prob_gauge
import plotly.graph_objects as go

st.set_page_config(page_title="Spend-Down", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:18px 22px;margin-bottom:14px;}
.kpi{font-size:1.8rem;font-weight:700;color:#00d4aa;}
.kpi-label{font-size:0.8rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;}
.sh{font-size:1.05rem;font-weight:600;color:#e6edf3;border-bottom:1px solid #21262d;
    padding-bottom:8px;margin:16px 0 12px 0;}
.danger{background:rgba(248,81,73,0.1);border:1px solid rgba(248,81,73,0.3);
        border-radius:8px;padding:10px 14px;font-size:.88rem;color:#f85149;}
</style>""", unsafe_allow_html=True)

def fmt(v):   return f"${v:,.0f}"
def fmt_m(v):
    if abs(v) >= 1e6: return f"${v/1e6:.2f}M"
    if abs(v) >= 1e3: return f"${v/1e3:,.0f}K"
    return fmt(v)

st.markdown("## 📉 Spend-Down & Survivor Analysis")
st.markdown("<p style='color:#8b949e;'>Year-by-year retirement drawdown with income waterfall, "
            "sequence-of-returns risk, and dual-life survivor modeling.</p>",
            unsafe_allow_html=True)

persons     = st.session_state.get("persons", [])
assumptions = st.session_state.get("assumptions", {})
scenarios   = st.session_state.get("scenarios", {})
gi          = st.session_state.get("_guaranteed_income", {})

if not persons:
    st.warning("Complete **Household Setup** first."); st.stop()

if "accum_result" not in st.session_state:
    st.warning("Run the **Accumulation** page first to generate a starting portfolio."); st.stop()

# ── Parameters ────────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Spend-Down Parameters</div>", unsafe_allow_html=True)

p1, p2, p3 = st.columns(3)
annual_spend = p1.number_input(
    "Annual Spending Target (today's $)", 20_000, 500_000,
    int(scenarios.get("sustain_spending", 105_000)), 100,
    help="The total household spending you want to model. Inflation-adjusted each year.")

reserve = p2.number_input(
    "Minimum Reserve ($)", 0, 500_000,
    int(scenarios.get("reserve_amount", 75_000)), 100,
    help="Floor balance — success means never dropping below this in today's dollars.")

use_real = p3.toggle("Show Today's Dollars", assumptions.get("show_real_dollars", False))

# Allocation in retirement
st.markdown("<div class='sh'>Retirement Portfolio Allocation</div>", unsafe_allow_html=True)
al1, al2, al3 = st.columns(3)
ws = al1.slider("Stocks %", 0, 100, 50) / 100
wb = al2.slider("Bonds %",  0, 100, 40) / 100
wc = al3.slider("Cash %",   0, 100, 10) / 100
if abs(ws + wb + wc - 1.0) > 0.02:
    st.warning(f"⚠️ Allocation sums to {(ws+wb+wc)*100:.0f}% — should be 100%.")

# ── Income sources ────────────────────────────────────────────────────────────
def build_income_sources():
    p0   = persons[0]
    fers = p0.get("fers") or {}
    calc = fers.get("_calc") or {}
    ss0  = p0.get("ss") or {}
    ss1  = (persons[1].get("ss") or {}) if len(persons) > 1 else {}
    include_ss = st.session_state.get("include_ss", True)
    return {
        "pension_annual":      gi.get("pension", calc.get("pension_median", 0)),
        "supplement_annual":   gi.get("supplement", fers.get("_supplement_annual", 0)),
        "ss_you_annual":       ss0.get("_annual_benefit", 0) if include_ss else 0.0,
        "ss_spouse_annual":    ss1.get("_annual_benefit", 0) if include_ss else 0.0,
        "ss_you_start_age":    ss0.get("claim_age", 67),
        "ss_spouse_start_age": ss1.get("claim_age", 67),
        "survivor_benefit":    (fers.get("survivor_option", "full") != "none"),
        "survivor_share":      {"none": 0.0, "partial": 0.25, "full": 0.50}.get(
                                fers.get("survivor_option", "full"), 0.50),
    }

# ── Run ───────────────────────────────────────────────────────────────────────
run_btn = st.button("▶ Run Spend-Down Monte Carlo", type="primary")

if run_btn or "spenddown_result" not in st.session_state:
    accum       = st.session_state["accum_result"]
    ret_you     = assumptions["retirement_age_you"]
    ret_spouse  = assumptions["retirement_age_spouse"]
    age_you     = persons[0]["age"]
    yr_ret      = min(max(ret_you - age_you, 0), accum["n_years"])
    initial_sims = accum["portfolio_paths"][:, yr_ret]
    inc          = build_income_sources()
    le_you       = persons[0].get("life_expectancy", 87)
    le_spouse    = (persons[1].get("life_expectancy", 90)
                   if len(persons) > 1 else 87)

    with st.spinner(f"Running {assumptions.get('n_simulations',1000):,} simulations…"):
        result = run_distribution_mc(
            initial_sims           = initial_sims,
            income_sources         = inc,
            assumptions            = assumptions,
            retirement_age_you     = ret_you,
            retirement_age_spouse  = ret_spouse,
            life_exp_you           = le_you,
            life_exp_spouse        = le_spouse,
            annual_spending        = annual_spend,
            reserve_amount         = reserve,
            seed                   = 77,
        )
        result["_ws"] = ws
        result["_wb"] = wb
        result["_wc"] = wc
        st.session_state["spenddown_result"] = result
        st.session_state["spenddown_income"]  = inc

res = st.session_state.get("spenddown_result")
if not res:
    st.info("Click **Run Spend-Down Monte Carlo** above."); st.stop()

inc      = st.session_state.get("spenddown_income", {})
pcts     = res["pct_real"] if use_real else res["pct_nom"]
ages_you = res["ages_you"]
inf_fac  = res["inf_factors"]
df_inc   = res["income_df"]

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
final_med = float(pcts["p50"][-1])
final_p10 = float(pcts["p10"][-1])

k1.markdown(f"""<div class='card'>
    <div class='kpi-label'>Final Balance (Median)</div>
    <div class='kpi'>{fmt_m(final_med)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>P10: {fmt_m(final_p10)}</div>
</div>""", unsafe_allow_html=True)

k2.markdown(f"""<div class='card'>
    <div class='kpi-label'>Probability of Success</div>
    <div class='kpi'>{res['prob_success']:.1f}%</div>
    <div style='color:#8b949e;font-size:.82rem;'>Never below {fmt_m(reserve)} reserve</div>
</div>""", unsafe_allow_html=True)

guaranteed_total = (inc.get("pension_annual", 0)
                   + inc.get("ss_you_annual", 0)
                   + inc.get("ss_spouse_annual", 0))
portfolio_gap = max(annual_spend - guaranteed_total, 0)

k3.markdown(f"""<div class='card'>
    <div class='kpi-label'>Guaranteed Income Floor</div>
    <div class='kpi'>{fmt_m(guaranteed_total)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>Portfolio gap: {fmt_m(portfolio_gap)}/yr</div>
</div>""", unsafe_allow_html=True)

k4.markdown(f"""<div class='card'>
    <div class='kpi-label'>Retirement Horizon</div>
    <div class='kpi'>{res['n_years']} yrs</div>
    <div style='color:#8b949e;font-size:.82rem;'>
        Age {ages_you[0]} → {ages_you[-1]}
    </div>
</div>""", unsafe_allow_html=True)

# ── Portfolio fan chart ───────────────────────────────────────────────────────
st.markdown("<div class='sh'>Portfolio Value Through Retirement</div>", unsafe_allow_html=True)

title = "Portfolio Spend-Down  (Today's Dollars)" if use_real else "Portfolio Spend-Down"
fig = fan_chart(pcts=pcts, x=ages_you, title=title, color="#00d4aa",
                x_label="Your Age", y_label="Portfolio Value", x_is_age=True)

# Reserve floor line
reserve_line = np.full(len(ages_you), reserve) if use_real else reserve * inf_fac
fig.add_trace(go.Scatter(
    x=ages_you, y=reserve_line[:len(ages_you)],
    name="Reserve Floor", line=dict(color="#f85149", width=1.5, dash="dot"),
    hovertemplate="<b>Age %{x}</b><br>Reserve: %{customdata}<extra></extra>",
    customdata=[fmt_m(v) for v in reserve_line[:len(ages_you)]],
))

# Life expectancy markers
le_you    = persons[0].get("life_expectancy", 87)
le_spouse = persons[1].get("life_expectancy", 90) if len(persons) > 1 else 87
fig.add_vline(x=le_you, line_dash="dash", line_color="#79c0ff",
              annotation_text=f"{persons[0]['name']} LE: {le_you}",
              annotation_font_color="#79c0ff")
if len(persons) > 1:
    fig.add_vline(x=le_spouse + (persons[1]["age"] - persons[0]["age"]),
                  line_dash="dash", line_color="#bc8cff",
                  annotation_text=f"{persons[1]['name']} LE: {le_spouse}",
                  annotation_font_color="#bc8cff")

# Sequence-of-returns danger zone (first 7 years)
danger_end = ages_you[min(7, len(ages_you)-1)]
fig.add_vrect(x0=ages_you[0], x1=danger_end,
              fillcolor="rgba(248,81,73,0.06)", line_width=0,
              annotation_text="Sequence risk zone", annotation_position="top left",
              annotation_font_color="#f85149", annotation_font_size=11)

st.plotly_chart(fig, width='stretch')

st.markdown("""<div class='danger'>
⚠️ <b>Sequence-of-Returns Risk:</b> A severe market downturn in the first 5–7 years of retirement
can permanently impair your portfolio even if long-run returns are fine. The shaded zone above
highlights this period. Consider holding 1–2 years of spending in cash as a buffer.
</div>""", unsafe_allow_html=True)

# ── Income waterfall ──────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Annual Income Sources</div>", unsafe_allow_html=True)
fig_wf = income_waterfall(df_inc, use_real=use_real,
                           inf_factors=inf_fac if use_real else None)
st.plotly_chart(fig_wf, width='stretch')

# ── Survivor analysis ─────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Survivor Analysis</div>", unsafe_allow_html=True)

surv_option = (persons[0].get("fers") or {}).get("survivor_option", "full")
surv_share  = {"none": 0.0, "partial": 0.25, "full": 0.50}.get(surv_option, 0.50)
pen_annual  = inc.get("pension_annual", 0)
ss_you      = inc.get("ss_you_annual", 0)
ss_sp       = inc.get("ss_spouse_annual", 0)

# Income before and after each death
income_both    = pen_annual + ss_you + ss_sp + inc.get("supplement_annual", 0)
income_you_die = pen_annual * surv_share + ss_sp  # you die first
income_sp_die  = pen_annual + ss_you               # spouse dies first

sa1, sa2, sa3 = st.columns(3)
sa1.markdown(f"""<div class='card'>
    <div class='kpi-label'>Both Alive</div>
    <div class='kpi' style='color:#3fb950;'>{fmt(income_both)}/yr</div>
    <div style='color:#8b949e;font-size:.82rem;'>Guaranteed income floor</div>
</div>""", unsafe_allow_html=True)

sa2.markdown(f"""<div class='card'>
    <div class='kpi-label'>If You Die First</div>
    <div class='kpi' style='color:#f0883e;'>{fmt(income_you_die)}/yr</div>
    <div style='color:#8b949e;font-size:.82rem;'>
        {surv_share*100:.0f}% pension + spouse SS
        &nbsp;(−{fmt(income_both - income_you_die)}/yr)
    </div>
</div>""", unsafe_allow_html=True)

sa3.markdown(f"""<div class='card'>
    <div class='kpi-label'>If Spouse Dies First</div>
    <div class='kpi' style='color:#f0883e;'>{fmt(income_sp_die)}/yr</div>
    <div style='color:#8b949e;font-size:.82rem;'>
        Full pension + your SS
        &nbsp;(−{fmt(income_both - income_sp_die)}/yr)
    </div>
</div>""", unsafe_allow_html=True)

# ── Year-by-year table ────────────────────────────────────────────────────────
with st.expander("📋 Year-by-Year Income Detail"):
    display_df = df_inc.copy()
    if use_real:
        for col in ["pension", "supplement", "ss_you", "ss_spouse",
                    "portfolio_withdrawal", "total_spend"]:
            display_df[col] = display_df[col] / inf_fac[:len(display_df)]

    display_df = display_df.rename(columns={
        "age_you": "Your Age", "pension": "Pension",
        "supplement": "FERS Supp.", "ss_you": "SS (You)",
        "ss_spouse": "SS (Spouse)", "portfolio_withdrawal": "Portfolio Draw",
        "total_spend": "Total Spend",
    })
    for col in ["Pension", "FERS Supp.", "SS (You)", "SS (Spouse)",
                "Portfolio Draw", "Total Spend"]:
        display_df[col] = display_df[col].apply(fmt)
    st.dataframe(display_df[["Your Age", "Pension", "FERS Supp.", "SS (You)",
                               "SS (Spouse)", "Portfolio Draw", "Total Spend"]],
                 width='stretch', hide_index=True)

# ── Probability gauge ─────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Probability of Success</div>", unsafe_allow_html=True)
gc1, gc2 = st.columns([1, 2])
with gc1:
    color = "#3fb950" if res["prob_success"] >= 80 else \
            "#f0883e" if res["prob_success"] >= 60 else "#f85149"
    fig_g = prob_gauge(res["prob_success"], "Money outlasts both lives", color)
    st.plotly_chart(fig_g, width='stretch')
with gc2:
    st.markdown(f"""
**Interpreting this number:**
- **≥ 90%** — Very high confidence. Consider whether you're over-saving.
- **80–90%** — Strong plan. Typical target for most financial advisors.
- **70–80%** — Acceptable with flexibility to adjust spending in bad markets.
- **< 70%** — Consider increasing savings, delaying retirement, or reducing spending.

Your current spending target is **{fmt(annual_spend)}/yr** in today's dollars.
Your guaranteed income covers **{fmt(guaranteed_total)}/yr**, leaving a portfolio gap of **{fmt(portfolio_gap)}/yr**.
""")
