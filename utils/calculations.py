"""
Core financial calculations: Monte Carlo, FERS pension, Social Security, taxes.
Uses log-normal returns with Cholesky-correlated stock/bond draws.
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Tuple

# ─── IRS Uniform Lifetime RMD Table (SECURE 2.0, effective 2023) ─────────────
RMD_TABLE: Dict[int, float] = {
    72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9,
    78: 22.0, 79: 21.1, 80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7,
    84: 16.8, 85: 16.0, 86: 15.2, 87: 14.4, 88: 13.7, 89: 12.9,
    90: 12.2, 91: 11.5, 92: 10.8, 93: 10.1, 94: 9.5,  95: 8.9,
    96: 8.4,  97: 7.8,  98: 7.3,  99: 6.8,  100: 6.4, 101: 6.0,
    102: 5.6, 103: 5.2, 104: 4.9, 105: 4.6,
}

# ─── 2024 Federal Tax Brackets (Married Filing Jointly) ──────────────────────
TAX_BRACKETS_MFJ = [
    (23_200,        0.10),
    (94_300,        0.12),
    (201_050,       0.22),
    (383_900,       0.24),
    (487_450,       0.32),
    (731_200,       0.35),
    (float("inf"),  0.37),
]
STANDARD_DEDUCTION_MFJ = 29_200  # 2024

# ─── FERS MRA Table (OPM) ────────────────────────────────────────────────────
def get_fers_mra(birth_year: int) -> int:
    """Minimum Retirement Age per OPM (simplified to integer years)."""
    if birth_year < 1948:   return 55
    if birth_year <= 1952:  return 55
    if birth_year <= 1954:  return 55
    if birth_year <= 1956:  return 56
    if birth_year <= 1964:  return 57  # 56y6m–57 range, simplified
    return 57

# ─── Tax Calculations ─────────────────────────────────────────────────────────

def calculate_federal_tax(gross_income: float, year_offset: int = 0,
                           inflation_rate: float = 0.03) -> float:
    """Approximate federal income tax (MFJ), brackets inflation-adjusted."""
    factor = (1 + inflation_rate) ** year_offset
    deduction = STANDARD_DEDUCTION_MFJ * factor
    taxable = max(0.0, gross_income - deduction)
    brackets = [(lim * factor, rate) for lim, rate in TAX_BRACKETS_MFJ]
    tax, prev = 0.0, 0.0
    for limit, rate in brackets:
        if taxable <= prev:
            break
        band = min(taxable, limit) - prev
        tax += band * rate
        prev = limit
    return tax

def get_marginal_rate(gross_income: float, year_offset: int = 0,
                       inflation_rate: float = 0.03) -> float:
    """Marginal federal tax rate (MFJ)."""
    factor = (1 + inflation_rate) ** year_offset
    deduction = STANDARD_DEDUCTION_MFJ * factor
    taxable = max(0.0, gross_income - deduction)
    brackets = [(lim * factor, rate) for lim, rate in TAX_BRACKETS_MFJ]
    prev = 0.0
    for limit, rate in brackets:
        if taxable <= limit:
            return rate
        prev = limit
    return 0.37

def calculate_rmd(balance: float, age: int) -> float:
    """Required Minimum Distribution (SECURE 2.0 — starts at 73)."""
    if age < 73 or balance <= 0:
        return 0.0
    divisor = RMD_TABLE.get(min(age, 105), 2.9)
    return balance / divisor

# ─── Return Simulation Helpers ────────────────────────────────────────────────

def _lognormal_params(mean: float, vol: float) -> Tuple[float, float]:
    """Convert arithmetic mean/vol to log-normal μ, σ."""
    mu    = np.log((1 + mean)**2 / np.sqrt((1 + mean)**2 + vol**2))
    sigma = np.sqrt(np.log(1 + (vol / (1 + mean))**2))
    return mu, sigma

def _correlated_returns(
    n_sims: int,
    n_years: int,
    stock_r: float, stock_v: float,
    bond_r:  float, bond_v:  float,
    corr:    float = -0.20,
    rng:     Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate correlated annual stock/bond returns using Cholesky decomposition
    and log-normal sampling.  Returns (stock, bond) each shape (n_sims, n_years).
    """
    if rng is None:
        rng = np.random.default_rng()
    mu_s, sig_s = _lognormal_params(stock_r, stock_v)
    mu_b, sig_b = _lognormal_params(bond_r,  bond_v)
    cov = np.array([[1.0, corr], [corr, 1.0]])
    L   = np.linalg.cholesky(cov)
    z   = rng.standard_normal((2, n_sims, n_years))
    cz  = np.einsum("ij,jkl->ikl", L, z)
    stocks = np.exp(mu_s + sig_s * cz[0]) - 1
    bonds  = np.exp(mu_b + sig_b * cz[1]) - 1
    return stocks, bonds

