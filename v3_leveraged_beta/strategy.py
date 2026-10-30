# Robert Miller
# v3 - leveraged beta: SPY / SSO / UPRO in uptrends, T-bills otherwise
# trend filters: 200 day SMA (Gayed & Bilello 2016) or 10 month SMA (Faber 2007)
# sizing: fixed leverage or kelly = k * premium / variance (Rotando & Thorp 1992)

import math
import os
from statistics import NormalDist
import numpy as np
import pandas as pd


tickers = ["SPY", "SSO", "UPRO"]

# picked in backtest.ipynb on 2000-2009 only
chosen_settings = {
    "trend": "sma200",
    "sizing": "fixed",
    "size": 3.0,
    "vol_source": "realized",
    "check": "monthly",
}

# walk-forward scores from 1994 and starts trading in 2000, so it has to sit through the dot com crash
score_start = "1994-01-01"
walk_forward_start = 2000

# middle of the 5-7% equity premium range from Zenner et al. (2008)
risk_premium = 0.06
max_leverage = 3.0

# account / fees
start_value = 10000
commission = 0.00        # $ per trade, most brokers are $0 for ETFs
trade_cost = 0.0005      # 5 bps spread + slippage
cash_fee = 0.0009        # SGOV expense ratio
min_trade = 0.05         # don't bother rebalancing unless something is 5% off
trading_days = 252
# expense ratios are already in the prices

# before SSO (2006) and UPRO (2009) existed they're rebuilt as leverage * SPY - borrowing - fee
# (spreads fitted to the real funds in backtest.ipynb)
sso_fee = 0.0089
sso_spread = 0.0070
upro_fee = 0.0091
upro_spread = 0.0060

# federal only, taxable account
short_term_rate = 0.22
long_term_rate = 0.15
dividend_rate = 0.15     # qualified dividends
interest_rate = 0.22     # T-bill interest = ordinary income
loss_limit = 3000
execution_lag = 1        # trade the day after the signal
use_loss_deduction = False
ordinary_payout_tickers = ["SSO", "UPRO"]   # leveraged ETF payouts are mostly short term gains
apply_wash_sale = True


def read_prices(file):
    prices = pd.read_csv(file)
    prices["Date"] = pd.to_datetime(prices["Date"])
    prices = prices.set_index("Date").sort_index()
    return prices


data_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def load_data(folder=data_folder):

    spy = read_prices(folder + "/SPY.csv")
    dates = spy.index

    adj = pd.DataFrame(index=dates)
    close = pd.DataFrame(index=dates)

    for ticker in tickers:
        prices = read_prices(folder + "/" + ticker + ".csv")
        adj[ticker] = prices["Adj Close"].reindex(dates)
        close[ticker] = prices["Close"].reindex(dates)

    vix = read_prices(folder + "/VIX.csv")["Close"].reindex(dates).ffill()

    # FRED changed the date column name at some point, so just use position
    tbill = pd.read_csv(folder + "/dtb3.csv")
    tbill = tbill.rename(columns={tbill.columns[0]: "date", tbill.columns[1]: "tbill_rate"})
    tbill["date"] = pd.to_datetime(tbill["date"])
    tbill["tbill_rate"] = pd.to_numeric(tbill["tbill_rate"], errors="coerce")
    tbill_rate = tbill.set_index("date")["tbill_rate"].sort_index()
    tbill_rate = tbill_rate.reindex(dates.union(tbill_rate.index)).ffill().reindex(dates)

    keep = tbill_rate.notna()
    dates = dates[keep]
    adj = adj.loc[dates]
    close = close.loc[dates]
    tbill_rate = tbill_rate.loc[dates]
    vix = vix.loc[dates]

    tbill_return = (1 + tbill_rate / 100) ** (1 / trading_days) - 1
    cash_return = (1 + tbill_rate / 100 - cash_fee) ** (1 / trading_days) - 1

    # adj close = total return, close = price only, difference = dividend
    total_return = adj.pct_change()
    price_return = close.pct_change()

    first_date = {}
    for ticker, leverage, fee, spread in [("SSO", 2, sso_fee, sso_spread), ("UPRO", 3, upro_fee, upro_spread)]:
        first = adj[ticker].first_valid_index()
        simulated = (leverage * total_return["SPY"] - (leverage - 1) * tbill_return
                     - ((leverage - 1) * spread + fee) / trading_days)
        total_return[ticker + "_actual"] = total_return[ticker]
        early = total_return.index <= first
        total_return.loc[early, ticker] = simulated[early]
        price_return.loc[early, ticker] = simulated[early]
        first_date[ticker] = first

    dividend_yield = (total_return[tickers] - price_return[tickers]).clip(lower=0)

    data = {
        "dates": dates,
        "total_return": total_return,
        "price_return": price_return,
        "dividend_yield": dividend_yield,
        "tbill_rate": tbill_rate,
        "tbill_return": tbill_return,
        "cash_return": cash_return,
        "first_date": first_date,
        "vix": vix,
    }

    return data


