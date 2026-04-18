"""
Plotly chart factory with consistent theming for the retirement planner.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Dict, List, Optional

# ─── Design tokens ────────────────────────────────────────────────────────────
BG      = "#0d1117"
BG2     = "#161b22"
TEXT    = "#e6edf3"
MUTED   = "#8b949e"
TEAL    = "#00d4aa"
GREEN   = "#3fb950"
BLUE    = "#79c0ff"
AMBER   = "#f0883e"
RED     = "#f85149"
PURPLE  = "#bc8cff"

SCENARIO_COLORS = {
    "grow":    GREEN,
    "sustain": BLUE,
    "deplete": AMBER,
}

ACCOUNT_PALETTE = [TEAL, BLUE, PURPLE, AMBER, GREEN, RED,
                   "#ff9f43", "#54a0ff", "#5f27cd", "#01abc3"]

BASE_LAYOUT = dict(
    paper_bgcolor = "rgba(0,0,0,0)",
    plot_bgcolor  = "rgba(0,0,0,0)",
    font          = dict(family="Inter, sans-serif", color=TEXT, size=13),
    legend        = dict(bgcolor="rgba(22,27,34,0.8)", bordercolor=MUTED,
                         borderwidth=1, font=dict(size=12)),
    margin        = dict(l=10, r=10, t=40, b=10),
    xaxis         = dict(gridcolor="#21262d", zerolinecolor="#21262d", color=MUTED),
    yaxis         = dict(gridcolor="#21262d", zerolinecolor="#21262d", color=MUTED),
)

def _fmt_m(v: float) -> str:
    """Format dollar value with M/K suffix."""
    if abs(v) >= 1e6:   return f"${v/1e6:.2f}M"
    if abs(v) >= 1e3:   return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

# ─── Fan / Cone Charts ────────────────────────────────────────────────────────

def fan_chart(
    x:       np.ndarray,
    pcts:    Dict[str, np.ndarray],   # {"p5", "p10", ..., "p95"}
    title:   str,
    color:   str   = TEAL,
    x_label: str   = "Year",
    y_label: str   = "Portfolio Value",
    show_real_toggle: bool = False,
    real_pcts: Optional[Dict] = None,
    x_is_age: bool = False,
) -> go.Figure:
    """Percentile fan/cone chart with shaded bands."""
    fig = go.Figure()

    bands = [("p5", "p95"), ("p10", "p90"), ("p25", "p75")]
    alphas = [0.12, 0.20, 0.30]

    for (lo, hi), alpha in zip(bands, alphas):
        rgb = _hex_to_rgb(color)
        fill_color = f"rgba({rgb},{alpha})"
        fig.add_trace(go.Scatter(
            x=list(x) + list(x[::-1]),
            y=list(pcts[hi]) + list(pcts[lo][::-1]),
            fill="toself",
            fillcolor=fill_color,
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Median line
    fig.add_trace(go.Scatter(
        x=x, y=pcts["p50"],
        name="Median (P50)",
        line=dict(color=color, width=2.5),
        hovertemplate=f"<b>{'Age' if x_is_age else 'Year'} %{{x}}</b><br>{y_label}: %{{customdata}}<extra></extra>",
        customdata=[_fmt_m(v) for v in pcts["p50"]],
    ))

    # Annotation bands legend
    fig.add_trace(go.Scatter(x=[None], y=[None], name="P25–P75", mode="lines",
                              line=dict(color=color, width=8), opacity=0.3))
    fig.add_trace(go.Scatter(x=[None], y=[None], name="P10–P90", mode="lines",
                              line=dict(color=color, width=8), opacity=0.20))

    layout = dict(**BASE_LAYOUT)
    layout["title"] = dict(text=title, font=dict(size=16, color=TEXT), x=0.02)
    layout["xaxis"]["title"] = x_label
    layout["yaxis"]["title"] = y_label
    layout["yaxis"]["tickformat"] = "$,.0f"

    fig.update_layout(**layout)
    return fig

def multi_scenario_fan(
    results: Dict[str, Dict],    # {"grow": dist_result, "sustain": ..., "deplete": ...}
    use_real: bool = False,
    x_label: str = "Age (You)",
) -> go.Figure:
    """Overlay fan charts for all three scenarios on one figure."""
    fig = go.Figure()
    labels = {"grow": "Grow", "sustain": "Sustain", "deplete": "Deplete"}

    for key, res in results.items():
        color = SCENARIO_COLORS[key]
        pcts  = res["pct_real"] if use_real else res["pct_nom"]
        x     = res["ages_you"]
        rgb   = _hex_to_rgb(color)

        # Shaded band (25–75)
        fig.add_trace(go.Scatter(
            x=list(x) + list(x[::-1]),
            y=list(pcts["p75"]) + list(pcts["p25"][::-1]),
            fill="toself",
            fillcolor=f"rgba({rgb},0.15)",
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=False, hoverinfo="skip",
        ))
        # Median
        fig.add_trace(go.Scatter(
            x=x, y=pcts["p50"],
            name=labels[key],
            line=dict(color=color, width=2.5),
            hovertemplate=f"<b>Age %{{x}}</b><br>{labels[key]}: %{{customdata}}<extra></extra>",
            customdata=[_fmt_m(v) for v in pcts["p50"]],
        ))

    layout = dict(**BASE_LAYOUT)
    layout["title"] = dict(text="Three Retirement Scenarios", font=dict(size=16, color=TEXT), x=0.02)
    layout["xaxis"]["title"] = x_label
    layout["yaxis"]["title"] = "Portfolio Value (Today's $)" if use_real else "Portfolio Value"
    layout["yaxis"]["tickformat"] = "$,.0f"
    fig.update_layout(**layout)
    return fig

# ─── Accumulation Stacked Area ────────────────────────────────────────────────

def stacked_account_area(
    acct_medians: Dict[str, Dict],
    ages:         np.ndarray,
    use_real:     bool = False,
) -> go.Figure:
    """Stacked area of median account balances over accumulation phase."""
    fig = go.Figure()
    key = "real" if use_real else "nominal"

    for i, (label, data) in enumerate(acct_medians.items()):
        color = ACCOUNT_PALETTE[i % len(ACCOUNT_PALETTE)]
        rgb   = _hex_to_rgb(color)
        fig.add_trace(go.Scatter(
            x=ages, y=data[key],
            name=label,
            stackgroup="one",
            fillcolor=f"rgba({rgb},0.75)",
            line=dict(color=color, width=1),
            hovertemplate=f"<b>Age %{{x}}</b><br>{label}: %{{customdata}}<extra></extra>",
            customdata=[_fmt_m(v) for v in data[key]],
        ))

    layout = dict(**BASE_LAYOUT)
    layout["title"] = dict(text="Portfolio Growth by Account", font=dict(size=16, color=TEXT), x=0.02)
    layout["xaxis"]["title"] = "Age"
    layout["yaxis"]["title"] = "Balance (Today's $)" if use_real else "Balance"
    layout["yaxis"]["tickformat"] = "$,.0f"
    fig.update_layout(**layout)
    return fig

# ─── Income Waterfall / Stacked Bar ──────────────────────────────────────────

def income_waterfall(income_df: pd.DataFrame, use_real: bool = False,
                      inf_factors: Optional[np.ndarray] = None) -> go.Figure:
    """Annual income breakdown: pension, supplement, SS, portfolio gap."""
    df = income_df.copy()
    if use_real and inf_factors is not None:
        for col in ["pension", "supplement", "ss_you", "ss_spouse", "portfolio_withdrawal"]:
            df[col] = df[col] / inf_factors[:len(df)]

    fig = go.Figure()
    layers = [
        ("pension",               "FERS Pension",      TEAL),
        ("supplement",            "FERS Supplement",   PURPLE),
        ("ss_you",                "SS (You)",          BLUE),
        ("ss_spouse",             "SS (Spouse)",       GREEN),
        ("portfolio_withdrawal",  "Portfolio Draw",    AMBER),
    ]
    for col, label, color in layers:
        if df[col].sum() == 0:
            continue
        rgb = _hex_to_rgb(color)
        fig.add_trace(go.Bar(
            x=df["age_you"], y=df[col],
            name=label,
            marker_color=f"rgba({rgb},0.85)",
            hovertemplate=f"<b>Age %{{x}}</b><br>{label}: %{{customdata}}<extra></extra>",
            customdata=[_fmt_m(v) for v in df[col]],
        ))

    layout = dict(**BASE_LAYOUT)
    layout["title"] = dict(text="Annual Retirement Income Sources", font=dict(size=16, color=TEXT), x=0.02)
    layout["xaxis"]["title"] = "Your Age"
    layout["yaxis"]["title"] = "Annual Income"
    layout["yaxis"]["tickformat"] = "$,.0f"
    layout["barmode"] = "stack"
    fig.update_layout(**layout)
    return fig

# ─── Roth vs Traditional ──────────────────────────────────────────────────────

def roth_vs_trad_chart(result: Dict) -> go.Figure:
    """After-tax wealth comparison: Roth vs Traditional + tax savings invested."""
    fig = go.Figure()
    years = result["years"]

    for band_idx, alpha in [(2, 0.15), (0, 0.15)]:
        fig.add_trace(go.Scatter(
            x=list(years) + list(years[::-1]),
            y=list(result["roth_paths"][band_idx]) + list(result["roth_paths"][2 - band_idx][::-1]),
            fill="toself", fillcolor=f"rgba(0,212,170,{alpha})",
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=False, hoverinfo="skip",
        ))
    fig.add_trace(go.Scatter(
        x=years, y=result["roth_paths"][1],
        name="Roth (after-tax value)",
        line=dict(color=TEAL, width=2.5),
        hovertemplate="<b>Year %{x}</b><br>Roth: %{customdata}<extra></extra>",
        customdata=[_fmt_m(v) for v in result["roth_paths"][1]],
    ))

    for band_idx, alpha in [(2, 0.15), (0, 0.15)]:
        fig.add_trace(go.Scatter(
            x=list(years) + list(years[::-1]),
            y=list(result["trad_paths"][band_idx]) + list(result["trad_paths"][2 - band_idx][::-1]),
            fill="toself", fillcolor=f"rgba(121,192,255,{alpha})",
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=False, hoverinfo="skip",
        ))
    fig.add_trace(go.Scatter(
        x=years, y=result["trad_paths"][1],
        name="Traditional + Tax Savings (after-tax)",
        line=dict(color=BLUE, width=2.5),
        hovertemplate="<b>Year %{x}</b><br>Traditional: %{customdata}<extra></extra>",
        customdata=[_fmt_m(v) for v in result["trad_paths"][1]],
    ))

    if result["crossover_year"] is not None:
        cy = result["crossover_year"]
        fig.add_vline(x=cy, line_dash="dash", line_color=MUTED,
                      annotation_text=f"Crossover yr {cy}", annotation_font_color=MUTED)

    layout = dict(**BASE_LAYOUT)
    layout["title"] = dict(text="Roth vs Traditional: After-Tax Wealth at Retirement",
                            font=dict(size=16, color=TEXT), x=0.02)
    layout["xaxis"]["title"] = "Years from Now"
    layout["yaxis"]["title"] = "After-Tax Portfolio Value"
    layout["yaxis"]["tickformat"] = "$,.0f"
    fig.update_layout(**layout)
    return fig

# ─── Probability Gauge ────────────────────────────────────────────────────────

def prob_gauge(prob: float, label: str, color: str = TEAL) -> go.Figure:
    """Semicircular gauge for probability of success."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=prob,
        number={"suffix": "%", "font": {"size": 32, "color": TEXT}},
        title={"text": label, "font": {"size": 13, "color": MUTED}},
        gauge={
            "axis":      {"range": [0, 100], "tickcolor": MUTED, "tickfont": {"color": MUTED}},
            "bar":       {"color": color},
            "bgcolor":   BG2,
            "bordercolor": BG2,
            "steps": [
                {"range": [0,  50], "color": "rgba(248,81,73,0.15)"},
                {"range": [50, 75], "color": "rgba(240,136,62,0.15)"},
                {"range": [75, 100], "color": "rgba(63,185,80,0.10)"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "value": prob},
        },
    ))
    layout = dict(**BASE_LAYOUT)
    layout["height"] = 220
    layout["margin"] = dict(l=20, r=20, t=30, b=10)
    fig.update_layout(**layout)
    return fig

# ─── Tax Rate Timeline ────────────────────────────────────────────────────────

def tax_rate_timeline(ages: np.ndarray, incomes: np.ndarray,
                       inflation: float = 0.03) -> go.Figure:
    """Marginal and effective tax rate over retirement."""
    from utils.calculations import calculate_federal_tax, get_marginal_rate
    marginals  = [get_marginal_rate(inc, t, inflation) * 100 for t, inc in enumerate(incomes)]
    effectives = [calculate_federal_tax(inc, t, inflation) / max(inc, 1) * 100
                  for t, inc in enumerate(incomes)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ages, y=marginals,  name="Marginal Rate",
                              line=dict(color=AMBER, width=2)))
    fig.add_trace(go.Scatter(x=ages, y=effectives, name="Effective Rate",
                              line=dict(color=TEAL, width=2)))

    layout = dict(**BASE_LAYOUT)
    layout["title"] = dict(text="Federal Tax Rates in Retirement",
                            font=dict(size=16, color=TEXT), x=0.02)
    layout["xaxis"]["title"] = "Your Age"
    layout["yaxis"]["title"] = "Tax Rate (%)"
    layout["yaxis"]["ticksuffix"] = "%"
    fig.update_layout(**layout)
    return fig

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"
