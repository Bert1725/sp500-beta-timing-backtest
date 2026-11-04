# Robert Miller
# run after the close on the last trading day of the month, trade the next day
# prints the SPY / T-bill split for next month

import os
import sys
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from pandas.tseries.offsets import BDay

# get_data.py is one folder up
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from strategy import load_data, get_target_exposure, chosen_settings, data_folder


def explain(data, date, settings):

    month_ends = data.groupby(data.index.to_period("M")).tail(1).index
    month_ends = month_ends[month_ends <= date]
    monthly_close = data.loc[month_ends, "adj_close"]

    sma = monthly_close.rolling(settings["sma_months"]).mean().iloc[-1]
    price = monthly_close.iloc[-1]
    vol = data.loc[:date, "spy_return"].tail(settings["vol_window"]).std() * (252 ** 0.5)

    print("  SPY adj close:", round(price, 2))
    print("  " + str(settings["sma_months"]) + " month average:", round(sma, 2))
    print("  Trend:", "up" if price > sma else "down")
    print("  Realized volatility (" + str(settings["vol_window"]) + " days):", str(round(vol * 100, 1)) + "%")
    print("  Target volatility:", str(round(settings["target_vol"] * 100, 1)) + "%")


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
settings = chosen_settings

target = get_target_exposure(data, **settings).dropna()

last_date = data.index[-1]
current_month = last_date.to_period("M")

# unless the month is over, the last row is just the latest day and not a real month end
month_over = month_is_over(last_date)
completed = target if month_over else target[target.index.to_period("M") < current_month]
official_date = completed.index[-1]
official_exposure = completed.iloc[-1]

print()
print("Settings:", settings)
print()
print("Signal from the last completed month end (" + str(official_date.date()) + "):")
explain(data, official_date, settings)
print("  SPY:", str(round(official_exposure * 100)) + "%", " T-bills:", str(round((1 - official_exposure) * 100)) + "%")

if not month_over:
    print()
    print("Preview if the month ended on the latest close (" + str(last_date.date()) + "):")
    explain(data, last_date, settings)
    preview = target.iloc[-1]
    print("  SPY:", str(round(preview * 100)) + "%", " T-bills:", str(round((1 - preview) * 100)) + "%")

print()
print("Trade on the next trading day, and only if the change is at least 5% of the account.")
