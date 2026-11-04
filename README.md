# Does Timing Beta Beat Buy and Hold After Taxes?

Robert Miller

November 2026. Data through October 29, 2026.

## Abstract

I test whether an investor who checks once a month in a regular taxable brokerage account can beat buying and holding the S&P 500 by changing how much market exposure (beta) they hold. I build three versions. The first uses a trend filter and volatility targeting on SPY, the second holds more or less beta through sector ETFs and the 2x fund SSO depending on the trend, and the third applies trend filters and leverage rules taken from published research to the 3x fund UPRO. Every result includes trading costs, next-day execution, and federal taxes with tax lots and the wash sale rule. Out of everything I tested, the best rule was to hold 3x whenever SPY is above its 200-day moving average and T-bills when it isn't. Starting in 2000 with $10,000, the walk-forward version ended with $121,387 after tax, while SPY ended with $69,793 and SSO with $86,467. Even though that's the highest ending number, it actually dropped 82% at one point. In addition, the lead over SPY isn't statistically significant (t = 1.66), and the strategy has trailed leveraged buy and hold ever since the real UPRO started trading in 2009. This means the edge mostly comes from sitting out 2000-2002 and 2008, rather than from a reliable way to time beta.

Keywords: market timing, leveraged ETFs, trend following, conditional beta, volatility targeting, after-tax backtesting

JEL classification: G11, G14, G17

## 1. Introduction

Buying and holding the S&P 500 is hard to beat, but it also means sitting through every crash at full exposure. My idea was that you could actually do better by holding more beta while the market trends up, and cutting back (or getting out) when it doesn't. Leveraged ETFs like SSO and UPRO make this a lot more interesting, since anyone with a brokerage account can hold 2x or 3x the market. So the real question isn't just whether to be in or out, it's also how much to hold.

Most backtests of this idea leave out things a real investor actually has to deal with. For example, they often trade at the same close that created the signal, ignore taxes, or pick settings using the same years they are scored on. I wanted to see what's left after accounting for all of that, specifically for someone like me who would run this once a month in a taxable account.

I built the project in three versions, and each one takes on beta in a different way. v1 only holds SPY and T-bills, and it uses a trend filter plus volatility targeting to decide how much SPY to hold. v2 adds SSO and the nine sector ETFs, since several papers found that high beta stocks beat low beta stocks in up markets. v3 drops the sectors and adds UPRO instead, and every trend filter and leverage rule in it comes from a published paper. All three get a fixed train/test split, and v2 and v3 also get a walk-forward test, where the settings are re-picked every January using only the years before it.

The short answer is that it didn't work reliably. v3 beat buy and hold SPY and SSO from 2000 and from 2005, but almost all of that came from sitting out long bear markets, and it mostly happened in years where UPRO didn't exist yet and had to be rebuilt from SPY. Since 2010, it has trailed buy and hold SSO and UPRO.

![v3 walk-forward vs buy and hold](images/walk_forward_2000.png)

*Figure 1: Growth of $10,000 from 2000 for the v3 walk-forward strategy and buy and hold SPY, SSO and UPRO, after the federal taxes paid each year (log scale). The strategy re-picks its setting every January using only earlier years.*

I start with background on the ETFs and the papers the rules come from (Section 2), then go through the data (Section 3) and how the rules, costs, taxes and tests work (Section 4). After that I show the main results (Section 5), run the robustness checks (Section 6), and finish with what I think it all means and where it falls short (Section 7).

## 2. Background and related literature

### 2.1 The ETFs

Table 1 lists every ticker used in the project and what it's used for.

*Table 1: Tickers used in the project*

