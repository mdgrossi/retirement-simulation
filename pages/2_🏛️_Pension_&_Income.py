"""Page 2 — Pension & Income"""

import streamlit as st
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.calculations import calculate_fers_pension, ss_annual_benefit, get_fers_mra, fers_cola_rate
from utils.defaults import FERS_SURVIVOR_OPTIONS
from utils.charts import _add_crosshair
import plotly.graph_objects as go

st.set_page_config(page_title="Pension & Income", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:18px 22px;margin-bottom:14px;}
.kpi{font-size:1.8rem;font-weight:700;color:#00d4aa;}
.kpi-label{font-size:0.8rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;}
.sh{font-size:1.05rem;font-weight:600;color:#e6edf3;border-bottom:1px solid #21262d;padding-bottom:8px;margin:16px 0 12px 0;}
.tip{background:rgba(0,212,170,0.07);border:1px solid rgba(0,212,170,0.2);border-radius:8px;
     padding:10px 14px;font-size:.85rem;color:#8b949e;margin-bottom:14px;}
</style>""", unsafe_allow_html=True)

def fmt(v): return f"${v:,.0f}"

st.markdown("## 🏛️ Pension & Income")
st.markdown("<p style='color:#8b949e;'>Configure your Federal Employees "
            "Retirement System (FERS) pension, Social Security estimates, "
            "and review your guaranteed income floor — the income you receive "
            "regardless of portfolio performance.</p>", unsafe_allow_html=True)

persons     = st.session_state.get("persons", [])
assumptions = st.session_state.get("assumptions", {})
inf         = assumptions.get("inflation_rate", 3.0) / 100.0

# ── FERS ──────────────────────────────────────────────────────────────────────
fers_persons = [p for p in persons if p.get("has_fers")]
if not fers_persons:
    st.info("No person has FERS enabled. Toggle it on the **Household Setup** page.")
else:
    for person in fers_persons:
        st.markdown(f"<div class='sh'>FERS Pension — {person['name']}</div>",
                    unsafe_allow_html=True)
        st.markdown("<div class='tip'>"
                    "Federal Employees Retirement System (FERS) is a defined-benefit pension. "
                    "Your annual benefit = <b>Multiplier × High-3 Salary × Years of Service</b>. "
                    "The multiplier is 1.0% in most cases, or 1.1% if you retire at age 62+ "
                    "with 20+ years of service. The high-3 is the average of your three highest "
                    "consecutive years of basic pay.</div>", unsafe_allow_html=True)

        fers = person.setdefault("fers", {})
        c1, c2, c3 = st.columns(3)
        fers["years_service_current"] = c1.number_input(
            "Current Years of Service", 0, 50,
            fers.get("years_service_current", 10), key=f"yos_{person['name']}",
            help="Your total years of creditable federal service today. Each additional year "
                 "of service adds directly to your pension (e.g., 1 more year at a \$100K "
                 "high-3 with a 1% multiplier = $1,000/yr more pension).")

        ret_key = "retirement_age_you" if person == persons[0] else "retirement_age_spouse"
        ret_age = c2.number_input(
            "Target Retirement Age", 50, 70,
            assumptions.get(ret_key, 62), key=f"ra_{person['name']}",
            help="The age at which you plan to retire from federal service. Must be at or above "
                 "your Minimum Retirement Age (MRA) shown to the right. Retiring at 62+ with "
                 "20+ years earns the 1.1% multiplier bonus.")
        assumptions[ret_key] = ret_age

        mra = get_fers_mra(person.get("birth_year", 1984))
        c3.markdown(f"""<div class='card' style='margin-top:4px;'>
            <div class='kpi-label'>Minimum Retirement Age (OPM)</div>
            <div class='kpi'>{mra}</div>
            <div style='color:#8b949e;font-size:.82rem;'>Birth year {person.get('birth_year',1984)}
            · Cannot retire with immediate pension before this age</div>
        </div>""", unsafe_allow_html=True)

        # Deferred retirement
        st.markdown("**Deferred Retirement Scenario**")
        fers["deferred"] = st.toggle(
            "Model deferred retirement (leave federal service early, collect pension later)",
            value=fers.get("deferred", False), key=f"def_{person['name']}",
            help="Turn this on to explore what happens if you leave federal service before "
                 "your planned retirement age — for example, taking a private sector job after "
                 "10 years. Your pension is frozen at separation but can be collected later. "
                 "Requires a minimum of 5 years of service.")

        if fers["deferred"]:
            st.markdown("<div class='tip'>"
                        "📋 <b>Deferred retirement rules (OPM):</b><br>"
                        "• Minimum 5 years of creditable service to qualify.<br>"
                        "• High-3 salary and years of service (YOS) are <b>frozen at separation</b> — no further accrual.<br>"
                        "• No FERS Supplement (only available for immediate retirees).<br>"
                        "• No cost of living adjustment (COLA) until pension payments begin.<br>"
                        "• Earliest collection: age 62 with 5–9 YOS; MRA with 10+ YOS."
                        "</div>", unsafe_allow_html=True)

            d1, d2, d3 = st.columns(3)
            fers["separation_age"] = d1.number_input(
                "Age at separation", person["age"], 65,
                fers.get("separation_age", person["age"] + 5),
                key=f"sep_age_{person['name']}",
                help="The age at which you leave federal service. Your salary projection and "
                     "YOS accrual stop here. The high-3 is computed from the 3 years prior.")

            max_yos = fers["years_service_current"] + (fers["separation_age"] - person["age"])
            fers["years_service_at_sep"] = d2.number_input(
                "YOS at separation", 5, int(max_yos),
                min(fers.get("years_service_at_sep", int(max_yos)), int(max_yos)),
                key=f"yos_sep_{person['name']}",
                help="Total years of creditable service when you leave. Defaults to current "
                     "YOS plus the years between now and your separation age.")

            yos_sep  = fers["years_service_at_sep"]
            min_col  = 62 if yos_sep < 10 else mra
            fers["collection_age"] = d3.number_input(
                "Age to begin collecting", min_col, 70,
                max(fers.get("collection_age", 62), min_col),
                key=f"col_age_{person['name']}",
                help=f"The age at which you elect to start receiving pension payments. "
                     f"Earliest allowed: age {min_col} based on {yos_sep} YOS. "
                     f"Note: delaying collection does NOT increase your deferred pension amount — "
                     f"unlike Social Security, there is no delayed-retirement credit for FERS.")

            gap = fers["collection_age"] - fers["separation_age"]
            if gap > 0:
                st.caption(f"⏳ {gap}-year income gap between separation "
                           f"(age {fers['separation_age']}) and collection "
                           f"(age {fers['collection_age']}). No pension and no COLA during this period.")

        # Survivor benefit
        st.markdown("**Survivor Benefit Election**")
        st.markdown("<div class='tip'>"
                    "The survivor benefit allows your spouse to continue receiving a portion of "
                    "your pension after your death, in exchange for a permanent reduction to your "
                    "pension while you are alive. This election is made at retirement and is "
                    "irrevocable (except under limited circumstances). Consider your spouse's "
                    "other income sources when deciding.</div>", unsafe_allow_html=True)

        surv_opts   = list(FERS_SURVIVOR_OPTIONS.keys())
        surv_labels = [FERS_SURVIVOR_OPTIONS[k][0] for k in surv_opts]
        cur_surv    = fers.get("survivor_option", "full")
        cur_idx     = surv_opts.index(cur_surv) if cur_surv in surv_opts else 2
        chosen      = st.radio(
            "Survivor benefit election", surv_labels, index=cur_idx,
            horizontal=True, key=f"surv_{person['name']}",
            help="None: no reduction, spouse receives nothing after your death. "
                 "Partial: 5% pension reduction, spouse receives 25% of your gross pension. "
                 "Full: 10% pension reduction, spouse receives 50% of your gross pension.")
        fers["survivor_option"] = surv_opts[surv_labels.index(chosen)]
        _, red, share = FERS_SURVIVOR_OPTIONS[fers["survivor_option"]]
        st.caption(f"Your pension is reduced by **{red*100:.0f}%**. "
                   f"After your death, survivor receives **{share*100:.0f}%** of your gross pension.")

        # Salary explanation
        with st.expander("ℹ️ How is the High-3 salary calculated?"):
            st.markdown("""
The **High-3** is the average of your **highest 3 consecutive years of basic pay**.

In this model:
- All salary sources for this person are **summed** to get total annual pay.
- That total is **projected forward** each year using your raise rate + random noise
  (configured on the Household Setup page).
- In normal mode, the final **3 years before retirement** are averaged → High-3.
- In deferred mode, the 3 years before **separation** are averaged instead.

The **teal dotted line** on the Accumulation page shows this individual salary
trajectory — exactly what feeds the High-3 calculation.
""")

        # Calculate pension
        # Only salaries marked as FERS basic pay feed the high-3
        fers_basic_sals = [s for s in person.get("salaries", [])
                           if s.get("is_fers_basic_pay", True)]
        if not fers_basic_sals:
            st.warning("⚠️ No salary is marked as FERS basic pay. "
                       "Toggle at least one salary as FERS basic pay on the "
                       "Household Setup page to compute the pension high-3.")
        primary_salary = sum(s.get("amount", 0) for s in fers_basic_sals)
        raise_r = np.mean([s.get("raise_rate",  3.0) for s in fers_basic_sals] or [3.0]) / 100
        raise_n = np.mean([s.get("raise_noise", 0.4) for s in fers_basic_sals] or [0.4]) / 100

        result = calculate_fers_pension(
            years_service_current = fers["years_service_current"],
            current_salary        = primary_salary,
            current_age           = person["age"],
            retirement_age        = ret_age,
            birth_year            = person.get("birth_year", 1984),
            survivor_option       = fers["survivor_option"],
            raise_rate            = raise_r,
            raise_noise           = raise_n,
            n_simulations         = 500,
            deferred              = fers.get("deferred", False),
            years_service_at_sep  = fers.get("years_service_at_sep"),
            separation_age        = fers.get("separation_age"),
            collection_age        = fers.get("collection_age"),
        )
        fers["_calc"] = result

        if fers.get("deferred") and not result.get("eligible", True):
            st.warning("⚠️ These settings may not meet FERS eligibility. "
                       "Minimum: 5 YOS and collect at 62, or 10 YOS and collect at MRA.")

        # KPI cards
        mode_label = (f"Deferred · sep {fers.get('separation_age')} · "
                      f"collect {fers.get('collection_age')}"
                      if fers.get("deferred") else f"Immediate · retire {ret_age}")

        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f"""<div class='card'>
            <div class='kpi-label'>Your Annual Pension (median)</div>
            <div class='kpi'>{fmt(result['pension_median'])}</div>
            <div style='color:#8b949e;font-size:.82rem;'>
                P10: {fmt(result['pension_p10'])} · P90: {fmt(result['pension_p90'])}<br>
                Range reflects salary raise uncertainty</div>
        </div>""", unsafe_allow_html=True)
        k2.markdown(f"""<div class='card'>
            <div class='kpi-label'>Survivor Pension</div>
            <div class='kpi'>{fmt(result['survivor_pension_med'])}</div>
            <div style='color:#8b949e;font-size:.82rem;'>
                {result['surv_share_pct']:.0f}% of gross · paid to spouse after your death</div>
        </div>""", unsafe_allow_html=True)
        k3.markdown(f"""<div class='card'>
            <div class='kpi-label'>Formula</div>
            <div class='kpi'>{result['multiplier']*100:.1f}% × {result['total_yos']} yrs</div>
            <div style='color:#8b949e;font-size:.82rem;'>
                High-3 median: {fmt(result['high3_median'])}</div>
        </div>""", unsafe_allow_html=True)
        k4.markdown(f"""<div class='card'>
            <div class='kpi-label'>Mode</div>
            <div class='kpi' style='font-size:1.1rem;
                color:{"#79c0ff" if fers.get("deferred") else "#00d4aa"};'>
                {"Deferred" if fers.get("deferred") else "Immediate"}</div>
            <div style='color:#8b949e;font-size:.82rem;'>{mode_label}</div>
        </div>""", unsafe_allow_html=True)

        if result["has_supplement"]:
            st.info("**FERS Supplement:** Because you're retiring before age 62, you'll receive "
                    "a supplement that approximates the Social Security (SS) benefit you've earned "
                    "through federal service. It is paid until you turn 62, then stops. "
                    "Configure your SS estimate below to calculate the supplement amount "
                    f"({result['supplement_fraction']*100:.0f}% × SS benefit, "
                    f"based on {result['total_yos']} years of service).")

        # Pension growth chart
        yrs      = np.arange(0, 31)
        ages_ch  = ret_age + yrs
        cola_r   = fers_cola_rate(inf)
        pen_nom  = result["pension_median"] * (1 + cola_r) ** yrs
        pen_real = pen_nom / (1 + inf) ** yrs
        surv_nom = result["survivor_pension_med"] * (1 + cola_r) ** yrs

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ages_ch, y=pen_nom,
                                  name="Your pension (nominal, COLA-adjusted)",
                                  line=dict(color="#00d4aa", width=2.5)))
        fig.add_trace(go.Scatter(x=ages_ch, y=pen_real,
                                  name="Your pension (today's dollars)",
                                  line=dict(color="#79c0ff", width=2, dash="dash")))
        fig.add_trace(go.Scatter(x=ages_ch, y=surv_nom,
                                  name="Survivor pension (nominal)",
                                  line=dict(color="#f0883e", width=2, dash="dot")))
        fig.update_layout(
            title="Pension Income Through Retirement",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e6edf3"), xaxis_title="Your Age",
            yaxis_title="Annual Amount", yaxis_tickformat="\$,.0f",
            xaxis=dict(gridcolor="#21262d"), yaxis=dict(gridcolor="#21262d"),
            legend=dict(bgcolor="rgba(22,27,34,0.8)", bordercolor="#21262d", borderwidth=1))
        _add_crosshair(fig)
        st.plotly_chart(fig, width='stretch')
        st.caption("**Teal (solid):** Your pension in future dollars, growing "
                   "each year by the FERS cost of living adjustment (COLA) "
                   "(consumer price index (CPI) minus 1 point when inflation "
                   "> 3%). **Blue (dashed):** The same pension expressed in "
                   "today's purchasing power — note how inflation slowly "
                   "erodes real value even with COLA. **Orange (dotted):** "
                   "What your survivor receives after your death, also "
                   "COLA-adjusted. The gap between teal and orange is the cost "
                   "of the survivor benefit election.")

# ── Social Security ────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Social Security</div>", unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "Social Security retirement benefits are based on your 35 highest-earning years. "
            "Your SSA.gov statement shows your estimated monthly benefit at Full Retirement Age "
            "(FRA). Claiming early (before FRA) permanently reduces your benefit; "
            "delaying past FRA earns 8% per year in delayed retirement credits up to age 70."
            "</div>", unsafe_allow_html=True)

col_ss_tog, _ = st.columns([2, 3])
include_ss = col_ss_tog.toggle(
    "Include Social Security in retirement income planning",
    value=st.session_state.get("include_ss", True),
    help="Toggle off to model retirement without Social Security (SS) — useful for conservative "
         "planning, or if Windfall Elimination Provision (WEP) or Government Pension Offset "
         "(GPO) significantly reduces your benefit. SS details are preserved when toggled off.")
st.session_state["include_ss"] = include_ss

if not include_ss:
    st.info("ℹ️ Social Security is **excluded** from all income projections on the "
            "Scenarios and Spend-Down pages. Re-enable the toggle above to include it.")

for person in persons:
    ss = person.setdefault("ss", {})
    st.markdown(f"**{person['name']}**")
    sc1, sc2, sc3 = st.columns(3)
    ss["monthly_fra"] = sc1.number_input(
        "Monthly Benefit at FRA ($)", 0, 10_000,
        int(ss.get("monthly_fra", 2_000)), 100, key=f"ss_fra_{person['name']}",
        help="Your estimated monthly Social Security (SS) benefit if you claim at your Full "
             "Retirement Age. Find this on your SSA.gov statement (ssa.gov/myaccount). "
             "As a very rough rule of thumb, SS typically replaces about 30–40% of "
             "pre-retirement income for average earners — so someone earning \$80K/yr "
             "might expect roughly \$2,000–\$2,700/mo at FRA. Your SSA statement is far "
             "more accurate than any estimate.")
    ss["fra"] = sc2.number_input(
        "Full Retirement Age", 62, 70, int(ss.get("fra", 67)),
        key=f"ss_fra_age_{person['name']}",
        help="The age at which you receive 100% of your earned benefit. For anyone born "
             "1960 or later, FRA is 67. Your SSA statement will confirm this.")
    ss["claim_age"] = sc3.number_input(
        "Planned Claim Age", 62, 70, int(ss.get("claim_age", 67)),
        key=f"ss_claim_{person['name']}",
        help="The age at which you plan to start collecting SS. Claiming before FRA "
             "reduces your benefit permanently (up to 30% reduction at age 62). "
             "Delaying past FRA increases it by 8%/year up to age 70 (+24% maximum). "
             "If you have a shorter life expectancy, claiming early may maximize lifetime benefits.")

    annual = ss_annual_benefit(ss["monthly_fra"], ss["fra"], ss["claim_age"])
    diff   = (annual / 12 - ss["monthly_fra"]) / max(ss["monthly_fra"], 1) * 100
    color  = "#3fb950" if diff >= 0 else "#f0883e"
    st.markdown(f"<span style='color:{color};font-weight:600;'>"
                f"Adjusted benefit: \${annual/12:,.0f}/mo ({diff:+.1f}% versus FRA) "
                f"→ \${annual:,.0f}/yr</span>", unsafe_allow_html=True)
    ss["_annual_benefit"] = annual

    # FERS supplement — always recompute from current calc and current SS benefit
    if person.get("has_fers"):
        fers = person.get("fers") or {}
        calc = fers.get("_calc") or {}
        fraction = calc.get("supplement_fraction", 0.0)
        has_supp = calc.get("has_supplement", False)
        # Explicitly zero if not applicable — guards against stale fraction values
        supp = (annual * fraction) if has_supp else 0.0
        fers["_supplement_annual"] = supp
        if has_supp:
            st.caption(
                f"**FERS Supplement:** ${supp:,.0f}/yr from age "
                f"{calc.get('retirement_age','?')} until age 62 "
                f"({fraction*100:.0f}% × your SS estimate of \${annual:,.0f}/yr, "
                f"based on {calc.get('total_yos', 0)} years of service). "
                f"This supplement stops abruptly at 62 and is unaffected by your SS claim age."
            )
        elif calc.get("deferred", False):
            st.caption("No FERS Supplement in deferred retirement mode.")
        else:
            ret_age_shown = calc.get("retirement_age", calc.get("collection_age", "?"))
            st.caption(f"No FERS Supplement — retiring at age {ret_age_shown} "
                       f"(supplement only applies when retiring before age 62).")
    st.markdown("---")

# ── Guaranteed income summary ──────────────────────────────────────────────────
st.markdown("<div class='sh'>📋 Guaranteed Income Summary at Retirement</div>",
            unsafe_allow_html=True)
st.markdown("<div class='tip'>"
            "This is your <b>income floor</b> — money you receive regardless of how the stock "
            "market performs. A higher floor means less portfolio withdrawal pressure and "
            "lower sequence-of-returns risk. The gap between this floor and your spending "
            "target is what your investment portfolio must cover.</div>", unsafe_allow_html=True)

pen  = sum(
    (p.get("fers") or {}).get("_calc", {}).get("pension_median", 0)
    for p in persons if p.get("has_fers")
)
supp = sum(
    (p.get("fers") or {}).get("_supplement_annual", 0)
    for p in persons if p.get("has_fers")
)
ss_t = sum((p.get("ss") or {}).get("_annual_benefit", 0) for p in persons)
if not st.session_state.get("include_ss", True):
    ss_t = 0.0
gtot = pen + supp + ss_t

g1, g2, g3, g4 = st.columns(4)
g1.metric("FERS Pension",             f"${pen:,.0f}/yr",
           help="Annual pension at retirement (median projection, after survivor reduction).")
g2.metric("FERS Supplement (pre-62)", f"${supp:,.0f}/yr",
           help="Paid from retirement until age 62 to bridge the gap before SS eligibility. "
                "Zero if retiring at 62+ or in deferred mode.")
g3.metric("Social Security",          f"${ss_t:,.0f}/yr",
           help="Combined SS for both household members at their planned claim ages. "
                "Zero if SS is excluded via the toggle above.")
g4.metric("Total Guaranteed",         f"${gtot:,.0f}/yr",
           help="Sum of all guaranteed income. Compare this to your spending targets on "
                "the Three Scenarios page to see how much your portfolio must supplement.")

st.session_state["_guaranteed_income"] = {
    "pension": pen, "supplement": supp, "ss": ss_t, "total": gtot}
