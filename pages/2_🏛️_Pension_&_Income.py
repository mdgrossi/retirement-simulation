"""Page 2 — Pension & Income"""

import streamlit as st
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.calculations import calculate_fers_pension, ss_annual_benefit, get_fers_mra, fers_cola_rate
from utils.defaults import FERS_SURVIVOR_OPTIONS
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
</style>""", unsafe_allow_html=True)

def fmt(v): return f"${v:,.0f}"

st.markdown("## 🏛️ Pension & Income")
st.markdown("<p style='color:#8b949e;'>FERS pension, Social Security, and guaranteed income summary.</p>",
            unsafe_allow_html=True)

persons     = st.session_state.get("persons", [])
assumptions = st.session_state.get("assumptions", {})
inf         = assumptions.get("inflation_rate", 3.0) / 100.0

# ── FERS ─────────────────────────────────────────────────────────────────────
fers_persons = [p for p in persons if p.get("has_fers")]
if not fers_persons:
    st.info("No person has FERS enabled. Toggle it on the Household Setup page.")
else:
    for person in fers_persons:
        st.markdown(f"<div class='sh'>FERS — {person['name']}</div>", unsafe_allow_html=True)
        fers = person.setdefault("fers", {})

        c1, c2, c3 = st.columns(3)
        fers["years_service_current"] = c1.number_input(
            "Current Years of Service", 0, 50, fers.get("years_service_current", 10),
            key=f"yos_{person['name']}")

        ret_key = "retirement_age_you" if person == persons[0] else "retirement_age_spouse"
        ret_age = c2.number_input("Target Retirement Age", 50, 70,
                                   assumptions.get(ret_key, 62), key=f"ra_{person['name']}")
        assumptions[ret_key] = ret_age

        mra = get_fers_mra(person.get("birth_year", 1984))
        c3.markdown(f"""<div class='card' style='margin-top:4px;'>
            <div class='kpi-label'>Min. Retirement Age (OPM)</div>
            <div class='kpi'>{mra}</div>
            <div style='color:#8b949e;font-size:.82rem;'>Birth year {person.get('birth_year',1984)}</div>
        </div>""", unsafe_allow_html=True)

        # ── Deferred retirement ───────────────────────────────────────────
        st.markdown("**Deferred Retirement Scenario**")
        fers["deferred"] = st.toggle(
            "Model deferred retirement (leave federal service early, collect pension later)",
            value=fers.get("deferred", False),
            key=f"def_{person['name']}",
            help="Useful for modeling what happens if you leave federal service before "
                 "your planned retirement age. High-3 and YOS are frozen at separation.")

        if fers["deferred"]:
            st.markdown("<div style='background:rgba(121,192,255,0.08);border:1px solid "
                        "rgba(121,192,255,0.2);border-radius:8px;padding:10px 14px;"
                        "font-size:.85rem;margin-bottom:10px;'>"
                        "📋 <b>FERS deferred retirement rules:</b> Minimum 5 years of service required. "
                        "Collection begins at age 62 (5–9 YOS) or MRA (10+ YOS). "
                        "High-3 and YOS are frozen at separation — no further accrual. "
                        "No FERS Supplement. No COLA until payments begin.</div>",
                        unsafe_allow_html=True)

            d1, d2, d3 = st.columns(3)
            fers["separation_age"] = d1.number_input(
                "Age at separation", person["age"], 65,
                fers.get("separation_age", person["age"] + 5),
                key=f"sep_age_{person['name']}",
                help="The age at which you leave federal service. Salary and YOS freeze here.")

            max_yos_at_sep = fers["years_service_current"] + (
                fers["separation_age"] - person["age"])
            fers["years_service_at_sep"] = d2.number_input(
                "YOS at separation", 5, int(max_yos_at_sep),
                min(fers.get("years_service_at_sep",
                    fers["years_service_current"] + (fers["separation_age"] - person["age"])),
                    int(max_yos_at_sep)),
                key=f"yos_sep_{person['name']}",
                help="Years of creditable service when you leave. Default: current YOS + years to separation.")

            yos_sep = fers["years_service_at_sep"]
            min_col = 62 if yos_sep < 10 else mra
            fers["collection_age"] = d3.number_input(
                "Age to begin collecting pension", min_col, 70,
                max(fers.get("collection_age", 62), min_col),
                key=f"col_age_{person['name']}",
                help=f"Earliest: age {min_col} based on {yos_sep} YOS. "
                     f"Delaying does NOT increase the pension amount for deferred retirees.")

            gap_yrs = fers["collection_age"] - fers["separation_age"]
            if gap_yrs > 0:
                st.caption(
                    f"⏳ {gap_yrs}-year gap between separation (age {fers['separation_age']}) "
                    f"and collection (age {fers['collection_age']}). "
                    f"No pension income and no COLA during this period.")

        # Survivor option
        st.markdown("**Survivor Benefit Election**")
        surv_opts   = list(FERS_SURVIVOR_OPTIONS.keys())
        surv_labels = [FERS_SURVIVOR_OPTIONS[k][0] for k in surv_opts]
        cur_surv    = fers.get("survivor_option", "full")
        cur_idx     = surv_opts.index(cur_surv) if cur_surv in surv_opts else 2
        chosen      = st.radio("", surv_labels, index=cur_idx,
                                horizontal=True, key=f"surv_{person['name']}")
        fers["survivor_option"] = surv_opts[surv_labels.index(chosen)]
        _, red, share = FERS_SURVIVOR_OPTIONS[fers["survivor_option"]]
        st.caption(
            f"Your pension is reduced by **{red*100:.0f}%**. "
            f"After your death, survivor receives **{share*100:.0f}%** of your gross pension."
        )

        # ── Salary explanation ────────────────────────────────────────────────
        with st.expander("ℹ️ How is the High-3 salary calculated?"):
            st.markdown("""