def get_month_ends(dates):
    # last trading day of every month
    month_ends = pd.Series(dates, index=dates).groupby(dates.to_period("M")).tail(1).index
    return month_ends


def get_check_dates(dates, check):
    if check == "monthly":
        return get_month_ends(dates)
    if check == "weekly":
        # last trading day of each week
        weeks = pd.Series(dates, index=dates).groupby(dates.to_period("W-FRI")).tail(1).index
        return weeks
    return dates


def leverage_to_weights(leverage):
    # leverage 0-1: SPY + cash, 1-2: SPY + SSO, 2-3: SSO + UPRO
    leverage = leverage.clip(lower=0, upper=max_leverage)
    weights = pd.DataFrame(0.0, index=leverage.index, columns=tickers)

    low = leverage <= 1
    mid = (leverage > 1) & (leverage <= 2)
    high = leverage > 2

    weights.loc[low, "SPY"] = leverage[low]
    weights.loc[mid, "SSO"] = leverage[mid] - 1
    weights.loc[mid, "SPY"] = 2 - leverage[mid]
    weights.loc[high, "UPRO"] = leverage[high] - 2
    weights.loc[high, "SSO"] = 3 - leverage[high]

    weights[leverage.isna()] = np.nan
    return weights


def get_target_leverage(data, trend, sizing, size, vol_source, check, vol_days=21, sma_days=200):
    # trend: "none", "sma200" (sma_days long) or "sma10m"
    # sizing: "fixed" (leverage = size) or "kelly" (size * premium / variance, capped at 3x)
    # vol_source: "realized" (21 day) or "vix"

    dates = data["dates"]
    spy = data["total_return"]["SPY"]
    growth = (1 + spy.fillna(0)).cumprod()

    if sizing == "fixed":
        leverage = pd.Series(size, index=dates)
    else:
        if vol_source == "vix":
            vol = data["vix"] / 100
        else:
            vol = spy.rolling(vol_days).std() * math.sqrt(trading_days)
        leverage = size * risk_premium / vol ** 2

    leverage = leverage.clip(upper=max_leverage)

    if trend == "sma200":
        sma = growth.rolling(sma_days).mean()
        trend_up = growth > sma
        leverage = leverage.where(trend_up, 0.0)
        leverage[sma.isna()] = np.nan
    elif trend == "sma10m":
        month_ends = get_month_ends(dates)
        monthly = growth.loc[month_ends]
        monthly_up = (monthly > monthly.rolling(10).mean()).astype(float)
        monthly_up[monthly.rolling(10).mean().isna()] = np.nan
        trend_up = monthly_up.reindex(dates).ffill()
        leverage = leverage.where(trend_up == 1, 0.0)
        leverage[trend_up.isna()] = np.nan

    check_dates = get_check_dates(dates, check)
    return leverage.loc[check_dates]


def get_target_weights(data, trend, sizing, size, vol_source, check, sma_days=200):
    leverage = get_target_leverage(data, trend, sizing, size, vol_source, check, sma_days=sma_days)
    return leverage_to_weights(leverage)


