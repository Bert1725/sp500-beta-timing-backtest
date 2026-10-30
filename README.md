# S&P 500 Beta Timing Backtest

Can you beat just buying and holding the S&P 500 by taking on more market exposure (beta) when it's going up and less when it isn't, after fees and taxes, checking once a month? This repo is my attempt to answer that. It goes through three versions, from a simple trend filter on SPY up to a 3x leveraged version using UPRO, and tests each one in a regular taxable account with a train/test split, a walk-forward test, and a few robustness checks.

**Short answer:** not reliably. The best version beat buy and hold SPY and the 2x fund SSO from 2000 and 2005, but almost all of that came from sitting out long bear markets, and it's trailed leveraged buy and hold since 2010.

![v3 walk-forward vs buy and hold](images/walk_forward_2000.png)

## Results

$10,000 start, after federal taxes, assuming everything is sold at the end. Data through October 29, 2026.

| | 2010-now (settings picked on 2000-2009) | 2000-now (walk-forward) | Max drawdown since 2000 |
|---|---|---|---|
| v1 - trend + vol targeting | $36,604 (8.0%/yr) | - | - |
| v2 - conditional beta | $48,696 (9.9%/yr) | - | - |
| v3 - 200 day trend, 3x | $96,681 (14.5%/yr) | **$121,387 (9.8%/yr)** | -82% |
| Buy and hold SPY | $76,769 (12.9%/yr) | $69,793 (7.5%/yr) | -55% |
| Buy and hold SSO (2x) | $261,801 (21.5%/yr) | $86,467 (8.4%/yr) | -89% |
| Buy and hold UPRO (3x) | **$611,415 (27.8%/yr)** | $53,118 (6.4%/yr) | -98% |

v2's walk-forward starts in 2005 instead (the sector ETFs only go back to 1998). From 2005, v2 made 10.8% a year after tax and v3 made 14.6%, vs 9.9% for SPY, 13.7% for SSO and 14.8% for UPRO.

A few things stood out to me:

- **The edge comes from bear markets.** v3 (3x UPRO above the 200 day average at month end, T-bills below it) avoided most of 2000-2002 and 2008, which is where buy and hold leverage gets wiped out. In bull markets with quick dips, like most of 2010-2026, it lagged because it kept selling near the bottom and buying back higher.
- **Most of v3's edge is in years where UPRO is rebuilt.** UPRO only started trading in June 2009, so before that it's rebuilt from SPY. Since the real fund exists, v3 made 19.9% a year before tax vs 24.4% for SSO and 31.8% for UPRO.
- **It isn't statistically strong.** v3's average yearly lead was t = 1.7 vs SPY and t = 0.9 vs SSO. Even though the deflated Sharpe ratio says its Sharpe is very likely above zero, SPY's Sharpe over the same years was about the same (0.43 vs 0.41).
- **The conditional beta idea didn't hold up in a tradable form.** High beta sectors do beat low beta ones in months when the market goes up, but splitting by the trend you know at the *start* of the month showed basically no effect (t = 0.06).
- **Outside the US it was mixed.** The same rule beat holding 2x on the DAX and Nikkei from 1994 or 2000, lost badly from 2010 on, and on the Nikkei from 1994 it did worse than just holding the index.

## Why I built this

I trade on the side, and I started with a script that used leverage, VWAP and MACD, plus a grid search over the whole data set. Looking at it again, it ignored dividends, borrowed for free, and picked its settings using the same years it was graded on, so the results didn't mean much. I wanted to redo it the right way and see what actually holds up once you add realistic costs, taxes and out of sample testing. I also wanted something I could actually run every month.

## What's in here

```
get_data.py                 downloads everything into data/ (yfinance + FRED)
compare_versions.ipynb      all three versions side by side
v1_trend_vol/               SPY + T-bills only, trend filter + volatility targeting
v2_conditional_beta/        adds SSO and the 9 sector SPDRs, more beta in uptrends
v3_leveraged_beta/          SPY / SSO / UPRO, trend filter + fixed or Kelly leverage up to 3x
```

Each version folder has a `backtest.ipynb` (the full analysis), a `strategy.py` (rules + the account simulator), and a `monthly_signal.py` that prints what to hold next month.

## How the backtest works

- **Data:** daily prices from Yahoo Finance through `yfinance` (Adj Close for total return, Close for price return, and the difference is the dividend), and the 3-month T-bill rate (DTB3) from FRED. SSO before 2006 and UPRO before 2009 are rebuilt as leverage x SPY's daily return minus borrowing costs and the fund fee. I fit the borrowing spread to the real funds where they overlap (0.996 and 0.998 correlation of daily returns).
- **Trading:** signals are calculated at the month end close and traded at the *next* day's close. $0 commission, 5 bps spread/slippage, and nothing trades unless a holding is at least 5% off. Cash sits in SGOV (T-bill rate minus 0.09%).
- **Taxes:** federal only, in a taxable account. Every purchase is its own tax lot (FIFO), 22% on short-term gains, interest and leveraged ETF payouts, 15% on long-term gains and dividends, losses carry forward, and the wash sale rule is applied. Taxes come out of the account each December.
- **Testing:** settings are picked on 2000-2009 and tested on 2010 to now. There's also a walk-forward, where every January the settings are re-picked using only the years before it. v3 also has a significance test, a Monte Carlo that re-runs the rule on resampled price paths, an SMA length sensitivity check, and the same rule on the Nikkei 225 and DAX.