def _portfolio_return(stocks, bonds, cash_r, ws, wb, wc):
    """Weighted portfolio return array."""
    return ws * stocks + wb * bonds + wc * cash_r

# ─── FERS Pension ─────────────────────────────────────────────────────────────

def fers_cola_rate(inflation: float) -> float:
    """FERS COLA per statute (sub-full CPI)."""
    if inflation <= 0.02:
        return inflation
    elif inflation <= 0.03:
        return inflation - 0.01
    else:
        return inflation - 0.02

def calculate_fers_pension(
    years_service_current: int,
    current_salary: float,
    current_age:   int,
    retirement_age: int,
    birth_year:    int,
    survivor_option: str  = "full",
    raise_rate:    float = 0.03,
    raise_noise:   float = 0.004,
    n_simulations: int  = 1000,
    rng: Optional[np.random.Generator] = None,
    # ── Deferred retirement parameters ──────────────────────────────────
    deferred:            bool = False,
    years_service_at_sep: int = None,   # YOS when leaving federal service
    separation_age:       int = None,   # age when leaving (freezes high-3)
    collection_age:       int = None,   # age when pension payments begin
) -> Dict:
    """
    FERS pension with simulated salary trajectory.

    Normal mode: salary projected to retirement_age; high-3 from final 3 years.

    Deferred mode (deferred=True):
      - Salary projected only to separation_age; high-3 frozen at that point.
      - YOS frozen at years_service_at_sep.
      - No FERS Supplement (not available for deferred retirees).
      - No COLA between separation and collection_age (pension is flat until it starts).
      - Collection begins at collection_age (must be ≥ 62 if YOS < 10, else ≥ MRA).

    Survivor options (OPM):
      none    → 0% reduction; survivor receives $0
      partial → 5% reduction; survivor receives 25% of gross pension
      full    → 10% reduction; survivor receives 50% of gross pension
    """
    from utils.defaults import FERS_SURVIVOR_OPTIONS
    if rng is None:
        rng = np.random.default_rng(0)

    if deferred:
        # ── Deferred path ────────────────────────────────────────────────
        sep_age  = separation_age if separation_age is not None else current_age
        yos_sep  = years_service_at_sep if years_service_at_sep is not None else years_service_current
        col_age  = collection_age if collection_age is not None else 62
        years_to_sep = max(0, sep_age - current_age)

        # Salary projected only to separation
        if years_to_sep > 0:
            noise    = rng.normal(0, raise_noise, (n_simulations, years_to_sep))
            salaries = np.zeros((n_simulations, years_to_sep + 1))
            salaries[:, 0] = current_salary
            for t in range(years_to_sep):
                salaries[:, t + 1] = salaries[:, t] * (1 + raise_rate + noise[:, t])
            high3 = (salaries[:, -3:].mean(axis=1)
                     if years_to_sep >= 3 else salaries.mean(axis=1))
        else:
            high3 = np.full(n_simulations, current_salary)

        # Multiplier: 1.1% only if collecting at ≥ 62 with ≥ 20 YOS
        multiplier  = 0.011 if (col_age >= 62 and yos_sep >= 20) else 0.010
        base_pension = high3 * multiplier * yos_sep
        total_yos    = yos_sep
        has_supplement = False   # never available for deferred retirees

        # Eligibility check
        mra = get_fers_mra(birth_year)
        eligible = (yos_sep >= 10 and col_age >= mra) or (yos_sep >= 5 and col_age >= 62)

    else:
        # ── Normal (immediate) path ──────────────────────────────────────
        years_to_retire = max(0, retirement_age - current_age)
        total_yos       = years_service_current + years_to_retire
        col_age         = retirement_age
        eligible        = True

        if years_to_retire > 0:
            noise    = rng.normal(0, raise_noise, (n_simulations, years_to_retire))
            salaries = np.zeros((n_simulations, years_to_retire + 1))
            salaries[:, 0] = current_salary
            for t in range(years_to_retire):
                salaries[:, t + 1] = salaries[:, t] * (1 + raise_rate + noise[:, t])
            high3 = (salaries[:, -3:].mean(axis=1)
                     if years_to_retire >= 3 else salaries.mean(axis=1))
        else:
            high3 = np.full(n_simulations, current_salary)

        multiplier   = 0.011 if (retirement_age >= 62 and total_yos >= 20) else 0.010
        base_pension = high3 * multiplier * total_yos
        has_supplement = retirement_age < 62

    # ── Survivor benefit (same for both paths) ───────────────────────────
    _, surv_reduction, surv_share = FERS_SURVIVOR_OPTIONS.get(
        survivor_option, FERS_SURVIVOR_OPTIONS["full"])
    net_pension      = base_pension * (1 - surv_reduction)
    survivor_pension = base_pension * surv_share

    mra = get_fers_mra(birth_year)
    supplement_frac = (min(total_yos / 40.0, 1.0)
                       if (has_supplement and not deferred) else 0.0)

    return {
        "pension_sims":         net_pension,
        "pension_median":       float(np.median(net_pension)),
        "pension_p10":          float(np.percentile(net_pension, 10)),
        "pension_p90":          float(np.percentile(net_pension, 90)),
        "survivor_pension_med": float(np.median(survivor_pension)),
        "high3_median":         float(np.median(high3)),
        "total_yos":            total_yos,
        "multiplier":           multiplier,
        "survivor_option":      survivor_option,
        "surv_reduction_pct":   surv_reduction * 100,
        "surv_share_pct":       surv_share * 100,
        "has_supplement":       has_supplement,
        "supplement_fraction":  supplement_frac,
        "mra":                  mra,
        "retirement_age":       col_age,
        "collection_age":       col_age,
        "deferred":             deferred,
        "eligible":             eligible if deferred else True,
        "cola_rate":            fers_cola_rate(0.03),
    }