def year_end_tax(st_gain, lt_gain, qualified_dividends, ordinary_income, st_carry, lt_carry):
    # rough federal tax for one year. losses net short vs short and long vs long first
    # ordinary_income = T-bill interest + SSO/UPRO payouts (those are mostly short term gains)

    st = st_gain + st_carry
    lt = lt_gain + lt_carry

    if st < 0 and lt > 0:
        lt = lt + st
        st = 0
    elif lt < 0 and st > 0:
        st = st + lt
        lt = 0

    # the $3k deduction saves tax outside the account, so it's off by default (use_loss_deduction)
    deduction = 0
    if use_loss_deduction and (st < 0 or lt < 0):
        total_loss = -(min(st, 0) + min(lt, 0))
        deduction = min(total_loss, loss_limit)

        used = deduction
        if st < 0:
            use_st = min(-st, used)
            st = st + use_st
            used = used - use_st
        if lt < 0:
            lt = lt + used

    st_carry = min(st, 0)
    lt_carry = min(lt, 0)

    tax = (
        short_term_rate * max(st, 0)
        + long_term_rate * max(lt, 0)
        + dividend_rate * qualified_dividends
        + interest_rate * ordinary_income
        - short_term_rate * deduction
    )

    return tax, st_carry, lt_carry


def delay_signals(weights, dates, days):
    # can't trade on a close you haven't seen yet, so push each signal back by `days`
    if days == 0:
        return weights
    weights = weights.dropna(how="all")
    position = dates.get_indexer(weights.index)
    position = np.minimum(position + days, len(dates) - 1)
    delayed = weights.copy()
    delayed.index = dates[position]
    return delayed[~delayed.index.duplicated(keep="last")]


