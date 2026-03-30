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
