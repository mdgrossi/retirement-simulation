"""Page 4 — Accumulation"""

import streamlit as st
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.calculations import run_accumulation_mc
from utils.charts import fan_chart, stacked_account_area, _add_crosshair
import plotly.graph_objects as go

st.set_page_config(page_title="Accumulation", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:18px 22px;margin-bottom:14px;}
.kpi{font-size:1.8rem;font-weight:700;color:#00d4aa;}
.kpi-label{font-size:0.8rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;}
.tip{background:rgba(0,212,170,0.07);border:1px solid rgba(0,212,170,0.2);border-radius:8px;
     padding:10px 14px;font-size:.85rem;color:#8b949e;margin-bottom:14px;}
</style>""", unsafe_allow_html=True)

def fmt_m(v):
    if v >= 1e6: return f"${v/1e6:.2f}M"
    if v >= 1e3: return f"${v/1e3:,.0f}K"
    return f"${v:,.0f}"

st.markdown("## 📈 Accumulation Phase")
st.markdown("<p style='color:#8b949e;'>Monte Carlo projection of your combined household "
            "portfolio from today to retirement. Contributions scale with salary growth, "
            "and each account's individual allocation is respected.</p>",
            unsafe_allow_html=True)

persons     = st.session_state.get("persons", [])
assumptions = st.session_state.get("assumptions", {})

if not persons:
    st.warning("Set up your household first on the **Household Setup** page."); st.stop()

st.markdown("<div class='tip'>"
            "Click <b>Run Accumulation Monte Carlo</b> after changing any settings on the "
            "Household Setup or Assumptions pages. Results are cached until you re-run. "
            "The fan chart shows 1,000 (or your chosen number of) independent future scenarios — "
            "the shaded bands represent the range of likely outcomes, not a single prediction."
            "</div>", unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    use_real = st.toggle(
        "Show Today's Dollars", assumptions.get("show_real_dollars", False),
        help="Divide all portfolio values by the cumulative inflation factor to show "
             "purchasing power in today's dollars rather than future nominal dollars.")
with c2:
    show_spaghetti = st.toggle(
        "Show sample paths", False,
        help="Overlay 50 individual simulation paths behind the fan chart. Useful for "
             "seeing the range and shape of individual outcomes, including the rare "
             "catastrophic and exceptional runs.")


import hashlib, json

def _fingerprint(persons, assumptions):
    key = json.dumps({
        "p": [(p.get("age"), str(p.get("accounts")), str(p.get("salaries"))) for p in persons],
        "a": assumptions,
    }, default=str, sort_keys=True)
    return hashlib.md5(key.encode()).hexdigest()[:10]

cur_fp = _fingerprint(persons, assumptions)
if ("accum_fp" in st.session_state
        and st.session_state["accum_fp"] != cur_fp
        and "accum_result" in st.session_state):
    st.warning("⚠️ Inputs have changed since the last run. "
               "Click **Run Accumulation Monte Carlo** to refresh.")

run_btn = st.button("▶ Run Accumulation Monte Carlo", type="primary",
                     help=f"Runs {assumptions.get('n_simulations',1000):,} simulations. "
                          "Re-run after changing accounts, salaries, or assumptions.")

if run_btn or "accum_result" not in st.session_state:
    with st.spinner(f"Running {assumptions.get('n_simulations',1000):,} simulations…"):
        result = run_accumulation_mc(persons, assumptions, seed=42)
        st.session_state["accum_result"] = result
        st.session_state["accum_fp"]     = cur_fp

result = st.session_state.get("accum_result")
if not result:
    st.info("Click **Run Accumulation Monte Carlo** above to generate projections."); st.stop()

n_years = result["n_years"]
age_you = persons[0]["age"]
ages    = np.arange(age_you, age_you + n_years + 1)
ret_age = assumptions.get("retirement_age_you", 62)
pcts    = result["pct_real"] if use_real else result["pct_nom"]

yr_at_retire = max(ret_age - age_you, 0)
yr_idx       = min(yr_at_retire, n_years)

# Confidence level — which percentile is the headline planning number
cl       = assumptions.get("confidence_level", "p50")
cl_label = {"p50": "Median (P50)", "p25": "P25 — 75% confidence", "p10": "P10 — 90% confidence"}[cl]
cl_pct   = {"p50": "50%", "p25": "75%", "p10": "90%"}[cl]

# KPIs
k1, k2, k3, k4 = st.columns(4)
suffix = " (today's $)" if use_real else ""
k1.markdown(f"""<div class='card'>
    <div class='kpi-label'>Portfolio at Retirement ({cl_label}){suffix}</div>
    <div class='kpi'>{fmt_m(pcts[cl][yr_idx])}</div>
    <div style='color:#8b949e;font-size:.82rem;'>
        Your portfolio meets or exceeds this in {cl_pct} of simulations<br>
        P10: {fmt_m(pcts['p10'][yr_idx])} · P50: {fmt_m(pcts['p50'][yr_idx])} · P90: {fmt_m(pcts['p90'][yr_idx])}</div>
</div>""", unsafe_allow_html=True)

total_now = sum(a["balance"] for p in persons for a in p.get("accounts", []))
k2.markdown(f"""<div class='card'>
    <div class='kpi-label'>Current Total Portfolio</div>
    <div class='kpi'>{fmt_m(total_now)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>Starting point across all accounts</div>
</div>""", unsafe_allow_html=True)

total_contrib = sum(
    a.get("annual_contribution", 0) + a.get("employer_match_pct", 0) / 100
    * sum(s.get("amount", 0) for s in p.get("salaries", []))
    for p in persons for a in p.get("accounts", []))
k3.markdown(f"""<div class='card'>
    <div class='kpi-label'>Annual Contributions (today)</div>
    <div class='kpi'>{fmt_m(total_contrib)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>Scales proportionally with salary growth</div>
</div>""", unsafe_allow_html=True)

sal_p50   = result["salary_p50"]
final_sal = sal_p50[min(yr_at_retire, len(sal_p50)-1)]
k4.markdown(f"""<div class='card'>
    <div class='kpi-label'>Salary at Retirement (Median)</div>
    <div class='kpi'>{fmt_m(final_sal)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>Combined household · nominal</div>
</div>""", unsafe_allow_html=True)

st.markdown("")

# Fan chart
fig = fan_chart(
    x=ages, pcts=pcts,
    title="Portfolio Growth to Retirement" + (" (Today's Dollars)" if use_real else ""),
    color="#00d4aa", x_label="Your Age", y_label="Portfolio Value", x_is_age=True)
fig.add_vline(x=ret_age, line_dash="dash", line_color="#8b949e",
              annotation_text=f"Retire age {ret_age}", annotation_font_color="#8b949e")

# Add confidence level line if not median (already shown)
if cl != "p50":
    fig.add_trace(go.Scatter(
        x=ages, y=pcts[cl],
        name=cl_label,
        line=dict(color="#f0883e", width=2, dash="dash"),
        hovertemplate=f"<b>Age %{{x}}</b><br>{cl_label}: %{{customdata}}<extra></extra>",
        customdata=[fmt_m(v) for v in pcts[cl]],
    ))


if show_spaghetti:
    paths = result["portfolio_real"] if use_real else result["portfolio_paths"]
    idx = np.random.default_rng(0).choice(result["n_sims"],
                                           size=min(50, result["n_sims"]), replace=False)
    for i in idx:
        fig.add_trace(go.Scatter(
            x=ages, y=paths[i],
            line=dict(color="rgba(0,212,170,0.08)", width=1),
            showlegend=False, hoverinfo="skip"))

st.plotly_chart(fig, width='stretch')
st.caption(
    "**Fan chart guide:** The dark center line is the median (50th percentile) outcome — "
    "half of simulations end above this, half below. "
    "The medium band covers the 25th–75th percentile (middle 50% of outcomes). "
    "The light outer band covers the 10th–90th percentile (middle 80% of outcomes). "
    "The dashed vertical line marks your target retirement age. "
    "Wide bands = high uncertainty; narrow bands = more predictable trajectory.")

# Account breakdown chart
st.markdown("### Account Breakdown (Median)")
fig2 = stacked_account_area(result["acct_medians"], ages, use_real=use_real)
fig2.add_vline(x=ret_age, line_dash="dash", line_color="#8b949e")

st.plotly_chart(fig2, width='stretch')
st.caption(
    "Median balance of each account stacked on top of each other. "
    "Each color represents one account. The total height of the stack equals the "
    "median portfolio value from the fan chart above. Useful for seeing which accounts "
    "are doing the heavy lifting and whether your mix is diversified across account types.")

# Salary chart
st.markdown("### Salary Trajectory (Median)")
PERSON_COLORS = ["#f0883e", "#bc8cff"]
fig3 = go.Figure()

person_sal_p50 = result.get("person_sal_p50", [])
for pi, person in enumerate(persons):
    if pi >= len(person_sal_p50): break
    color = PERSON_COLORS[pi % len(PERSON_COLORS)]
    name  = person.get("name", f"Person {pi+1}")
    sal_labels = ", ".join(s["label"] for s in person.get("salaries", []))
    fig3.add_trace(go.Scatter(
        x=ages[:len(person_sal_p50[pi])], y=person_sal_p50[pi],
        name=f"{name}: all income ({sal_labels})",
        line=dict(color=color, width=2)))

fers_person = next((p for p in persons if p.get("has_fers")), None)
if fers_person and result.get("fers_salary_p50") is not None:
    fers_sals  = [s for s in fers_person.get("salaries", [])
                  if s.get("is_fers_basic_pay", False)]
    none_marked = not fers_sals
    if none_marked:
        # fallback — all used, show warning
        fers_sals = fers_person.get("salaries", [])
        st.warning("⚠️ No salary is marked as FERS basic pay — all of "
                   f"{fers_person['name']}'s salaries are included in the pension high-3. "
                   "Fix this on **Household Setup** by enabling the FERS basic pay toggle "
                   "on only the federal salary.")
    fers_label = ", ".join(s["label"] for s in fers_sals) or "all salaries"
    fig3.add_trace(go.Scatter(
        x=ages[:len(result["fers_salary_p50"])],
        y=result["fers_salary_p50"],
        name=f"Pension high-3 source: {fers_label}",
        line=dict(color="#00d4aa", width=2.5, dash="dot")))

fig3.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e6edf3"),
    xaxis=dict(title="Age", gridcolor="#21262d"),
    yaxis=dict(title="Salary", tickformat="$,.0f", gridcolor="#21262d"),
    legend=dict(bgcolor="rgba(22,27,34,0.8)", bordercolor="#21262d", borderwidth=1))
_add_crosshair(fig3)
st.plotly_chart(fig3, width='stretch')
st.caption(
    "Each solid line shows one person's total income (all salary sources combined). "
    "**Teal dotted line:** only the income sources marked as FERS basic federal pay on the "
    "Household Setup page — this is the exact trajectory used to compute the pension high-3. "
    "If the teal line overlaps a solid line, all that person's salaries are feeding the "
    "pension calculation — go to Household Setup and uncheck any non-federal income sources."
)

st.session_state["_final_portfolio_sims"] = result["final_portfolio_sims"]
