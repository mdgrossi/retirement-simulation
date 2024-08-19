import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator

def sims_matrix(rows, cols, mean, stdev):
    """Create a matrix of simulation adding noise (random numbers) about the mean and standard devation 'stdev'. Rows contain time and columns contain different simulations.
    """
    x = np.random.randn(rows, cols)
    x = mean + (x * stdev)
    return x

def growth(principal, rate, n, contribution):
    """Calculate new balance over 1-year time step with annual compounding interest and additional regular contributions. Agrees with https://www.moneygeek.com/compound-interest-calculator/ if n_p=n.

    Inputs:
        principal: float, starting account balance
        rate: float, average interest rate expressed as a decimal
        n: int or float, number of contributions. For monthly, use n=12.
        contribution: float, amount to be contributed n times.
    
    Output:
       New account balance after interest and contributions
    """
    t = 1
    compound_interest = principal * (1 + (rate / n)) ** (n * t)
    contributions = contribution * (((1 + (rate / n)) ** (n * t) - 1) / (rate / n))
    return np.round(compound_interest + contributions, 2)


def growth_simulation(start_capital, return_mean, return_stdev, raise_mean, raise_stdev, monthly_contribution, n_years=30, n_simulations=100):
    """Simulate investment growth from a starting amount under different pay raises and growth scenarios and with monthly contributions. The output of this calculator agrees, to a few cents, with The Calculator Site,
    https://www.thecalculatorsite.com/finance/calculators/compoundinterestcalculator.php.
    
    Inputs:
        start_capital: float, starting investment amount
        return_mean: float, average rate of return on investment as a percent
        return_stdev: float, standard deviation for return on investment
        raise_mean: float, average annual pay raise as a percent.    
            Used to adjust contributions.
        raise_stdev: float, standard deviation of annual pay raises
        monthly_contribution: float, amount to be contributed each month
        n_years: int, number of years to simulate drawdown
        n_simulations: int, number of simulations to generate
    
    Output:
        Dataframe of account balances over time (rows) for each simulation (columns).
    """
    # Convert mean and standard deviations from percents to decimals
    return_mean = return_mean / 100
    return_stdev = return_stdev / 100
    raise_mean = raise_mean / 100
    raise_stdev = raise_stdev / 100

    # Convert annual values to monthly (using volitility square root of time for stdev)
    n_months = 12 * n_years
    monthly_return_mean = return_mean / 12
    # monthly_return_mean = ((return_mean + 1) ** (1/12)) - 1
    monthly_return_stdev = return_stdev / np.sqrt(12)

    # Simulate returns and raises
    monthly_returns = sims_matrix(
        rows=n_months+12,
        cols=n_simulations,
        mean=monthly_return_mean,
        stdev=monthly_return_stdev)
    raises = sims_matrix(
        rows=n_years,
        cols=n_simulations, 
        mean=raise_mean+1,
        stdev=raise_stdev)

    # Contributions adjusted for annual inflation raises
    contributions = np.full((n_years+1, n_simulations),
                            float(monthly_contribution))
    for j in range(n_years):
        contributions[j+1, :] = contributions[j, :] * raises[j, :]
    contributions = np.repeat(contributions, 12, axis=0)
    contributions = np.concatenate((np.zeros((1, n_simulations)), contributions), axis=0)

    # Simulate growth
    sims = np.full((n_months+12, n_simulations), float(start_capital))
    for j in range(n_months+11):
        sims[j+1, :] = \
            growth(principal=sims[j, :],
                   rate=monthly_returns[j, :], n=1,
                   contribution=contributions[j+1, :])

    return pd.DataFrame(sims[:-11,:])


def growth_plot(nav_df):
    # Define the figure and axes
    fig, ax1 = plt.subplots(1, 1)

    # Create x-axis in years
    thisYear = pd.to_datetime('today').year
    xlabs = np.linspace(0, nav_df.shape[0]/12, num=nav_df.shape[0]) + thisYear

    for column in nav_df.columns:
        ax1.plot(xlabs, nav_df[column], alpha=0.3)

    ax1.set_xlim(min(xlabs), max(xlabs))
    ax1.xaxis.set_minor_locator(AutoMinorLocator())
    xlabels = [item.get_text() for item in ax1.get_xticklabels()]
    xlabels = [l+f'\n({float(l)-1986})' for l in xlabels]
    ax1.set_xticklabels(xlabels)
    ax1.yaxis.set_major_formatter(mpl.ticker.StrMethodFormatter('${x:,.0f}'))
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.title.set_text('Projected retirement savings balance by year (age)')
    ax1.grid(True, alpha=0.5)

    plt.tight_layout()

    return fig