# ─── Social Security ──────────────────────────────────────────────────────────

def ss_annual_benefit(monthly_fra: float, fra: int, claim_age: int) -> float:
    """Annual SS benefit adjusted for early/delayed claiming."""
    diff = claim_age - fra
    if diff < 0:
        months_early = -diff * 12
        if months_early <= 36:
            reduction = months_early * (5/9) / 100
        else:
            reduction = (36 * (5/9) + (months_early - 36) * (5/12)) / 100
        return monthly_fra * (1 - reduction) * 12
    elif diff > 0:
        return monthly_fra * (1 + 0.08 * diff) * 12
    return monthly_fra * 12

# ─── Accumulation Monte Carlo ─────────────────────────────────────────────────

def run_accumulation_mc(
    persons:    List[Dict],
    assumptions: Dict,
    seed: int = 42,
) -> Dict:
    """
    Simulate household portfolio accumulation to each person's retirement age.
    Contributions scale with simulated salary growth.

    Returns percentile trajectories (nominal + real) and per-account medians.
    """
    rng = np.random.default_rng(seed)

    ret_you    = assumptions["retirement_age_you"]
    ret_spouse = assumptions["retirement_age_spouse"]
    age_you    = persons[0]["age"]
    age_spouse = persons[1]["age"] if len(persons) > 1 else age_you

    n_years = max(ret_you - age_you, ret_spouse - age_spouse, 1)
    n_sims  = int(assumptions["n_simulations"])
    inf     = assumptions["inflation_rate"] / 100.0

    s_r  = assumptions["stock_return"]     / 100.0
    s_v  = assumptions["stock_volatility"] / 100.0
    b_r  = assumptions["bond_return"]      / 100.0
    b_v  = assumptions["bond_volatility"]  / 100.0
    c_r  = assumptions["cash_return"]      / 100.0
    corr = assumptions["stock_bond_correlation"]

    stocks_r, bonds_r = _correlated_returns(n_sims, n_years, s_r, s_v, b_r, b_v, corr, rng)

    # ── Collect all accounts with person index
    all_accounts: List[Dict] = []
    for pi, person in enumerate(persons):
        for acct in person.get("accounts", []):
            all_accounts.append({**acct, "_pi": pi})

    n_accts = len(all_accounts)
    acct_paths = np.zeros((n_accts, n_sims, n_years + 1))
    for i, a in enumerate(all_accounts):
        acct_paths[i, :, 0] = a["balance"]

    # ── Salary trajectories for contribution scaling
    sal_paths = np.zeros((2, n_sims, n_years + 1))
    for pi, person in enumerate(persons):
        if pi >= 2: break
        total_sal = sum(s["amount"] for s in person.get("salaries", [{}]))
        rr  = np.mean([s.get("raise_rate",  3.0) for s in person.get("salaries", [{}])]) / 100.0
        rn  = np.mean([s.get("raise_noise", 0.4) for s in person.get("salaries", [{}])]) / 100.0
        sal_paths[pi, :, 0] = total_sal
        for t in range(n_years):
            noise = rng.normal(0, rn, n_sims)
            sal_paths[pi, :, t + 1] = sal_paths[pi, :, t] * (1 + rr + noise)

    # ── Accumulation loop
    for t in range(n_years):
        for i, a in enumerate(all_accounts):
            pi = a["_pi"]
            alloc = a.get("allocation", {"stocks": 0.7, "bonds": 0.2, "cash": 0.1})
            ws, wb, wc = alloc.get("stocks", 0.7), alloc.get("bonds", 0.2), alloc.get("cash", 0.1)
            ret = ws * stocks_r[:, t] + wb * bonds_r[:, t] + wc * c_r

            # Stop contributions after that person's retirement
            person = persons[pi]
            ret_age = ret_you if pi == 0 else ret_spouse
            person_age_at_t = person["age"] + t
            if person_age_at_t >= ret_age:
                contribution = 0.0
            else:
                curr_sal = sal_paths[pi, :, t]
                init_sal = sal_paths[pi, :, 0]
                scale    = np.where(init_sal > 0, curr_sal / init_sal, 1.0)
                employee_contrib = a["annual_contribution"] * scale
                # HSA: flat employer pass-through; others: % of salary
                if a.get("account_type") == "hsa":
                    employer_contrib = float(a.get("employer_contrib_flat", 0))
                else:
                    match_pct = a.get("employer_match_pct", 0.0) / 100.0
                    employer_contrib = curr_sal * match_pct
                contribution = employee_contrib + employer_contrib

            acct_paths[i, :, t + 1] = acct_paths[i, :, t] * (1 + ret) + contribution

    # ── Aggregate
    portfolio_paths = acct_paths.sum(axis=0)    # (n_sims, n_years+1)
    inf_factors = np.array([(1 + inf) ** t for t in range(n_years + 1)])
    portfolio_real = portfolio_paths / inf_factors[np.newaxis, :]

    pcts = [5, 10, 25, 50, 75, 90, 95]
    pct_nom  = {f"p{p}": np.percentile(portfolio_paths, p, axis=0) for p in pcts}
    pct_real = {f"p{p}": np.percentile(portfolio_real,  p, axis=0) for p in pcts}

    acct_medians = {}
    for i, a in enumerate(all_accounts):
        real_a = acct_paths[i] / inf_factors[np.newaxis, :]
        acct_medians[a["label"]] = {
            "nominal": np.percentile(acct_paths[i], 50, axis=0),
            "real":    np.percentile(real_a, 50, axis=0),
            "type":    a["account_type"],
        }

    total_sal_paths = sal_paths.sum(axis=0)  # (n_sims, n_years+1)

    # FERS person salary path (person index 0 if has_fers)
    fers_pi = next((i for i, p in enumerate(persons) if p.get("has_fers")), None)
    fers_sal_p50 = (np.percentile(sal_paths[fers_pi], 50, axis=0)
                    if fers_pi is not None else None)

    # Final portfolio distribution (at each person's retirement year)
    yr_you    = max(ret_you - age_you, 0)
    yr_spouse = max(ret_spouse - age_spouse, 0)
    final_you    = portfolio_paths[:, min(yr_you, n_years)]
    final_spouse = portfolio_paths[:, min(yr_spouse, n_years)]

    return {
        "portfolio_paths":  portfolio_paths,
        "portfolio_real":   portfolio_real,
        "pct_nom":          pct_nom,
        "pct_real":         pct_real,
        "acct_medians":     acct_medians,
        "acct_labels":      [a["label"] for a in all_accounts],
        "acct_types":       [a["account_type"] for a in all_accounts],
        "salary_p50":       np.percentile(total_sal_paths, 50, axis=0),
        "fers_salary_p50":  fers_sal_p50,
        "inf_factors":      inf_factors,
        "years":            np.arange(n_years + 1),
        "n_years":          n_years,
        "n_sims":           n_sims,
        "age_start":        min(age_you, age_spouse),
        "final_portfolio_sims": final_you,          # use for distribution MC
    }