def simulate(data, weights, start=None, end=None, taxes=False, lag=None):
    # day by day account simulation in dollars
    # weights: target weight per ETF on signal dates (nan rows = no signal), rest is T-bills
    # taxes=True tracks tax lots (FIFO), wash sales, and pays tax every December

    if lag is None:
        lag = execution_lag
    weights = delay_signals(weights, data["dates"], lag)

    dates = data["dates"]
    keep = np.ones(len(dates), dtype=bool)
    if start is not None:
        keep &= dates >= pd.Timestamp(start)
    if end is not None:
        keep &= dates <= pd.Timestamp(end)

    # day 0 = last trade on or before start
    signals = weights.dropna(how="all")
    first_signal = signals.index[signals.index <= dates[keep][0]]
    if len(first_signal) == 0:
        first_signal = signals.index[0]
    else:
        first_signal = first_signal[-1]
    keep = dates >= first_signal
    if end is not None:
        keep &= dates <= pd.Timestamp(end)

    dates = dates[keep]
    n_days = len(dates)
    n_assets = len(tickers)

    total_ret = data["total_return"].loc[dates, tickers].fillna(0).values
    price_ret = data["price_return"].loc[dates, tickers].fillna(0).values
    div_yield = data["dividend_yield"].loc[dates, tickers].fillna(0).values
    cash_ret = data["cash_return"].loc[dates].values
    ordinary_payout = np.array([ticker in ordinary_payout_tickers for ticker in tickers])

    targets = weights.reindex(dates).values

    # only used for cost basis
    price_index = np.cumprod(1 + price_ret, axis=0)

    year_end = np.zeros(n_days, dtype=bool)
    year_end[:-1] = dates.year[:-1] != dates.year[1:]

    holdings = np.zeros(n_assets)
    cash = float(start_value)

    # lot = [date, units, cost per unit, units already used as a wash sale replacement]
    lots = [[] for a in range(n_assets)]
    pending = [[] for a in range(n_assets)]   # losses that could still get washed

    tax = {"st": 0.0, "lt": 0.0, "qualified": 0.0, "ordinary": 0.0, "st_carry": 0.0, "lt_carry": 0.0,
           "washed": 0.0}

    values = np.zeros(n_days)
    costs = np.zeros(n_days)
    traded = np.zeros(n_days)
    taxes_paid = np.zeros(n_days)
    held = np.zeros((n_days, n_assets))

    def add_gain(gain, long_term):
        if long_term:
            tax["lt"] += gain
        else:
            tax["st"] += gain

    def sell(a, amount, i):
        # FIFO
        if not taxes:
            return
        price = price_index[i, a]
        units = amount / price
        while units > 1e-12 and len(lots[a]) > 0:
            lot = lots[a][0]
            sold = min(lot[1], units)
            gain = sold * (price - lot[2])
            long_term = (dates[i] - lot[0]).days > 365
            lot[1] -= sold
            lot[3] = min(lot[3], lot[1])
            units -= sold
            if lot[1] <= 1e-12:
                lots[a].pop(0)

            if gain >= 0 or not apply_wash_sale:
                add_gain(gain, long_term)
                continue

            # wash sale: shares bought in the 30 days before this sale count as replacements,
            # so that part of the loss moves into their cost basis
            loss_per_unit = -gain / sold
            left = sold
            for other in lots[a]:
                if left <= 1e-12:
                    break
                recent = 0 <= (dates[i] - other[0]).days <= 30
                free = other[1] - other[3]
                if recent and free > 1e-12:
                    matched = min(left, free)
                    other[2] += loss_per_unit * matched / other[1]
                    other[3] += matched
                    tax["washed"] += loss_per_unit * matched
                    left -= matched

            if left > 1e-12:
                add_gain(-loss_per_unit * left, long_term)
                # anything left waits 30 days in case it gets bought back
                pending[a].append([dates[i], left, loss_per_unit, long_term])

    def buy(a, amount, i):
        if not taxes or amount <= 0:
            return
        price = price_index[i, a]
        units = amount / price
        basis = price
        left = units
        for loss in pending[a]:
            if left <= 1e-12:
                break
            if (dates[i] - loss[0]).days <= 30 and loss[1] > 1e-12:
                matched = min(left, loss[1])
                disallowed = loss[2] * matched
                # TODO: holding period should carry over too
                add_gain(disallowed, loss[3])
                basis += disallowed / units
                tax["washed"] += disallowed
                loss[1] -= matched
                left -= matched
        pending[a][:] = [loss for loss in pending[a] if (dates[i] - loss[0]).days <= 30 and loss[1] > 1e-12]
        lots[a].append([dates[i], units, basis, units - left])

    def rebalance(target, i):
        # sell first, then buy
        nonlocal cash
        total = holdings.sum() + cash
        wanted = np.nan_to_num(target) * total
        change = wanted - holdings
        spent = 0.0
        moved = 0.0

        for a in range(n_assets):
            if change[a] < -1e-9:
                amount = -change[a]
                sell(a, amount, i)
                holdings[a] -= amount
                cost = amount * trade_cost + commission
                cash += amount - cost
                spent += cost
                moved += amount

        buys = np.clip(change, 0, None)
        buys[buys < 1e-9] = 0
        n_buys = int((buys > 0).sum())
        if n_buys > 0:
            budget = (cash - commission * n_buys) / (1 + trade_cost)
            if buys.sum() > budget:
                buys = buys * max(budget, 0) / buys.sum()
            for a in range(n_assets):
                if buys[a] > 0:
                    holdings[a] += buys[a]
                    buy(a, buys[a], i)
                    cost = buys[a] * trade_cost + commission
                    cash -= buys[a] + cost
                    spent += cost
                    moved += buys[a]

        costs[i] += spent
        traded[i] += moved

    rebalance(weights.loc[first_signal].values, 0)

    for i in range(n_days):

        if i > 0:
            # daily returns
            if taxes:
                for a in range(n_assets):
                    if holdings[a] > 0:
                        dividend_cash = holdings[a] * div_yield[i, a]
                        holdings[a] = holdings[a] * (1 + price_ret[i, a])
                        if dividend_cash > 0:
                            if ordinary_payout[a]:
                                tax["ordinary"] += dividend_cash
                            else:
                                tax["qualified"] += dividend_cash
                            holdings[a] += dividend_cash
                            buy(a, dividend_cash, i)
                tax["ordinary"] += cash * cash_ret[i]
            else:
                holdings[:] = holdings * (1 + total_ret[i])

            cash = cash * (1 + cash_ret[i])

        target = targets[i]
        if i > 0 and not np.isnan(target).all():
            total = holdings.sum() + cash
            current = holdings / total
            off = np.abs(np.nan_to_num(target) - current)
            exit_small = ((np.nan_to_num(target) == 0) & (holdings > 0)).any()
            if off.max() >= min_trade or exit_small:
                rebalance(target, i)

        # taxes come out of the account in December (really due in April but close enough)
        if taxes and year_end[i]:
            bill, tax["st_carry"], tax["lt_carry"] = year_end_tax(
                tax["st"], tax["lt"], tax["qualified"], tax["ordinary"], tax["st_carry"], tax["lt_carry"])
            tax["st"] = 0.0
            tax["lt"] = 0.0
            tax["qualified"] = 0.0
            tax["ordinary"] = 0.0

            if bill > cash and bill > 0:
                # not enough cash, sell a slice of everything
                need = bill - cash
                invested = holdings.sum()
                for a in range(n_assets):
                    if holdings[a] > 0:
                        amount = need * holdings[a] / invested
                        sell(a, amount, i)
                        holdings[a] -= amount
                cash += need
            cash -= bill
            taxes_paid[i] = bill

        values[i] = holdings.sum() + cash
        held[i] = holdings / values[i]

    result = pd.DataFrame({
        "value": values,
        "cost": costs,
        "traded": traded,
        "taxes_paid": taxes_paid,
        "spy_return": data["total_return"].loc[dates, "SPY"].values,
        "tbill_return": data["tbill_return"].loc[dates].values,
    }, index=dates)

    for a, ticker in enumerate(tickers):
        result["w_" + ticker] = held[:, a]

    result["invested"] = held.sum(axis=1)

    previous = np.concatenate([[start_value], values[:-1]])
    result["strategy_return"] = values / previous - 1

    # what you'd actually walk away with if you sold everything on the last day
    if taxes:
        i = n_days - 1
        selling_cost = 0.0
        for a in range(n_assets):
            if holdings[a] > 0:
                sell(a, holdings[a], i)
                selling_cost += holdings[a] * trade_cost + commission
        bill, _, _ = year_end_tax(tax["st"], tax["lt"], tax["qualified"], tax["ordinary"],
                                  tax["st_carry"], tax["lt_carry"])
        result.attrs["liquidation_value"] = values[-1] - bill - selling_cost
        result.attrs["total_taxes"] = taxes_paid.sum()
        result.attrs["wash_sale_losses_disallowed"] = tax["washed"]

    return result


