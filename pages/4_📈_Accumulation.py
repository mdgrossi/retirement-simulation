"""
Page 4 — Accumulation
Monte Carlo portfolio growth from now to retirement.
"""

import streamlit as st
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.calculations import run_accumulation_mc
from utils.charts import fan_chart, stacked_account_area

st.set_page_config(page_title="Accumulation", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.card { background:#161b22; border:1px solid #21262d; border-radius:12px; padding:18px 22px; margin-bottom:14px; }
.kpi { font-size:1.8rem; font-weight:700; color:#00d4aa; }
.kpi-label { font-size:0.8rem; color:#8b949e; text-transform:uppercase; letter-spacing:.05em; }
</style>""", unsafe_allow_html=True)

def fmt_m(v):
    if v >= 1e6: return f"${v/1e6:.2f}M"
    if v >= 1e3: return f"${v/1e3:,.0f}K"
    return f"${v:,.0f}"

st.markdown("## 📈 Accumulation Phase")
st.markdown("<p style='color:#8b949e;'>Monte Carlo projection of portfolio growth from today to retirement. "
            "Includes all accounts, salary growth, and contribution scaling.</p>", unsafe_allow_html=True)

persons     = st.session_state.get("persons", [])
assumptions = st.session_state.get("assumptions", {})

if not persons:
    st.warning("Set up your household first on the Household Setup page.")
    st.stop()

# ── Controls
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    use_real = st.toggle("Show Today's Dollars (inflation-adjusted)",
                          assumptions.get("show_real_dollars", False))
with c2:
    show_spaghetti = st.toggle("Show sample simulation paths", False,
                                help="Shows 50 individual simulation paths behind the fan chart.")

run_btn = st.button("▶ Run Accumulation Monte Carlo", type="primary")

if run_btn or "accum_result" not in st.session_state:
    with st.spinner(f"Running {assumptions.get('n_simulations',1000):,} simulations…"):
        result = run_accumulation_mc(persons, assumptions, seed=42)
        st.session_state["accum_result"] = result

result = st.session_state.get("accum_result")
if not result:
    st.info("Click **Run Accumulation Monte Carlo** to generate projections.")
    st.stop()

n_years  = result["n_years"]
age_you  = persons[0]["age"]
ages     = np.arange(age_you, age_you + n_years + 1)
ret_age  = assumptions.get("retirement_age_you", 62)
pcts     = result["pct_real"] if use_real else result["pct_nom"]

# ── KPI row at retirement year
yr_at_retire = max(ret_age - age_you, 0)
yr_idx = min(yr_at_retire, n_years)

k1, k2, k3, k4 = st.columns(4)
suffix = " (today's $)" if use_real else ""
with k1:
    st.markdown(f"""<div class='card'>
        <div class='kpi-label'>Portfolio at Retirement (Median){suffix}</div>
        <div class='kpi'>{fmt_m(pcts['p50'][yr_idx])}</div>
        <div style='color:#8b949e;font-size:.82rem;'>
            P10: {fmt_m(pcts['p10'][yr_idx])} · P90: {fmt_m(pcts['p90'][yr_idx])}
        </div>
    </div>""", unsafe_allow_html=True)
with k2:
    total_now = sum(a["balance"] for p in persons for a in p.get("accounts", []))
    st.markdown(f"""<div class='card'>
        <div class='kpi-label'>Current Total Portfolio</div>
        <div class='kpi'>{fmt_m(total_now)}</div>
        <div style='color:#8b949e;font-size:.82rem;'>Across all accounts</div>
    </div>""", unsafe_allow_html=True)
with k3:
    total_contrib = sum(
        a.get("annual_contribution", 0) + a.get("employer_match", 0)
        for p in persons for a in p.get("accounts", [])
    )
    st.markdown(f"""<div class='card'>
        <div class='kpi-label'>Annual Contributions (today)</div>
        <div class='kpi'>{fmt_m(total_contrib)}</div>
        <div style='color:#8b949e;font-size:.82rem;'>Scales with salary growth</div>
    </div>""", unsafe_allow_html=True)
with k4:
    sal_p50 = result["salary_p50"]
    final_sal = sal_p50[min(yr_at_retire, len(sal_p50)-1)]
    st.markdown(f"""<div class='card'>
        <div class='kpi-label'>Salary at Retirement (Median)</div>
        <div class='kpi'>{fmt_m(final_sal)}</div>
        <div style='color:#8b949e;font-size:.82rem;'>Combined household</div>
    </div>""", unsafe_allow_html=True)

st.markdown("")

# ── Fan chart
fig = fan_chart(
    x       = ages,
    pcts    = pcts,
    title   = "Portfolio Growth to Retirement  (Today's Dollars)" if use_real else "Portfolio Growth to Retirement",
    color   = "#00d4aa",
    x_label = "Your Age",
    y_label = "Portfolio Value",
    x_is_age=True,
)

# Retirement marker
fig.add_vline(x=ret_age, line_dash="dash", line_color="#8b949e",
              annotation_text=f"Retire age {ret_age}", annotation_font_color="#8b949e")

# Spaghetti paths (50 random sims)
if show_spaghetti:
    paths = result["portfolio_real"] if use_real else result["portfolio_paths"]
    idx = np.random.default_rng(0).choice(result["n_sims"], size=min(50, result["n_sims"]), replace=False)
    for i in idx:
        fig.add_trace(
            __import__("plotly.graph_objects", fromlist=["Scatter"]).Scatter(
                x=ages, y=paths[i],
                line=dict(color="rgba(0,212,170,0.08)", width=1),
                showlegend=False, hoverinfo="skip",
            )
        )

st.plotly_chart(fig, width='stretch')

# ── Account breakdown
st.markdown("### Account Breakdown (Median)")
fig2 = stacked_account_area(result["acct_medians"], ages, use_real=use_real)
fig2.add_vline(x=ret_age, line_dash="dash", line_color="#8b949e")
st.plotly_chart(fig2, width='stretch')

# ── Salary trajectory
st.markdown("### Salary Trajectory (Median)")
import plotly.graph_objects as go
fig3 = go.Figure()
sal_real = result["salary_p50"] / result["inf_factors"]
fig3.add_trace(go.Scatter(x=ages[:len(result["salary_p50"])], y=result["salary_p50"],
                           name="Combined Household (nominal)",
                           line=dict(color="#f0883e", width=2)))
fig3.add_trace(go.Scatter(x=ages[:len(sal_real)], y=sal_real,
                           name="Combined Household (today's $)",
                           line=dict(color="#f0883e", width=2, dash="dash")))

# FERS person salary separately (used for pension high-3)
fers_person = next((p for p in persons if p.get("has_fers")), None)
if fers_person and "fers_salary_p50" in result:
    fig3.add_trace(go.Scatter(
        x=ages[:len(result["fers_salary_p50"])],
        y=result["fers_salary_p50"],
        name=f"{fers_person['name']} only — pension high-3 source (nominal)",
        line=dict(color="#00d4aa", width=2, dash="dot")))

fig3.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e6edf3"), xaxis=dict(title="Age", gridcolor="#21262d"),
    yaxis=dict(title="Salary", tickformat="$,.0f", gridcolor="#21262d"),
    legend=dict(bgcolor="rgba(22,27,34,0.8)", bordercolor="#21262d", borderwidth=1),
)
st.plotly_chart(fig3, width='stretch')

st.caption(
    "🏛️ **Pension note:** The teal dotted line shows the FERS person's individual salary — "
    "this is the trajectory used to compute the **high-3** for pension calculations. "
    "The high-3 is the average of the final 3 years of that line before retirement. "
    "The orange combined line is for contribution scaling only."
)

# Save final portfolio distribution for use in scenarios
st.session_state["_final_portfolio_sims"] = result["final_portfolio_sims"]