# ─── Distribution Monte Carlo ─────────────────────────────────────────────────

def run_distribution_mc(
    initial_sims:   np.ndarray,   # (n_sims,) portfolio at retirement
    income_sources: Dict,          # pension, SS, supplement amounts
    assumptions:    Dict,
    retirement_age_you:    int,
    retirement_age_spouse: int,
    life_exp_you:   int,
    life_exp_spouse: int,
    annual_spending: float,        # today's dollars target spend
    reserve_amount:  float = 75_000,
    seed: int = 99,
) -> Dict:
    """
    Monte Carlo distribution phase with sequential income sources.
    Income waterfall: pension → FERS supplement → SS → portfolio gap.
    Survivor adjustments applied at actuarial midpoint.
    """
    rng = np.random.default_rng(seed)
    inf = assumptions["inflation_rate"] / 100.0
    s_r = assumptions["stock_return"]     / 100.0
    s_v = assumptions["stock_volatility"] / 100.0
    b_r = assumptions["bond_return"]      / 100.0
    b_v = assumptions["bond_volatility"]  / 100.0
    c_r = assumptions["cash_return"]      / 100.0
    corr = assumptions["stock_bond_correlation"]
    n_sims = len(initial_sims)

    retire_start = min(retirement_age_you, retirement_age_spouse)
    max_age      = max(life_exp_you, life_exp_spouse)
    n_years      = max_age - retire_start + 1

    # Conservative allocation in retirement
    ws_ret, wb_ret, wc_ret = 0.50, 0.40, 0.10

    stocks_r, bonds_r = _correlated_returns(n_sims, n_years, s_r, s_v, b_r, b_v, corr, rng)

    pension_nominal   = income_sources.get("pension_annual",   0.0)
    pension_cola      = fers_cola_rate(inf)
    supplement_annual = income_sources.get("supplement_annual", 0.0)
    ss_you_annual     = income_sources.get("ss_you_annual",    0.0)
    ss_spouse_annual  = income_sources.get("ss_spouse_annual", 0.0)
    ss_you_start      = income_sources.get("ss_you_start_age", 67)
    ss_spouse_start   = income_sources.get("ss_spouse_start_age", 67)
    survivor_benefit  = income_sources.get("survivor_benefit", True)
    survivor_share    = income_sources.get("survivor_share",   0.50)  # actual elected share

    portfolio = np.copy(initial_sims).astype(float)
    paths = np.zeros((n_sims, n_years + 1))
    paths[:, 0] = portfolio

    income_breakdown = []  # median income per year for chart

    for t in range(n_years):
        age_you    = retirement_age_you    + t
        age_spouse = retirement_age_spouse + t

        inf_t = (1 + inf) ** t

        # --- Survivor check (deterministic at life expectancy midpoint)
        you_alive    = age_you    <= life_exp_you
        spouse_alive = age_spouse <= life_exp_spouse

        # Pension: full while you're alive, survivor portion after
        if you_alive:
            pen = pension_nominal * (1 + pension_cola) ** t
        else:
            pen = pension_nominal * (1 + pension_cola) ** t * (survivor_share if survivor_benefit else 0.0)

        # FERS Supplement (only for you, only before age 62)
        supp = supplement_annual * inf_t if (you_alive and age_you < 62) else 0.0

        # Social Security
        ss_you   = ss_you_annual   * inf_t if (you_alive   and age_you    >= ss_you_start)   else 0.0
        ss_sp    = ss_spouse_annual * inf_t if (spouse_alive and age_spouse >= ss_spouse_start) else 0.0

        # Survivor SS adjustment: survivor gets max of own or 100% of deceased's
        if not you_alive and spouse_alive:
            ss_sp = max(ss_sp, ss_you_annual * inf_t)
        if not spouse_alive and you_alive:
            ss_you = max(ss_you, ss_spouse_annual * inf_t * 0.50)  # spousal adjustment

        guaranteed = pen + supp + ss_you + ss_sp

        target_spend = annual_spending * inf_t
        gap = max(0.0, target_spend - guaranteed)

        ret = ws_ret * stocks_r[:, t] + wb_ret * bonds_r[:, t] + wc_ret * c_r

        paths[:, t + 1] = np.maximum(paths[:, t] * (1 + ret) - gap, 0.0)

        income_breakdown.append({
            "year":        t,
            "age_you":     age_you,
            "pension":     pen,
            "supplement":  supp,
            "ss_you":      ss_you,
            "ss_spouse":   ss_sp,
            "guaranteed":  guaranteed,
            "portfolio_withdrawal": gap,
            "total_spend": target_spend,
        })

    inf_factors = np.array([(1 + inf) ** t for t in range(n_years + 1)])
    paths_real  = paths / inf_factors[np.newaxis, :]

    pcts = [5, 10, 25, 50, 75, 90, 95]
    pct_nom  = {f"p{p}": np.percentile(paths, p, axis=0) for p in pcts}
    pct_real = {f"p{p}": np.percentile(paths_real, p, axis=0) for p in pcts}

    # Probability of success: never falls below real reserve
    reserve_nom = reserve_amount * inf_factors
    success = np.all(paths >= reserve_nom[np.newaxis, :], axis=1)
    prob_success = float(success.mean() * 100)

    ages_you    = np.arange(retirement_age_you,    retirement_age_you    + n_years + 1)
    ages_spouse = np.arange(retirement_age_spouse, retirement_age_spouse + n_years + 1)

    return {
        "paths":            paths,
        "paths_real":       paths_real,
        "pct_nom":          pct_nom,
        "pct_real":         pct_real,
        "prob_success":     prob_success,
        "income_df":        pd.DataFrame(income_breakdown),
        "inf_factors":      inf_factors,
        "years":            np.arange(n_years + 1),
        "ages_you":         ages_you,
        "ages_spouse":      ages_spouse,
        "n_years":          n_years,
        "n_sims":           n_sims,
        "retire_start":     retire_start,
    }

