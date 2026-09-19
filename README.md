# financial-data

Repository for raw and processed financial datasets useful for Indian tax and finance workflows.

## Dataset: SBI Forex Card Rates

This repository stores SBI Forex Card reference PDFs and compact JSON time-series for ITR use-cases where only USD TT buying and TT selling rates are required.

### Folder structure

- `src/sbi-fx-card-rates/<year>/<yyyy-MM-dd>.pdf`
- `docs/sbi-fx-card-rates/<year>/USD.json`

JSON format:

```json
{"header":["date","tt_buy","tt_sell"],"data":[["2026-03-30",83.1,84.2]]}
```

## Historical Data Attribution

Historical SBI data copied into this repository is sourced from:

- https://github.com/sahilgupta/sbi-fx-ratekeeper

Source split:

- Up to 2026-03-30: data created from the source GitHub repository above
- From 2026-03-31 onwards: data is obtained directly from SBI site via scheduled automation

Please refer to the source repository for original collection logic, credits, and historical provenance notes.

## Automation

GitHub Actions workflow:

- `.github/workflows/sbi-fx-card-rates-daily.yml`

What it does:

- Runs on schedule at `30 10,16 * * *` (10:30 and 16:30 UTC; 16:00 and 22:00 IST)
- Downloads latest SBI Forex Card PDF
- Updates compact yearly USD JSON files (`tt_buy`, `tt_sell` only)
- Commits and pushes changes automatically

Failure notification:

- On workflow failure, it creates a GitHub issue with run details so you receive repository notifications.

## Local commands

Install dependencies:

```bash
pip install -r requirements.txt
```

Migrate historical data from a local clone of source repo:

```bash
python scripts/sbi_fx_card_rates_sync.py --repo-root . --migrate-historical --source-repo /path/to/sbi-fx-ratekeeper
```

Fetch latest rates once:

```bash
python scripts/sbi_fx_card_rates_sync.py --repo-root . --fetch-latest
```

## Target Dataset Specification

The goal is to automate the fetching and consolidation of the following index / proxy streams.

### 1. International (Irish accumulating only)

| Category | Exposure | Reference series (TR) → source | Irish Acc proxy | ISIN | Proxy start |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **All** | All World (DM + EM) | MSCI ACWI Net TR → MSCI index-data search | `SSAC.L` | IE00B6R52259 | Oct 2011 |
| **DM** | Developed Markets | MSCI World Net TR → MSCI | `SWDA.L` | IE00B4L5Y983 | Sep 2009 |
| **EM** | Emerging Markets | MSCI EM Net TR → MSCI | `SEMA.L` | IE00B4L5YC18 | Sep 2009 |
| **USA** | US Broad (MSCI USA) | MSCI USA Net TR → MSCI | `CSUS.L` | IE00B52SFT06 | Jan 2010 |
| **USA** | S&P 500 | S&P 500 TR → S&P Dow Jones Indices | `CSPX.L` | IE00B5BMR087 | May 2010 |
| **USA** | Nasdaq 100 | Nasdaq-100 TR (XNDX) → Nasdaq Global Indexes | `CNDX.L` | IE00B53SZB19 | Jan 2010 |
| **India** | India Broad (MSCI) | MSCI India Net TR → MSCI | `NDIA.L` | IE00BZCQB185 | May 2018 |
| **Gold** | Global Gold (USD) | LBMA Gold Price PM → IBA licence | `IGLN.L` | IE00B4ND3602 | Apr 2011 |

### 2. India

| Category | Exposure | Reference series (TR) → source | Investable proxy | ISIN | Proxy start |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Equities** | Nifty 50 | Nifty 50 TRI → niftyindices.com | `NIFTYBEES` | INF204KB14I2 | Dec 2001 |
| **Equities** | Nifty Next 50 | Nifty Next 50 TRI → NSE Indices | `JUNIORBEES` | INF732E01045 | Feb 2003 |
| **Equities** | Nifty Midcap 150 | Nifty Midcap 150 TRI → NSE Indices | `MID150BEES` | INF204KB1V68 | Jan 2019 |
| **Equities** | Nifty Smallcap 250| Nifty Smallcap 250 TRI → NSE Indices | `HDFCSML250` | INF179KC1FB2 | Feb 2023 |
| **Gold** | Domestic Gold (INR) | GOLDBEES NAV → ibjarates.com (cross-check) | `GOLDBEES` | INF204KB17I5 | Mar 2007 |
| **Macro** | USD/INR (benchmark)| FBIL reference rate from Jul 2018 | — | — | — |
| **Macro** | USD/INR (tax) | SBI TT buy/sell → daily PDF scraper | — | — | — |
| **Macro** | India inflation | MoSPI CPI Combined (all-India) | — | — | — |

### 3. Debt (US & India)

| Region | Tier | Reference series (TR) → source | Investable series | ID | Starts |
|:--|:--|:--|:--|:--|:--|
| **US** | Short | ICE U.S. Treasury Short Bond Index → ICE (licensed) | iShares $ Treasury Bond 0-1yr UCITS ETF (Acc), `IB01` | IE00BGSF1X88 | Feb 2019 |
| **US** | Long | ICE U.S. Treasury 7-10 Year Bond Index → ICE (licensed) | iShares $ Treasury Bond 7-10yr UCITS ETF (Acc), `CBU0` | IE00B3VWN518 | Jun 2009 |
| **India** | Short | NIFTY Liquid Index A-I → NSE Indices | SBI Liquid Fund, Direct-Growth | INF200K01UT4 | Jan 2013 |
| **India** | Long | NIFTY All Duration G-Sec Index → NSE Indices (confirm the factsheet) | SBI Gilt Fund, Direct-Growth | INF200K01SH3 | Jan 2013 |

**Why 7-10 yr rather than 20+ for US long**
- **Duration:** SBI Gilt's manager sets duration, so neither US bucket matches it exactly. The 7-10 yr fund is the nearer and less extreme match, since 20+ yr is far longer by definition.
- **Fallback:** If you'd rather have a longer-duration US bucket, swap in `DTLA` (IE00BFM6TC58) instead.

**If you later want three tiers on each side**
- **US:** IB01, CBU0 and DTLA.
- **India:** SBI Liquid, SBI Constant Maturity 10 Year Gilt Fund (INF200K01SK7) and SBI Gilt.

### Implementation Notes
- **Net vs gross**: Use MSCI Net to match the Irish accumulating funds. NSE TRIs are what the Indian ETFs track. Check S&P and Nasdaq factsheet benchmark tickers to ensure gross/net alignment.
- **Price series**: Use the issuer's **NAV history** for every proxy row rather than exchange closes.
- **Licensing**: For anything public, publish only the issuer NAV series. Compute pre-inception history privately as MSCI/ICE/LBMA/FBIL restrict commercial redistribution.
- **Breaks**: GOLDBEES NAV valuation changed on 1 Apr 2026 to exchange-polled spot prices.
- **Back-calculations**: Midcap 150 and Smallcap 250 values before Apr 2016 are back-calculated. The NIFTY Composite Debt Index A-III is back-calculated before Apr 2022.

- **Splices:** The `CBU0` index changed in 2014 and 2016.
- **ISINs:** The Indian ISINs come from aggregator and Paytm Money URLs, so confirm them against AMFI.
