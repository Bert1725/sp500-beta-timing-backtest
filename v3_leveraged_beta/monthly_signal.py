# Robert Miller
# run after the close on the last trading day of the month, trade the next day
# uses this year's walk-forward pick, so it re-runs the grid first (~1 min)

import os
import sys
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from pandas.tseries.offsets import BDay

# get_data.py is one folder up
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from strategy import (load_data, get_target_leverage, leverage_to_weights, get_settings_grid,
                      walk_forward, tickers, data_folder)


def month_is_over(last_date):
    # true if the latest close is the last trading day of its month
    # (misses holidays like good friday, but then it shows up the next morning anyway)
    today = datetime.now(ZoneInfo("America/New_York")).date()
    if (last_date + BDay(1)).month != last_date.month:
        return True
    # --no-download can leave the data a few days old, so only trust the calendar if it's recent
    return today.month != last_date.month and (today - last_date.date()).days <= 4


# --no-download uses whatever is already in data/
if "--no-download" not in sys.argv:
    from get_data import download_data
    download_data(data_folder)

data = load_data()
last_date = data["dates"][-1]
current_month = last_date.to_period("M")

print("Picking this year's setting...")
walk_weights, picks = walk_forward(data, get_settings_grid())
# december's signal is for january
signal_year = last_date.year + 1 if last_date.month == 12 else last_date.year
settings = picks.loc[signal_year].to_dict()
settings["size"] = float(settings["size"])

leverage = get_target_leverage(data, **settings).dropna()
weights = leverage_to_weights(leverage)

# unless the month is over, the last row is just the latest day and not a real month end
month_over = month_is_over(last_date)
if settings["check"] == "monthly" and not month_over:
    completed = weights[weights.index.to_period("M") < current_month]
else:
    completed = weights


def show(row):
    for ticker in tickers:
        if row[ticker] > 0.001:
            print("  " + ticker + ":", str(round(row[ticker] * 100)) + "%")
    cash = 1 - row.sum()
    if cash > 0.001:
        print("  T-bills:", str(round(cash * 100)) + "%")


spy_growth = (1 + data["total_return"]["SPY"].fillna(0)).cumprod()
sma = spy_growth.rolling(200).mean()

print()
print("Setting for", signal_year, ":", settings)
print()
print("SPY vs its 200-day average at the latest close:", str(round((spy_growth.iloc[-1] / sma.iloc[-1] - 1) * 100, 1)) + "% above" if spy_growth.iloc[-1] > sma.iloc[-1] else str(round((1 - spy_growth.iloc[-1] / sma.iloc[-1]) * 100, 1)) + "% below")
print()
print("Signal from the last completed check (" + str(completed.index[-1].date()) + "), leverage " + str(round(leverage.loc[completed.index[-1]], 2)) + "x:")
show(completed.iloc[-1])
if not month_over:
    print()
    print("Preview if the month ended on the latest close (" + str(last_date.date()) + "), leverage " + str(round(leverage.iloc[-1], 2)) + "x:")
    show(weights.iloc[-1])
print()
print("Trade on the next trading day, and only if a holding is off by at least 5% of the account.")