# ─── Roth vs Traditional Analysis ─────────────────────────────────────────────

def roth_vs_traditional(
    annual_contribution: float,
    current_age:         int,
    retirement_age:      int,
    gross_income_now:    float,
    expected_retirement_income: float,
    stock_r:  float = 0.07,
    bond_r:   float = 0.035,
    ws:       float = 0.70,
    inflation: float = 0.03,
    n_sims:   int   = 500,
    seed:     int   = 7,
) -> Dict:
    """
    Compare after-tax wealth for Roth vs Traditional contributions over career.
    Traditional analysis includes investing the annual tax savings in a taxable account.
    """
    years = max(retirement_age - current_age, 1)
    rng   = np.random.default_rng(seed)

    marg_now    = get_marginal_rate(gross_income_now)
    marg_retire = get_marginal_rate(expected_retirement_income,
                                     year_offset=years, inflation_rate=inflation)

    s_v, b_v = 0.15, 0.06
    stocks_r, bonds_r = _correlated_returns(n_sims, years, stock_r, 0.15, bond_r, 0.06, -0.20, rng)
    port_r = ws * stocks_r + (1 - ws) * bonds_r   # (n_sims, years)

    # ── Roth: invest after-tax dollars, grows tax-free
    roth_contrib = annual_contribution  # assume already after-tax designation
    roth = np.zeros((n_sims, years + 1))
    for t in range(years):
        roth[:, t + 1] = roth[:, t] * (1 + port_r[:, t]) + roth_contrib

    # ── Traditional: invest pre-tax, taxed at retirement rate on withdrawal
    trad = np.zeros((n_sims, years + 1))
    for t in range(years):
        trad[:, t + 1] = trad[:, t] * (1 + port_r[:, t]) + annual_contribution
    trad_after_tax = trad * (1 - marg_retire)

    # ── Tax savings invested in taxable (penalizes trad for fair comparison)
    tax_saving = annual_contribution * marg_now  # tax saved each year by going trad
    taxable = np.zeros((n_sims, years + 1))
    for t in range(years):
        # Taxable account grows at after-tax return (~85% of gross, LTCG)
        after_tax_r = port_r[:, t] * 0.85
        taxable[:, t + 1] = taxable[:, t] * (1 + after_tax_r) + tax_saving

    trad_total_after_tax = trad_after_tax + taxable

    # ── Paths for chart
    roth_p = np.percentile(roth, [10, 50, 90], axis=0)              # (3, years+1)
    trad_p = np.percentile(trad_total_after_tax, [10, 50, 90], axis=0)

    roth_final = float(np.median(roth[:, years]))
    trad_final = float(np.median(trad_total_after_tax[:, years]))

    # ── Crossover year (median)
    crossover = None
    for t in range(years + 1):
        if float(np.median(trad_total_after_tax[:, t])) > float(np.median(roth[:, t])):
            crossover = t
            break

    return {
        "roth_final_p50":     roth_final,
        "trad_final_p50":     trad_final,
        "roth_better":        roth_final > trad_final,
        "advantage":          abs(roth_final - trad_final),
        "marg_now":           marg_now,
        "marg_retire":        marg_retire,
        "roth_paths":         roth_p,              # [10, 50, 90] x years+1
        "trad_paths":         trad_p,
        "years":              np.arange(years + 1),
        "tax_saving_annual":  tax_saving,
        "crossover_year":     crossover,
    }

