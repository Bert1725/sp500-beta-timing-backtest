# Robert Miller
# run after the close on the last trading day of the month, trade the next day
# uses this year's walk-forward pick, so it re-runs the grid first (a minute or two)

import os
import sys
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from pandas.tseries.offsets import BDay

# get_data.py is one folder up
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from strategy import load_data, get_target_weights, get_settings_grid, walk_forward, tickers, data_folder


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
for key in ["sma_months", "beta_window"]:
    settings[key] = int(settings[key])
if pd.isna(settings["target_vol"]):
    settings["target_vol"] = None

weights = get_target_weights(data, **settings).dropna(how="all")

# unless the month is over, the last row is just the latest day and not a real month end
month_over = month_is_over(last_date)
completed = weights if month_over else weights[weights.index.to_period("M") < current_month]


def show(row):
    for ticker in tickers:
        if row[ticker] > 0.001:
            print("  " + ticker + ":", str(round(row[ticker] * 100)) + "%")
    cash = 1 - row.sum()
    if cash > 0.001:
        print("  T-bills:", str(round(cash * 100)) + "%")


print()
print("Setting for", signal_year, ":", settings)
print()
print("Signal from the last completed month end (" + str(completed.index[-1].date()) + "):")
show(completed.iloc[-1])
if not month_over:
    print()
    print("Preview if the month ended on the latest close (" + str(last_date.date()) + "):")
    show(weights.iloc[-1])
print()
print("Trade on the next trading day, and only if a holding is off by at least 5% of the account.")
