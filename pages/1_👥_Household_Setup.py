"""Page 1 — Household Setup"""

import streamlit as st
import sys, os, json, copy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.defaults import ACCOUNT_TYPES, EMPLOYER_MATCH_TYPES, DEFAULT_STATE

st.set_page_config(page_title="Household Setup", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:18px 22px;margin-bottom:14px;}
.sh{font-size:1.05rem;font-weight:600;color:#e6edf3;border-bottom:1px solid #21262d;padding-bottom:8px;margin:16px 0 12px 0;}
</style>""", unsafe_allow_html=True)

if "persons" not in st.session_state:
    st.session_state.persons = copy.deepcopy(DEFAULT_STATE["persons"])

def fmt(v): return f"${v:,.0f}"

# ── Export / Import sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💾 Save / Load Profile")

    def build_export():
        return {
            "persons":     st.session_state.get("persons", []),
            "assumptions": st.session_state.get("assumptions", {}),
            "scenarios":   st.session_state.get("scenarios", {}),
        }

    export_data = json.dumps(build_export(), indent=2, default=str)
    st.download_button("⬇️ Export profile (JSON)", export_data,
                        file_name="retirement_profile.json", mime="application/json")

    uploaded = st.file_uploader("⬆️ Import profile (JSON)", type="json")
    if uploaded:
        try:
            data = json.load(uploaded)
            if "persons" in data:
                st.session_state.persons     = data["persons"]
            if "assumptions" in data:
                st.session_state.assumptions = data["assumptions"]
            if "scenarios" in data:
                st.session_state.scenarios   = data["scenarios"]
            st.success("Profile loaded!")
            st.rerun()
        except Exception as e:
            st.error(f"Could not load file: {e}")

    st.markdown("---")
    if st.button("🔄 Reset to Defaults"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ── Person panel ─────────────────────────────────────────────────────────────
def render_person(pi: int):
    person = st.session_state.persons[pi]

    # Personal info
    st.markdown("<div class='sh'>Personal</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    person["name"]            = c1.text_input("Name", person["name"], key=f"n_{pi}")
    person["age"]             = c2.number_input("Age", 20, 80, person["age"], key=f"a_{pi}")
    person["birth_year"]      = c3.number_input("Birth Year", 1940, 2005,
                                                  person.get("birth_year", 1984), key=f"by_{pi}")
    person["life_expectancy"] = c4.number_input("Life Expectancy", 60, 110,
                                                  person["life_expectancy"], key=f"le_{pi}")

    # Salaries
    st.markdown("<div class='sh'>Salary / Income Sources</div>", unsafe_allow_html=True)
    salaries = person.setdefault("salaries", [])
    for si, sal in enumerate(salaries):
        sc1, sc2, sc3, sc4, sc5 = st.columns([3, 2, 1.5, 1.5, 0.6])
        sal["label"]       = sc1.text_input("Label", sal["label"], key=f"sl_{pi}_{si}")
        sal["amount"]      = sc2.number_input("Annual ($)", 0, 2_000_000,
                                               int(sal["amount"]), 100, key=f"sa_{pi}_{si}")
        sal["raise_rate"]  = sc3.number_input("Raise %", 0.0, 10.0,
                                               float(sal["raise_rate"]), 0.1, key=f"sr_{pi}_{si}")
        sal["raise_noise"] = sc4.number_input("Noise σ%", 0.0, 0.99,
                                               float(sal["raise_noise"]), 0.05, key=f"sn_{pi}_{si}",
                                               help="Std dev of random annual raise variation (<1%)")
        sc5.markdown("<br>", unsafe_allow_html=True)
        if len(salaries) > 1 and sc5.button("🗑️", key=f"ds_{pi}_{si}"):
            salaries.pop(si); st.rerun()

    if st.button("➕ Add Salary Source", key=f"as_{pi}"):
        salaries.append({"label": "New Salary", "amount": 50_000,
                          "raise_rate": 3.0, "raise_noise": 0.4})
        st.rerun()

    # Accounts
    st.markdown("<div class='sh'>Investment Accounts</div>", unsafe_allow_html=True)
    accounts = person.setdefault("accounts", [])
    for ai, acct in enumerate(accounts):
        atype = acct.get("account_type", "ira_roth")
        label = ACCOUNT_TYPES.get(atype, atype)
        with st.expander(f"🏦 **{acct['label']}** — {label}", expanded=False):
            r1, r2 = st.columns([3, 1])
            acct["label"] = r1.text_input("Account Name", acct["label"], key=f"al_{pi}_{ai}")
            types = list(ACCOUNT_TYPES.keys())
            cur   = types.index(atype) if atype in types else 0
            acct["account_type"] = r2.selectbox("Type", types, cur,
                                                  format_func=lambda k: ACCOUNT_TYPES[k],
                                                  key=f"at_{pi}_{ai}")

            b1, b2, b3 = st.columns(3)
            acct["balance"] = b1.number_input("Balance ($)", 0, 10_000_000,
                                               int(acct["balance"]), 100, key=f"ab_{pi}_{ai}")
            acct["annual_contribution"] = b2.number_input("Your Contribution ($)", 0, 200_000,
                                                            int(acct.get("annual_contribution", 0)),
                                                            100, key=f"ac_{pi}_{ai}")

            # Employer match: % of salary for eligible types; flat dollar for HSA; hidden otherwise
            if acct["account_type"] in EMPLOYER_MATCH_TYPES:
                acct["employer_match_pct"] = b3.slider(
                    "Employer Match (% of salary)", 0.0, 5.0,
                    float(acct.get("employer_match_pct", 0.0)), 0.25,
                    key=f"em_{pi}_{ai}",
                    help="Scales automatically as salary grows. Max 5% per TSP/IRS rules.")
                sal_total = sum(s.get("amount", 0) for s in person.get("salaries", []))
                est_match = sal_total * acct["employer_match_pct"] / 100
                b3.caption(f"≈ {fmt(est_match)}/yr at current salary")
            elif acct["account_type"] == "hsa":
                acct["employer_contrib_flat"] = b3.number_input(
                    "Employer Pass-Through ($)", 0, 10_000,
                    int(acct.get("employer_contrib_flat", 0)), 100,
                    key=f"hsa_emp_{pi}_{ai}",
                    help="Fixed annual employer HSA contribution (pass-through or seeding). "
                         "Not salary-linked — stays flat each year.")
            else:
                acct["employer_match_pct"] = 0.0

            # Allocation — cash-like accounts default to 100% cash
            if acct["account_type"] in {"money_market", "savings"}:
                acct["allocation"] = {"stocks": 0.0, "bonds": 0.0, "cash": 1.0}
                st.info("Money market / savings accounts earn the cash return rate set in Assumptions.")
            else:
                st.markdown("**Asset Allocation**")
                alloc = acct.setdefault("allocation", {"stocks": 0.70, "bonds": 0.20, "cash": 0.10})
                a1, a2, a3 = st.columns(3)
                alloc["stocks"] = a1.slider("Stocks %", 0, 100,
                                             int(alloc.get("stocks", 0.70) * 100), key=f"as_{pi}_{ai}") / 100
                alloc["bonds"]  = a2.slider("Bonds %",  0, 100,
                                             int(alloc.get("bonds",  0.20) * 100), key=f"ab2_{pi}_{ai}") / 100
                alloc["cash"]   = a3.slider("Cash %",   0, 100,
                                             int(alloc.get("cash",   0.10) * 100), key=f"ac2_{pi}_{ai}") / 100
                total = alloc["stocks"] + alloc["bonds"] + alloc["cash"]
                if abs(total - 1.0) > 0.02:
                    st.warning(f"⚠️ Allocation sums to {total*100:.0f}% — should be 100%.")

            if st.button("🗑️ Remove Account", key=f"da_{pi}_{ai}"):
                accounts.pop(ai); st.rerun()

    new_type = st.selectbox(f"Type to add ({person['name']})", list(ACCOUNT_TYPES.keys()),
                             format_func=lambda k: ACCOUNT_TYPES[k], key=f"nt_{pi}")
    if st.button(f"➕ Add Account", key=f"aa_{pi}"):
        accounts.append({
            "label": ACCOUNT_TYPES[new_type], "account_type": new_type,
            "balance": 0, "annual_contribution": 0, "employer_match_pct": 0.0,
            "allocation": {"stocks": 0.0, "bonds": 0.0, "cash": 1.0}
                         if new_type in {"money_market", "savings"}
                         else {"stocks": 0.70, "bonds": 0.20, "cash": 0.10},
        })
        st.rerun()

    person["has_fers"] = st.toggle("Has FERS Pension", person.get("has_fers", False), key=f"hf_{pi}")
    if person["has_fers"]:
        st.info("⚙️ Configure FERS details on the **Pension & Income** page.")

# ── Main ─────────────────────────────────────────────────────────────────────
st.markdown("## 👥 Household Setup")
st.markdown("<p style='color:#8b949e;'>All changes are held in memory during your session. "
            "Use the sidebar to export/import your profile as JSON.</p>", unsafe_allow_html=True)

tabs = st.tabs([p["name"] for p in st.session_state.persons])
for pi, tab in enumerate(tabs):
    with tab:
        render_person(pi)

# Summary table
st.markdown("---")
st.markdown("### 📋 Account Summary")
import pandas as pd
rows = []
for p in st.session_state.persons:
    sal = sum(s.get("amount", 0) for s in p.get("salaries", []))
    for a in p.get("accounts", []):
        match_est = sal * a.get("employer_match_pct", 0.0) / 100
        rows.append({
            "Owner":          p["name"],
            "Account":        a["label"],
            "Type":           ACCOUNT_TYPES.get(a.get("account_type",""), ""),
            "Balance":        fmt(a["balance"]),
            "Your Contrib":   fmt(a.get("annual_contribution", 0)),
            "Employer Match": f"{a.get('employer_match_pct',0):.2f}% ≈ {fmt(match_est)}",
            "Stocks":         f"{a.get('allocation',{}).get('stocks',0)*100:.0f}%",
        })
if rows:
    st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
