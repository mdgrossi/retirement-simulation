"""Page 7 — Tax Analysis"""

import streamlit as st
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.calculations import (calculate_federal_tax, get_marginal_rate, calculate_rmd,
                                 roth_vs_traditional, TAX_BRACKETS_MFJ, STANDARD_DEDUCTION_MFJ)
from utils.charts import roth_vs_trad_chart, _add_crosshair
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
.tip{background:rgba(0,212,170,0.07);border:1px solid rgba(0,212,170,0.2);border-radius:8px;
     padding:10px 14px;font-size:.85rem;color:#8b949e;margin-bottom:14px;}
.hl{background:rgba(0,212,170,0.08);border:1px solid rgba(0,212,170,0.25);
    border-radius:8px;padding:10px 14px;font-size:.88rem;}
.warn{background:rgba(240,136,62,0.1);border:1px solid rgba(240,136,62,0.3);
      border-radius:8px;padding:10px 14px;font-size:.88rem;color:#f0883e;}
</style>""", unsafe_allow_html=True)

def fmt(v):  return f"${v:,.0f}"
def fmt_m(v):
    if abs(v) >= 1e6: return f"${v/1e6:.2f}M"
    if abs(v) >= 1e3: return f"${v/1e3:,.0f}K"
    return fmt(v)
def pct(v):  return f"{v*100:.1f}%"

st.markdown("## 💰 Tax Analysis")
st.markdown("<p style='color:#8b949e;'>Roth vs Traditional comparison, RMD projections, "
            "Roth conversion window, IRMAA risk, and optimal withdrawal sequencing.</p>",
            unsafe_allow_html=True)

persons     = st.session_state.get("persons", [])
assumptions = st.session_state.get("assumptions", {})
inf         = assumptions.get("inflation_rate", 3.0) / 100.0

if not persons:
    st.warning("Complete **Household Setup** first."); st.stop()

p0 = persons[0]
p1 = persons[1] if len(persons) > 1 else {}
total_sal_now = sum(
    sum(s.get("amount", 0) for s in p.get("salaries", []))
    for p in persons)

# ── Section 1: Current Tax Snapshot ──────────────────────────────────────────
st.markdown("<div class='sh'>Current Tax Snapshot (Working Years)</div>",
            unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "Estimated federal income tax using 2024 Married Filing Jointly brackets and the "
            "standard deduction. State taxes are not modeled. This snapshot helps you "
            "understand your current tax position, which is the baseline for Roth vs "
            "Traditional decisions.</div>", unsafe_allow_html=True)

tax_now  = calculate_federal_tax(total_sal_now)
marg_now = get_marginal_rate(total_sal_now)
eff_now  = tax_now / max(total_sal_now, 1)

k1, k2, k3, k4 = st.columns(4)
k1.markdown(f"""<div class='card'>
    <div class='kpi-label'>Household Income</div>
    <div class='kpi'>{fmt(total_sal_now)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>Combined salaries from Household Setup</div>
</div>""", unsafe_allow_html=True)
k2.markdown(f"""<div class='card'>
    <div class='kpi-label'>Est. Federal Tax</div>
    <div class='kpi'>{fmt(tax_now)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>MFJ standard deduction applied</div>
</div>""", unsafe_allow_html=True)
k3.markdown(f"""<div class='card'>
    <div class='kpi-label'>Marginal Rate</div>
    <div class='kpi'>{pct(marg_now)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>
        The rate on your last dollar of income.<br>
        Every pre-tax contribution saves you {pct(marg_now)} in taxes today.</div>
</div>""", unsafe_allow_html=True)
k4.markdown(f"""<div class='card'>
    <div class='kpi-label'>Effective Rate</div>
    <div class='kpi'>{pct(eff_now)}</div>
    <div style='color:#8b949e;font-size:.82rem;'>
        Actual % of income paid in tax.<br>
        Always lower than marginal rate due to progressive brackets.</div>
</div>""", unsafe_allow_html=True)

# ── Section 2: Roth vs Traditional ────────────────────────────────────────────
st.markdown("<div class='sh'>Roth vs Traditional Comparison</div>", unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "The core question: pay taxes now (Roth) or later (Traditional)? "
            "If your tax rate is <b>lower now</b> than in retirement → Roth wins. "
            "If your tax rate is <b>higher now</b> → Traditional wins. "
            "This analysis accounts for investing the annual tax savings from Traditional "
            "contributions in a taxable account, making the comparison fair.</div>",
            unsafe_allow_html=True)

rc1, rc2 = st.columns(2)
tax = st.session_state.setdefault("tax_settings", {
    "roth_contrib":    7_000,
    "exp_ret_income":  int(st.session_state.get("_guaranteed_income", {}).get("total", 80_000)),
})

roth_contrib = rc1.number_input(
    "Annual contribution to compare ($)", 1_000, 100_000,
    int(tax.get("roth_contrib", 7_000)), 100,
    key="tax_roth_contrib",
    help="The dollar amount you are deciding between Roth and Traditional. "
         "For IRAs the 2024 limit is $7,000 ($8,000 if age 50+); "
         "for TSP up to $23,000 ($30,500 if 50+). "
         "The analysis shows which approach leaves you with more after-tax wealth "
         "at retirement for this contribution amount.")
tax["roth_contrib"] = roth_contrib

exp_ret_income = rc2.number_input(
    "Expected retirement income (today's $)", 0, 500_000,
    int(tax.get("exp_ret_income",
        st.session_state.get("_guaranteed_income", {}).get("total", 80_000))), 100,
    key="tax_exp_ret_income",
    help="Your estimated total taxable income in retirement — pension, SS, and any "
         "Traditional withdrawals. Used to estimate your future marginal tax bracket. "
         "Your guaranteed income total from the Pension & Income page is pre-filled.")
tax["exp_ret_income"] = exp_ret_income

ret_age_you = assumptions.get("retirement_age_you", 62)
roth_result = roth_vs_traditional(
    annual_contribution        = roth_contrib,
    current_age                = p0.get("age", 40),
    retirement_age             = ret_age_you,
    gross_income_now           = total_sal_now,
    expected_retirement_income = exp_ret_income,
    stock_r                    = assumptions.get("stock_return", 7.0) / 100.0,
    inflation                  = inf, n_sims=500)

winner       = "Roth" if roth_result["roth_better"] else "Traditional"
winner_color = "#00d4aa" if roth_result["roth_better"] else "#79c0ff"

rk1, rk2, rk3, rk4 = st.columns(4)
rk1.markdown(f"""<div class='card'>
    <div class='kpi-label'>Roth Final Value (median)</div>
    <div class='kpi'>{fmt_m(roth_result['roth_final_p50'])}</div>
    <div style='color:#8b949e;font-size:.82rem;'>After-tax · at retirement</div>
</div>""", unsafe_allow_html=True)
rk2.markdown(f"""<div class='card'>
    <div class='kpi-label'>Traditional Final Value (median)</div>
    <div class='kpi'>{fmt_m(roth_result['trad_final_p50'])}</div>
    <div style='color:#8b949e;font-size:.82rem;'>After-tax incl. tax savings invested</div>
</div>""", unsafe_allow_html=True)
rk3.markdown(f"""<div class='card'>
    <div class='kpi-label'>Winner</div>
    <div class='kpi' style='color:{winner_color};'>{winner}</div>
    <div style='color:#8b949e;font-size:.82rem;'>by {fmt_m(roth_result['advantage'])}</div>
</div>""", unsafe_allow_html=True)
rk4.markdown(f"""<div class='card'>
    <div class='kpi-label'>Tax Rate Now → Retirement</div>
    <div class='kpi'>{pct(roth_result['marg_now'])} → {pct(roth_result['marg_retire'])}</div>
    <div style='color:#8b949e;font-size:.82rem;'>Marginal brackets (MFJ)</div>
</div>""", unsafe_allow_html=True)

if roth_result["marg_now"] < roth_result["marg_retire"]:
    st.markdown("<div class='hl'>✅ <b>Roth favored:</b> Your current marginal rate is lower than "
                "your projected retirement rate. Pay taxes now at the lower rate and let "
                "the account grow tax-free.</div>", unsafe_allow_html=True)
elif roth_result["marg_now"] > roth_result["marg_retire"]:
    st.markdown(
        f"<div class='hl'>✅ <b>Traditional favored:</b> "
        f"Your current marginal rate ({pct(roth_result['marg_now'])}) is higher than your "
        f"projected retirement rate ({pct(roth_result['marg_retire'])}). "
        f"Contributing pre-tax now defers the tax bill to retirement, when you will owe less — "
        f"saving you the rate difference on every dollar. "
        f"Invest the annual tax savings (≈ {fmt(roth_result['tax_saving_annual'])}/yr) "
        f"in a taxable account to maximize the benefit.</div>",
        unsafe_allow_html=True)
else:
    st.markdown("<div class='hl'>⚖️ <b>Rates equal:</b> The mathematical difference is small. "
                "Consider splitting contributions to hedge future tax uncertainty, "
                "or favor Roth for estate planning flexibility (no RMDs on Roth IRA).</div>",
                unsafe_allow_html=True)

st.plotly_chart(roth_vs_trad_chart(roth_result), width='stretch')
st.caption(
    "After-tax wealth at retirement for each strategy, across all simulations (P10/median/P90 bands). "
    "**Teal (Roth):** contributions are post-tax; the entire balance is yours tax-free at retirement. "
    "**Blue (Traditional):** includes both the account balance (after tax at retirement rate) "
    "AND a taxable account funded by investing the annual tax savings. "
    "The crossover point (dashed line, if shown) is where Traditional overtakes Roth — "
    "before that year, Roth is ahead; after it, Traditional wins.")

# ── Section 3: Roth Conversion Window ─────────────────────────────────────────
st.markdown("<div class='sh'>Roth Conversion Opportunity Window</div>", unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "After retiring but before Social Security and RMDs begin, many FERS retirees "
            "enter a temporarily low-income period — an ideal window to convert Traditional "
            "or TSP balances to Roth at a favorable rate. <b>Bracket Headroom</b> shows how "
            "much you could convert before jumping to the next bracket. "
            "Conversions add to ordinary income in the year converted.</div>",
            unsafe_allow_html=True)

gi        = st.session_state.get("_guaranteed_income", {})
pen       = gi.get("pension", 0)
ss_you    = (p0.get("ss") or {}).get("_annual_benefit", 0)
ss_sp     = (p1.get("ss") or {}).get("_annual_benefit", 0) if p1 else 0
ss_claim  = (p0.get("ss") or {}).get("claim_age", 67)

conv_rows = []
for age in range(ret_age_you, min(ret_age_you + 20, 90)):
    t       = age - ret_age_you
    inf_t   = (1 + inf) ** t
    pen_n   = pen * inf_t
    s_n     = (p0.get("fers") or {}).get("_supplement_annual", 0) * inf_t if age < 62 else 0.0
    ss_n    = (ss_you + ss_sp) * inf_t if age >= ss_claim else 0.0
    base    = pen_n + s_n + ss_n
    factor  = (1 + inf) ** t
    deduct  = STANDARD_DEDUCTION_MFJ * factor
    taxable = max(0, base - deduct)
    headroom = 0.0
    for limit, rate in TAX_BRACKETS_MFJ:
        lim_adj = limit * factor
        if taxable < lim_adj:
            headroom = lim_adj - taxable
            break
    marg = get_marginal_rate(base, t, inf)
    conv_rows.append({
        "Age":              age,
        "Base Income":      fmt(base),
        "Marginal Rate":    pct(marg),
        "Bracket Headroom": fmt(headroom),
        "RMDs Started":     "⚠️ Yes" if age >= 73 else "✅ No",
        "SS Active":        "Yes" if age >= ss_claim else "No",
        "FERS Supp.":       "Yes" if age < 62 else "—",
    })

conv_df = pd.DataFrame(conv_rows)
low_mask = conv_df["Marginal Rate"].apply(
    lambda x: float(x.strip("%")) < float(pct(marg_now).strip("%")))
st.dataframe(conv_df, width='stretch', hide_index=True)
st.caption(
    "**Base Income:** guaranteed income (pension + supplement + SS) before any conversions. "
    "**Bracket Headroom:** how much additional income (conversions or Traditional withdrawals) "
    "you can take before jumping to the next bracket. "
    "**RMDs Started:** once RMDs begin at 73, they add forced taxable income, reducing "
    "headroom for voluntary conversions.")

window = conv_df[low_mask]["Age"].tolist()
if window:
    st.markdown(f"<div class='hl'>💡 <b>Conversion window: Ages {window[0]}–{window[-1]}</b> — "
                f"your marginal rate in retirement is below your current {pct(marg_now)}. "
                f"Consider converting up to the bracket headroom each year during this window. "
                f"Prioritize conversions before RMDs begin at 73.</div>",
                unsafe_allow_html=True)

# ── Section 4: RMD Schedule ────────────────────────────────────────────────────
st.markdown("<div class='sh'>Required Minimum Distribution (RMD) Schedule</div>",
            unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "The IRS requires withdrawals from Traditional IRAs, TSP (Traditional), 401k, and "
            "403b accounts starting at age 73 (SECURE 2.0, effective 2023). "
            "RMDs are calculated by dividing your account balance by a life expectancy factor "
            "from the IRS Uniform Lifetime Table. They are taxed as ordinary income and cannot "
            "be rolled into a Roth — but you can satisfy an RMD before doing a Roth conversion. "
            "Roth IRAs have <b>no RMDs</b>.</div>", unsafe_allow_html=True)

trad_types   = {"tsp_traditional", "ira_traditional", "retirement_traditional"}
trad_balance = sum(a.get("balance", 0) for p in persons
                   for a in p.get("accounts", []) if a.get("account_type") in trad_types)
rmd_ret      = assumptions.get("stock_return", 7.0) / 100.0
yrs_to_rmd   = max(73 - p0.get("age", 40), 0)
bal_at_rmd   = trad_balance * (1 + rmd_ret) ** yrs_to_rmd

rmd_rows = []
bal = bal_at_rmd
for age in range(73, min(p0.get("life_expectancy", 87) + 1, 106)):
    rmd     = calculate_rmd(bal, age)
    t       = age - p0.get("age", 40)
    rmd_rows.append({
        "Age":             age,
        "Account Balance": fmt_m(bal),
        "RMD Amount":      fmt(rmd),
        "RMD %":           f"{rmd/max(bal,1)*100:.2f}%",
        "Est. Tax on RMD": fmt(calculate_federal_tax(pen * (1+inf)**(age-ret_age_you) + rmd)),
    })
    bal = max(bal - rmd, 0) * (1 + rmd_ret)

rmd_df = pd.DataFrame(rmd_rows)
st.dataframe(rmd_df, width='stretch', hide_index=True)

rmd_fig = go.Figure()
rmd_fig.add_trace(go.Bar(
    x=rmd_df["Age"],
    y=rmd_df["RMD Amount"].apply(lambda x: float(x.replace("$","").replace(",",""))),
    name="Annual RMD", marker_color="rgba(240,136,62,0.8)"))
rmd_fig.add_trace(go.Scatter(
    x=rmd_df["Age"],
    y=rmd_df["Account Balance"].apply(
        lambda x: float(x.replace("$","").replace("M","e6").replace("K","e3"))),
    name="Traditional Balance", yaxis="y2",
    line=dict(color="#79c0ff", width=2)))
rmd_fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e6edf3"),
    xaxis=dict(title="Age", gridcolor="#21262d"),
    yaxis=dict(title="Annual RMD", tickformat="$,.0f", gridcolor="#21262d"),
    yaxis2=dict(title="Balance", overlaying="y", side="right",
                tickformat="$,.2s", showgrid=False),
    legend=dict(bgcolor="rgba(22,27,34,0.8)", bordercolor="#21262d", borderwidth=1))
_add_crosshair(rmd_fig)
st.plotly_chart(rmd_fig, width='stretch')
st.caption(
    "**Orange bars (left axis):** annual RMD dollar amount, growing each year as the "
    "divisor shrinks (you're expected to live fewer years). "
    "**Blue line (right axis):** remaining Traditional account balance. "
    "RMDs accelerate as you age — by your mid-80s you may be withdrawing 6–8% per year "
    "regardless of market conditions. Large RMDs can push you into higher brackets and "
    "trigger IRMAA surcharges — this is why Roth conversions before 73 are valuable.")

# ── Section 5: IRMAA ──────────────────────────────────────────────────────────
st.markdown("<div class='sh'>IRMAA Medicare Surcharge Risk</div>", unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "IRMAA (Income-Related Monthly Adjustment Amount) adds a surcharge to Medicare "
            "Part B and Part D premiums when your Modified Adjusted Gross Income exceeds "
            "thresholds. It uses a <b>2-year lookback</b> — your 2024 income determines your "
            "2026 premium. Plan Roth conversions and large Traditional withdrawals with this "
            "in mind. Thresholds shown are 2024 MFJ values.</div>", unsafe_allow_html=True)

IRMAA_MFJ = [
    (206_000, "$0",              "Standard premium"),
    (258_000, "+$69.90/mo/person",  "Tier 1"),
    (322_000, "+$174.70/mo/person", "Tier 2"),
    (386_000, "+$279.50/mo/person", "Tier 3"),
    (750_000, "+$384.30/mo/person", "Tier 4"),
    (float("inf"), "+$419.30/mo/person", "Tier 5 (highest)"),
]

irmaa_rows = []
for age in range(ret_age_you, min(p0.get("life_expectancy", 87) + 1, 90)):
    t       = age - ret_age_you
    inf_t   = (1 + inf) ** t
    pen_n   = pen * inf_t
    ss_n    = (ss_you + ss_sp) * inf_t if age >= ss_claim else 0
    rmd_est = 0.0
    if age >= 73:
        bal_est = bal_at_rmd * (1 + rmd_ret) ** (age - 73)
        rmd_est = calculate_rmd(bal_est, age)
    magi = pen_n + ss_n + rmd_est
    tier = surcharge = "Standard premium"
    for thresh, sur, name in IRMAA_MFJ:
        if magi <= thresh:
            tier = name; surcharge = sur; break
    irmaa_rows.append({
        "Age": age, "Est. MAGI": fmt_m(magi),
        "IRMAA Tier": tier, "Surcharge": surcharge,
        "Flag": "⚠️" if tier != "Standard premium" else "✅",
    })

irmaa_df = pd.DataFrame(irmaa_rows)
flagged  = irmaa_df[irmaa_df["Flag"] == "⚠️"]
st.dataframe(irmaa_df, width='stretch', hide_index=True)
st.caption(
    "**Est. MAGI:** projected Modified AGI (pension + SS + RMDs). Does not include "
    "Roth conversions or other income you may add. "
    "**Flag:** ✅ means standard Medicare premium; ⚠️ means a surcharge applies. "
    "Remember the 2-year lookback — income in year N affects premiums in year N+2.")

if not flagged.empty:
    first = int(flagged["Age"].iloc[0])
    st.markdown(f"<div class='warn'>⚠️ IRMAA surcharges begin at age <b>{first}</b>. "
                f"To avoid this, keep MAGI below the threshold in age <b>{first-2}</b> "
                f"(two years prior). Consider smoothing Roth conversions and Traditional "
                f"withdrawals to stay under the threshold.</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='hl'>✅ No IRMAA surcharges projected based on current income.</div>",
                unsafe_allow_html=True)

# ── Section 6: Withdrawal Order ───────────────────────────────────────────────
st.markdown("<div class='sh'>Optimal Withdrawal Order</div>", unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "The order in which you draw from different account types significantly affects "
            "your lifetime tax bill and estate. The goal is to keep taxable income low while "
            "letting tax-advantaged accounts grow as long as possible.</div>",
            unsafe_allow_html=True)

st.markdown("""
| Priority | Source | Why |
|---|---|---|
| 1 | **Guaranteed income** (Pension, SS, FERS Supplement) | Received automatically — not a choice |
| 2 | **HSA** (for qualified medical expenses only) | Triple tax-advantaged: deductible contributions, tax-free growth, tax-free medical withdrawals |
| 3 | **Taxable Brokerage** | Pay long-term capital gains rates (0–20%) instead of ordinary income; stepped-up basis at death reduces heirs' tax burden |
| 4 | **Traditional IRA / TSP / 401k / 403b** | Defer as long as possible, but draw down before RMDs force large distributions. Prime Roth conversion source. |
| 5 | **Roth IRA / Roth TSP** | Last resort — grows tax-free indefinitely; Roth IRA has no RMDs; ideal to leave to heirs |

**FERS-specific notes:**
- Your pension is ordinary income from day one — plan other income sources around it.
- In years before SS begins, your taxable income may be low enough for favorable Roth conversions.
- The FERS Supplement is also ordinary income and counts toward IRMAA MAGI.
- TSP Roth balances have no RMDs if rolled to a Roth IRA before age 73.
""")
