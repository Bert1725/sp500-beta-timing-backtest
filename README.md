# S&P 500 Beta Timing Backtest

Robert Miller

## Overview

This project tests whether you can beat simply buying and holding the S&P 500 by changing how much market exposure (beta) you hold, more when the market is trending up and less or none when it isn't. Everything is checked once a month, in a regular taxable brokerage account, after trading costs and federal taxes.

I built it in three versions, and each one takes on beta in a different way. v1 only holds SPY and T-bills, and it uses a trend filter plus volatility targeting to decide how much SPY to hold. v2 adds the 2x fund SSO and the nine sector ETFs, since several papers found that high beta stocks beat low beta stocks in up markets. v3 drops the sectors and adds the 3x fund UPRO instead, and every trend filter and leverage rule in it is taken directly from a published paper.

All three versions get a fixed train/test split, where the settings are picked on the years up to 2009 and then tested on 2010 to now. v2 and v3 also get a walk-forward test, where the settings are re-picked every January using only the years before it.

So did it work? Not reliably. The best version (v3) beat buy and hold SPY and SSO from 2000 and from 2005, but almost all of that came from sitting out long bear markets. It also mostly happened in years where UPRO didn't exist yet and had to be rebuilt from SPY. Since 2010, it has trailed buy and hold SSO and UPRO.

![v3 walk-forward vs buy and hold](images/walk_forward_2000.png)

## Background: the tickers

