"""Page 7 — Tax Analysis"""

import streamlit as st
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.calculations import (
    calculate_federal_tax, get_marginal_rate, calculate_rmd,
    roth_vs_traditional, RMD_TABLE, TAX_BRACKETS_MFJ, STANDARD_DEDUCTION_MFJ,
)
from utils.charts import roth_vs_trad_chart, tax_rate_timeline
import plotly.graph_objects as go

st.set_page_config(page_title="Tax Analysis", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:18px 22px;margin-bottom:14px;}
.kpi{font-size:1.8rem;font-weight:700;color:#00d4aa;}
.kpi-label{font-size:0.8rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;}
.sh{font-size:1.05rem;font-weight:600;color:#e6edf3;border-bottom:1px solid #21262d;
    padding-bottom:8px;margin:16px 0 12px 0;}
.highlight{background:rgba(0,212,170,0.08);border:1px solid rgba(0,212,170,0.25);
           border-radius:8px;padding:10px 14px;font-size:.88rem;}
.warn{background:rgba(240,136,62,0.1);border:1px solid rgba(240,136,62,0.3);
      border-radius:8px;padding:10px 14px;font-size:.88rem;color:#f0883e;}
</style>""", unsafe_allow_html=True)

def fmt(v):   return f"${v:,.0f}"
def fmt_m(v):
    if abs(v) >= 1e6: return f"${v/1e6:.2f}M"
    if abs(v) >= 1e3: return f"${v/1e3:,.0f}K"
    return fmt(v)
def pct(v):   return f"{v*100:.1f}%"

st.markdown("## 💰 Tax Analysis")
st.markdown("<p style='color:#8b949e;'>Roth vs Traditional comparison, RMD schedule, "
            "bracket optimization, and IRMAA risk flags.</p>", unsafe_allow_html=True)

persons     = st.session_state.get("persons", [])
assumptions = st.session_state.get("assumptions", {})
inf         = assumptions.get("inflation_rate", 3.0) / 100.0

if not persons:
    st.warning("Complete **Household Setup** first."); st.stop()

p0 = persons[0]
p1 = persons[1] if len(persons) > 1 else {}

total_sal_now = sum(
    sum(s.get("amount", 0) for s in p.get("salaries", []))
    for p in persons
)

# ════════════════════════════════════════════════════════════════════════
# SECTION 1 — Current Tax Snapshot
# ════════════════════════════════════════════════════════════════════════
st.markdown("<div class='sh'>Current Tax Snapshot (Working Years)</div>", unsafe_allow_html=True)

tax_now  = calculate_federal_tax(total_sal_now)
marg_now = get_marginal_rate(total_sal_now)
eff_now  = tax_now / max(total_sal_now, 1)

k1, k2, k3, k4 = st.columns(4)
k1.markdown(f"""<div class='card'>
    <div class='kpi-label'>Household Income</div>
    <div class='kpi'>{fmt(total_sal_now)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>Combined salaries</div>
</div>""", unsafe_allow_html=True)
k2.markdown(f"""<div class='card'>
    <div class='kpi-label'>Est. Federal Tax</div>
    <div class='kpi'>{fmt(tax_now)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>MFJ standard deduction</div>
</div>""", unsafe_allow_html=True)
k3.markdown(f"""<div class='card'>
    <div class='kpi-label'>Marginal Rate</div>
    <div class='kpi'>{pct(marg_now)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>Top bracket you're in</div>
</div>""", unsafe_allow_html=True)
k4.markdown(f"""<div class='card'>
    <div class='kpi-label'>Effective Rate</div>
    <div class='kpi'>{pct(eff_now)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>Actual % of income paid</div>
</div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
# SECTION 2 — Roth vs Traditional
# ════════════════════════════════════════════════════════════════════════
st.markdown("<div class='sh'>Roth vs Traditional Comparison</div>", unsafe_allow_html=True)
st.caption("Compares after-tax wealth at retirement. Traditional analysis includes "
           "investing the annual tax savings in a taxable account.")

rc1, rc2, rc3 = st.columns(3)
roth_contrib = rc1.number_input(
    "Annual contribution to compare ($)", 1_000, 100_000, 7_000, 100,
    help="The dollar amount you're deciding whether to put in Roth or Traditional.")
ret_age_you  = assumptions.get("retirement_age_you", 62)
exp_ret_income = rc2.number_input(
    "Expected retirement income (today's $)", 0, 500_000,
    int(st.session_state.get("_guaranteed_income", {}).get("total", 80_000)), 100,
    help="Estimated total taxable income in retirement (pension + SS + withdrawals). "
         "Used to estimate your retirement marginal rate.")
stock_r = assumptions.get("stock_return", 7.0) / 100.0

roth_result = roth_vs_traditional(
    annual_contribution         = roth_contrib,
    current_age                 = p0.get("age", 40),
    retirement_age              = ret_age_you,
    gross_income_now            = total_sal_now,
    expected_retirement_income  = exp_ret_income,
    stock_r                     = stock_r,
    inflation                   = inf,
    n_sims                      = 500,
)

winner      = "Roth" if roth_result["roth_better"] else "Traditional"
winner_color = "#00d4aa" if roth_result["roth_better"] else "#79c0ff"

rk1, rk2, rk3, rk4 = st.columns(4)
rk1.markdown(f"""<div class='card'>
    <div class='kpi-label'>Roth Final Value (median)</div>
    <div class='kpi'>{fmt_m(roth_result['roth_final_p50'])}</div>
    <div style='color:#8b949e;font-size:.82rem;'>After-tax, at retirement</div>
</div>""", unsafe_allow_html=True)
rk2.markdown(f"""<div class='card'>
    <div class='kpi-label'>Traditional Final Value (median)</div>
    <div class='kpi'>{fmt_m(roth_result['trad_final_p50'])}</div>
    <div style='color:#8b949e;font-size:.82rem;'>After-tax incl. tax savings invested</div>
</div>""", unsafe_allow_html=True)
rk3.markdown(f"""<div class='card'>
    <div class='kpi-label'>Advantage</div>
    <div class='kpi' style='color:{winner_color};'>{winner}</div>
    <div style='color:#8b949e;font-size:.82rem;'>by {fmt_m(roth_result['advantage'])}</div>
</div>""", unsafe_allow_html=True)
rk4.markdown(f"""<div class='card'>
    <div class='kpi-label'>Tax Rate: Now vs Retirement</div>
    <div class='kpi'>{pct(roth_result['marg_now'])} → {pct(roth_result['marg_retire'])}</div>
    <div style='color:#8b949e;font-size:.82rem;'>Marginal bracket (MFJ)</div>
</div>""", unsafe_allow_html=True)

# Rule-of-thumb guidance
if roth_result["marg_now"] < roth_result["marg_retire"]:
    st.markdown("<div class='highlight'>✅ <b>Roth favored:</b> Your marginal rate is <i>lower now</i> "
                "than projected in retirement — pay taxes now at the lower rate and grow tax-free.</div>",
                unsafe_allow_html=True)
elif roth_result["marg_now"] > roth_result["marg_retire"]:
    st.markdown("<div class='highlight'>✅ <b>Traditional favored:</b> Your marginal rate is <i>higher now</i> "
                "— defer taxes and pay at the lower retirement rate. Invest the tax savings.</div>",
                unsafe_allow_html=True)
else:
    st.markdown("<div class='highlight'>⚖️ <b>Rates are equal</b> — the choice depends on "
                "your view of future tax policy. Splitting contributions hedges both outcomes.</div>",
                unsafe_allow_html=True)

st.plotly_chart(roth_vs_trad_chart(roth_result), width='stretch')

# ════════════════════════════════════════════════════════════════════════
# SECTION 3 — Roth Conversion Window
# ════════════════════════════════════════════════════════════════════════
st.markdown("<div class='sh'>Roth Conversion Opportunity Window</div>", unsafe_allow_html=True)
st.markdown("""
The years **between retirement and age 73 (RMD start) / SS claim** are often a low-income window
where converting Traditional / TSP balances to Roth can lock in a low tax rate.
""")

gi       = st.session_state.get("_guaranteed_income", {})
pen      = gi.get("pension", 0)
supp     = gi.get("supplement", 0)
ss_you   = (p0.get("ss") or {}).get("_annual_benefit", 0)
ss_sp    = (p1.get("ss") or {}).get("_annual_benefit", 0) if p1 else 0
ss_claim = (p0.get("ss") or {}).get("claim_age", 67)

conv_ages  = np.arange(ret_age_you, min(ret_age_you + 20, 90))
conv_rows  = []

for age in conv_ages:
    t       = age - ret_age_you
    inf_t   = (1 + inf) ** t
    # Income in this year (before any conversion)
    p_nom   = pen * (1 + inf) ** t
    s_nom   = supp * inf_t if age < 62 else 0.0
    ss_nom  = (ss_you + ss_sp) * inf_t if age >= ss_claim else 0.0
    base_income = p_nom + s_nom + ss_nom

    # How much room to top of current bracket?
    factor  = (1 + inf) ** t
    deduct  = STANDARD_DEDUCTION_MFJ * factor
    taxable = max(0, base_income - deduct)
    # Find headroom to next bracket
    headroom = 0.0
    prev     = 0.0
    for limit, rate in TAX_BRACKETS_MFJ:
        lim_adj = limit * factor
        if taxable < lim_adj:
            headroom = lim_adj - taxable
            break
        prev = lim_adj

    marg = get_marginal_rate(base_income, t, inf)
    rmd_age_trigger = age >= 73

    conv_rows.append({
        "Age":              age,
        "Base Income":      fmt(base_income),
        "Marginal Rate":    pct(marg),
        "Bracket Headroom": fmt(headroom),
        "RMDs Started":     "⚠️ Yes" if rmd_age_trigger else "✅ No",
        "SS Active":        "Yes" if age >= ss_claim else "No",
        "FERS Supp.":       "Yes" if age < 62 else "—",
    })

conv_df = pd.DataFrame(conv_rows)
# Highlight the low-rate window
low_rate_mask = conv_df["Marginal Rate"].apply(
    lambda x: float(x.strip("%")) < float(pct(marg_now).strip("%")))

st.dataframe(conv_df, width='stretch', hide_index=True)

window_ages = conv_df[low_rate_mask]["Age"].tolist()
if window_ages:
    st.markdown(f"<div class='highlight'>💡 <b>Conversion window: Ages {window_ages[0]}–{window_ages[-1]}</b> "
                f"— your marginal rate in retirement is below your current {pct(marg_now)} rate. "
                f"Consider converting up to the bracket headroom each year.</div>",
                unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
# SECTION 4 — RMD Schedule
# ════════════════════════════════════════════════════════════════════════
st.markdown("<div class='sh'>Required Minimum Distribution (RMD) Schedule</div>", unsafe_allow_html=True)
st.caption("SECURE 2.0: RMDs begin at age 73. Applies to Traditional IRA, TSP (Traditional), 401k/403b.")

# Get traditional balances
trad_types   = {"tsp_traditional", "ira_traditional", "retirement_traditional"}
trad_balance = sum(
    a.get("balance", 0)
    for p in persons for a in p.get("accounts", [])
    if a.get("account_type") in trad_types
)

rmd_start  = 73
rmd_ret    = assumptions.get("stock_return", 7.0) / 100.0  # growth while in account

rmd_rows   = []
balance    = trad_balance
# Grow balance from now to age 73 first
yrs_to_rmd = max(rmd_start - p0.get("age", 40), 0)
balance_at_rmd = trad_balance * (1 + rmd_ret) ** yrs_to_rmd

bal = balance_at_rmd
for age in range(rmd_start, min(p0.get("life_expectancy", 87) + 1, 106)):
    rmd     = calculate_rmd(bal, age)
    inf_t   = (1 + inf) ** (age - p0.get("age", 40))
    tax_est = calculate_federal_tax(pen * (1+inf)**(age-ret_age_you) + rmd)
    rmd_rows.append({
        "Age":              age,
        "Account Balance":  fmt_m(bal),
        "RMD Amount":       fmt(rmd),
        "RMD %":            f"{rmd/max(bal,1)*100:.2f}%",
        "Est. Tax on RMD":  fmt(tax_est),
    })
    bal = max(bal - rmd, 0) * (1 + rmd_ret)  # remaining grows

rmd_df = pd.DataFrame(rmd_rows)
st.dataframe(rmd_df, width='stretch', hide_index=True)

rmd_fig = go.Figure()
rmd_fig.add_trace(go.Bar(
    x=rmd_df["Age"], y=rmd_df["RMD Amount"].apply(lambda x: float(x.replace("$","").replace(",",""))),
    name="Annual RMD", marker_color="rgba(240,136,62,0.8)"))
rmd_fig.add_trace(go.Scatter(
    x=rmd_df["Age"],
    y=rmd_df["Account Balance"].apply(
        lambda x: float(x.replace("$","").replace("M","e6").replace("K","e3"))),
    name="Traditional Balance", yaxis="y2",
    line=dict(color="#79c0ff", width=2)))
rmd_fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e6edf3"), barmode="overlay",
    xaxis=dict(title="Age", gridcolor="#21262d"),
    yaxis=dict(title="RMD Amount", tickformat="$,.0f", gridcolor="#21262d"),
    yaxis2=dict(title="Balance", overlaying="y", side="right",
                tickformat="$,.2s", showgrid=False),
    legend=dict(bgcolor="rgba(22,27,34,0.8)", bordercolor="#21262d", borderwidth=1),
)
st.plotly_chart(rmd_fig, width='stretch')

# ════════════════════════════════════════════════════════════════════════
# SECTION 5 — IRMAA Risk Flags
# ════════════════════════════════════════════════════════════════════════
st.markdown("<div class='sh'>IRMAA Medicare Surcharge Risk</div>", unsafe_allow_html=True)
st.caption("IRMAA applies when MAGI exceeds thresholds (2024 MFJ). "
           "Triggered 2 years after the income year — plan ahead.")

IRMAA_THRESHOLDS_MFJ = [
    (206_000, "$0",    "Standard premium"),
    (258_000, "+$69.90/mo per person",  "Tier 1"),
    (322_000, "+$174.70/mo per person", "Tier 2"),
    (386_000, "+$279.50/mo per person", "Tier 3"),
    (750_000, "+$384.30/mo per person", "Tier 4"),
    (float("inf"), "+$419.30/mo per person", "Tier 5 (highest)"),
]

irmaa_rows = []
for age in range(ret_age_you, min(p0.get("life_expectancy", 87) + 1, 90)):
    t       = age - ret_age_you
    inf_t   = (1 + inf) ** t
    pen_n   = pen * inf_t
    ss_n    = (ss_you + ss_sp) * inf_t if age >= ss_claim else 0
    # Add estimated RMD if over 73
    rmd_est = 0.0
    if age >= 73:
        bal_est = balance_at_rmd * (1 + rmd_ret) ** (age - rmd_start)
        rmd_est = calculate_rmd(bal_est, age)
    magi = pen_n + ss_n + rmd_est

    tier = "Standard"
    surcharge = "$0"
    for thresh, sur, name in IRMAA_THRESHOLDS_MFJ:
        if magi <= thresh:
            tier      = name
            surcharge = sur
            break

    irmaa_rows.append({
        "Age":       age,
        "Est. MAGI": fmt_m(magi),
        "IRMAA Tier": tier,
        "Surcharge":  surcharge,
        "Flag":       "⚠️" if tier != "Standard premium" else "✅",
    })

irmaa_df = pd.DataFrame(irmaa_rows)
flagged  = irmaa_df[irmaa_df["Flag"] == "⚠️"]
st.dataframe(irmaa_df, width='stretch', hide_index=True)

if not flagged.empty:
    first_flag = int(flagged["Age"].iloc[0])
    st.markdown(f"<div class='warn'>⚠️ IRMAA surcharges begin at age <b>{first_flag}</b> "
                f"based on projected income. Consider Roth conversions or income smoothing "
                f"before age <b>{first_flag - 2}</b> (2-year lookback) to stay below thresholds.</div>",
                unsafe_allow_html=True)
else:
    st.markdown("<div class='highlight'>✅ No IRMAA surcharges projected based on current income estimates.</div>",
                unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
# SECTION 6 — Optimal Withdrawal Order
# ════════════════════════════════════════════════════════════════════════
st.markdown("<div class='sh'>Optimal Withdrawal Order</div>", unsafe_allow_html=True)
st.markdown("""
General tax-efficient sequence for retirement withdrawals:

| Priority | Source | Why |
|---|---|---|
| 1 | **Required income** (Pension, SS, FERS Supplement) | Non-discretionary — received regardless |
| 2 | **HSA** (for qualified medical expenses) | Triple tax-advantaged; use for healthcare first |
| 3 | **Taxable Brokerage** | Pay LTCG rates (0–20%) instead of ordinary income; step-up basis at death |
| 4 | **Traditional IRA / TSP / 401k** | Defer as long as possible but draw before RMDs force large distributions |
| 5 | **Roth IRA / TSP Roth** | Last resort — grows tax-free forever; no RMDs on Roth IRA; ideal for estate |

> **FERS-specific note:** Your pension counts as ordinary income from day one.
> In years before SS begins, your taxable income may be low enough to do
> Roth conversions or take extra Traditional withdrawals at a favorable rate.
""")
