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
.tip{background:rgba(0,212,170,0.07);border:1px solid rgba(0,212,170,0.2);border-radius:8px;
     padding:10px 14px;font-size:.85rem;color:#8b949e;margin-bottom:14px;}
</style>""", unsafe_allow_html=True)

if "persons" not in st.session_state:
    st.session_state.persons = copy.deepcopy(DEFAULT_STATE["persons"])

def fmt(v): return f"${v:,.0f}"

# ── Export / Import sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💾 Save / Load Profile")
    st.caption("Your data lives only in this browser session. "
               "Export to JSON to save it between sessions.")

    EXPORT_VERSION = "1.2"
    EXPORTABLE_KEYS = [
        "persons", "assumptions", "scenarios",
        "include_ss", "spend_down", "tax_settings",
    ]

    def build_export():
        import datetime
        data = {"_version": EXPORT_VERSION,
                "_exported_at": datetime.datetime.now().isoformat(timespec="seconds")}
        for key in EXPORTABLE_KEYS:
            val = st.session_state.get(key)
            if val is not None:
                data[key] = val
        return data

    def clean_export(obj):
        """Strip computed/private keys (prefixed _) before export."""
        if isinstance(obj, dict):
            return {k: clean_export(v) for k, v in obj.items()
                    if not k.startswith("_")}
        if isinstance(obj, list):
            return [clean_export(i) for i in obj]
        return obj

    export_data = json.dumps(clean_export(build_export()), indent=2, default=str)
    st.download_button(
        "⬇️ Export profile (JSON)", export_data,
        file_name="retirement_profile.json", mime="application/json",
        help="Saves all accounts, salaries, FERS settings, SS configuration, "
             "market assumptions, scenario targets, SS toggle, spend-down "
             "allocation, and tax analysis inputs.")

    uploaded = st.file_uploader(
        "⬆️ Import profile (JSON)", type="json",
        help="Upload a previously exported profile. Compatible with exports "
             "from any version of this tool.")
    if uploaded:
        try:
            data = json.load(uploaded)
            imported, skipped = [], []
            for key in EXPORTABLE_KEYS:
                if key in data:
                    st.session_state[key] = data[key]
                    imported.append(key)
                else:
                    skipped.append(key)
            ver = data.get("_version", "pre-1.2")
            st.success(f"Profile loaded (v{ver}). "
                       f"Restored: {', '.join(imported)}.")
            if skipped:
                st.caption(f"Not in file (defaults kept): {', '.join(skipped)}")
            st.rerun()
        except Exception as e:
            st.error(f"Could not load file: {e}")

    st.markdown("---")
    if st.button("🔄 Reset to Defaults",
                  help="Clears all data and restores the built-in placeholder values."):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ── Person panel ──────────────────────────────────────────────────────────────
def render_person(pi: int):
    person = st.session_state.persons[pi]

    # Personal info
    st.markdown("<div class='sh'>Personal Information</div>", unsafe_allow_html=True)
    st.markdown("<div class='tip'>These fields drive age-based calculations throughout the app — "
                "retirement horizon, FERS MRA eligibility, life expectancy for spend-down "
                "projections, and Social Security FRA.</div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    person["name"] = c1.text_input(
        "Name", person["name"], key=f"n_{pi}",
        help="Display name used on charts and tables.")
    person["age"] = c2.number_input(
        "Current Age", 20, 80, person["age"], key=f"a_{pi}",
        help="Your age today. Used to calculate years until retirement and the "
             "accumulation horizon.")
    person["birth_year"] = c3.number_input(
        "Birth Year", 1940, 2005, person.get("birth_year", 1984), key=f"by_{pi}",
        help="Used to determine your FERS Minimum Retirement Age (MRA), which varies "
             "from 55–57 depending on birth year per OPM rules.")
    person["life_expectancy"] = c4.number_input(
        "Life Expectancy", 60, 110, person["life_expectancy"], key=f"le_{pi}",
        help="The age used as the end of your spend-down projection. SSA actuarial tables "
             "suggest ~85–87 for men and ~87–90 for women at age 40. Consider using a "
             "higher value (90–95) to plan conservatively.")

    # Salaries
    st.markdown("<div class='sh'>Salary / Income Sources</div>", unsafe_allow_html=True)
    st.markdown("<div class='tip'>Add every source of earned income. Multiple salary rows are useful "
                "if you hold more than one job or have distinct income streams (e.g., federal "
                "salary + consulting). The FERS high-3 pension calculation uses the <b>sum</b> of "
                "all salary rows for this person, projected forward with your raise assumptions."
                "</div>", unsafe_allow_html=True)

    salaries = person.setdefault("salaries", [])
    for si, sal in enumerate(salaries):
        # Stable key: use salary index (salaries rarely reorder, and no delete-shift problem
        # since salary indices are managed separately from accounts)
        sc1, sc2, sc3, sc4, sc5, sc6 = st.columns([2.5, 1.8, 1.3, 1.3, 1.3, 0.6])
        sal["label"] = sc1.text_input(
            "Label", sal["label"], key=f"sl_{pi}_{si}",
            help="A short description of this income source, e.g. 'GS-13 Step 5' or 'Side income'.")
        sal["amount"] = sc2.number_input(
            "Annual ($)", 0, 2_000_000, int(sal["amount"]), 100, key=f"sa_{pi}_{si}",
            help="Gross annual salary before taxes. Used for contribution scaling and pension high-3.")
        sal["raise_rate"] = sc3.number_input(
            "Raise %", 0.0, 10.0, float(sal["raise_rate"]), 0.1, key=f"sr_{pi}_{si}",
            help="Expected average annual pay raise.")
        sal["raise_noise"] = sc4.number_input(
            "Noise σ%", 0.0, 0.99, float(sal["raise_noise"]), 0.05, key=f"sn_{pi}_{si}",
            help="Std dev of random annual raise variation (<1%).")
        if person.get("has_fers"):
            sal["is_fers_basic_pay"] = sc5.toggle(
                "FERS basic pay", sal.get("is_fers_basic_pay", si == 0),
                key=f"sfp_{pi}_{si}",
                help="Only salaries marked here count toward your FERS high-3 pension calculation. "
                     "Non-federal income (consulting, part-time, etc.) should NOT be checked.")
        else:
            sal["is_fers_basic_pay"] = False
        sc6.markdown("<br>", unsafe_allow_html=True)
        if len(salaries) > 1 and sc6.button("🗑️", key=f"ds_{pi}_{si}",
                                              help="Remove this salary row."):
            salaries.pop(si); st.rerun()

    if st.button("➕ Add Salary Source", key=f"as_{pi}",
                  help="Add another income stream for this person."):
        salaries.append({"label": "New Salary", "amount": 50_000,
                          "raise_rate": 3.0, "raise_noise": 0.4})
        st.rerun()

    # Accounts
    st.markdown("<div class='sh'>Investment Accounts</div>", unsafe_allow_html=True)
    st.markdown("<div class='tip'>Add every investment and savings account. Each account can have "
                "its own asset allocation, contribution amount, and employer match. "
                "Account type determines tax treatment in the withdrawal sequencing and "
                "Roth vs Traditional analysis.</div>", unsafe_allow_html=True)

    accounts = person.setdefault("accounts", [])
    for acct in accounts:
        # Assign a stable uid if missing (handles imported profiles and old data)
        if "uid" not in acct:
            import uuid
            acct["uid"] = str(uuid.uuid4())[:8]
        uid = acct["uid"]  # stable across deletions and reorders

        atype = acct.get("account_type", "ira_roth")
        label = ACCOUNT_TYPES.get(atype, atype)
        with st.expander(f"🏦 **{acct['label']}** — {label}", expanded=False):
            r1, r2 = st.columns([3, 1])
            acct["label"] = r1.text_input(
                "Account Name", acct["label"], key=f"al_{uid}",
                help="A nickname for this account, e.g. 'TSP C Fund' or 'Vanguard Roth IRA'.")
            types = list(ACCOUNT_TYPES.keys())
            cur   = types.index(atype) if atype in types else 0
            acct["account_type"] = r2.selectbox(
                "Type", types, cur, format_func=lambda k: ACCOUNT_TYPES[k],
                key=f"at_{uid}",
                help="Account type determines tax treatment.")

            b1, b2, b3 = st.columns(3)
            acct["balance"] = b1.number_input(
                "Balance ($)", 0, 10_000_000, int(acct["balance"]), 100, key=f"ab_{uid}",
                help="Current account balance today.")
            acct["annual_contribution"] = b2.number_input(
                "Your Contribution ($/yr)", 0, 200_000,
                int(acct.get("annual_contribution", 0)), 100, key=f"ac_{uid}",
                help="The amount you personally contribute each year. For TSP, the 2026 "
                     "limit is $24,500 ($32,500 if age 50–59 or 64+; $35,750 if age 60–63). "
                     "For IRAs, $7,500 ($8,600 if 50+). For HSA, $4,400 individual / $8,750 family. "
                     "Contributions scale proportionally as your salary grows in the simulation.")

            if acct["account_type"] in EMPLOYER_MATCH_TYPES:
                acct["employer_match_pct"] = b3.slider(
                    "Employer Match (% of salary)", 0.0, 5.0,
                    float(acct.get("employer_match_pct", 0.0)), 0.25,
                    key=f"em_{uid}",
                    help="Your employer's matching contribution as a percentage of your salary. "
                         "Scales automatically as salary grows.")
                sal_total = sum(s.get("amount", 0) for s in person.get("salaries", []))
                est_match = sal_total * acct["employer_match_pct"] / 100
                b3.caption(f"≈ {fmt(est_match)}/yr at current salary")
            elif acct["account_type"] == "hsa":
                acct["employer_contrib_flat"] = b3.number_input(
                    "Employer Pass-Through ($/yr)", 0, 10_000,
                    int(acct.get("employer_contrib_flat", 0)), 100,
                    key=f"hsa_emp_{uid}",
                    help="Fixed annual employer HSA contribution. Not salary-linked.")
            else:
                acct["employer_match_pct"] = 0.0

            if acct["account_type"] in {"money_market", "savings"}:
                acct["allocation"] = {"stocks": 0.0, "bonds": 0.0, "cash": 1.0}
                st.info("💵 Earns the Cash Return rate set on the Assumptions page.")
            else:
                st.markdown("**Asset Allocation**")
                alloc = acct.setdefault("allocation",
                                        {"stocks": 0.70, "bonds": 0.20, "cash": 0.10})
                a1, a2, a3 = st.columns(3)
                alloc["stocks"] = a1.slider(
                    "Stocks %", 0, 100, int(alloc.get("stocks", 0.70) * 100),
                    key=f"as_{uid}",
                    help="Percentage in equities.") / 100
                alloc["bonds"] = a2.slider(
                    "Bonds %", 0, 100, int(alloc.get("bonds", 0.20) * 100),
                    key=f"ab2_{uid}",
                    help="Percentage in fixed income.") / 100
                alloc["cash"] = a3.slider(
                    "Cash %", 0, 100, int(alloc.get("cash", 0.10) * 100),
                    key=f"ac2_{uid}",
                    help="Percentage in stable value / money market.") / 100
                total = alloc["stocks"] + alloc["bonds"] + alloc["cash"]
                if abs(total - 1.0) > 0.02:
                    st.warning(f"⚠️ Allocation sums to {total*100:.0f}% — adjust to reach 100%.")

            if st.button("🗑️ Remove Account", key=f"da_{uid}",
                          help="Permanently remove this account from the projection."):
                accounts.remove(acct); st.rerun()

    new_type = st.selectbox(
        f"Account type to add ({person['name']})", list(ACCOUNT_TYPES.keys()),
        format_func=lambda k: ACCOUNT_TYPES[k], key=f"nt_{pi}",
        help="Select the type of account you want to add, then click the button below.")
    if st.button(f"➕ Add Account", key=f"aa_{pi}"):
        import uuid
        accounts.append({
            "label": ACCOUNT_TYPES[new_type],
            "uid": str(uuid.uuid4())[:8],
            "account_type": new_type,
            "balance": 0, "annual_contribution": 0, "employer_match_pct": 0.0,
            "allocation": {"stocks": 0.0, "bonds": 0.0, "cash": 1.0}
                         if new_type in {"money_market", "savings"}
                         else {"stocks": 0.70, "bonds": 0.20, "cash": 0.10},
        })
        st.rerun()

    st.markdown("<div class='sh'>Pension</div>", unsafe_allow_html=True)
    person["has_fers"] = st.toggle(
        "Has FERS Pension", person.get("has_fers", False), key=f"hf_{pi}",
        help="Enable if this person is a federal employee covered by the Federal Employees "
             "Retirement System. Unlocks the full FERS calculator on the Pension & Income page, "
             "including high-3 projection, FERS Supplement, survivor benefit elections, and "
             "deferred retirement modeling.")
    if person["has_fers"]:
        st.info("⚙️ Configure FERS details on the **Pension & Income** page.")

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("## 👥 Household Setup")
st.markdown("<p style='color:#8b949e;'>Enter accounts, salaries, and personal details. "
            "Use the sidebar to export your profile to JSON and reload it next session — "
            "data is not saved automatically.</p>", unsafe_allow_html=True)

tabs = st.tabs([p["name"] for p in st.session_state.persons])
for pi, tab in enumerate(tabs):
    with tab:
        render_person(pi)

# Summary table
st.markdown("---")
st.markdown("### 📋 Account Summary")
st.caption("A consolidated view of all accounts across both household members. "
           "Employer match shown as percentage and estimated dollar amount at current salary.")

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