| Ticker | What it is | Started | Expense ratio used | Role here |
|---|---|---|---|---|
| SPY | SPDR S&P 500 ETF. Tracks the S&P 500 (about 500 of the largest US companies, weighted by size). | Jan 1993 | 0.0945% | The benchmark, and 1x exposure |
| SSO | ProShares Ultra S&P 500. Aims for 2x the S&P 500's daily return. | Jun 2006 | 0.89% | 2x exposure |
| UPRO | ProShares UltraPro S&P 500. Aims for 3x the S&P 500's daily return. | Jun 2009 | 0.91% | 3x exposure |
| SGOV | iShares 0-3 Month Treasury Bond ETF. Holds very short-term T-bills. | 2020 | 0.09% | Where the cash sits (modeled as the 3-month T-bill rate minus SGOV's fee) |
| XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY | The nine original Select Sector SPDRs: materials, energy, financials, industrials, technology, consumer staples, utilities, health care and consumer discretionary. | Dec 1998 | about 0.08% | v2 ranks these by beta and holds the highest (or lowest) beta sectors |
| ^VIX | CBOE Volatility Index. The market's own estimate of S&P 500 volatility over the next 30 days, based on options prices. | 1990 | n/a | One of v3's ways to size leverage |
| ^N225, ^GDAXI | Japan's Nikkei 225 and Germany's DAX stock indexes. | n/a | n/a | Only used to test v3's rule outside the US |

One thing I had to understand before using SSO and UPRO is that they don't just return 2x or 3x over time. They reset their leverage every day, so what you get is 2x or 3x of each day's return, not of the month's or the year's. When the market trends steadily, that daily reset actually helps a little, but when it chops back and forth it costs you. For example, say the S&P 500 is up 10% one day and down 10% the next. That leaves it down 1%, since 1.10 x 0.90 = 0.99. A 3x fund would be up 30% and then down 30%, and 1.30 x 0.70 = 0.91, so it ends down 9% instead of the 3% you'd expect. People call this volatility decay, and it shows up in real data too. Specifically, Bianchi and Goldberg (2026) point out that the S&P 500 was basically flat over 2022-2023 while UPRO lost 28%. This is the main reason v3 uses a trend filter, since the idea is to only hold leverage when there's an actual trend.

When I say beta, I mean how much something moves with the market. SPY has a beta of 1, SSO about 2, UPRO about 3, and T-bills 0. For example, a sector with a beta of 1.3 has historically moved about 1.3% for every 1% move in the S&P 500.

## Data

`get_data.py` downloads daily prices from Yahoo Finance through `yfinance` for every ticker in the table except SGOV, which only goes back to 2020. Instead, cash is modeled with the 3-month T-bill rate (DTB3) from FRED, which doesn't need an API key. From Yahoo I use both Adj Close and Close. Adj Close includes reinvested dividends, so its percent change is the total return, while Close is the price only. The difference between the two on a given day is the dividend, which the tax model needs.

SSO didn't exist before June 2006 and UPRO didn't exist before June 2009, so for those years I rebuild them from SPY as leverage x SPY's daily return, minus the T-bill rate plus a spread on the borrowed part, minus the fund's fee. I fit the spread (0.7% for SSO, 0.6% for UPRO) so the rebuilt fund grows at the same rate as the real one over the years where both exist. The rebuilt and real daily returns end up with a 0.996 (SSO) and 0.998 (UPRO) correlation.

The data runs from January 1993 to October 29, 2026.

## Method

Every version calculates its signal at the month end close. Depending on the version and setting, that signal is SPY's total return index compared to its 200-day or N-month average, SPY's recent volatility, or each sector's beta over the last 6 or 12 months. The trade then goes in at the next day's close, since you can't trade at a close you haven't seen yet. There's no commission, but I charge 5 basis points of spread and slippage on every dollar traded, and nothing trades unless a holding is at least 5% off its target.

The account is taxable, and I only model federal tax. Every purchase is its own tax lot, and the oldest shares are sold first (FIFO). Short-term gains, T-bill interest and SSO/UPRO payouts are taxed at 22%, since leveraged funds mostly pay out short-term gains. On the other hand, long-term gains and SPY/sector dividends are taxed at 15%. Losses offset gains and carry forward, the wash sale rule is applied, and the tax bill comes out of the account every December. The results are shown after tax and sold at the end, which means the last step also pays the tax on any gains that haven't been sold yet. I think that's the fairer comparison, since buy and hold always has a big untaxed gain sitting in it.

For the fixed split, settings are picked on 2000-2009 by after-tax growth, then locked in and tested on 2010 to now. v1 is a little different, since it uses 1995-2009 and ranks by Sharpe ratio instead. For the walk-forward, every setting is scored each January on all the years before it, and the best one is traded for the next 12 months. v3's walk-forward starts in 2000 (scored from 1994) so it has to get through the dot com crash, while v2's starts in 2005 because the sector ETFs only go back to December 1998.

Since v3 ended up being the strongest version, it also gets the most checking. Specifically, there's a yearly t-test and the deflated Sharpe ratio (Bailey and Lopez de Prado 2014), which adjusts for how many settings were tried. In addition, there's a Monte Carlo that re-runs the rule on 1,000 resampled S&P 500 paths, a rolling 5-year version of the walk-forward, a check on the moving average length, and the same rule run on the Nikkei 225 and DAX.

## Results

$10,000 start, after federal taxes, sold at the end. Data through October 29, 2026. v1's settings were picked on 1995-2009 instead of 2000-2009, and only v3 has a walk-forward from 2000.

| | 2010-now (settings picked on 2000-2009) | 2000-now (walk-forward) | Max drawdown since 2000 |
|---|---|---|---|
| v1 - trend + vol targeting | $36,604 (8.0%/yr) | - | - |
| v2 - conditional beta | $48,696 (9.9%/yr) | - | - |
| v3 - 200 day trend, 3x | $96,681 (14.5%/yr) | $121,387 (9.8%/yr) | -82% |
| Buy and hold SPY | $76,769 (12.9%/yr) | $69,793 (7.5%/yr) | -55% |
| Buy and hold SSO (2x) | $261,801 (21.5%/yr) | $86,467 (8.4%/yr) | -89% |
| Buy and hold UPRO (3x) | $611,415 (27.8%/yr) | $53,118 (6.4%/yr) | -98% |

From 2005 (where v2's walk-forward starts), v2 made 10.8% a year after tax and v3 made 14.6%, compared to 9.9% for SPY, 13.7% for SSO and 14.8% for UPRO.

The rule v3 picked was 3x (100% UPRO) whenever SPY is above its 200-day moving average at month end, and 100% T-bills when it's below. From 2010 on it was at 3x about 84% of the time and in T-bills the rest.

![drawdowns since 2010](images/drawdowns_2010.png)

## Discussion

Most of v3's edge came from bear markets. It avoided most of 2000-2002 and 2008, which is exactly where buy and hold leverage gets wiped out. For example, from 2000-2009 buy and hold SSO lost about 11% a year after tax and UPRO lost about 22%. On the other hand, in bull markets with quick dips (most of 2010-2026), the filter kept selling near the bottom and buying back higher. You can see that in the drawdown chart above in 2011, 2015-2016, late 2018, 2020 and 2022-2023. This matches what Zakamulin (2014) found for moving average timing in general.

The bigger problem is that those bear market years are mostly years where UPRO had to be rebuilt. Since UPRO actually started trading in June 2009, v3 made 19.9% a year before tax, compared to 24.4% for SSO and 31.8% for UPRO. This means the result depends a lot on how realistic the rebuilt UPRO is for 2000-2009.

The lead also isn't statistically strong. v3's average yearly lead was t = 1.7 vs SPY and t = 0.9 vs SSO, and I'd want at least 2 before calling it convincing. Although the deflated Sharpe ratio says v3's Sharpe (0.43) is very likely above zero, SPY's Sharpe over the same years was about the same (0.41). In addition, it only beat SSO in 41-51% of the simulated 10-year paths in the Monte Carlo.

As for v2, the conditional beta idea didn't hold up once I made it tradable. High beta sectors do beat low beta sectors in months when the market goes up (t = 3.9 from 2010 on), but that test splits months by a return you don't know yet. When I split by the trend you actually know at the start of the month, the effect basically disappeared (t = 0.06). That's also why v2's walk-forward never picked the high beta sectors, and it only picked the low beta sectors for downtrends in 2024-2026.

Outside the US, the results were mixed. On the DAX and Nikkei, the same rule beat holding 2x from 1994 or 2000 but lost badly from 2010 on. Furthermore, on the Nikkei from 1994 it actually did worse than just holding the plain index.

Lastly, the timing is fragile. Trading at the signal's own close (which isn't actually possible) would have made 11.2% a year from 2000, compared to 9.8% for the next day and 10.7% for two days later. A one-day difference moving the result that much is a warning sign on its own.

## Mistakes I fixed along the way

My first pass made the strategies look a lot better than they were, so I went back through everything:

- It traded at the same close that created the signal. Moving to next-day trades cut v3's 2005-now result from 16.9% to about 14.7% a year.
- The walk-forward started in 2005, which happened to skip the year it would have picked plain 3x right before the dot com crash. Starting in 2000 shows the -82% drawdown.
- I wasn't applying the wash sale rule, I was crediting the $3,000 loss deduction to the account (that's really saved outside the account), and I was taxing leveraged ETF payouts as qualified dividends.
- My first Monte Carlo just reshuffled the strategy's own returns, so it couldn't show the trend filter failing.
- In v2 I was treating the Pettengill-style conditional beta test as evidence, even though it uses the market's future return.