def withdrawal_simulation(start_capital, return_mean, return_stdev, inflation_mean, inflation_stdev, monthly_withdrawal, n_years=30, n_simulations=100):
    """Simulate monthly withdrawals from a starting investment amount under different inflation and growth scenarios.
    
    Inputs:
        start_capital: float, starting investment amount
        return_mean: float, average rate of return on investment as a percent
        return_stdev: float, standard deviation for return on investment
        inflation_mean: float, average rate of inflation as a percent
        inflation_stdev: float, standard deviation of inflation
        monthly_withdrawal: float, amount to be withdrawn each month
        n_years: int, number of years to simulate drawdown
        n_simulations: int, number of simulations to generate
    
    Output:
        Dataframe of account balances over time (rows) for each simulation (columns).
    """
    # Convert mean percents to decimals
    if return_mean > 1:
        return_mean = return_mean / 100
    if inflation_mean > 1:
        inflation_mean = inflation_mean / 100

    # Convert annual values to monthly (using volitility square root of time for stdev)
    n_months = 12 * n_years
    monthly_return_mean = return_mean / 12
    monthly_return_stdev = return_stdev / np.sqrt(12)
    monthly_inflation_mean = inflation_mean / 12
    monthly_inflation_stdev = inflation_stdev / np.sqrt(12)

    # Simulate returns and inflation
    monthly_returns = sims_matrix(
        rows=n_months,
        cols=n_simulations,
        mean=monthly_return_mean,
        stdev=monthly_return_stdev)
    monthly_inflation = sims_matrix(
        rows=n_months,
        cols=n_simulations, 
        mean=monthly_inflation_mean,
        stdev=monthly_inflation_stdev)
    monthly_withdrawal = sims_matrix(
        rows=n_months,
        cols=n_simulations,
        mean=monthly_withdrawal,
        stdev=0.05)

    # Simulate withdrawals
    sims = np.full((n_months + 1, n_simulations), float(start_capital))
    for j in range(n_months):
        sims[j + 1, :] = (
            sims[j, :] *
            (1 + monthly_returns[j, :] - monthly_inflation[j, :]) -
            monthly_withdrawal[j, :]
        )

    # Set sims values below 0 to NaN
    sims[sims < 0] = np.nan

    # convert to millions
    sims = sims / 1000000

    return pd.DataFrame(sims)


def withdrawal_plot(nav_df, scenario_percent, retire_age):
    # For the histogram, we will fill NaNs with -1
    nav_df_zeros = nav_df.ffill().fillna(0).iloc[-1, :]

    # Define the figure and axes
    fig = plt.figure()

    # Create the top plot for time series on the first row that spans all columns
    ax1 = plt.subplot2grid((2, 2), (0, 0), colspan=2)

    # Create the bottom left plot for the percentage above zero
    ax2 = plt.subplot2grid((2, 2), (1, 0), colspan=2)

    # Create x-axis in years
    xlabs = np.linspace(0, nav_df.shape[0]/12, num=nav_df.shape[0]) + retire_age

    for column in nav_df.columns:
        ax1.plot(xlabs, nav_df[column], alpha=0.3)

    ax1.set_xlim(min(xlabs), max(xlabs))
    ax1.xaxis.set_minor_locator(AutoMinorLocator())
    ax1.yaxis.set_major_formatter(mpl.ticker.StrMethodFormatter('${x:,.0f}'))
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.title.set_text(f"Projected value of capital over {int(nav_df[1:].shape[0]/12)} years")
    ax1.grid(True, alpha=0.5)

    # Calculate the percentage of columns that are above zero for each date and plot (bottom left plot)
    percent_above_zero = (nav_df > 0).sum(axis=1) / nav_df.shape[1] * 100
    ax2.plot(
        xlabs[percent_above_zero>scenario_percent],
        percent_above_zero[percent_above_zero>scenario_percent], color='darkgreen', linewidth=2)
    ax2.plot(
        xlabs[percent_above_zero<scenario_percent], percent_above_zero[percent_above_zero<scenario_percent], color='darkred', linewidth=2)
    ax2.plot(
        xlabs[(percent_above_zero>=scenario_percent-2.5) & (percent_above_zero<=scenario_percent+2.5)], 
        percent_above_zero[(percent_above_zero>=scenario_percent-2.5) & (percent_above_zero<=scenario_percent+2.5)], color='khaki', linewidth=2)
    ax2.set_xlim(min(xlabs), max(xlabs))
    ax2.xaxis.set_minor_locator(AutoMinorLocator())
    ax2.set_ylim(0, 105)  # Percentage goes from 0 to 100 with buffer
    ax2.yaxis.set_major_formatter('{x:.0f}%')
    ax2.title.set_text("Percent of scenarios still paying out")
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.set_xlabel("Age")
    ax2.grid(True, alpha=0.5)
    ax2.fill_between(x=xlabs, y1=percent_above_zero, color="red", 
        alpha=0.2, where=percent_above_zero<scenario_percent-2.5)
    ax2.fill_between(x=xlabs, y1=percent_above_zero, color="green", 
        alpha=0.2, where=percent_above_zero>scenario_percent+2.5)
    ax2.fill_between(
        x=xlabs[(percent_above_zero>=scenario_percent-2.5) & (percent_above_zero<=scenario_percent+2.5)], 
        y1=percent_above_zero[(percent_above_zero>=scenario_percent-2.5) & (percent_above_zero<=scenario_percent+2.5)], color='yellow', alpha=0.2)

    plt.tight_layout()

    return fig
