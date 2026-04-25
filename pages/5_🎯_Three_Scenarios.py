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
</style>""", unsafe_allow_html=True)

def fmt(v):   return f"${v:,.0f}"
def fmt_m(v):
    if abs(v) >= 1e6: return f"${v/1e6:.2f}M"
    if abs(v) >= 1e3: return f"${v/1e3:,.0f}K"
    return fmt(v)
def hfmt(v):  return f"&#36;{v:,.0f}"       # dollar sign as HTML entity (no LaTeX trigger)
def hfmt_m(v):
    if abs(v) >= 1e6: return f"&#36;{v/1e6:.2f}M"
    if abs(v) >= 1e3: return f"&#36;{v/1e3:,.0f}K"
    return hfmt(v)

st.markdown("## 🎯 Three Retirement Scenarios")
st.markdown("""<p style='color:#8b949e;'>
The core planning page. Compare
<span style='color:#3fb950;font-weight:600;'>Grow</span> ·
<span style='color:#79c0ff;font-weight:600;'>Sustain</span> ·
<span style='color:#f0883e;font-weight:600;'>Deplete</span>
outcomes across all simulations, see your income sources year by year,
and find out how much you need to save today to reach each target.
</p>""", unsafe_allow_html=True)

st.markdown("<div class='tip'>"
            "<b>How the three scenarios work:</b><br>"
            "• <b style='color:#3fb950;'>Grow:</b> You spend less than your portfolio earns. "
            "Balance increases throughout retirement. Leaves a larger estate but requires "
            "the most savings or lowest spending now.<br>"
            "• <b style='color:#79c0ff;'>Sustain:</b> Spending ≈ portfolio returns after inflation. "
            "Real balance stays roughly flat — a perpetuity. The 'sustainable withdrawal rate' scenario.<br>"
            "• <b style='color:#f0883e;'>Deplete:</b> You spend more than returns. Portfolio slowly "
            "draws down toward the reserve floor by the last survivor's life expectancy. "
            "Maximizes spending in retirement but requires the reserve never be breached."
            "</div>", unsafe_allow_html=True)

persons   = st.session_state.get("persons", [])
assumptions = st.session_state.get("assumptions", {})
scenarios = st.session_state.setdefault("scenarios", {
    "deplete_spending": 130_000, "sustain_spending": 105_000,
    "grow_spending": 80_000, "reserve_amount": 75_000,
})
gi = st.session_state.get("_guaranteed_income", {})

def build_income_sources():
    gi_   = st.session_state.get("_guaranteed_income", {})
    p0    = persons[0]
    fers  = p0.get("fers") or {}
    calc  = fers.get("_calc") or {}
    ss_p0 = p0.get("ss") or {}
    ss_p1 = (persons[1].get("ss") or {}) if len(persons) > 1 else {}
    inc_ss = st.session_state.get("include_ss", True)
    if p0.get("has_fers"):
        pension_annual    = gi_.get("pension", calc.get("pension_median", 0))
        supplement_annual = gi_.get("supplement", fers.get("_supplement_annual", 0))
        survivor_benefit  = (fers.get("survivor_option", "full") != "none")
        survivor_share    = {"none": 0.0, "partial": 0.25, "full": 0.50}.get(
                             fers.get("survivor_option", "full"), 0.50)
    else:
        pension_annual    = 0.0
        supplement_annual = 0.0
        survivor_benefit  = False
        survivor_share    = 0.0
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

if not persons:
    st.warning("Complete **Household Setup** first."); st.stop()

# Guaranteed income panel
pen  = gi.get("pension", 0)
supp = gi.get("supplement", 0)
ss   = gi.get("ss", 0)
gtot = gi.get("total", 0)
with st.expander("📋 Guaranteed Income Floor (from Pension & Income page)", expanded=True):
    gc = st.columns(4)
    gc[0].metric("FERS Pension",    fmt(pen)  + "/yr",
                  help="Annual pension at retirement. Does not depend on portfolio performance.")
    gc[1].metric("FERS Supplement", fmt(supp) + "/yr",
                  help="Paid until age 62. Zero for deferred retirees or those retiring at 62+.")
    gc[2].metric("Social Security", fmt(ss)   + "/yr",
                  help="Combined SS for both partners. Zero if excluded via the SS toggle.")
    gc[3].metric("Total Guaranteed", fmt(gtot) + "/yr",
                  help="Your income floor. The gap between this and your spending target "
                       "is what your portfolio must cover each year.")
    if gtot == 0:
        st.info("💡 Configure pension and SS on the **Pension & Income** page.")

st.markdown("---")

# SS exclusion notice
if not st.session_state.get("include_ss", True):
    st.markdown("<div style='background:rgba(240,136,62,0.1);border:1px solid rgba(240,136,62,0.3);"
                "border-radius:8px;padding:8px 14px;font-size:.88rem;color:#f0883e;margin-bottom:12px;'>"
                "⚠️ <b>Social Security is excluded</b> from income streams. "
                "Re-enable on the <b>Pension &amp; Income</b> page.</div>",
                unsafe_allow_html=True)

st.markdown("<div class='sh'>Spending Targets & Required Portfolio Analysis</div>",
            unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "<b>How to read the three scenarios:</b> All three start from the <i>same projected portfolio</i> "
            "at retirement. The difference is how much you spend each year. If you set all three "
            "spending amounts to the same value, all three panels will show identical results — "
            "that is expected and correct. Set them to three different spending levels to see "
            "the tradeoff between lifestyle and portfolio longevity.<br><br>"
            + ("⚠️ <b>SS excluded</b> from income — targets reflect pension-only floor. "
               if not st.session_state.get("include_ss", True) else
               "ℹ️ SS is <b>included</b> in income — toggle on Pension &amp; Income page to exclude.")
            + "</div>", unsafe_allow_html=True)

# Target portfolio analysis
# Always read guaranteed income live from session state — don't depend on stale scenario cache
_gi_live = st.session_state.get("_guaranteed_income", {})
include_ss = st.session_state.get("include_ss", True)
gtot_floor = (
    _gi_live.get("pension",    0) +
    _gi_live.get("supplement", 0) +
    (_gi_live.get("ss", 0) if include_ss else 0)
)
if gtot_floor == 0 and not _gi_live:
    st.info("💡 Visit **Pension & Income** first to load your guaranteed income floor. "
            "Without it, the analysis assumes your portfolio must cover the full spending target.")

ta1, ta2, ta3, ta4 = st.columns(4)
target_income = ta1.number_input(
    "Desired Annual Retirement Income ($)", 20_000, 500_000,
    int(scenarios.get("sustain_spending", 105_000)), 100,
    help="The total household income you want in retirement (today's dollars). "
         "The analysis below shows what portfolio size is required to fund the gap "
         "between this target and your guaranteed income, under each scenario approach.")
le_you_ta   = persons[0].get("life_expectancy", 87)
ret_you_ta  = assumptions.get("retirement_age_you", 62)
yrs_dist_ta = max(le_you_ta - ret_you_ta, 1)
real_ret_ta = (assumptions.get("stock_return", 7.0) - assumptions.get("inflation_rate", 3.0)) / 100
gap_ta      = max(target_income - gtot_floor, 0)

with st.expander("📐 How these numbers are calculated", expanded=False):
    st.markdown(f"""
