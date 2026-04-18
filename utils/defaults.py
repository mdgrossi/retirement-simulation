"""Default configuration — all dollar amounts are placeholder/anonymized values."""

ACCOUNT_TYPES = {
    "tsp_traditional":        "TSP (Traditional)",
    "tsp_roth":               "TSP (Roth)",
    "ira_traditional":        "IRA (Traditional)",
    "ira_roth":               "IRA (Roth)",
    "retirement_traditional": "401k / 403b (Traditional)",
    "retirement_roth":        "401k / 403b (Roth)",
    "hsa":                    "HSA",
    "brokerage":              "Taxable Brokerage",
    "money_market":           "Money Market",
    "savings":                "Savings Account",
}

# Tax treatment classification
TAXABLE_ACCOUNT_TYPES  = {"tsp_traditional", "ira_traditional", "retirement_traditional"}
ROTH_ACCOUNT_TYPES     = {"tsp_roth", "ira_roth", "retirement_roth"}
HSA_ACCOUNT_TYPES      = {"hsa"}
CASH_LIKE_TYPES        = {"money_market", "savings"}

# Account types that support employer matching
EMPLOYER_MATCH_TYPES   = {"tsp_traditional", "tsp_roth", "retirement_traditional", "retirement_roth"}

# FERS survivor benefit options:
#   none    → 0% reduction, survivor receives $0/yr
#   partial → 5% reduction, survivor receives 25% of your pension
#   full    → 10% reduction, survivor receives 50% of your pension
FERS_SURVIVOR_OPTIONS = {
    "none":    ("No Survivor Benefit",      0.00, 0.00),
    "partial": ("Partial (25% to survivor)",0.05, 0.25),
    "full":    ("Full (50% to survivor)",   0.10, 0.50),
}

DEFAULT_STATE = {
    "persons": [
        {
            "name": "You",
            "age": 40,
            "birth_year": 1984,
            "life_expectancy": 87,
            "salaries": [
                {"label": "Federal Salary", "amount": 100_000,
                 "raise_rate": 3.0, "raise_noise": 0.4},
            ],
            "accounts": [
                {
                    "label": "TSP (Traditional)",
                    "account_type": "tsp_traditional",
                    "balance": 180_000,
                    "annual_contribution": 18_000,
                    "employer_match_pct": 5.0,
                    "allocation": {"stocks": 0.70, "bonds": 0.20, "cash": 0.10},
                },
                {
                    "label": "TSP (Roth)",
                    "account_type": "tsp_roth",
                    "balance": 40_000,
                    "annual_contribution": 4_500,
                    "employer_match_pct": 0.0,
                    "allocation": {"stocks": 0.80, "bonds": 0.15, "cash": 0.05},
                },
                {
                    "label": "Roth IRA",
                    "account_type": "ira_roth",
                    "balance": 25_000,
                    "annual_contribution": 7_000,
                    "employer_match_pct": 0.0,
                    "allocation": {"stocks": 0.85, "bonds": 0.10, "cash": 0.05},
                },
                {
                    "label": "HSA",
                    "account_type": "hsa",
                    "balance": 12_000,
                    "annual_contribution": 4_200,
                    "employer_match_pct": 0.0,
                    "employer_contrib_flat": 500,
                    "allocation": {"stocks": 0.60, "bonds": 0.30, "cash": 0.10},
                },
            ],
            "has_fers": True,
            "fers": {
                "years_service_current": 10,
                "survivor_option": "full",
            },
            "has_ss": True,
            "ss": {"monthly_fra": 2_500, "fra": 67, "claim_age": 67},
        },
        {
            "name": "Spouse",
            "age": 38,
            "birth_year": 1986,
            "life_expectancy": 90,
            "salaries": [
                {"label": "Primary Salary", "amount": 80_000,
                 "raise_rate": 3.0, "raise_noise": 0.4},
            ],
            "accounts": [
                {
                    "label": "403(b) Traditional",
                    "account_type": "retirement_traditional",
                    "balance": 90_000,
                    "annual_contribution": 15_000,
                    "employer_match_pct": 3.0,
                    "allocation": {"stocks": 0.70, "bonds": 0.25, "cash": 0.05},
                },
                {
                    "label": "403(b) Roth",
                    "account_type": "retirement_roth",
                    "balance": 20_000,
                    "annual_contribution": 5_000,
                    "employer_match_pct": 0.0,
                    "allocation": {"stocks": 0.75, "bonds": 0.20, "cash": 0.05},
                },
                {
                    "label": "Roth IRA",
                    "account_type": "ira_roth",
                    "balance": 30_000,
                    "annual_contribution": 7_000,
                    "employer_match_pct": 0.0,
                    "allocation": {"stocks": 0.85, "bonds": 0.10, "cash": 0.05},
                },
                {
                    "label": "Traditional IRA",
                    "account_type": "ira_traditional",
                    "balance": 18_000,
                    "annual_contribution": 0,
                    "employer_match_pct": 0.0,
                    "allocation": {"stocks": 0.65, "bonds": 0.30, "cash": 0.05},
                },
            ],
            "has_fers": False,
            "fers": None,
            "has_ss": True,
            "ss": {"monthly_fra": 1_800, "fra": 67, "claim_age": 67},
        },
    ],
    "assumptions": {
        "stock_return":            7.0,
        "stock_volatility":       15.0,
        "bond_return":             3.5,
        "bond_volatility":         6.0,
        "cash_return":             2.0,
        "stock_bond_correlation": -0.20,
        "inflation_rate":          3.0,
        "n_simulations":        1_000,
        "show_real_dollars":    False,
        "retirement_age_you":      62,
        "retirement_age_spouse":   60,
    },
    "scenarios": {
        "deplete_spending":  130_000,
        "sustain_spending":  105_000,
        "grow_spending":      80_000,
        "reserve_amount":     75_000,
        "results":            None,
    },
}