## Mistakes I fixed along the way

My first pass at this made the strategies look a lot better than they were, so I went back through everything:

- It traded at the same close that created the signal, which isn't actually possible. Moving to next-day trades cut v3's 2005-now result from 16.9% to about 14.7% a year.
- The walk-forward started in 2005, which happened to skip the year it would have picked plain 3x right before the dot com crash. Starting in 2000 shows the -82% drawdown.
- I wasn't applying the wash sale rule, I was crediting the $3,000 loss deduction to the account, and I was taxing leveraged ETF payouts as qualified dividends.
- My first Monte Carlo just reshuffled the strategy's own returns, so it couldn't show the trend filter failing.
- In v2 I was treating the Pettengill-style conditional beta test as evidence, but it splits months by the market's *future* return, so it can't be traded on.

Across the whole project I tried about 277 settings (96 in v1, 126 in v2, 13 in a technical indicator version I dropped, and 42 in v3), so I report the deflated Sharpe ratio to account for that.

## Running it

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python get_data.py
```

Then open any of the notebooks. To get next month's position for v3, run this after the close on the last trading day of the month and trade the next day:

```
python v3_leveraged_beta/monthly_signal.py
```

## Limitations

- 3x leverage is a lot of risk. A one day crash like October 1987 (-20.5%) would be about -60% at 3x, and since it only checks at month end it would still be fully invested.
- There's no live forward test yet. Everything here is historical, so the real test is running the monthly signal going forward and tracking it.
- The rebuilt SSO/UPRO prices before 2006/2009 are an approximation.
- Federal tax only, and the wash sale rule is simplified (the holding period doesn't carry over).
- 30 years of data only has a few real bear markets, so a handful of events drive most of the results.

This is a personal project, not financial advice.

## References

- Bailey, D. and Lopez de Prado, M. (2014). The Deflated Sharpe Ratio. *Journal of Portfolio Management*, 40(5), 94-107.
- Bianchi, S. and Goldberg, L. (2026). A Levered ETF Anomaly Explained. arXiv:2604.27287.
- Campbell, J. and Vuolteenaho, T. (2003). Bad Beta, Good Beta. Working paper, Harvard University.
- Cederburg, S., O'Doherty, M., Wang, F. and Yan, X. (2020). On the Performance of Volatility-Managed Portfolios. *Journal of Financial Economics*, 138(1), 95-117.
- Cheng, M. and Madhavan, A. (2009). The Dynamics of Leveraged and Inverse Exchange-Traded Funds. *Journal of Investment Management*, 7(4), 43-62.
- Clare, A., Seaton, J., Smith, P. and Thomas, S. (2013). Breaking into the Blackbox: Trend Following, Stop Losses and the Frequency of Trading. *Journal of Asset Management*, 14(3), 182-194.
- Elsas, R., El-Shaer, M. and Theissen, E. (2003). Beta and Returns Revisited. *Journal of International Financial Markets, Institutions and Money*, 13, 1-18.
- Faber, M. (2007). A Quantitative Approach to Tactical Asset Allocation. *Journal of Wealth Management*.
- Gayed, M. and Bilello, C. (2016). Leverage for the Long Run. Charles H. Dow Award paper.
- Genc, E., Moench, E. and Pazarbasi, A. (2025). Reaching for Beta. Working paper.
- Harvey, C. et al. (2018). The Impact of Volatility Targeting. *Journal of Portfolio Management*, 45(1), 14-33.
- Hsu, J., Kalesnik, V. and Li, F. (2012). An Investor's Guide to Smart Beta Strategies. *AAII Journal*.
- Lakonishok, J. and Shapiro, A. (1984). Stock Returns, Beta, Variance and Size. *Financial Analysts Journal*, 40(4), 36-41.
- Lo, A. (2002). The Statistics of Sharpe Ratios. *Financial Analysts Journal*, 58(4), 36-52.
- Moreira, A. and Muir, T. (2017). Volatility-Managed Portfolios. *Journal of Finance*, 72(4), 1611-1644.
- Pettengill, G., Sundaram, S. and Mathur, I. (1995). The Conditional Relation between Beta and Returns. *Journal of Financial and Quantitative Analysis*, 30(1), 101-116.
- Rotando, L. and Thorp, E. (1992). The Kelly Criterion and the Stock Market. *American Mathematical Monthly*, 99(10), 922-931.
- Xiao, B. (2016). Conditional Relationship Between Beta and Return in the US Stock Market. *Expert Journal of Business and Management*, 4(1), 46-55.
- Zakamulin, V. (2014). The Real-Life Performance of Market Timing with Moving Average and Time-Series Momentum Rules. *Journal of Asset Management*, 15(4), 261-278.
- Zenner, M., Hill, S., Clark, J. and Mago, N. (2008). The Most Important Number in Finance. J.P. Morgan.