**Step 1 — Portfolio gap:**
`Gap = Desired income − Guaranteed income floor`
`Gap = {hfmt(target_income)} − {hfmt(gtot_floor)} = {hfmt(gap_ta)}/yr`

The guaranteed floor is your pension + FERS supplement + Social Security (if included).
Your portfolio only needs to cover the *gap* — not the full spending target.

**Step 2 — Required portfolio by scenario** (real return = {real_ret_ta*100:.1f}%):

| Scenario | Formula | Required |
|---|---|---|
| 🌱 Grow | `Gap ÷ (real_r − 1%)` | Most capital — portfolio grows 1%/yr in real terms |
| ⚖️ Sustain | `Gap ÷ real_r` | Middle — perpetuity, balance never changes |
| 📉 Deplete | PV of annuity over {yrs_dist_ta} yrs + PV of reserve | Least capital — principal spent down |

**How the 4% rule fits in:**

The famous 4% rule says: `Portfolio needed = Annual income ÷ 4%`.
That is mathematically identical to the **Sustain** perpetuity formula when real return = 4%.
They are the same equation: `gap / 0.04`.

The Trinity Study (1998) found that this portfolio size gave a ~95% historical survival
rate over 30 years. "Survival" means the portfolio didn't hit zero — not that it stayed
flat. In many scenarios it shrank; in good ones it grew. The 4% rule is agnostic about
what happens to the balance; it only bounds the probability of ruin.