def get_settings_grid():
    sizing_list = [("fixed", 2.0, "realized"), ("fixed", 3.0, "realized"),
                   ("kelly", 0.5, "realized"), ("kelly", 1.0, "realized"),
                   ("kelly", 0.5, "vix"), ("kelly", 1.0, "vix")]

    settings_list = []
    for trend in ["none", "sma200", "sma10m"]:
        for sizing, size, vol_source in sizing_list:
            for check in ["monthly", "weekly", "daily"]:

                if trend == "sma10m" and check != "monthly":
                    continue

                settings_list.append({
                    "trend": trend,
                    "sizing": sizing,
                    "size": size,
                    "vol_source": vol_source,
                    "check": check,
                })

    return settings_list


def walk_forward(data, settings_list, first_year=walk_forward_start, start=score_start, window_years=None):
    # each january pick whatever grew the most (after tax) up to last year, trade it for 12 months
    # window_years=None scores every year since `start`, window_years=5 only the last 5
    all_weights = [get_target_weights(data, **settings) for settings in settings_list]

    growth = {}
    for i, weights in enumerate(all_weights):
        bt = simulate(data, weights, start=start, taxes=True)
        growth[i] = bt["value"]
    growth = pd.DataFrame(growth)

    dates = data["dates"]
    year_ends = pd.Series(dates, index=dates).groupby(dates.year).last()
    combined = pd.DataFrame(np.nan, index=dates, columns=tickers)
    picks = []

    # december's signal is for january, so need next year's pick too
    last_year = dates[-1].year
    if dates[-1].month == 12:
        last_year += 1

    for year in range(first_year, last_year + 1):

        past = growth.loc[:str(year - 1) + "-12-31"]
        if window_years is None:
            score = past.iloc[-1]
        else:
            past = past.loc[str(year - window_years) + "-01-01":]
            score = past.iloc[-1] / past.iloc[0]
        best = int(score.values.argmax())
        picks.append(dict(settings_list[best], year=year))

        weights = all_weights[best]
        start_day = year_ends.loc[year - 1]
        if year == last_year:
            rows = weights.index[weights.index >= start_day]
        else:
            end_day = year_ends.loc[year]
            rows = weights.index[(weights.index >= start_day) & (weights.index < end_day)]
        combined.loc[rows] = weights.loc[rows].values

    picks = pd.DataFrame(picks).set_index("year")

    return combined, picks


def run_strategy(data, settings, start=None, end=None, taxes=False):
    weights = get_target_weights(data, **settings)
    return simulate(data, weights, start, end, taxes)