Across the whole project I tried about 277 settings (96 in v1, 126 in v2, 13 in a technical indicator version I dropped, and 42 in v3). That's why I report the deflated Sharpe ratio.

## Limitations

- 3x leverage is a lot of risk. A one day crash like October 1987 (-20.5%) would be about -60% at 3x, and since the rule only checks at month end it would still be fully invested.
- There's no live forward test yet. Everything here is historical, so the real test is running the monthly signal going forward and tracking it.
- The rebuilt SSO/UPRO prices before 2006/2009 are an approximation, and a lot of v3's edge comes from those years.
- Federal tax only, at today's rates. The wash sale rule is simplified (the holding period doesn't carry over), and taxes are paid in December instead of April.
- 30 years of data only has a few real bear markets, so a handful of events drive most of the results.

## Repo structure

```
get_data.py                 downloads everything into data/ (yfinance + FRED)
compare_versions.ipynb      all three versions side by side
images/                     charts used in this README
v1_trend_vol/               SPY + T-bills, trend filter + volatility targeting
v2_conditional_beta/        adds SSO and the 9 sector SPDRs
v3_leveraged_beta/          SPY / SSO / UPRO, trend filters + fixed or Kelly leverage up to 3x
```

Each version folder has:
- `backtest.ipynb`: the full analysis
- `strategy.py`: the rules and the account / tax simulator
- `monthly_signal.py`: prints what to hold next month

## Reproducing it

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python get_data.py
```

Then open any of the notebooks and run all cells. The results will move a little depending on the date you download the data.

To get next month's position for v3, run this after the close on the last trading day of the month and place the trade the next day:

```
python v3_leveraged_beta/monthly_signal.py
```

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

*This is a personal research project, not financial advice.*
