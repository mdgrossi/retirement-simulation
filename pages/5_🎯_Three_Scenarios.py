"""
Page 5 — Three Scenarios (Core Feature)
Grow / Sustain / Deplete scenario comparison with Monte Carlo.
"""

import streamlit as st
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.calculations import (
    run_accumulation_mc, run_distribution_mc,
    estimate_needed_portfolio, additional_contribution_needed, fers_cola_rate,
)
from utils.charts import fan_chart, multi_scenario_fan, income_waterfall, prob_gauge, SCENARIO_COLORS
import plotly.graph_objects as go

st.set_page_config(page_title="Three Scenarios", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.card  { background:#161b22; border:1px solid #21262d; border-radius:12px; padding:18px 22px; margin-bottom:14px; }
.sh { font-size:1.05rem; font-weight:600; color:#e6edf3; border-bottom:1px solid #21262d;
     padding-bottom:8px; margin:18px 0 12px 0; }
.kpi-big  { font-size:2rem; font-weight:700; line-height:1.1; }
.kpi-lbl  { font-size:0.78rem; color:#8b949e; text-transform:uppercase; letter-spacing:.05em; margin-top:4px;}
.scenario-header { font-size:1.3rem; font-weight:700; margin-bottom:4px; }
.grow-color    { color: #3fb950; }
.sustain-color { color: #79c0ff; }
.deplete-color { color: #f0883e; }
</style>""", unsafe_allow_html=True)

def fmt(v): return f"${v:,.0f}"
def fmt_m(v):
    if abs(v) >= 1e6: return f"${v/1e6:.2f}M"
    if abs(v) >= 1e3: return f"${v/1e3:,.0f}K"
    return fmt(v)

st.markdown("## 🎯 Three Retirement Scenarios")
st.markdown("""<p style='color:#8b949e;'>
Compare <span style='color:#3fb950;font-weight:600;'>Grow</span> ·
<span style='color:#79c0ff;font-weight:600;'>Sustain</span> ·
<span style='color:#f0883e;font-weight:600;'>Deplete</span> outcomes
with full Monte Carlo uncertainty bands and income source breakdown.
</p>""", unsafe_allow_html=True)

persons     = st.session_state.get("persons", [])
assumptions = st.session_state.get("assumptions", {})
scenarios   = st.session_state.setdefault("scenarios", {
    "deplete_spending": 130_000, "sustain_spending": 105_000,
    "grow_spending": 80_000, "reserve_amount": 75_000,
})
gi = st.session_state.get("_guaranteed_income", {})

if not persons:
    st.warning("Complete **Household Setup** first."); st.stop()

# ─── Guaranteed income panel ──────────────────────────────────────────────────
pen  = gi.get("pension", 0)
supp = gi.get("supplement", 0)
ss   = gi.get("ss", 0)
gtot = gi.get("total", 0)

with st.expander("📋 Guaranteed Income Floor (from Pension & Income page)", expanded=True):
    gc = st.columns(4)
    gc[0].metric("FERS Pension", fmt(pen) + "/yr")
    gc[1].metric("FERS Supplement (pre-62)", fmt(supp) + "/yr")
    gc[2].metric("Social Security (combined)", fmt(ss) + "/yr")
    gc[3].metric("Total Guaranteed", fmt(gtot) + "/yr",
                  help="Income regardless of portfolio performance")
    if gtot == 0:
        st.info("💡 Configure your pension and SS on the **Pension & Income** page "
                "to see how guaranteed income offsets portfolio withdrawals.")

st.markdown("---")

# SS status notice
if not st.session_state.get("include_ss", True):
    st.markdown("<div style='background:rgba(240,136,62,0.1);border:1px solid rgba(240,136,62,0.3);"
                "border-radius:8px;padding:8px 14px;font-size:.88rem;color:#f0883e;margin-bottom:12px;'>"
                "⚠️ <b>Social Security is excluded</b> from income streams. "
                "Re-enable on the <b>Pension &amp; Income</b> page.</div>",
                unsafe_allow_html=True)

# ─── Scenario spending sliders ────────────────────────────────────────────────
st.markdown("<div class='sh'>Annual Spending Targets (Today's Dollars)</div>", unsafe_allow_html=True)

sc1, sc2, sc3, sc4 = st.columns(4)
with sc1:
    scenarios["grow_spending"] = st.number_input(
        "🌱 Grow — Annual Spending ($)", 20_000, 500_000,
        int(scenarios.get("grow_spending", 80_000)), 1_000, key="grow_sp",
        help="Portfolio grows: spending < portfolio returns. Legacy building."
    )
with sc2:
    scenarios["sustain_spending"] = st.number_input(
        "⚖️ Sustain — Annual Spending ($)", 20_000, 500_000,
        int(scenarios.get("sustain_spending", 105_000)), 1_000, key="sus_sp",
        help="Portfolio stays flat in real terms: spending ≈ returns after inflation."
    )
with sc3:
    scenarios["deplete_spending"] = st.number_input(
        "📉 Deplete — Annual Spending ($)", 20_000, 500_000,
        int(scenarios.get("deplete_spending", 130_000)), 1_000, key="dep_sp",
        help="Portfolio gradually drawn down; last survivor has reserve at death."
    )
with sc4:
    scenarios["reserve_amount"] = st.number_input(
        "🔒 Minimum Reserve at Death ($)", 0, 500_000,
        int(scenarios.get("reserve_amount", 75_000)), 5_000, key="res_amt",
        help="Worst-case floor: even in the Deplete scenario, you never run completely out."
    )

display_options = st.columns([1, 1, 2])
with display_options[0]:
    use_real = st.toggle("Today's Dollars", assumptions.get("show_real_dollars", False), key="sc_real")
with display_options[1]:
    mc_type  = st.radio("MC output", ["Fan Chart (percentile bands)", "Probability of Success"],
                         horizontal=True, label_visibility="collapsed")

# ─── Run simulations ──────────────────────────────────────────────────────────
run_btn = st.button("▶ Run All Three Scenarios", type="primary")

def build_income_sources():
    """Collect income parameters from session state."""
    gi  = st.session_state.get("_guaranteed_income", {})
    p0  = persons[0]
    fers = p0.get("fers") or {}
    calc = fers.get("_calc") or {}
    ss_p0 = p0.get("ss") or {}
    ss_p1 = (persons[1].get("ss") or {}) if len(persons) > 1 else {}
    include_ss = st.session_state.get("include_ss", True)

    return {
        "pension_annual":      gi.get("pension", calc.get("pension_median", 0)),
        "supplement_annual":   gi.get("supplement", fers.get("_supplement_annual", 0)),
        "ss_you_annual":       ss_p0.get("_annual_benefit", 0) if include_ss else 0.0,
        "ss_spouse_annual":    ss_p1.get("_annual_benefit", 0) if include_ss else 0.0,
        "ss_you_start_age":    ss_p0.get("claim_age", 67),
        "ss_spouse_start_age": ss_p1.get("claim_age", 67),
        "survivor_benefit":    fers.get("survivor_benefit", True),
        "reserve_amount":      scenarios.get("reserve_amount", 75_000),
    }

if run_btn or "scenario_results" not in st.session_state:
    # Get or run accumulation
    with st.spinner("Running Monte Carlo simulations…"):
        if "accum_result" not in st.session_state:
            accum = run_accumulation_mc(persons, assumptions, seed=42)
            st.session_state["accum_result"] = accum
        accum = st.session_state["accum_result"]

        ret_you    = assumptions["retirement_age_you"]
        ret_spouse = assumptions["retirement_age_spouse"]
        age_you    = persons[0]["age"]
        age_spouse = persons[1]["age"] if len(persons) > 1 else age_you
        yr_ret     = max(ret_you - age_you, 0)

        initial_sims = accum["portfolio_paths"][:, min(yr_ret, accum["n_years"])]
        income_src   = build_income_sources()
        le_you       = persons[0].get("life_expectancy", 87)
        le_spouse    = persons[1].get("life_expectancy", 90) if len(persons) > 1 else 87

        results = {}
        for key, spend_key in [("grow", "grow_spending"), ("sustain", "sustain_spending"), ("deplete", "deplete_spending")]:
            spending = scenarios[spend_key]
            res = run_distribution_mc(
                initial_sims=initial_sims,
                income_sources=income_src,
                assumptions=assumptions,
                retirement_age_you=ret_you,
                retirement_age_spouse=ret_spouse,
                life_exp_you=le_you,
                life_exp_spouse=le_spouse,
                annual_spending=spending,
                reserve_amount=scenarios["reserve_amount"],
                seed=99,
            )
            results[key] = res

        st.session_state["scenario_results"] = results
        st.session_state["scenario_income_src"] = income_src

results = st.session_state.get("scenario_results")
if not results:
    st.info("Click **Run All Three Scenarios** above.")
    st.stop()

income_src = st.session_state.get("scenario_income_src", {})

# ─── Summary row ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("<div class='sh'>Scenario Summary</div>", unsafe_allow_html=True)

labels = {"grow": ("🌱 Grow", "#3fb950", "grow-color"),
          "sustain": ("⚖️ Sustain", "#79c0ff", "sustain-color"),
          "deplete": ("📉 Deplete", "#f0883e", "deplete-color")}
spend_map = {"grow": "grow_spending", "sustain": "sustain_spending", "deplete": "deplete_spending"}

sum_cols = st.columns(3)
for i, (key, (label, color, cls)) in enumerate(labels.items()):
    res     = results[key]
    spend   = scenarios[spend_map[key]]
    gap     = max(spend - income_src.get("pension_annual", 0)
                  - income_src.get("ss_you_annual", 0) - income_src.get("ss_spouse_annual", 0), 0)
    pct_nom = res["pct_nom"]
    final   = pct_nom["p50"][-1]

    with sum_cols[i]:
        st.markdown(f"""<div class='card'>
            <div class='scenario-header {cls}'>{label}</div>
            <div style='color:#8b949e;font-size:.85rem;margin-bottom:12px;'>
                Target spend: <b style='color:#e6edf3;'>{fmt(spend)}/yr</b>
                &nbsp;·&nbsp; Portfolio gap: <b style='color:#e6edf3;'>{fmt(gap)}/yr</b>
            </div>
            <table style='width:100%;font-size:.9rem;'>
            <tr><td style='color:#8b949e;'>Final balance (median)</td>
                <td style='text-align:right;font-weight:600;color:{color};'>{fmt_m(final)}</td></tr>
            <tr><td style='color:#8b949e;'>Prob. of success</td>
                <td style='text-align:right;font-weight:600;color:{color};'>{res["prob_success"]:.1f}%</td></tr>
            <tr><td style='color:#8b949e;'>Monthly budget</td>
                <td style='text-align:right;font-weight:600;color:{color};'>{fmt(spend/12)}/mo</td></tr>
            </table>
        </div>""", unsafe_allow_html=True)

# ─── Overlay chart ────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Portfolio Trajectories — All Three Scenarios</div>", unsafe_allow_html=True)
fig_overlay = multi_scenario_fan(results, use_real=use_real)
st.plotly_chart(fig_overlay, width='stretch')

# ─── Individual scenario charts ───────────────────────────────────────────────
if mc_type == "Fan Chart (percentile bands)":
    cols = st.columns(3)
    for i, (key, (label, color, cls)) in enumerate(labels.items()):
        res  = results[key]
        pcts = res["pct_real"] if use_real else res["pct_nom"]
        ages = res["ages_you"]
        with cols[i]:
            fig = fan_chart(pcts=pcts, x=ages, title=label, color=color,
                             x_label="Your Age", y_label="Portfolio Value",
                             x_is_age=True)
            # Reserve line
            inf_f = res["inf_factors"]
            reserve_nom = scenarios["reserve_amount"] * (1 if use_real else inf_f[-1])
            # Draw horizontal dashed line at reserve
            fig.add_hline(y=scenarios["reserve_amount"] if use_real else scenarios["reserve_amount"] * inf_f[-1],
                          line_dash="dot", line_color="#f85149",
                          annotation_text="Reserve floor", annotation_font_color="#f85149")
            fig.update_layout(height=380)
            st.plotly_chart(fig, width='stretch')
            st.metric("Probability of Success", f"{res['prob_success']:.1f}%")
else:
    # Probability gauges
    gauge_cols = st.columns(3)
    for i, (key, (label, color, _)) in enumerate(labels.items()):
        with gauge_cols[i]:
            st.markdown(f"<div style='text-align:center;font-weight:600;color:#e6edf3;'>{label}</div>",
                         unsafe_allow_html=True)
            fig_g = prob_gauge(results[key]["prob_success"], "Probability of Success", color)
            st.plotly_chart(fig_g, width='stretch')
            st.markdown(f"<div style='text-align:center;color:#8b949e;font-size:.85rem;'>"
                        f"Spending: {fmt(scenarios[spend_map[key]])}/yr</div>", unsafe_allow_html=True)

# ─── Income breakdown (median scenario) ──────────────────────────────────────
st.markdown("<div class='sh'>Income Breakdown — Sustain Scenario (Median)</div>", unsafe_allow_html=True)
sus_df  = results["sustain"]["income_df"]
inf_fac = results["sustain"]["inf_factors"]
fig_wf  = income_waterfall(sus_df, use_real=use_real,
                            inf_factors=inf_fac if use_real else None)
st.plotly_chart(fig_wf, width='stretch')

# ─── What savings rate achieves each scenario? ────────────────────────────────
st.markdown("<div class='sh'>Savings Rate Optimizer</div>", unsafe_allow_html=True)
st.caption("Deterministic estimate of additional annual savings needed to hit each scenario target at the P50 level.")

from utils.calculations import estimate_needed_portfolio, additional_contribution_needed

ret_you   = assumptions["retirement_age_you"]
age_you   = persons[0]["age"]
yrs_ret   = max(ret_you - age_you, 1)
real_ret  = (assumptions["stock_return"] - assumptions["inflation_rate"]) / 100
le_you    = persons[0].get("life_expectancy", 87)
yrs_dist  = le_you - ret_you

accum = st.session_state.get("accum_result", {})
yr_idx = min(max(ret_you - age_you, 0), accum.get("n_years", 1))
current_p50 = float(accum.get("pct_nom", {}).get("p50", [0]*100)[yr_idx]) if accum else 0

gtot = income_src.get("pension_annual", 0) + income_src.get("ss_you_annual", 0) + income_src.get("ss_spouse_annual", 0)

oc1, oc2, oc3 = st.columns(3)
for col, (key, label, mode, color) in zip(
    [oc1, oc2, oc3],
    [("grow_spending", "🌱 Grow", "grow", "#3fb950"),
     ("sustain_spending", "⚖️ Sustain", "sustain", "#79c0ff"),
     ("deplete_spending", "📉 Deplete", "deplete", "#f0883e")]
):
    spend  = scenarios[key]
    gap    = max(spend - gtot, 0)
    target = estimate_needed_portfolio(gap, yrs_dist, real_ret, mode,
                                        reserve=scenarios["reserve_amount"])
    extra  = additional_contribution_needed(target, current_p50, yrs_ret, real_ret)
    deficit = max(target - current_p50, 0)
    with col:
        on_track = deficit < 1
        badge = "✅ On Track" if on_track else f"⚠️ Gap: {fmt_m(deficit)}"
        badge_color = "#3fb950" if on_track else "#f0883e"
        st.markdown(f"""<div class='card'>
            <div style='font-weight:700;color:{color};font-size:1.1rem;'>{label}</div>
            <div style='font-size:.82rem;color:#8b949e;margin:4px 0 10px 0;'>Spending: {fmt(spend)}/yr</div>
            <table style='width:100%;font-size:.88rem;'>
            <tr><td style='color:#8b949e;'>Target Portfolio at Retire</td>
                <td style='text-align:right;font-weight:600;'>{fmt_m(target)}</td></tr>
            <tr><td style='color:#8b949e;'>P50 Projected at Retire</td>
                <td style='text-align:right;font-weight:600;'>{fmt_m(current_p50)}</td></tr>
            <tr><td style='color:#8b949e;'>Add'l Annual Savings Needed</td>
                <td style='text-align:right;font-weight:700;color:{color};'>{fmt_m(extra)}/yr</td></tr>
            </table>
            <div style='margin-top:10px;font-size:.82rem;color:{badge_color};font-weight:600;'>{badge}</div>
        </div>""", unsafe_allow_html=True)