def run_fixed(data, fixed_weights, start=None, end=None, taxes=False):
    # e.g. {"SPY": 1.0} = buy and hold
    month_ends = get_month_ends(data["dates"])
    weights = pd.DataFrame(0.0, index=month_ends, columns=tickers)
    for ticker, w in fixed_weights.items():
        weights[ticker] = w
    return simulate(data, weights, start, end, taxes)


def max_drawdown(returns):
    growth = (1 + returns).cumprod()
    peak = growth.cummax()
    drawdown = growth / peak - 1
    return drawdown.min()


def get_stats(returns, cash_returns, spy_returns):
    # cash_returns = plain T-bill return (risk free rate)

    years = len(returns) / trading_days
    growth = (1 + returns).prod()
    cagr = growth ** (1 / years) - 1

    volatility = returns.std() * math.sqrt(trading_days)

    excess = returns - cash_returns
    sharpe = excess.mean() / excess.std() * math.sqrt(trading_days)

    downside = np.sqrt((excess.clip(upper=0) ** 2).mean()) * math.sqrt(trading_days)
    sortino = excess.mean() * trading_days / downside

    drawdown = max_drawdown(returns)
    calmar = cagr / abs(drawdown)

    beta = returns.cov(spy_returns) / spy_returns.var()

    var_95 = returns.quantile(0.05)

    stats = {
        "growth_of_1": growth,
        "cagr": cagr,
        "volatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": drawdown,
        "calmar": calmar,
        "beta": beta,
        "daily_var_95": var_95,
    }

    return stats


def after_tax_cagr(result):
    years = len(result) / trading_days
    return (result.attrs["liquidation_value"] / start_value) ** (1 / years) - 1


def block_bootstrap(strategy_returns, spy_returns, cash_returns,
                    years=5, block_size=21, sims=2000, seed=314):
    # resamples 21 day blocks of the strategy's own returns (same blocks for both, so it's paired)
    # note: this can't show the trend filter failing, see rule_monte_carlo in v3

    rng = np.random.default_rng(seed)

    strategy_values = strategy_returns.values
    spy_values = spy_returns.values
    cash_values = cash_returns.values

    n_days = years * trading_days
    n_blocks = math.ceil(n_days / block_size)
    last_start = len(strategy_values) - block_size

    results = []

    for sim in range(sims):

        starts = rng.integers(0, last_start, n_blocks)
        picks = np.concatenate([np.arange(s, s + block_size) for s in starts])[:n_days]

        strategy_path = pd.Series(strategy_values[picks])
        spy_path = pd.Series(spy_values[picks])
        cash_path = pd.Series(cash_values[picks])

        results.append({
            "strategy_cagr": (1 + strategy_path).prod() ** (1 / years) - 1,
            "spy_cagr": (1 + spy_path).prod() ** (1 / years) - 1,
            "strategy_drawdown": max_drawdown(strategy_path),
            "spy_drawdown": max_drawdown(spy_path),
            "strategy_sharpe": (strategy_path - cash_path).mean() / (strategy_path - cash_path).std() * math.sqrt(trading_days),
            "spy_sharpe": (spy_path - cash_path).mean() / (spy_path - cash_path).std() * math.sqrt(trading_days),
        })

    return pd.DataFrame(results)


def significance(strategy_returns, benchmark_returns, cash_returns, n_trials, trial_sharpes):
    # is it luck? yearly t-test vs the benchmark, Sharpe SE (Lo 2002), and the
    # deflated Sharpe ratio (Bailey & Lopez de Prado 2014) for the number of settings tried

    years_s = (1 + strategy_returns).groupby(strategy_returns.index.year).prod() - 1
    years_b = (1 + benchmark_returns).groupby(benchmark_returns.index.year).prod() - 1
    # full years only (skip the current partial year)
    counts = strategy_returns.groupby(strategy_returns.index.year).size()
    full = counts[counts >= 245].index
    gap = (years_s - years_b).loc[full]
    t_yearly = gap.mean() / (gap.std() / math.sqrt(len(gap)))

    excess = strategy_returns - cash_returns
    sr = excess.mean() / excess.std()                 # daily Sharpe
    n = len(excess)
    skew = ((excess - excess.mean()) ** 3).mean() / excess.std() ** 3
    kurt = ((excess - excess.mean()) ** 4).mean() / excess.std() ** 4

    annual_sr = sr * math.sqrt(trading_days)
    sr_se = math.sqrt((1 + 0.5 * annual_sr ** 2) / (n / trading_days))

    # best Sharpe you'd expect from n_trials tries if none of them actually work
    euler = 0.5772156649
    norm = NormalDist()
    sr_var = np.var(trial_sharpes, ddof=1)
    sr0 = math.sqrt(sr_var) * ((1 - euler) * norm.inv_cdf(1 - 1 / n_trials)
                               + euler * norm.inv_cdf(1 - 1 / (n_trials * math.e)))
    denom = math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2)
    deflated = norm.cdf((sr - sr0) * math.sqrt(n - 1) / denom)
    probabilistic = norm.cdf(sr * math.sqrt(n - 1) / denom)

    return {
        "years": len(gap),
        "average_yearly_gap": gap.mean(),
        "years_ahead": int((gap > 0).sum()),
        "t_stat_yearly_gap": t_yearly,
        "sharpe": annual_sr,
        "sharpe_standard_error": sr_se,
        "prob_sharpe_above_0": probabilistic,
        "luck_hurdle_sharpe": sr0 * math.sqrt(trading_days),
        "deflated_sharpe_prob": deflated,
    }