The **High-3** is the average of your **highest 3 consecutive years of basic pay** before retirement.

In this model:
- All salary sources for this person are **summed** to get total annual pay.
- That total is **projected forward** each year using your raise rate + random noise.
- The final **3 years before retirement** are averaged to produce the High-3.

Raise noise is kept below 1% std dev per your specification. The High-3 shown below is the **median** across all simulations.
""")

        primary_salary = sum(s.get("amount", 0) for s in person.get("salaries", []))
        raise_r = np.mean([s.get("raise_rate",  3.0) for s in person.get("salaries", [])]) / 100
        raise_n = np.mean([s.get("raise_noise", 0.4) for s in person.get("salaries", [])]) / 100

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

        # Eligibility warning for deferred
        if fers.get("deferred") and not result.get("eligible", True):
            st.warning("⚠️ With the current settings, this deferred retirement may not meet "
                       "FERS eligibility requirements. Minimum: 5 YOS + collect at 62, "
                       "or 10 YOS + collect at MRA.")

        if fers.get("deferred"):
            mode_label = (f"Deferred · Sep age {fers.get('separation_age')} · "
                          f"Collect age {fers.get('collection_age')}")
        else:
            mode_label = f"Immediate · retire age {ret_age}"

        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f"""<div class='card'>
            <div class='kpi-label'>Your Annual Pension (median)</div>
            <div class='kpi'>{fmt(result['pension_median'])}</div>
            <div style='color:#8b949e;font-size:.82rem;'>P10: {fmt(result['pension_p10'])} · P90: {fmt(result['pension_p90'])}</div>
        </div>""", unsafe_allow_html=True)
        k2.markdown(f"""<div class='card'>
            <div class='kpi-label'>Survivor Pension</div>
            <div class='kpi'>{fmt(result['survivor_pension_med'])}</div>
            <div style='color:#8b949e;font-size:.82rem;'>{result['surv_share_pct']:.0f}% of gross · after your death</div>
        </div>""", unsafe_allow_html=True)
        k3.markdown(f"""<div class='card'>
            <div class='kpi-label'>Formula</div>
            <div class='kpi'>{result['multiplier']*100:.1f}% × {result['total_yos']} yrs</div>
            <div style='color:#8b949e;font-size:.82rem;'>High-3 median: {fmt(result['high3_median'])}</div>
        </div>""", unsafe_allow_html=True)
        cola = fers_cola_rate(inf) * 100
        k4.markdown(f"""<div class='card'>
            <div class='kpi-label'>Mode</div>
            <div class='kpi' style='font-size:1.1rem;color:{"#79c0ff" if fers.get("deferred") else "#00d4aa"};'>
                {"Deferred" if fers.get("deferred") else "Immediate"}</div>
            <div style='color:#8b949e;font-size:.82rem;'>{mode_label}</div>
        </div>""", unsafe_allow_html=True)

        if result["has_supplement"]:
            st.info(f"**FERS Supplement** paid from age {ret_age} until 62. "
                    f"Configure SS below to calculate the amount "
                    f"({result['supplement_fraction']*100:.0f}% of SS benefit, "
                    f"based on {result['total_yos']} years).")

        # Pension growth chart
        yrs   = np.arange(0, 31)
        ages  = ret_age + yrs
        cola_r = fers_cola_rate(inf)
        pen_nom  = result["pension_median"] * (1 + cola_r) ** yrs
        pen_real = pen_nom / (1 + inf) ** yrs
        surv_nom = result["survivor_pension_med"] * (1 + cola_r) ** yrs

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ages, y=pen_nom,  name="Your pension (nominal)",
                                  line=dict(color="#00d4aa", width=2.5)))
        fig.add_trace(go.Scatter(x=ages, y=pen_real, name="Your pension (today's $)",
                                  line=dict(color="#79c0ff", width=2, dash="dash")))
        fig.add_trace(go.Scatter(x=ages, y=surv_nom, name="Survivor pension (nominal)",
                                  line=dict(color="#f0883e", width=2, dash="dot")))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font=dict(color="#e6edf3"), xaxis_title="Your Age",
                          yaxis_title="Annual Amount", yaxis_tickformat="$,.0f",
                          xaxis=dict(gridcolor="#21262d"), yaxis=dict(gridcolor="#21262d"),
                          legend=dict(bgcolor="rgba(22,27,34,0.8)", bordercolor="#21262d", borderwidth=1))
        st.plotly_chart(fig, width='stretch')

# ── Social Security ───────────────────────────────────────────────────────────
st.markdown("<div class='sh'>Social Security</div>", unsafe_allow_html=True)

col_ss_tog, _ = st.columns([2, 3])
include_ss = col_ss_tog.toggle(
    "Include SS in retirement income planning",
    value=st.session_state.get("include_ss", True),
    help="Turn off to model retirement without Social Security — "
         "useful for conservative planning or if WEP/GPO applies.")
st.session_state["include_ss"] = include_ss

if not include_ss:
    st.info("ℹ️ Social Security is **excluded** from income projections on the "
            "Scenarios and Spend-Down pages. SS details below are still saved "
            "and will reappear if you re-enable the toggle.")

for person in persons:
    ss = person.setdefault("ss", {})
    st.markdown(f"**{person['name']}**")
    sc1, sc2, sc3 = st.columns(3)
    ss["monthly_fra"] = sc1.number_input("Monthly Benefit at FRA ($)", 0, 10_000,
                                          int(ss.get("monthly_fra", 2_000)), 100,
                                          key=f"ss_fra_{person['name']}")
    ss["fra"]         = sc2.number_input("Full Retirement Age", 62, 70,
                                          int(ss.get("fra", 67)), key=f"ss_fra_age_{person['name']}")
    ss["claim_age"]   = sc3.number_input("Planned Claim Age", 62, 70,
                                          int(ss.get("claim_age", 67)), key=f"ss_claim_{person['name']}")

    annual = ss_annual_benefit(ss["monthly_fra"], ss["fra"], ss["claim_age"])
    diff   = (annual / 12 - ss["monthly_fra"]) / max(ss["monthly_fra"], 1) * 100
    color  = "#3fb950" if diff >= 0 else "#f0883e"
    st.markdown(f"<span style='color:{color};font-weight:600;'>"
                f"Adjusted: ${annual/12:,.0f}/mo ({diff:+.1f}% vs FRA) → ${annual:,.0f}/yr</span>",
                unsafe_allow_html=True)
    ss["_annual_benefit"] = annual

    # FERS supplement calc
    if person.get("has_fers"):
        fers = person.get("fers") or {}
        calc = fers.get("_calc") or {}
        supp = annual * calc.get("supplement_fraction", 0)
        fers["_supplement_annual"] = supp
        if calc.get("has_supplement"):
            st.markdown(f"**FERS Supplement:** ${supp:,.0f}/yr until age 62")
    st.markdown("---")

# ── Summary ───────────────────────────────────────────────────────────────────
st.markdown("<div class='sh'>📋 Guaranteed Income Summary at Retirement</div>", unsafe_allow_html=True)
pen  = sum((p.get("fers") or {}).get("_calc", {}).get("pension_median", 0) for p in persons)
supp = sum((p.get("fers") or {}).get("_supplement_annual", 0) for p in persons)
ss_t = sum((p.get("ss") or {}).get("_annual_benefit", 0) for p in persons)
gtot = pen + supp + ss_t

g1, g2, g3, g4 = st.columns(4)
g1.metric("FERS Pension",            f"${pen:,.0f}/yr")
g2.metric("FERS Supplement (pre-62)", f"${supp:,.0f}/yr")
g3.metric("Social Security",          f"${ss_t:,.0f}/yr")
g4.metric("Total Guaranteed",         f"${gtot:,.0f}/yr")

st.session_state["_guaranteed_income"] = {
    "pension": pen, "supplement": supp, "ss": ss_t, "total": gtot}