# ─── Savings Rate Optimizer ────────────────────────────────────────────────────

def estimate_needed_portfolio(
    annual_gap:       float,   # spending minus guaranteed income
    years_retirement: int,     # planning horizon in years
    real_return:      float,   # expected real portfolio return (annual)
    mode:             str      = "sustain",  # "deplete" | "sustain" | "grow"
    reserve:          float    = 75_000,
    grow_rate:        float    = 0.01,       # target annual real growth for "grow"
) -> float:
    """
    Estimate portfolio needed at retirement to fund a given annual spending gap.
    Uses deterministic present-value formulas as a quick estimate.
    """
    if annual_gap <= 0:
        return 0.0
    r = max(real_return, 0.0001)
    if mode == "sustain":
        # Perpetuity: P = gap / r
        return annual_gap / r
    elif mode == "grow":
        # Gordon Growth: P = gap / (r - g)
        return annual_gap / max(r - grow_rate, 0.001)
    else:
        # "deplete": PV of annuity ending at reserve
        # PV_annuity = gap * (1-(1+r)^-n)/r, then add PV of reserve
        pv_annuity  = annual_gap * (1 - (1 + r) ** -years_retirement) / r
        pv_reserve  = reserve / (1 + r) ** years_retirement
        return pv_annuity + pv_reserve

