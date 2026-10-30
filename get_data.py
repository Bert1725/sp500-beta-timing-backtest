# Robert Miller
# pulls everything into data/ - prices from yahoo (yfinance) and the 3 month T-bill rate from FRED
# SSO = 2x S&P, UPRO = 3x S&P, XL* = sector SPDRs, N225/GDAXI are only for the non-US test

import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf

tickers = ["SPY", "SSO", "UPRO", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "^VIX",
           "^N225", "^GDAXI"]


def download_data(folder="data"):

    os.makedirs(folder, exist_ok=True)

    for ticker in tickers:

        prices = yf.download(ticker, start="1993-01-29", auto_adjust=False, progress=False)

        if prices.empty:
            print(ticker, "data was not found. Check your internet connection.")
            return False

        if isinstance(prices.columns, pd.MultiIndex):
            prices.columns = prices.columns.get_level_values(0)

        # if this runs during the trading day, today's row is not a final close yet, so drop it
        now = datetime.now(ZoneInfo("America/New_York"))
        if prices.index[-1].date() == now.date() and (now.hour, now.minute) < (16, 30):
            prices = prices.iloc[:-1]

        name = ticker.replace("^", "")
        prices.index.name = "Date"
        prices.to_csv(os.path.join(folder, name + ".csv"))
        print("Saved", name + ".csv:", len(prices), "rows,", prices.index[0].date(), "to", prices.index[-1].date())

    tbill = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3")
    tbill.to_csv(os.path.join(folder, "dtb3.csv"), index=False)
    print("Saved dtb3.csv:", len(tbill), "rows")

    return True


if __name__ == "__main__":
    download_data()
