# Robert Miller
# v1 - SPY trend + vol targeting (SPY and T-bills only, no leverage)

import math
import os
import numpy as np
import pandas as pd


# picked in backtest.ipynb on 1995-2009 only
chosen_settings = {
    "sma_months": 12,
    "vol_window": 21,
    "target_vol": 0.20,
    "off_weight": 0.0,
}

# account / fees
start_value = 10000
commission = 0.00        # $ per trade, most brokers are $0 for ETFs
trade_cost = 0.0005      # 5 bps spread + slippage
cash_fee = 0.0009        # SGOV expense ratio (0 if you buy T-bills directly)
min_trade = 0.05         # don't bother rebalancing unless it's 5% off
trading_days = 252
# SPY's 0.0945% fee is already in the price

# federal only, taxable account
short_term_rate = 0.22
long_term_rate = 0.15
dividend_rate = 0.15     # qualified dividends
interest_rate = 0.22     # T-bill interest = ordinary income
loss_limit = 3000
execution_lag = 1        # trade the day after the signal
use_loss_deduction = False
ordinary_payout_tickers = []
apply_wash_sale = True
tickers = ["SPY"]


data_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def load_data(spy_file=os.path.join(data_folder, "SPY.csv"), tbill_file=os.path.join(data_folder, "dtb3.csv")):

    spy = pd.read_csv(spy_file)
    spy = spy.rename(columns={
        "Date": "date",
        "Adj Close": "adj_close",
        "Close": "close",
        "High": "high",
        "Low": "low",
        "Open": "open",
        "Volume": "volume"
    })
    spy["date"] = pd.to_datetime(spy["date"])
    spy = spy.set_index("date").sort_index()

    # FRED changed the date column name at some point, so just use position
    tbill = pd.read_csv(tbill_file)
    tbill = tbill.rename(columns={tbill.columns[0]: "date", tbill.columns[1]: "tbill_rate"})
    tbill["date"] = pd.to_datetime(tbill["date"])
    tbill["tbill_rate"] = pd.to_numeric(tbill["tbill_rate"], errors="coerce")
    tbill = tbill.set_index("date").sort_index()

    data = spy[["adj_close", "close", "volume"]].copy()

    # T-bill rate is in percent per year, carry it forward over holidays and missing days
    data = data.join(tbill, how="left")
    data["tbill_rate"] = data["tbill_rate"].ffill()
    data = data.dropna(subset=["adj_close", "close", "tbill_rate"])

    # adj close includes dividends, so this is the total return of SPY
    data["spy_return"] = data["adj_close"].pct_change().fillna(0)

    # close does not include dividends, the gap between the two is the dividend
    data["price_return"] = data["close"].pct_change().fillna(0)
    data["dividend_yield"] = (data["spy_return"] - data["price_return"]).clip(lower=0)

    # daily return from holding T-bills
    data["tbill_return"] = (1 + data["tbill_rate"] / 100) ** (1 / trading_days) - 1
    data["cash_return"] = (1 + data["tbill_rate"] / 100 - cash_fee) ** (1 / trading_days) - 1

    return data


def get_month_ends(data):
    # last trading day of every month
    month_ends = data.groupby(data.index.to_period("M")).tail(1).index
    return month_ends


def get_target_exposure(data, sma_months, vol_window, target_vol, off_weight):

    month_ends = get_month_ends(data)
    monthly_close = data.loc[month_ends, "adj_close"]

    # trend filter: is SPY above its moving average of month end prices?
    monthly_sma = monthly_close.rolling(sma_months).mean()
    trend_on = monthly_close > monthly_sma

    # volatility targeting: scale down when SPY has been moving a lot
    realized_vol = data["spy_return"].rolling(vol_window).std() * math.sqrt(trading_days)
    realized_vol = realized_vol.loc[month_ends]
    vol_weight = (target_vol / realized_vol).clip(upper=1.0)

    target = pd.Series(np.nan, index=month_ends)

    for date in month_ends:

        if pd.isna(monthly_sma.loc[date]) or pd.isna(vol_weight.loc[date]):
            continue

        if trend_on.loc[date]:
            target.loc[date] = vol_weight.loc[date]
        else:
            target.loc[date] = vol_weight.loc[date] * off_weight

    # no leverage, no shorting
    target = target.clip(lower=0.0, upper=1.0)

    return target


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


def simulate_account(data, weights, start=None, end=None, taxes=False, lag=None):
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

            if gain >= 0:
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


def simulate(data, target, start=None, end=None, taxes=False, lag=None):
    # wrapper so v1's dataframe works with the same simulator as v2/v3
    engine_data = {
        "dates": data.index,
        "total_return": pd.DataFrame({"SPY": data["spy_return"]}),
        "price_return": pd.DataFrame({"SPY": data["price_return"]}),
        "dividend_yield": pd.DataFrame({"SPY": data["dividend_yield"]}),
        "cash_return": data["cash_return"],
        "tbill_return": data["tbill_return"],
    }
    weights = pd.DataFrame({"SPY": target})
    result = simulate_account(engine_data, weights, start, end, taxes, lag)
    result["exposure"] = result["w_SPY"]
    return result


def run_backtest(data, sma_months, vol_window, target_vol, off_weight,
                 start=None, end=None, taxes=False):
    target = get_target_exposure(data, sma_months, vol_window, target_vol, off_weight)
    return simulate(data, target, start, end, taxes)


def run_buy_and_hold(data, start=None, end=None, taxes=False):
    target = pd.Series(1.0, index=get_month_ends(data))
    return simulate(data, target, start, end, taxes)


def run_static_mix(data, spy_weight, start=None, end=None, taxes=False):
    # fixed SPY / T-bill mix, same average exposure = fair comparison
    target = pd.Series(spy_weight, index=get_month_ends(data))
    return simulate(data, target, start, end, taxes)


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