| Ticker | What it is | Started | Expense ratio used | Role here |
|---|---|---|---|---|
| SPY | SPDR S&P 500 ETF. Tracks the S&P 500 (about 500 of the largest US companies, weighted by size). | Jan 1993 | 0.0945% | The benchmark, and 1x exposure |
| SSO | ProShares Ultra S&P 500. Aims for 2x the S&P 500's daily return. | Jun 2006 | 0.89% | 2x exposure |
| UPRO | ProShares UltraPro S&P 500. Aims for 3x the S&P 500's daily return. | Jun 2009 | 0.91% | 3x exposure |
| SGOV | iShares 0-3 Month Treasury Bond ETF. Holds very short-term T-bills. | 2020 | 0.09% | Where the cash sits (modeled as the 3-month T-bill rate minus SGOV's fee) |
| XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY | The nine original Select Sector SPDRs: materials, energy, financials, industrials, technology, consumer staples, utilities, health care and consumer discretionary. | Dec 1998 | about 0.08% | v2 ranks these by beta and holds the highest (or lowest) beta sectors |
| ^VIX | CBOE Volatility Index. The market's own estimate of S&P 500 volatility over the next 30 days, based on options prices. | 1990 | n/a | One of v3's ways to size leverage |
| ^N225, ^GDAXI | Japan's Nikkei 225 and Germany's DAX stock indexes. | n/a | n/a | Only used to test v3's rule outside the US |

Notes: Expense ratios for the ETFs are already included in their Yahoo Finance prices. They are only applied directly when SSO and UPRO are rebuilt before they existed (Section 3.2) and to the cash return.

When I say beta, I mean how much something moves with the market. SPY has a beta of 1, SSO about 2, UPRO about 3, and T-bills 0. For example, a sector with a beta of 1.3 has historically moved about 1.3% for every 1% move in the S&P 500.

### 2.2 Why leveraged ETFs don't just return 2x or 3x

One thing I had to understand before using SSO and UPRO is that they don't just return 2x or 3x over time. They reset their leverage every day, so what you get is 2x or 3x of each day's return, not of the month's or the year's. When the market trends steadily, that daily reset actually helps a little, but when it chops back and forth it costs you. For example, say the S&P 500 is up 10% one day and down 10% the next. That leaves it down 1%, since 1.10 x 0.90 = 0.99. A 3x fund would be up 30% and then down 30%, and 1.30 x 0.70 = 0.91, so it ends down 9% instead of the 3% you'd expect. People call this volatility decay, and Cheng and Madhavan (2009) work through it in detail. It also shows up in real data. Specifically, Bianchi and Goldberg (2026) point out that the S&P 500 was basically flat over 2022-2023 while UPRO lost 28%. This is the main reason v3 uses a trend filter, since the idea is to only hold leverage when there's an actual trend.

### 2.3 Beta and conditional beta

v2 mostly comes from Lakonishok and Shapiro (1984). Across NYSE stocks from 1962-1980, beta by itself didn't explain returns, but high beta stocks did better than low beta stocks in up markets and worse in down markets. Pettengill, Sundaram and Mathur (1995) built a test around that, and both Xiao (2016) for the US and Elsas, El-Shaer and Theissen (2003) for Germany found the same thing with it. In other words, beta only seems to pay if you know which way the market is going. The catch is that their test splits months by the market's return in that same month, which you can't trade on. So the real question for v2 is whether a trend signal you do know ahead of time can stand in for it.

A few other papers shaped the setup. Zenner et al. (2008) put the market risk premium at about 5-7% a year, so sitting in cash has a real cost. Genc, Moench and Pazarbasi (2025) found fund managers pile into high beta stocks when rates rise, which raises raw returns but not risk-adjusted ones, so high beta can be a crowded trade. In addition, Hsu, Kalesnik and Li (2012) found equal weighting beat the S&P 500 from 1967-2010, mostly through value and small-cap tilts, which Campbell and Vuolteenaho's (2003) "bad beta, good beta" paper helps explain. That's why v2 includes an equal weight sector portfolio as a comparison.

### 2.4 Trend following and volatility management

v3's trend filter comes from Gayed and Bilello (2016). They held a leveraged S&P 500 only when it was above its 200-day moving average (T-bills otherwise), and from 1928-2015 that beat both regular and leveraged buy and hold. Faber (2007) does basically the same thing with a 10-month average. For how often to check, Clare et al. (2013) found that for the S&P 500, checking at month end was as good as checking daily, and stop losses didn't help.

For position size, Moreira and Muir (2017) and Harvey et al. (2018) found that scaling exposure by 1/variance raised the market's Sharpe ratio. This is basically the same thing as the Kelly rule from Rotando and Thorp (1992), where leverage equals the risk premium divided by the variance. v1's volatility targeting and v3's Kelly-style sizing both come from this idea.

On the other hand, a couple of papers were basically warnings. Cederburg et al. (2020) found volatility management usually did not beat buy and hold out of sample, and Zakamulin (2014) found moving average timing mostly wins in a few big bear markets and lags in bull markets once you test it out of sample with realistic costs. As it turns out, my results line up with both.

## 3. Data

### 3.1 Sources

`get_data.py` downloads daily prices from Yahoo Finance through `yfinance` for every ticker in Table 1 except SGOV, which only goes back to 2020. Instead, cash is modeled with the 3-month T-bill rate (DTB3) from FRED, which doesn't need an API key. From Yahoo I use both Adj Close and Close. Adj Close includes reinvested dividends, so its percent change is the total return, while Close is the price only. The difference between the two on a given day is the dividend, which the tax model needs. The data runs from January 1993 to October 29, 2026.

### 3.2 Rebuilding SSO and UPRO before they existed

SSO didn't exist before June 2006 and UPRO didn't exist before June 2009, so for those years I rebuild them from SPY. The daily return of a fund with leverage $L$ is

$$r_{L,t} = L \cdot r_{SPY,t} - (L-1) \cdot r_{f,t} - \frac{(L-1) \cdot s + f}{252} \qquad (1)$$

where $r_{f,t}$ is the daily T-bill return, $s$ is the extra borrowing spread, and $f$ is the fund's expense ratio. I fit the spread ($s$ = 0.7% for SSO and 0.6% for UPRO) so the rebuilt fund grows at the same rate as the real one over the years where both exist. The rebuilt and real daily returns end up with a 0.996 (SSO) and 0.998 (UPRO) correlation.

## 4. Methodology

### 4.1 Strategy rules

Every version calculates its signal at the month end close. For v1, if SPY's total return index is above its N-month average, the trend is up and the strategy holds SPY, and if not it moves to T-bills (or only partly, using an "off weight"). In addition, the SPY weight is scaled by volatility,

$$w_t = \min\left(1, \frac{\sigma^*}{\hat{\sigma}_t}\right) \qquad (2)$$

where $\sigma^*$ is the target volatility and $\hat{\sigma}_t$ is SPY's recent realized volatility.

v2 uses the same kind of trend signal (8, 10 or 12 months). In an uptrend it takes on more beta, either by holding 100% SPY, the 2-4 highest beta sector ETFs, or a SPY/SSO mix that gets to a beta of 1.5 or 2. In a downtrend it takes on less, so it either moves to T-bills or holds the 3 lowest beta sectors. Sector betas are measured over the last 6 or 12 months.

v3 holds SPY, SSO, UPRO and T-bills, so leverage can be anywhere from 0 to 3x. The trend filter is either the 200-day average, the 10-month average, or none. Leverage is either a fixed 2x or 3x, or a Kelly-style rule,

$$L_t = \min\left(3, k \cdot \frac{\mu}{\hat{\sigma}_t^2}\right) \qquad (3)$$

with $k$ = 0.5 or 1, a risk premium $\mu$ of 6% (the middle of Zenner et al.'s range), and volatility from either the last 21 days or the VIX. Table 2 lists every setting that was tested.

*Table 2: Settings tested in each version*

| Version | Parameters | Combinations |
|---|---|---|
| v1 | Trend length 6, 8, 10 or 12 months; volatility window 21 or 63 days; target volatility 10%, 12.5%, 15% or 20%; off weight 0, 25% or 50% | 96 |
| v2 | Trend length 8, 10 or 12 months; uptrend holding (SPY, top 2/3/4 beta sectors, or 1.5x/2x SPY/SSO); downtrend holding (T-bills or 3 lowest beta sectors); beta window 6 or 12 months; optional 20% volatility cap | 126 |
| v3 | Trend filter (none, 200-day, 10-month); sizing (fixed 2x/3x, Kelly 0.5/1 with realized or VIX volatility); check frequency (monthly, weekly, daily) | 42 |

Notes: The 10-month filter in v3 is only tested monthly. The beta window in v2 only matters when sectors are held. I also tried 13 settings in a technical indicator version that I dropped, so the project has about 277 trials in total.

### 4.2 Execution and trading costs

The trade goes in at the next day's close after the signal, since you can't trade at a close you haven't seen yet. There's no commission, but I charge 5 basis points of spread and slippage on every dollar traded, and nothing trades unless a holding is at least 5% off its target. The account starts with $10,000, and cash earns the T-bill rate minus SGOV's 0.09% fee.

### 4.3 Taxes

The account is taxable, and I only model federal tax. Every purchase is its own tax lot, and the oldest shares are sold first (FIFO). Short-term gains, T-bill interest and SSO/UPRO payouts are taxed at 22%, since leveraged funds mostly pay out short-term gains. On the other hand, long-term gains and SPY/sector dividends are taxed at 15%. Losses offset gains and carry forward, the wash sale rule is applied, and the tax bill comes out of the account every December. I don't credit the $3,000 deduction against other income, since that saving happens outside the account. The results are shown after tax and sold at the end, which means the last step also pays the tax on any gains that haven't been sold yet. I think that's the fairer comparison, since buy and hold always has a big untaxed gain sitting in it.

### 4.4 Testing design

For the fixed split, settings are picked on 2000-2009 by after-tax growth, then locked in and tested on 2010 to now. v1 is a little different, since it uses 1995-2009 and ranks by Sharpe ratio instead, because ranking by growth would just pick whatever holds the most SPY. For the walk-forward, every setting is scored each January on all the years before it, and the best one is traded for the next 12 months. v3's walk-forward starts in 2000 (scored from 1994) so it has to get through the dot com crash, while v2's starts in 2005 because the sector ETFs only go back to December 1998.

## 5. Results

### 5.1 Main results

Table 3 shows the main results. From 2005 (where v2's walk-forward starts), v2 made 10.8% a year after tax and v3 made 14.6%, compared to 9.9% for SPY, 13.7% for SSO and 14.8% for UPRO.

*Table 3: Ending value of $10,000 after federal taxes, sold at the end*

| | 2010-now (fixed split) | 2000-now (walk-forward) | Max drawdown since 2000 |
|---|---|---|---|
| v1 - trend + vol targeting | $36,604 (8.0%/yr) | - | - |
| v2 - conditional beta | $48,696 (9.9%/yr) | - | - |
| v3 - 200 day trend, 3x | $96,681 (14.5%/yr) | $121,387 (9.8%/yr) | -82% |
| Buy and hold SPY | $76,769 (12.9%/yr) | $69,793 (7.5%/yr) | -55% |
| Buy and hold SSO (2x) | $261,801 (21.5%/yr) | $86,467 (8.4%/yr) | -89% |
| Buy and hold UPRO (3x) | $611,415 (27.8%/yr) | $53,118 (6.4%/yr) | -98% |

Notes: Fixed split settings were picked on 2000-2009 (1995-2009 for v1). Only v3 has a walk-forward from 2000. Drawdowns are from before-tax daily returns.

v1 did what it was built to do on risk, but not on return. From 2010 its max drawdown was about -21% vs -34% for SPY and its beta was only 0.57, but its Sharpe ratio was lower (0.65 vs 0.77), so the smoother ride didn't make up for the lost return. v2's fixed split pick made 9.9% a year vs 12.9% for SPY, with a worse drawdown (-45% vs -34%).

v3's rule ended up being 3x (100% UPRO) whenever SPY is above its 200-day moving average at month end, and 100% T-bills when it's below. From 2010 on it was at 3x about 84% of the time and in T-bills the rest, and it beat SSO in 8 of the 17 years before tax.

![drawdowns since 2010](images/drawdowns_2010.png)

*Figure 2: Drawdown from the previous high since 2010 for v3 (fixed split setting) and buy and hold SPY, SSO and UPRO, before tax.*

### 5.2 Results by start year

Since a single start date can make any strategy look good or bad, Table 4 runs the same v3 walk-forward signals from different start years.

*Table 4: v3 walk-forward after-tax CAGR by start year*

| Start | v3 | SPY | SSO | UPRO | v3 max drawdown |
|---|---|---|---|---|---|
| 2000 | 9.8% | 7.5% | 8.4% | 6.4% | -82% |
| 2005 | 14.6% | 9.9% | 13.7% | 14.8% | -64% |
| 2008 | 15.6% | 10.3% | 14.6% | 15.6% | -64% |
| 2010 | 14.5% | 12.9% | 21.5% | 27.8% | -64% |
| 2015 | 9.6% | 12.3% | 19.3% | 23.6% | -64% |
| 2020 | 13.9% | 13.4% | 19.4% | 21.7% | -64% |

Notes: Same signals in every row, only the start date changes. Each row's taxes start from a new $10,000 account.

The edge shrinks or flips with later start years. Starting in 2010, 2015 or 2020, it actually trailed SSO every time, and the 2015 start even trailed plain SPY. The -82% from 2000 happened because scoring 1994-1999 picked plain 3x buy and hold for 2000 and 2001, right into the dot com crash, and it only switched to the trend filter in 2002.

### 5.3 Where the edge comes from

Most of v3's edge came from bear markets. It avoided most of 2000-2002 and 2008, which is exactly where buy and hold leverage gets wiped out. For example, from 2000-2009 buy and hold SSO lost about 11% a year after tax and UPRO lost about 22%. On the other hand, in bull markets with quick dips (most of 2010-2026), the filter kept selling near the bottom and buying back higher. You can see that in Figure 2 in 2011, 2015-2016, late 2018, 2020 and 2022-2023. This matches what Zakamulin (2014) found for moving average timing in general.

### 5.4 The conditional beta test

The conditional beta idea behind v2 didn't hold up once I made it tradable. Each month I regressed the sectors' next-month returns on their beta from the previous 12 months. When I split months by whether SPY beat T-bills that month, high beta sectors did better in up months (t = 3.9 from 2010 on) and worse in down months (t = -4.9), which matches the papers. However, that split uses a return you don't know yet, and if betas stay about the same over time, it mostly comes out that way automatically. When I split by the trend signal you actually know at the start of the month, the effect basically disappeared (t = 0.06 in uptrends from 2010 on, -0.21 in training). That's also why v2's walk-forward never picked the high beta sectors, and it only picked the low beta sectors for downtrends in 2024-2026.

## 6. Robustness

### 6.1 Rebuilt vs real UPRO

UPRO only exists since June 25, 2009, so everything before that is rebuilt using equation (1). In the rebuilt years (2000 to June 2009), the strategy lost 3.5% a year before tax, compared to -3.0% for SPY, -14.8% for SSO and -27.7% for UPRO. Since UPRO actually started trading, it made 19.9% a year vs 14.8% for SPY, 24.4% for SSO and 31.8% for UPRO. This means all of v3's edge over leveraged buy and hold comes from years where UPRO had to be rebuilt, so the result depends a lot on how realistic the rebuilt UPRO is.

### 6.2 Statistical significance

Over 26 years, v3's average yearly lead was about 10.7 points over SPY (ahead in 15 years, t = 1.66) and about 4.7 points over SSO (ahead in 14 years, t = 0.91). I'd want at least 2 before calling either one convincing. Its Sharpe ratio was 0.43 with a standard error of 0.20 (Lo 2002). The deflated Sharpe ratio (Bailey and Lopez de Prado 2014), which adjusts for fat tails and for how many settings I tried, puts the chance that the true Sharpe is above zero at 92% with 42 trials and 88% with 277. Although that sounds good, SPY's Sharpe over the same years was about the same (0.41), so it doesn't really show the strategy is better.

### 6.3 Monte Carlo

This builds 1,000 new 10-year S&P 500 paths out of random blocks of SPY's real daily returns since 1993 (with the T-bill rate and VIX from the same days), rebuilds SSO and UPRO from each path, and re-runs the rule on each one, so the trend filter can actually fail. With 6-month blocks, v3 beat SPY in 55% of paths and SSO in 41%, and with 1-year blocks it beat SPY in 65% and SSO in 51%. In addition, its median max drawdown (-68% and -62%) was worse than SSO's (-60% and -59%). Even though stitching blocks together breaks up long trends, which makes this a tough test for a trend filter, it still doesn't show a clear edge over SSO.

### 6.4 Rolling window walk-forward

The walk-forward in Section 5 scores every year back to 1994, so 2000-2002 and 2008 stay in the score forever, which is probably why it picks the same rule every year. When it only looks at the last 5 years, it switches to plain 3x buy and hold from 2014-2022. That version ended at 10.3% a year after tax, also with an -82% drawdown. So the "same rule every year" result really just comes from always scoring back to 1994.

### 6.5 Trade timing

Trading at the signal's own close (which isn't actually possible) would have made 11.2% a year after tax from 2000, compared to 9.8% for the next day and 10.7% for two days later. From 2010 the same three numbers are 17.2%, 14.5% and 15.7%. A one-day difference moving the result that much is a warning sign on its own.

### 6.6 Moving average length

The papers say anywhere from 200-300 days works, and if the result only showed up at exactly 200 it would probably be luck. Table 5 runs the same rule with a fixed trend filter (no walk-forward) from 100 to 300 days. I didn't use this table to pick anything.

*Table 5: After-tax CAGR from 2000 by moving average length*

| | 100 days | 150 days | 200 days | 250 days | 300 days |
|---|---|---|---|---|---|
| 2x | 6.8% | 10.7% | 10.5% | 11.6% | 9.5% |
| 3x | 8.0% | 13.8% | 13.3% | 14.7% | 11.0% |

Notes: Buy and hold SSO made 8.4% over the same years. These numbers are higher than the 9.8% walk-forward in Table 3 because the walk-forward held 3x with no filter in 2000 and 2001.

This was the one check that went its way, since every length from 150 to 300 days beat SSO. However, 100 days didn't.

### 6.7 Outside the US

Table 6 runs the same rule (200 days, 3x, monthly, next-day trades) on Japan's Nikkei 225 and Germany's DAX. There aren't 2x/3x funds or local T-bill data going back that far, so this is a simpler before-tax version where 2x and 3x are rebuilt the same way, cash earns 0%, and borrowing only costs the spread.

*Table 6: Before-tax CAGR outside the US*

| Index | Start | Rule 3x | Rule 2x | Hold 1x | Hold 2x | Hold 3x | Rule 3x max drawdown |
|---|---|---|---|---|---|---|---|
| Nikkei 225 | 1994 | 3.5% | 4.7% | 4.2% | 1.1% | -6.1% | -83% |
| Nikkei 225 | 2000 | 6.6% | 7.0% | 4.8% | 2.2% | -4.8% | -83% |
| Nikkei 225 | 2010 | 7.1% | 7.9% | 11.6% | 16.9% | 17.7% | -79% |
| DAX | 1994 | 13.4% | 11.0% | 7.7% | 8.7% | 5.5% | -74% |
| DAX | 2000 | 11.5% | 9.6% | 5.1% | 3.4% | -2.2% | -74% |
| DAX | 2010 | 6.0% | 6.0% | 9.0% | 12.6% | 13.2% | -74% |

Notes: The Nikkei is price only, and the DAX includes dividends.

The results were mixed. On both indexes the rule beat holding 2x from 1994 or 2000 but lost badly from 2010 on. Furthermore, on the Nikkei from 1994 the 3x rule actually did worse than just holding the plain index.

## 7. Conclusion

The 200-day 3x rule beat buy and hold SPY and SSO over stretches that include a long bear market, but mostly in years where UPRO had to be rebuilt. Since the real UPRO started trading it has trailed leveraged buy and hold. In addition, the lead isn't statistically strong, it depends on the exact trade day, and the drawdowns got to -82%. The simpler versions didn't do better either. v1 cut risk but gave up too much return, and v2 only beat SPY after taxes because it sat out 2008. Simply put, I don't think this backtest shows a proven way to beat buy and hold. It's a high-risk rule that has helped in long crashes and lagged in long bull markets.

### 7.1 Limitations

There are a few things this backtest can't account for. First, 3x leverage is a lot of risk. A one day crash like October 1987 (-20.5%) would be about -60% at 3x, and since the rule only checks at month end it would still be fully invested. The worst single day in the backtest was already -19.8% (August 8, 2011). Second, there's no live forward test yet, so the real test is running the monthly signal going forward and tracking it. Third, the rebuilt SSO/UPRO prices before 2006/2009 are an approximation, and a lot of v3's edge comes from those years. In addition, I only model federal tax at today's rates, the wash sale rule is simplified (the holding period doesn't carry over), and taxes are paid in December instead of April. 3x was also the most leverage I allowed and it won, so the result is partly just a bet on leverage. Lastly, 30 years of data only has a few real bear markets, so a handful of events drive most of the results.

## References

Bailey, D. and Lopez de Prado, M. (2014). The Deflated Sharpe Ratio. *Journal of Portfolio Management*, 40(5), 94-107.

Bianchi, S. and Goldberg, L. (2026). A Levered ETF Anomaly Explained. arXiv:2604.27287.

Campbell, J. and Vuolteenaho, T. (2003). Bad Beta, Good Beta. Working paper, Harvard University.

Cederburg, S., O'Doherty, M., Wang, F. and Yan, X. (2020). On the Performance of Volatility-Managed Portfolios. *Journal of Financial Economics*, 138(1), 95-117.

Cheng, M. and Madhavan, A. (2009). The Dynamics of Leveraged and Inverse Exchange-Traded Funds. *Journal of Investment Management*, 7(4), 43-62.

Clare, A., Seaton, J., Smith, P. and Thomas, S. (2013). Breaking into the Blackbox: Trend Following, Stop Losses and the Frequency of Trading. *Journal of Asset Management*, 14(3), 182-194.

Elsas, R., El-Shaer, M. and Theissen, E. (2003). Beta and Returns Revisited. *Journal of International Financial Markets, Institutions and Money*, 13, 1-18.

Faber, M. (2007). A Quantitative Approach to Tactical Asset Allocation. *Journal of Wealth Management*.

Gayed, M. and Bilello, C. (2016). Leverage for the Long Run. Charles H. Dow Award paper.

Genc, E., Moench, E. and Pazarbasi, A. (2025). Reaching for Beta. Working paper.

Harvey, C. et al. (2018). The Impact of Volatility Targeting. *Journal of Portfolio Management*, 45(1), 14-33.

Hsu, J., Kalesnik, V. and Li, F. (2012). An Investor's Guide to Smart Beta Strategies. *AAII Journal*.

Lakonishok, J. and Shapiro, A. (1984). Stock Returns, Beta, Variance and Size. *Financial Analysts Journal*, 40(4), 36-41.

Lo, A. (2002). The Statistics of Sharpe Ratios. *Financial Analysts Journal*, 58(4), 36-52.

Moreira, A. and Muir, T. (2017). Volatility-Managed Portfolios. *Journal of Finance*, 72(4), 1611-1644.

Pettengill, G., Sundaram, S. and Mathur, I. (1995). The Conditional Relation between Beta and Returns. *Journal of Financial and Quantitative Analysis*, 30(1), 101-116.

Rotando, L. and Thorp, E. (1992). The Kelly Criterion and the Stock Market. *American Mathematical Monthly*, 99(10), 922-931.

Xiao, B. (2016). Conditional Relationship Between Beta and Return in the US Stock Market. *Expert Journal of Business and Management*, 4(1), 46-55.

Zakamulin, V. (2014). The Real-Life Performance of Market Timing with Moving Average and Time-Series Momentum Rules. *Journal of Asset Management*, 15(4), 261-278.

Zenner, M., Hill, S., Clark, J. and Mago, N. (2008). The Most Important Number in Finance. J.P. Morgan.

## Appendix A: Corrections to the first draft

My first pass made the strategies look a lot better than they were, so I went back through everything. It traded at the same close that created the signal, and moving to next-day trades cut v3's 2005-now result from 16.9% to about 14.7% a year. The walk-forward started in 2005, which happened to skip the year it would have picked plain 3x right before the dot com crash, and starting in 2000 shows the -82% drawdown. I also wasn't applying the wash sale rule, I was crediting the $3,000 loss deduction to the account, and I was taxing leveraged ETF payouts as qualified dividends. In addition, my first Monte Carlo just reshuffled the strategy's own returns, so it couldn't show the trend filter failing. Lastly, in v2 I was treating the Pettengill-style conditional beta test as evidence, even though it uses the market's future return. Everything in this README is from the corrected version.

## Appendix B: Reproducing the results

### B.1 Computational requirements

Everything here was run on my Mac using Python 3.9.6. I pinned the package versions in `requirements.txt` (pandas 2.3.3, numpy 2.0.2, matplotlib 3.9.4, yfinance 1.2.0 and jupyter 1.1.1), but the last cell of each notebook also prints what it was really run with, just in case. The data itself isn't in the repo, so `get_data.py` pulls it from Yahoo Finance and FRED. Even though it's the same source, Yahoo goes back and changes old prices once in a while. So each notebook ends with the last date and a SHA-256 hash of every file it used, which tells you right away if your download differs from mine.

### B.2 Repository structure

```
get_data.py                 downloads everything into data/ (yfinance + FRED)
requirements.txt            pinned package versions
compare_versions.ipynb      all three versions side by side
images/                     charts used in this README
v1_trend_vol/               SPY + T-bills, trend filter + volatility targeting
v2_conditional_beta/        adds SSO and the 9 sector SPDRs
v3_leveraged_beta/          SPY / SSO / UPRO, trend filters + fixed or Kelly leverage up to 3x
```

Each version folder has a `backtest.ipynb` with the full analysis, a `strategy.py` with the rules and the account / tax simulator, and a `monthly_signal.py` that prints what to hold next month.

### B.3 Instructions

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python get_data.py
```

Once that finishes, I just open a notebook and hit Run All. None of them rely on another one, so you can start anywhere. Also, if you pull the data on a different day than I did, the numbers will probably be a bit off from mine. To get next month's position for v3, run this after the close on the last trading day of the month and place the trade the next day:

```
python v3_leveraged_beta/monthly_signal.py
```

### B.4 Where each table and figure comes from

| In this README | Notebook | Section of the notebook |
|---|---|---|
| Table 1 | none | ETF and index facts, no code |
| Table 2 | `v1_trend_vol`, `v2_conditional_beta`, `v3_leveraged_beta` | Section 2 (v1), Section 4 (v2), Section 2 (v3) |
| Table 3 | `compare_versions` | Fixed split, v3 from 2000 |
| Figure 1 | `v3_leveraged_beta` | Section 4 (saved as `images/walk_forward_2000.png`) |
| Figure 2 | `v3_leveraged_beta` | Section 3 (saved as `images/drawdowns_2010.png`) |
| Table 4 | `v3_leveraged_beta` | Section 4 |
| Section 5.1 (v1 risk numbers) | `v1_trend_vol` | Section 3 |
| Section 5.4 | `v2_conditional_beta` | Section 3 |
| Table 5 | `v3_leveraged_beta` | Section 5 |
| Sections 6.1-6.5 | `v3_leveraged_beta` | Section 6 |
| Table 6 | `v3_leveraged_beta` | Section 6, Outside the US |

*This is a personal research project, not financial advice.*