**Therefore:**
- **Grow** requires *more* than the 4% rule — you need extra capital to fund ongoing growth
- **Sustain** *equals* the 4% rule portfolio — same formula, `gap ÷ real_r`
- **Deplete** requires *less* than the 4% rule — you're spending principal over {yrs_dist_ta} years,
  so a smaller lump sum is sufficient (present value of a finite annuity, not a perpetuity)

The 5.9% withdrawal rate on Deplete is intentional: at that rate, the portfolio is
exhausted near life expectancy. The Monte Carlo fan charts on this page show the full
probability distribution; use those as your primary planning tool.

**Step 3 — P50 projected portfolio:**
Reads your median portfolio at retirement from the Accumulation Monte Carlo.
Run that page first for an accurate comparison.
""")  

ta2.markdown(f"""<div class='card'>
    <div class='kpi-label'>Guaranteed Income Floor</div>
    <div class='kpi' style='font-size:1.4rem;'>{hfmt(gtot_floor)}/yr</div>
    <div style='color:#8b949e;font-size:.82rem;'>Pension + SS (per current settings)</div>
</div>""", unsafe_allow_html=True)
ta3.markdown(f"""<div class='card'>
    <div class='kpi-label'>Portfolio Must Cover</div>
    <div class='kpi' style='font-size:1.4rem;color:#f0883e;'>{hfmt(gap_ta)}/yr</div>
    <div style='color:#8b949e;font-size:.82rem;'>Target − guaranteed income</div>
</div>""", unsafe_allow_html=True)
ta4.markdown(f"""<div class='card'>
    <div class='kpi-label'>Retirement Horizon</div>
    <div class='kpi' style='font-size:1.4rem;'>{yrs_dist_ta} yrs</div>
    <div style='color:#8b949e;font-size:.82rem;'>Age {ret_you_ta} → {le_you_ta}</div>
