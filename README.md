# 📊 Retirement Planning Dashboard

A personal retirement planning tool built with Streamlit, featuring Monte Carlo
simulation, FERS pension modeling, tax-aware analysis, and three-scenario
spend-down projections.

---

## Features

- **Monte Carlo simulation** — log-normal, correlated stock/bond returns across
  1,000+ simulations with percentile fan charts
- **FERS pension calculator** — immediate and deferred retirement modes, all three
  survivor benefit elections, FERS Supplement bridge, sub-full COLA
- **Three retirement scenarios** — Grow / Sustain / Deplete with probability of
  success and savings rate optimizer
- **Tax-aware analysis** — Roth vs Traditional comparison, RMD schedule, Roth
  conversion window, IRMAA risk flags
- **Dual-life survivor modeling** — income under both-alive / you-die-first /
  spouse-dies-first states
- **Inflation toggle** — view all projections in nominal or today's dollars
- **Export / Import** — save and restore your full profile as JSON
- **Account types** — TSP (Roth + Traditional), IRA, 401k/403b, HSA (with
  employer pass-through), taxable brokerage, money market, savings

---

## Prerequisites

Choose one path:

| Path | Requirements |
|---|---|
| Docker (recommended) | Docker Desktop or Docker Engine + Compose |
| Local Python | Python 3.11+ |

---

## Quick Start — Docker (Recommended)

```bash
# 1. Unzip and enter the project folder
unzip retirement_planner.zip
cd retirement_planner

# 2. Build and start
docker compose up --build

# 3. Open in your browser
# http://localhost:8501
```

To stop:

```bash
docker compose down
```

**Hot reloading:** The `pages/`, `utils/`, and `Home.py` files are volume-mounted
into the container. Edits to those files take effect immediately — no rebuild
needed. You only need to rebuild if you change `requirements.txt`.

---

## Quick Start — Local Python

```bash
# 1. Unzip and enter the project folder
unzip retirement_planner.zip
cd retirement_planner

# 2. Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
streamlit run Home.py

# 5. Open in your browser
# http://localhost:8501
```

---

## Deployment — Streamlit Community Cloud (Free)

This is the recommended way to host the app so it's accessible from any device.

1. Push the project to a **GitHub repository** (public or private).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app** and select your repository.
4. Set **Main file path** to `Home.py`.
5. Click **Deploy**.

The app will be live at `https://<your-app>.streamlit.app` within a few minutes.

> **Note:** All data entered in the app is held in session memory only — nothing
> is written to disk or stored between sessions. Use the **Export Profile** button
> on the Household Setup sidebar to save your inputs as a JSON file and reload
> them next time.

---

## Project Structure

```
retirement_planner/
├── Home.py                        # Landing page and navigation
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .streamlit/
│   └── config.toml                # Dark theme configuration
├── pages/
│   ├── 1_👥_Household_Setup.py    # Accounts, salaries, export/import
│   ├── 2_🏛️_Pension_&_Income.py   # FERS pension, SS, guaranteed income
│   ├── 3_⚙️_Assumptions.py        # Return assumptions, inflation, MC settings
│   ├── 4_📈_Accumulation.py       # Pre-retirement Monte Carlo
│   ├── 5_🎯_Three_Scenarios.py    # Grow / Sustain / Deplete comparison
│   ├── 6_📉_Spend_Down.py         # Retirement drawdown and survivor analysis
│   └── 7_💰_Tax_Analysis.py       # Roth vs Trad, RMDs, IRMAA, brackets
└── utils/
    ├── calculations.py            # Core math: Monte Carlo, FERS, SS, tax, RMDs
    ├── charts.py                  # Plotly chart factory
    └── defaults.py                # Placeholder default values and constants
```

---

## Recommended Workflow

1. **Household Setup** — Enter accounts and salaries for both partners. Use
   placeholder/anonymized values if you prefer not to store real numbers.
2. **Pension & Income** — Configure your FERS details (immediate or deferred),
   Social Security estimates, and the SS include/exclude toggle.
3. **Assumptions** — Adjust return expectations, inflation, and retirement ages.
   The return distribution preview updates live.
4. **Accumulation** — Run the Monte Carlo to see portfolio growth to retirement.
   Check the teal dotted salary line — that is the trajectory used to compute
   your FERS high-3.
5. **Three Scenarios** — The core page. Set spending targets for each scenario and
   run all three. Use the savings rate optimizer to see whether you are on track.
6. **Spend-Down** — Drill into a single spending target with full income waterfall,
   survivor analysis, and sequence-of-returns risk callout.
7. **Tax Analysis** — Compare Roth vs Traditional, identify your Roth conversion
   window, and check for IRMAA exposure.
8. **Export your profile** — Use the sidebar on Household Setup to download your
   inputs as JSON. Upload the same file next session to avoid re-entering data.

---

## Key Assumptions and Methodology

### Monte Carlo
Returns are drawn from a log-normal distribution parameterized by arithmetic mean
and standard deviation. Stock and bond returns are correlated using Cholesky
decomposition (default correlation: −0.20). Each simulation runs independently
from today through the last survivor's life expectancy.

### FERS Pension
- **Immediate retirement:** Multiplier is 1.0% × high-3 × YOS, or 1.1% if
  retiring at age 62+ with 20+ years of service. High-3 is the average of the
  three highest consecutive years of basic pay, projected using your raise rate
  assumption with random noise.
- **Deferred retirement:** High-3 and YOS are frozen at separation. No FERS
  Supplement. No COLA accrues between separation and collection start.
- **FERS COLA:** Sub-full CPI per statute — CPI minus 1 percentage point when
  inflation exceeds 3%, full CPI when between 2–3%, and full CPI when below 2%.
- **Survivor benefit:** Three OPM options modeled — None (0% reduction),
  Partial / 25% to survivor (5% reduction), Full / 50% to survivor (10%
  reduction).

### Social Security
Benefits are adjusted for early or delayed claiming relative to your Full
Retirement Age using the SSA's standard reduction/credit factors. A toggle on
the Pension & Income page excludes SS from all income projections for
conservative planning.

### Taxes
Federal income tax is estimated using Married Filing Jointly brackets, inflated
forward each year. State taxes are not modeled. RMDs follow the IRS Uniform
Lifetime Table under SECURE 2.0 (starting age 73). IRMAA thresholds are based
on 2024 MFJ brackets.

### Inflation
All projections run internally in nominal dollars. The global "Today's Dollars"
toggle divides every value by the cumulative inflation factor to show real
purchasing power.

---

## Disclaimer

This tool is for personal planning and educational purposes only. It is not
financial, legal, or tax advice. Consult a qualified financial advisor, CPA, or
attorney before making retirement, investment, or tax decisions. All default
values are placeholders and do not represent any real individual's finances.

FERS rules summarized here are based on OPM guidance current as of early 2025.
Rules, brackets, and thresholds may change. Verify details at
[opm.gov](https://www.opm.gov/retirement-services/) and
[ssa.gov](https://www.ssa.gov).
