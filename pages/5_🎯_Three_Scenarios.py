"""Page 5 — Three Scenarios"""

import streamlit as st
import numpy as np
import sys, os, hashlib, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.calculations import (run_accumulation_mc, run_distribution_mc,
                                 estimate_needed_portfolio, additional_contribution_needed,
                                 calculate_scenario_spending)
from utils.charts import fan_chart, multi_scenario_fan, income_waterfall, prob_gauge, SCENARIO_COLORS
import plotly.graph_objects as go

st.set_page_config(page_title="Three Scenarios", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:18px 22px;margin-bottom:14px;}
.sh{font-size:1.05rem;font-weight:600;color:#e6edf3;border-bottom:1px solid #21262d;padding-bottom:8px;margin:18px 0 12px 0;}
.tip{background:rgba(0,212,170,0.07);border:1px solid rgba(0,212,170,0.2);border-radius:8px;
     padding:10px 14px;font-size:.85rem;color:#8b949e;margin-bottom:14px;}
.scenario-header{font-size:1.3rem;font-weight:700;margin-bottom:4px;}
.divider{border-top:1px solid #21262d;margin:8px 0;}
</style>""", unsafe_allow_html=True)

def fmt(v):   return f"\${v:,.0f}"
def fmt_m(v):
    if abs(v) >= 1e6: return f"\${v/1e6:.2f}M"
    if abs(v) >= 1e3: return f"\${v/1e3:,.0f}K"
    return fmt(v)
def hfmt(v):  return f"&#36;{v:,.0f}"
def hfmt_m(v):
    if abs(v) >= 1e6: return f"&#36;{v/1e6:.2f}M"
    if abs(v) >= 1e3: return f"&#36;{v/1e3:,.0f}K"
    return hfmt(v)

# ── State ────────────────────────────────────────────────────────────────────
persons     = st.session_state.get("persons", [])
assumptions = st.session_state.get("assumptions", {})
scenarios   = st.session_state.setdefault("scenarios", {
    "deplete_spending": 130_000, "sustain_spending": 105_000,
    "grow_spending": 80_000, "reserve_amount": 75_000,
})

if not persons:
    st.warning("Complete **Household Setup** first."); st.stop()

# ── Income sources helper ─────────────────────────────────────────────────────
def build_income_sources():
    gi_    = st.session_state.get("_guaranteed_income", {})
    p0     = persons[0]
    fers   = p0.get("fers") or {}
    calc   = fers.get("_calc") or {}
    ss_p0  = p0.get("ss") or {}
    ss_p1  = (persons[1].get("ss") or {}) if len(persons) > 1 else {}
    inc_ss = st.session_state.get("include_ss", True)
    if p0.get("has_fers"):
        pension_annual    = gi_.get("pension", calc.get("pension_median", 0))
        supplement_annual = gi_.get("supplement", fers.get("_supplement_annual", 0))
        survivor_benefit  = (fers.get("survivor_option", "full") != "none")
        survivor_share    = {"none": 0.0, "partial": 0.25, "full": 0.50}.get(
                             fers.get("survivor_option", "full"), 0.50)
    else:
        pension_annual = supplement_annual = 0.0
        survivor_benefit = False
        survivor_share   = 0.0
    return {
        "pension_annual":      pension_annual,
        "supplement_annual":   supplement_annual,
        "ss_you_annual":       ss_p0.get("_annual_benefit", 0) if inc_ss else 0.0,
        "ss_spouse_annual":    ss_p1.get("_annual_benefit", 0) if inc_ss else 0.0,
        "ss_you_start_age":    ss_p0.get("claim_age", 67),
        "ss_spouse_start_age": ss_p1.get("claim_age", 67),
        "survivor_benefit":    survivor_benefit,
        "survivor_share":      survivor_share,
        "reserve_amount":      scenarios.get("reserve_amount", 75_000),
    }

inc = st.session_state.get("scenario_income_src") or build_income_sources()

# ── Fingerprint for stale detection ──────────────────────────────────────────
def _fingerprint(p, a):
    key = json.dumps({
        "p": [(x.get("age"), str(x.get("accounts")), str(x.get("salaries"))) for x in p],
        "a": a,
    }, default=str, sort_keys=True)
    return hashlib.md5(key.encode()).hexdigest()[:10]

cur_fp = _fingerprint(persons, assumptions)

# ── Confidence level ──────────────────────────────────────────────────────────
cl       = assumptions.get("confidence_level", "p50")
cl_label = {"p50": "Median (P50)", "p25": "P25 — 75% confidence",
            "p10": "P10 — 90% confidence"}[cl]
cl_pct   = {"p50": "50%", "p25": "75%", "p10": "90%"}[cl]

# ── Common derived values ─────────────────────────────────────────────────────
ret_you    = assumptions.get("retirement_age_you", 62)
ret_spouse = assumptions.get("retirement_age_spouse", 60)
age_you    = persons[0]["age"]
le_you     = persons[0].get("life_expectancy", 87)
le_spouse  = persons[1].get("life_expectancy", 90) if len(persons) > 1 else 87
yrs_ret    = max(ret_you - age_you, 1)
yrs_dist   = max(le_you - ret_you, 1)
real_ret   = (assumptions.get("stock_return", 7.0) - assumptions.get("inflation_rate", 3.0)) / 100

# Guaranteed income (always live from session state)
_gi_live   = st.session_state.get("_guaranteed_income", {})
include_ss = st.session_state.get("include_ss", True)
gtot_floor = (
    _gi_live.get("pension",    0) +
    _gi_live.get("supplement", 0) +
    (_gi_live.get("ss", 0) if include_ss else 0)
)

# Projected portfolio at retirement (at confidence level)
accum   = st.session_state.get("accum_result", {})
yr_idx  = min(max(ret_you - age_you, 0), accum.get("n_years", 1))
cur_proj = float(accum.get("pct_nom", {}).get(cl, [0]*200)[yr_idx]) if accum else 0

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("## 🎯 Three Retirement Scenarios")
st.markdown("""<p style='color:#8b949e;'>
Compare <span style='color:#3fb950;font-weight:600;'>Grow</span> ·
<span style='color:#79c0ff;font-weight:600;'>Sustain</span> ·
<span style='color:#f0883e;font-weight:600;'>Deplete</span>
— three different spending levels against the same projected portfolio.
Each scenario answers: <i>if I spend this much, what does my financial future look like?</i>
</p>""", unsafe_allow_html=True)

st.markdown("<div class='tip'>"
            "• <b style='color:#3fb950;'>Grow:</b> Spend less than your portfolio earns — balance "
            "increases in real terms. Leaves a larger estate; requires the most capital or lowest spending.<br>"
            "• <b style='color:#79c0ff;'>Sustain:</b> Spending ≈ portfolio returns. Real balance stays "
            "flat indefinitely — equivalent to the '4% rule' portfolio at 4% real return.<br>"
            "• <b style='color:#f0883e;'>Deplete:</b> Spend more than returns. Portfolio drawn toward "
            "the reserve floor by life expectancy. Maximizes spending; requires the least upfront capital."
            "</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — SETUP
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Step 1 — Your Guaranteed Income Floor</div>",
            unsafe_allow_html=True)
st.caption("This income arrives every year regardless of market performance. "
           "Your portfolio only needs to cover the gap between this and your spending target.")

gi = st.session_state.get("_guaranteed_income", {})
gc1, gc2, gc3, gc4 = st.columns(4)
gc1.metric("FERS Pension",             fmt(gi.get("pension",    0)) + "/yr",
            help="Annual pension at retirement. Does not depend on portfolio performance.")
gc2.metric("FERS Supplement (pre-62)", fmt(gi.get("supplement", 0)) + "/yr",
            help="Paid until age 62. Zero for deferred retirees or those retiring at 62+.")
gc3.metric("Social Security",          fmt(gi.get("ss", 0))       + "/yr",
            help="Combined Social Security for both partners. Zero if excluded via the toggle.")
gc4.metric("Total Guaranteed Floor",   fmt(gtot_floor)            + "/yr",
            help="The gap between this and your spending target is what your portfolio must cover.")

if not include_ss:
    st.markdown("<div style='background:rgba(240,136,62,0.1);border:1px solid rgba(240,136,62,0.3);"
                "border-radius:8px;padding:8px 14px;font-size:.88rem;color:#f0883e;margin-bottom:4px;'>"
                "⚠️ <b>Social Security excluded</b> — toggle on the Pension &amp; Income page to include it.</div>",
                unsafe_allow_html=True)
if not _gi_live:
    st.info("💡 Visit **Pension & Income** first to load your guaranteed income floor.")

st.markdown("<div class='sh'>Step 2 — Set Spending Targets</div>", unsafe_allow_html=True)
st.caption("Annual household spending in today's dollars, inflated forward automatically. "
           "Set three different levels to see the tradeoff. "
           "Use the auto-calculate button below to derive mathematically consistent targets "
           "from your projected portfolio.")

sc1, sc2, sc3, sc4 = st.columns(4)
scenarios["grow_spending"] = sc1.number_input(
    "🌱 Grow ($)", 20_000, 500_000, int(scenarios.get("grow_spending", 80_000)), 100,
    key="grow_sp",
    help="Portfolio grows — withdrawals < returns. Your estate increases over time.")
scenarios["sustain_spending"] = sc2.number_input(
    "⚖️ Sustain ($)", 20_000, 500_000, int(scenarios.get("sustain_spending", 105_000)), 100,
    key="sus_sp",
    help="Portfolio flat — withdrawals ≈ returns after inflation. Equivalent to the 4% rule "
         "portfolio at 4% real return.")
scenarios["deplete_spending"] = sc3.number_input(
    "📉 Deplete ($)", 20_000, 500_000, int(scenarios.get("deplete_spending", 130_000)), 100,
    key="dep_sp",
    help="Portfolio depletes toward reserve floor by life expectancy. Maximum sustainable "
         "spending without running out.")
scenarios["reserve_amount"] = sc4.number_input(
    "🔒 Reserve ($)", 0, 500_000, int(scenarios.get("reserve_amount", 75_000)), 100,
    key="res_amt",
    help="Minimum balance to maintain even in the Deplete scenario. A safety buffer against "
         "living longer than expected or unexpected expenses. Success is never breaching this floor.")

# Auto-calculate button
if cur_proj > 0:
    suggested = calculate_scenario_spending(
        portfolio_p50     = cur_proj,
        guaranteed_income = gtot_floor,
        years_retirement  = yrs_dist,
        real_return       = real_ret,
        reserve           = scenarios.get("reserve_amount", 75_000),
    )
    with st.expander(f"💡 Auto-calculate spending targets from projected portfolio ({cl_label}: {fmt_m(cur_proj)})",
                     expanded=False):
        st.caption(f"Based on your {cl_label} projected portfolio of {fmt_m(cur_proj)} at retirement, "
                   f"a real return of {real_ret*100:.1f}%, and a {yrs_dist}-year horizon.")
        ac1, ac2, ac3 = st.columns(3)
        ac1.metric("🌱 Grow", fmt(suggested["grow_spending"]) + "/yr",
                    help="Portfolio grows 1% per year in real terms")
        ac2.metric("⚖️ Sustain", fmt(suggested["sustain_spending"]) + "/yr",
                    help="Balance stays flat in real terms — perpetuity formula")
        ac3.metric("📉 Deplete", fmt(suggested["deplete_spending"]) + "/yr",
                    help="Present value annuity that exhausts portfolio to reserve by life expectancy")
        if st.button("↩ Apply these targets to the inputs above"):
            scenarios["grow_spending"]    = int(suggested["grow_spending"])
            scenarios["sustain_spending"] = int(suggested["sustain_spending"])
            scenarios["deplete_spending"] = int(suggested["deplete_spending"])
            st.rerun()
else:
    st.caption("Run **Accumulation** first to enable auto-calculate spending targets.")

st.markdown("<div class='sh'>Step 3 — Run the Simulation</div>", unsafe_allow_html=True)

disp1, disp2, disp3 = st.columns([1, 2, 1])
use_real = disp1.toggle(
    "Show Today's Dollars", assumptions.get("show_real_dollars", False), key="sc_real",
    help="Show all portfolio values in today's purchasing power.")
mc_type = disp2.radio(
    "Chart type", ["Fan Chart (percentile bands)", "Probability of Success"],
    horizontal=True, label_visibility="collapsed",
    help="Fan chart: shows the full range of outcomes as percentile bands. "
         "Gauge: single probability-of-success percentage per scenario.")

if ("scenario_fp" in st.session_state
        and st.session_state["scenario_fp"] != cur_fp
        and "scenario_results" in st.session_state):
    st.warning("⚠️ Inputs have changed since the last run — click Run to refresh.")

run_btn = st.button("▶ Run All Three Scenarios", type="primary",
                     help="Runs the distribution Monte Carlo for all three spending targets.")

if run_btn or "scenario_results" not in st.session_state:
    with st.spinner("Running Monte Carlo simulations…"):
        if "accum_result" not in st.session_state:
            st.session_state["accum_result"] = run_accumulation_mc(persons, assumptions, seed=42)
        accum_r  = st.session_state["accum_result"]
        yr_ret   = max(ret_you - age_you, 0)
        initial  = accum_r["portfolio_paths"][:, min(yr_ret, accum_r["n_years"])]
        inc      = build_income_sources()
        results  = {}
        for key, spend_key in [("grow","grow_spending"), ("sustain","sustain_spending"),
                                ("deplete","deplete_spending")]:
            results[key] = run_distribution_mc(
                initial_sims=initial, income_sources=inc, assumptions=assumptions,
                retirement_age_you=ret_you, retirement_age_spouse=ret_spouse,
                life_exp_you=le_you, life_exp_spouse=le_spouse,
                annual_spending=scenarios[spend_key],
                reserve_amount=scenarios["reserve_amount"], seed=99)
        st.session_state["scenario_results"]    = results
        st.session_state["scenario_income_src"] = inc
        st.session_state["scenario_fp"]         = cur_fp

results = st.session_state.get("scenario_results")
if not results:
    st.info("Configure your spending targets above, then click **Run All Three Scenarios**.")
    st.stop()

inc = st.session_state.get("scenario_income_src", {})

# Refresh projected portfolio after possible new accum run
accum   = st.session_state.get("accum_result", {})
yr_idx  = min(max(ret_you - age_you, 0), accum.get("n_years", 1))
cur_proj = float(accum.get("pct_nom", {}).get(cl, [0]*200)[yr_idx]) if accum else 0
gtot_inc = (inc.get("pension_annual", 0) + inc.get("ss_you_annual", 0)
            + inc.get("ss_spouse_annual", 0))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — RESULTS: UNIFIED SCENARIO CARDS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Results — Scenario Comparison</div>", unsafe_allow_html=True)
st.caption(f"All three scenarios use the same starting portfolio ({cl_label}: {fmt_m(cur_proj)} at retirement). "
           f"Spending targets differ; everything else is identical. "
           f"Confidence level: **{cl_label}**. Change on Assumptions page.")

labels   = {"grow":    ("🌱 Grow",    "#3fb950", "color:#3fb950"),
            "sustain": ("⚖️ Sustain", "#79c0ff", "color:#79c0ff"),
            "deplete": ("📉 Deplete", "#f0883e", "color:#f0883e")}
spend_map = {"grow": "grow_spending", "sustain": "sustain_spending", "deplete": "deplete_spending"}
sum_cols  = st.columns(3)

for i, (key, (label, color, style)) in enumerate(labels.items()):
    res   = results[key]
    spend = scenarios[spend_map[key]]
    gap   = max(spend - gtot_inc, 0)
    final = (res["pct_real"] if use_real else res["pct_nom"])["p50"][-1]

    # Deterministic target portfolio
    target  = estimate_needed_portfolio(gap, yrs_dist, real_ret, key,
                                         reserve=scenarios["reserve_amount"])
    deficit = max(target - cur_proj, 0)
    on_track = deficit < 1
    extra   = additional_contribution_needed(target, cur_proj, yrs_ret, real_ret)

    # Behavior sanity check
    sustain_threshold = cur_proj * real_ret
    if key == "grow" and gap >= sustain_threshold:
        behavior_warn = "⚠️ Spending too high to grow — portfolio will shrink"
    elif key == "sustain" and abs(gap - sustain_threshold) > sustain_threshold * 0.20:
        behavior_warn = ("⚠️ Spending too high — portfolio will shrink"
                         if gap > sustain_threshold else
                         "⚠️ Spending too low — portfolio will grow")
    elif key == "deplete" and final > scenarios.get("reserve_amount", 75_000) * 3:
        behavior_warn = "⚠️ Portfolio too large to deplete — use auto-calculate above"
    else:
        behavior_warn = "✅ On track"

    status_color = "#3fb950" if on_track else "#f0883e"
    warn_color   = "#3fb950" if behavior_warn.startswith("✅") else "#f0883e"
    warn_html    = (f"<div style='margin-top:6px;font-size:.8rem;color:{warn_color};'>"
                    f"{behavior_warn}</div>")

    with sum_cols[i]:
        st.markdown(f"""<div class='card'>
            <div class='scenario-header' style='{style};'>{label}</div>
            <div style='color:#8b949e;font-size:.85rem;margin-bottom:10px;'>
                {hfmt(spend)}/yr &nbsp;·&nbsp; {hfmt(spend/12)}/mo
            </div>
            <div class='divider'></div>
            <div style='font-size:.75rem;color:#8b949e;text-transform:uppercase;
                letter-spacing:.05em;margin:8px 0 4px;'>Portfolio gap</div>
            <div style='font-size:.95rem;margin-bottom:8px;'>
                <b style='color:#e6edf3;'>{hfmt(gap)}/yr</b>
                <span style='color:#8b949e;font-size:.82rem;'> after guaranteed income</span>
            </div>
            <div class='divider'></div>
            <div style='font-size:.75rem;color:#8b949e;text-transform:uppercase;
                letter-spacing:.05em;margin:8px 0 4px;'>Portfolio target</div>
            <table style='width:100%;font-size:.88rem;margin-bottom:6px;'>
            <tr><td style='color:#8b949e;'>Required (deterministic)</td>
                <td style='text-align:right;font-weight:700;'>{hfmt_m(target)}</td></tr>
            <tr><td style='color:#8b949e;'>Projected ({cl_label})</td>
                <td style='text-align:right;'>{hfmt_m(cur_proj)}</td></tr>
            <tr><td style='color:#8b949e;'>Extra savings needed</td>
                <td style='text-align:right;font-weight:700;color:{status_color};'>
                {"—" if on_track else hfmt_m(extra) + "/yr"}</td></tr>
            </table>
            <div class='divider'></div>
            <div style='font-size:.75rem;color:#8b949e;text-transform:uppercase;
                letter-spacing:.05em;margin:8px 0 4px;'>Monte Carlo outcome</div>
            <table style='width:100%;font-size:.88rem;'>
            <tr><td style='color:#8b949e;'>Final balance (median)</td>
                <td style='text-align:right;font-weight:600;color:{color};'>{hfmt_m(final)}</td></tr>
            <tr><td style='color:#8b949e;'>Probability of success</td>
                <td style='text-align:right;font-weight:600;color:{color};'>{res['prob_success']:.1f}%</td></tr>
            </table>
            {warn_html}
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — CHARTS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Portfolio Trajectories</div>", unsafe_allow_html=True)
fig_overlay = multi_scenario_fan(results, use_real=use_real)
st.plotly_chart(fig_overlay, width='stretch')
st.caption(
    "All three scenarios plotted from the same starting portfolio. "
    "Shaded bands cover the 25th–75th percentile of Monte Carlo simulations; "
    "solid lines are medians. Where scenarios overlap, market uncertainty dominates "
    "spending differences — the choice of spending level matters less than it appears.")

if mc_type == "Fan Chart (percentile bands)":
    cols = st.columns(3)
    for i, (key, (label, color, _)) in enumerate(labels.items()):
        res  = results[key]
        pcts = res["pct_real"] if use_real else res["pct_nom"]
        ages = res["ages_you"]
        with cols[i]:
            fig = fan_chart(pcts=pcts, x=ages, title=label, color=color,
                             x_label="Your Age", y_label="Portfolio Value", x_is_age=True)
            inf_f = res["inf_factors"]
            floor = scenarios["reserve_amount"] if use_real else scenarios["reserve_amount"] * inf_f[-1]
            fig.add_hline(y=floor, line_dash="dot", line_color="#f85149",
                          annotation_text="Reserve floor", annotation_font_color="#f85149")
            fig.update_layout(height=380)
            st.plotly_chart(fig, width='stretch')
else:
    gauge_cols = st.columns(3)
    for i, (key, (label, color, _)) in enumerate(labels.items()):
        with gauge_cols[i]:
            st.markdown(f"<div style='text-align:center;font-weight:600;color:#e6edf3;'>"
                        f"{label}</div>", unsafe_allow_html=True)
            fig_g = prob_gauge(results[key]["prob_success"], "Probability of Success", color)
            st.plotly_chart(fig_g, width='stretch')
            st.caption(f"{fmt(scenarios[spend_map[key]])}/yr · {fmt(scenarios[spend_map[key]]/12)}/mo")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — INCOME BREAKDOWN
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Income Sources — Sustain Scenario</div>", unsafe_allow_html=True)
st.caption("Where your retirement income comes from each year, using the Sustain scenario spending level. "
           "The amber bar is the portfolio withdrawal needed on top of guaranteed income.")
sus_df  = results["sustain"]["income_df"]
inf_fac = results["sustain"]["inf_factors"]
fig_wf  = income_waterfall(sus_df, use_real=use_real,
                            inf_factors=inf_fac if use_real else None)
st.plotly_chart(fig_wf, width='stretch')

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — METHODOLOGY (collapsed)
# ─────────────────────────────────────────────────────────────────────────────
with st.expander("📐 How are these numbers calculated?", expanded=False):
    gap_ta = max(scenarios.get("sustain_spending", 105_000) - gtot_floor, 0)
    st.markdown(f"""
**Portfolio gap** = Desired spending − Guaranteed income floor

Your portfolio only needs to cover the gap — not your full spending target.
At the Sustain level: {fmt(scenarios.get('sustain_spending', 105_000))} − {fmt(gtot_floor)} = **{fmt(gap_ta)}/yr**

**Required portfolio formulas** (real return = {real_ret*100:.1f}%):

| Scenario | Formula | Concept |
|---|---|---|
| 🌱 Grow | `Gap ÷ (return − 1%)` | Portfolio grows 1% per year in real terms |
| ⚖️ Sustain | `Gap ÷ return` | Perpetuity — balance never changes |
| 📉 Deplete | Present Value of {yrs_dist}-year annuity + Present Value of reserve | Principal spent down to reserve |

**The 4% rule** (`Portfolio = Income ÷ 4%`) is mathematically identical to the
Sustain formula when real return = 4%. The Trinity Study found this portfolio size
had a ~95% historical survival rate over 30 years — meaning the balance may shrink,
but the portfolio doesn't hit zero. Grow requires more capital; Deplete requires less.

**Projected portfolio** uses the **{cl_label}** from the Accumulation Monte Carlo —
meaning {cl_pct} of simulations produce a portfolio at or above this value.
Change the confidence level on the Assumptions page to match Fidelity (90%) or use
the median (50%) for an optimistic baseline.
""")