def calculate_scenario_spending(
    portfolio_p50:    float,
    guaranteed_income: float,
    years_retirement: int,
    real_return:      float,
    reserve:          float = 75_000,
    grow_rate:        float = 0.005,
) -> dict:
    """
    Given a projected portfolio at retirement (P50) and guaranteed income floor,
    calculate the annual spending that defines each scenario.

    Grow:    spending = guaranteed + portfolio × (real_return - grow_rate)
             Portfolio grows at grow_rate in real terms.
    Sustain: spending = guaranteed + portfolio × real_return
             Portfolio stays flat in real terms (perpetuity).
    Deplete: spending = guaranteed + annuity payment that draws portfolio
             from current value down to reserve by end of years_retirement.
    """
    r = max(real_return, 0.0001)

    grow_gap    = max(portfolio_p50 * (r - grow_rate), 0.0)
    sustain_gap = portfolio_p50 * r

    # Deplete: annuity that draws (portfolio - PV_reserve) over n years
    pv_reserve  = reserve / (1 + r) ** years_retirement
    usable      = max(portfolio_p50 - pv_reserve, 0.0)
    if usable > 0 and years_retirement > 0:
        deplete_gap = usable * r / (1 - (1 + r) ** -years_retirement)
    else:
        deplete_gap = sustain_gap  # fallback

    return {
        "grow_spending":    round(guaranteed_income + grow_gap,    -2),
        "sustain_spending": round(guaranteed_income + sustain_gap, -2),
        "deplete_spending": round(guaranteed_income + deplete_gap, -2),
        "grow_gap":    grow_gap,
        "sustain_gap": sustain_gap,
        "deplete_gap": deplete_gap,
    }

def additional_contribution_needed(
    portfolio_target:   float,
    portfolio_p50_now:  float,   # current median projected portfolio
    years_to_retire:    int,
    real_return:        float,
) -> float:
    """
    Additional annual contribution needed to close a portfolio gap.
    Uses FV of annuity formula.
    """
    gap = max(portfolio_target - portfolio_p50_now, 0)
    if gap <= 0 or years_to_retire <= 0:
        return 0.0
    r = max(real_return, 0.0001)
    fv_factor = ((1 + r) ** years_to_retire - 1) / r
    return gap / fv_factor