def rule_monte_carlo(data, settings, years=10, block_size=126, sims=1000, seed=314):
    # builds fake SPY paths from random blocks of real daily returns and re-runs the rule on
    # each one, so unlike block_bootstrap the trend filter can actually fail. pre-tax

    rng = np.random.default_rng(seed)
    real = data["total_return"]["SPY"].fillna(0).values
    tbill = data["tbill_return"].values
    cash = data["cash_return"].values
    vix = data["vix"].bfill().values

    warm_up = 252
    n_days = years * trading_days + warm_up
    n_blocks = math.ceil(n_days / block_size)
    fake_dates = pd.bdate_range("2100-01-01", periods=n_days)

    results = []
    for sim in range(sims):
        starts = rng.integers(0, len(real) - block_size, n_blocks)
        picks = np.concatenate([np.arange(st, st + block_size) for st in starts])[:n_days]

        spy = real[picks]
        total = pd.DataFrame({"SPY": spy}, index=fake_dates)
        tb = pd.Series(tbill[picks], index=fake_dates)
        for ticker, leverage, fee, spread in [("SSO", 2, sso_fee, sso_spread), ("UPRO", 3, upro_fee, upro_spread)]:
            total[ticker] = leverage * total["SPY"] - (leverage - 1) * tb - ((leverage - 1) * spread + fee) / trading_days

        fake = {
            "dates": fake_dates,
            "total_return": total,
            "price_return": total,
            "dividend_yield": total * 0,
            "tbill_return": tb,
            "cash_return": pd.Series(cash[picks], index=fake_dates),
            "vix": pd.Series(vix[picks], index=fake_dates),
        }

        start = fake_dates[warm_up]
        strat = simulate(fake, get_target_weights(fake, **settings), start=start)
        row = {}
        for name, bt in [("strategy", strat),
                         ("spy", run_fixed(fake, {"SPY": 1.0}, start=start)),
                         ("sso", run_fixed(fake, {"SSO": 1.0}, start=start))]:
            row[name + "_cagr"] = (bt["value"].iloc[-1] / start_value) ** (trading_days / len(bt)) - 1
            row[name + "_drawdown"] = max_drawdown(bt["strategy_return"])
        results.append(row)

    return pd.DataFrame(results)


def index_data(file):
    # same format as load_data but for a foreign index (nikkei / dax), pre-tax only
    # no local T-bill data so cash = 0% and borrowing = spread only (japan was ~0% anyway)
    # nikkei is price only, DAX includes dividends
    prices = read_prices(file)
    close = prices["Adj Close"].dropna()
    close = close[close > 0]
    dates = close.index
    index_return = close.pct_change().fillna(0)

    total = pd.DataFrame({"SPY": index_return}, index=dates)
    for ticker, leverage, fee, spread in [("SSO", 2, sso_fee, sso_spread), ("UPRO", 3, upro_fee, upro_spread)]:
        total[ticker] = leverage * index_return - ((leverage - 1) * spread + fee) / trading_days

    zero = pd.Series(0.0, index=dates)
    return {
        "dates": dates,
        "total_return": total,
        "price_return": total,
        "dividend_yield": total * 0,
        "tbill_return": zero,
        "cash_return": zero,
        "vix": zero,
    }