</div>""", unsafe_allow_html=True)

accum_now  = st.session_state.get("accum_result", {})
yr_idx_ta  = min(max(ret_you_ta - persons[0]["age"], 0), accum_now.get("n_years", 1))
cur_p50_ta = float(accum_now.get("pct_nom", {}).get("p50", [0]*200)[yr_idx_ta]) if accum_now else 0

req_cols = st.columns(3)
for col, (mode, label, color, desc) in zip(req_cols, [
    ("grow",    "🌱 Grow",    "#3fb950", "Portfolio grows — spend less than returns"),
    ("sustain", "⚖️ Sustain", "#79c0ff", "Portfolio flat — spend equals returns"),
    ("deplete", "📉 Deplete", "#f0883e", "Portfolio depletes to reserve by LE"),
]):
    req = estimate_needed_portfolio(gap_ta, yrs_dist_ta, real_ret_ta, mode,
                                     reserve=scenarios.get("reserve_amount", 75_000))
    shortfall = max(req - cur_p50_ta, 0)
    on_track  = shortfall < 1
    yrs_ret_ta = max(ret_you_ta - persons[0]["age"], 1)
    extra_ta   = additional_contribution_needed(req, cur_p50_ta, yrs_ret_ta, real_ret_ta)
    status_color = "#3fb950" if on_track else "#f0883e"
    status_text  = "✅ On track" if on_track else f"⚠️ Short by {hfmt_m(shortfall)}"
    with col:
        st.markdown(f"""<div class='card'>
            <div class='scenario-header' style='color:{color};'>{label}</div>
            <div style='color:#8b949e;font-size:.82rem;margin-bottom:10px;'>{desc}</div>
            <table style='width:100%;font-size:.88rem;'>
            <tr><td style='color:#8b949e;'>Required portfolio</td>
                <td style='text-align:right;font-weight:700;'>{hfmt_m(req)}</td></tr>
            <tr><td style='color:#8b949e;'>P50 projected</td>
                <td style='text-align:right;'>{hfmt_m(cur_p50_ta)}</td></tr>
            <tr><td style='color:#8b949e;'>Extra savings/yr</td>
                <td style='text-align:right;font-weight:700;color:{color};'>
                    {"—" if on_track else hfmt_m(extra_ta) + "/yr"}</td></tr>
            </table>
            <div style='margin-top:10px;font-size:.85rem;font-weight:600;
                color:{status_color};'>{status_text}</div>
        </div>""", unsafe_allow_html=True)

# Stale-data detection
def _fingerprint(persons, assumptions):
    key = json.dumps({
        "p": [(p.get("age"), str(p.get("accounts")), str(p.get("salaries"))) for p in persons],
        "a": assumptions,
    }, default=str, sort_keys=True)
    return hashlib.md5(key.encode()).hexdigest()[:10]

cur_fp = _fingerprint(persons, assumptions)
if ("scenario_fp" in st.session_state
        and st.session_state["scenario_fp"] != cur_fp
        and "scenario_results" in st.session_state):
    st.warning("⚠️ Inputs have changed since the last run. "
               "Click **Run All Three Scenarios** to refresh projections.")

# Auto-calculate scenario spending targets
accum_preview = st.session_state.get("accum_result", {})
ret_you_prev  = assumptions.get("retirement_age_you", 62)
age_you_prev  = persons[0].get("age", 40)
yr_prev       = min(max(ret_you_prev - age_you_prev, 0), accum_preview.get("n_years", 1))
cur_p50_prev  = float(accum_preview.get("pct_nom", {}).get("p50", [0]*200)[yr_prev]) \
                if accum_preview else 0
le_prev       = persons[0].get("life_expectancy", 87)
real_ret_prev = (assumptions.get("stock_return", 7.0)
                 - assumptions.get("inflation_rate", 3.0)) / 100
inc_prev      = st.session_state.get("scenario_income_src", {})
gtot_prev     = (inc_prev.get("pension_annual", 0)
                 + inc_prev.get("ss_you_annual", 0)
                 + inc_prev.get("ss_spouse_annual", 0))

if cur_p50_prev > 0:
    suggested = calculate_scenario_spending(
        portfolio_p50    = cur_p50_prev,
        guaranteed_income = gtot_prev,
        years_retirement  = max(le_prev - ret_you_prev, 1),
        real_return       = real_ret_prev,
        reserve           = scenarios.get("reserve_amount", 75_000),
    )
    with st.expander("💡 Auto-calculate scenario spending from your projected portfolio", expanded=False):
        st.markdown(
            f"Based on your **P50 projected portfolio of {fmt_m(cur_p50_prev)}** at retirement "
            f"and a real return of **{real_ret_prev*100:.1f}%**, here are the spending levels "
            f"that mathematically define each scenario:")
        ac1, ac2, ac3 = st.columns(3)
        ac1.metric("🌱 Grow", fmt(suggested["grow_spending"]) + "/yr",
                    help="Spending where portfolio grows in real terms (return - 0.5%)")
        ac2.metric("⚖️ Sustain", fmt(suggested["sustain_spending"]) + "/yr",
                    help="Spending equal to portfolio return — balance stays flat in real terms")
        ac3.metric("📉 Deplete", fmt(suggested["deplete_spending"]) + "/yr",
                    help="Annuity payment that draws portfolio to reserve by your life expectancy")
        if st.button("Apply these targets to the spending sliders below",
                      help="Overwrites the spending inputs with the calculated values."):
            scenarios["grow_spending"]    = int(suggested["grow_spending"])
            scenarios["sustain_spending"] = int(suggested["sustain_spending"])
            scenarios["deplete_spending"] = int(suggested["deplete_spending"])
            st.rerun()

# Spending sliders
st.markdown("<div class='sh'>Annual Spending Targets (Today's Dollars)</div>",
            unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "Set your target annual household spending in today's dollars. The simulation "
            "inflates these forward each year automatically. Start with your current spending "
            "and adjust for expected retirement lifestyle changes (no commuting costs, "
            "more travel, higher healthcare, etc.).</div>", unsafe_allow_html=True)

sc1, sc2, sc3, sc4 = st.columns(4)
scenarios["grow_spending"] = sc1.number_input(
    "🌱 Grow — Annual Spending ($)", 20_000, 500_000,
    int(scenarios.get("grow_spending", 80_000)), 100, key="grow_sp",
    help="Spending level where your portfolio grows in real terms. Withdrawals are less "
         "than portfolio returns minus inflation. Your estate grows over time.")
scenarios["sustain_spending"] = sc2.number_input(
    "⚖️ Sustain — Annual Spending ($)", 20_000, 500_000,
    int(scenarios.get("sustain_spending", 105_000)), 100, key="sus_sp",
    help="The 'perpetuity' spending level. Portfolio returns roughly equal withdrawals "
         "plus inflation, so real balance stays flat. Similar to a 3–4% safe withdrawal rate.")
scenarios["deplete_spending"] = sc3.number_input(
    "📉 Deplete — Annual Spending ($)", 20_000, 500_000,
    int(scenarios.get("deplete_spending", 130_000)), 100, key="dep_sp",
    help="Spending level that gradually draws down the portfolio. The goal is to reach "
         "the reserve floor near the end of the last survivor's life expectancy — "
         "maximizing spending while never running completely out.")
scenarios["reserve_amount"] = sc4.number_input(
    "🔒 Minimum Reserve ($)", 0, 500_000,
    int(scenarios.get("reserve_amount", 75_000)), 100, key="res_amt",
    help="A safety floor in today's dollars. Even in the Deplete scenario, the portfolio "
         "should never fall below this amount. Provides a buffer against unexpected expenses "
         "or living longer than expected. The probability of success metric is defined as "
         "never breaching this floor.")

disp1, disp2 = st.columns([1, 2])
use_real = disp1.toggle(
    "Today's Dollars", assumptions.get("show_real_dollars", False), key="sc_real",
    help="Show all portfolio values adjusted for inflation, in today's purchasing power.")
mc_type = disp2.radio(
    "Monte Carlo output", ["Fan Chart (percentile bands)", "Probability of Success"],
    horizontal=True, label_visibility="collapsed",
    help="Fan chart: shows the full range of simulation outcomes as percentile bands. "
         "Probability of success: summarizes results as a single percentage — the fraction "
         "of simulations where the portfolio never fell below the reserve floor.")

# Build income sources
run_btn = st.button("▶ Run All Three Scenarios", type="primary",
                     help="Runs the distribution Monte Carlo for all three spending targets "
                          "using your accumulation results as the starting portfolio.")

if run_btn or "scenario_results" not in st.session_state:
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
        initial    = accum["portfolio_paths"][:, min(yr_ret, accum["n_years"])]
        inc        = build_income_sources()
        le_you     = persons[0].get("life_expectancy", 87)
        le_spouse  = persons[1].get("life_expectancy", 90) if len(persons) > 1 else 87
        results    = {}
        for key, spend_key in [("grow","grow_spending"),
                                ("sustain","sustain_spending"),
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
    st.info("Click **Run All Three Scenarios** above."); st.stop()

inc = st.session_state.get("scenario_income_src", {})
labels   = {"grow":    ("🌱 Grow",    "#3fb950", "color:#3fb950"),
            "sustain": ("⚖️ Sustain", "#79c0ff", "color:#79c0ff"),
            "deplete": ("📉 Deplete", "#f0883e", "color:#f0883e")}
spend_map = {"grow": "grow_spending", "sustain": "sustain_spending", "deplete": "deplete_spending"}

# Summary cards
st.markdown("---")
st.markdown("<div class='sh'>Scenario Summary</div>", unsafe_allow_html=True)
sum_cols = st.columns(3)
for i, (key, (label, color, style)) in enumerate(labels.items()):
    res   = results[key]
    spend = scenarios[spend_map[key]]
    gap   = max(spend - inc.get("pension_annual",0)
                - inc.get("ss_you_annual",0) - inc.get("ss_spouse_annual",0), 0)
    final = res["pct_nom"]["p50"][-1]
    initial_p50 = res["pct_nom"]["p50"][0]

    # Check if behavior matches the label
    real_ret = (assumptions.get("stock_return", 7.0) - assumptions.get("inflation_rate", 3.0)) / 100
    sustain_threshold = initial_p50 * real_ret
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

    with sum_cols[i]:
        warn_color = "#3fb950" if behavior_warn.startswith("✅") else "#f0883e"
        warn_html  = (f"<div style='margin-top:8px;font-size:.8rem;"
                      f"color:{warn_color};'>{behavior_warn}</div>")
        st.markdown(f"""<div class='card'>
            <div class='scenario-header' style='{style};'>{label}</div>
            <div style='color:#8b949e;font-size:.85rem;margin-bottom:12px;'>
                Spend: <b style='color:#e6edf3;'>{hfmt(spend)}/yr</b>
                &nbsp;·&nbsp; Portfolio gap: <b style='color:#e6edf3;'>{hfmt(gap)}/yr</b>
            </div>
            <table style='width:100%;font-size:.9rem;'>
            <tr><td style='color:#8b949e;'>Final balance (median)</td>
                <td style='text-align:right;font-weight:600;color:{color};'>{hfmt_m(final)}</td></tr>
            <tr><td style='color:#8b949e;'>Probability of success</td>
                <td style='text-align:right;font-weight:600;color:{color};'>{res['prob_success']:.1f}%</td></tr>
            <tr><td style='color:#8b949e;'>Monthly budget</td>
                <td style='text-align:right;font-weight:600;color:{color};'>{hfmt(spend/12)}/mo</td></tr>
            </table>
            {warn_html}
        </div>""", unsafe_allow_html=True)

# Overlay chart
st.markdown("<div class='sh'>Portfolio Trajectories — All Three Scenarios</div>",
            unsafe_allow_html=True)
fig_overlay = multi_scenario_fan(results, use_real=use_real)
st.plotly_chart(fig_overlay, width='stretch')
st.caption(
    "All three scenarios plotted together using the same starting portfolio. "
    "Each colored band covers the 25th–75th percentile of simulations for that scenario; "
    "the solid line is the median. The vertical spread between scenarios shows the "
    "dollar impact of your spending choices. Where scenarios overlap, the outcomes are "
    "indistinguishable — market uncertainty dominates spending differences.")

# Individual charts
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
            st.metric("Probability of Success", f"{res['prob_success']:.1f}%",
                       help="Percentage of simulations where the portfolio never fell below "
                            "the reserve floor throughout the entire retirement horizon.")
else:
    gauge_cols = st.columns(3)
    for i, (key, (label, color, _)) in enumerate(labels.items()):
        with gauge_cols[i]:
            st.markdown(f"<div style='text-align:center;font-weight:600;color:#e6edf3;'>"
                        f"{label}</div>", unsafe_allow_html=True)
            fig_g = prob_gauge(results[key]["prob_success"], "Probability of Success", color)
            st.plotly_chart(fig_g, width='stretch')
            st.caption(f"Spending: {fmt(scenarios[spend_map[key]])}/yr · "
                       f"Monthly: {fmt(scenarios[spend_map[key]]/12)}/mo")

# Income waterfall
st.markdown("<div class='sh'>Income Breakdown — Sustain Scenario (Median)</div>",
            unsafe_allow_html=True)
sus_df  = results["sustain"]["income_df"]
inf_fac = results["sustain"]["inf_factors"]
fig_wf  = income_waterfall(sus_df, use_real=use_real,
                            inf_factors=inf_fac if use_real else None)
st.plotly_chart(fig_wf, width='stretch')
st.caption(
    "Stacked bar chart showing where your retirement income comes from each year. "
    "**Teal:** FERS pension (COLA-adjusted). "
    "**Purple:** FERS Supplement (stops at age 62). "
    "**Blue/Green:** Social Security for each partner (begins at their claim ages). "
    "**Amber:** The portion your portfolio must cover — the gap between guaranteed income "
    "and your spending target. A smaller amber bar means less portfolio risk.")

# Savings optimizer
st.markdown("<div class='sh'>Savings Rate Optimizer</div>", unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "Deterministic estimates of the portfolio needed at retirement for each scenario, "
            "compared to your P50 projected portfolio. Shows additional annual savings needed "
            "to close any gap. These are approximations — run the full Monte Carlo for "
            "accurate probability-of-success figures.</div>", unsafe_allow_html=True)

ret_you   = assumptions["retirement_age_you"]
age_you   = persons[0]["age"]
yrs_ret   = max(ret_you - age_you, 1)
real_ret  = (assumptions["stock_return"] - assumptions["inflation_rate"]) / 100
le_you    = persons[0].get("life_expectancy", 87)
yrs_dist  = le_you - ret_you
accum     = st.session_state.get("accum_result", {})
yr_idx    = min(max(ret_you - age_you, 0), accum.get("n_years", 1))
cur_p50   = float(accum.get("pct_nom", {}).get("p50", [0]*100)[yr_idx]) if accum else 0
gtot_inc  = (inc.get("pension_annual", 0) + inc.get("ss_you_annual", 0)
             + inc.get("ss_spouse_annual", 0))

oc1, oc2, oc3 = st.columns(3)
for col, (spend_key, label, mode, color) in zip(
    [oc1, oc2, oc3],
    [("grow_spending",    "🌱 Grow",    "grow",    "#3fb950"),
     ("sustain_spending", "⚖️ Sustain", "sustain", "#79c0ff"),
     ("deplete_spending", "📉 Deplete", "deplete", "#f0883e")]):
    spend  = scenarios[spend_key]
    gap    = max(spend - gtot_inc, 0)
    target = estimate_needed_portfolio(gap, yrs_dist, real_ret, mode,
                                        reserve=scenarios["reserve_amount"])
    extra  = additional_contribution_needed(target, cur_p50, yrs_ret, real_ret)
    deficit = max(target - cur_p50, 0)
    on_track = deficit < 1
    badge_color = "#3fb950" if on_track else "#f0883e"
    badge = "✅ On Track" if on_track else f"⚠️ Gap: {hfmt_m(deficit)}"
    with col:
        st.markdown(f"""<div class='card'>
            <div style='font-weight:700;color:{color};font-size:1.1rem;'>{label}</div>
            <div style='font-size:.82rem;color:#8b949e;margin:4px 0 10px 0;'>
                Spending: {hfmt(spend)}/yr</div>
            <table style='width:100%;font-size:.88rem;'>
            <tr><td style='color:#8b949e;'>Target at retirement</td>
                <td style='text-align:right;font-weight:600;'>{hfmt_m(target)}</td></tr>
            <tr><td style='color:#8b949e;'>P50 projected</td>
                <td style='text-align:right;font-weight:600;'>{hfmt_m(cur_p50)}</td></tr>
            <tr><td style='color:#8b949e;'>Extra savings needed</td>
                <td style='text-align:right;font-weight:700;color:{color};'>{hfmt_m(extra)}/yr</td></tr>
            </table>
            <div style='margin-top:10px;font-size:.82rem;color:{badge_color};
                font-weight:600;'>{badge}</div>
        </div>""", unsafe_allow_html=True)
