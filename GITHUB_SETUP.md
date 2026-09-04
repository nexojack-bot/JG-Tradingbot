# Setting up the daily automation

## 1. Create the repo and upload
Same as the carbon-credit-quant repo: create a new GitHub repo (public,
needed for free GitHub Pages), upload the entire `tradingbot` folder
through the web uploader — including the hidden `.github/workflows/`
folder (GitHub's uploader includes dotfiles/dotfolders automatically when
you drag the whole directory in).

## 2. Add your Alpaca keys as repo secrets
Repo → Settings → Secrets and variables → Actions → New repository secret.
Add two:
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`

Same keys you've been using — but since they were pasted into this chat
earlier, rotate them from your Alpaca dashboard first and use the NEW pair
here, so the ones stored in GitHub Secrets aren't ones that ever appeared
in a chat transcript.

## 3. Enable GitHub Pages
Repo → Settings → Pages → under "Build and deployment", set Source to
**GitHub Actions** (not "Deploy from a branch" — the workflow handles
deployment itself).

## 4. Turn on Actions
Repo → Actions tab → if prompted, click "I understand my workflows, go
ahead and enable them."

## 5. Test it manually before trusting the schedule
Actions tab → "Daily Strategy Run" (left sidebar) → "Run workflow" button
→ Run workflow. Watch it execute — both jobs (`run-daily-experiment` then
`deploy-pages`) should turn green. If `run-daily-experiment` fails, click
into it to see the actual error (most likely cause: a secret name typo).

## What happens automatically after that
Every day at 21:30 UTC (after US market close, works across both EST/EDT):
1. The full 44-strategy cycle runs against live Alpaca data (~70 seconds).
2. Results commit back into `experiment/experiment.db` — this is what makes
   day 2 pick up where day 1 left off, rather than resetting every day.
3. The dashboard rebuilds from the fresh data and deploys to your GitHub
   Pages URL (found under Settings → Pages once the first deploy succeeds).

## Included seed data
The `experiment/experiment.db` and `experiment/dashboard_data.json` files
included in this upload are NOT placeholder/demo data — they're a real
first day, already run against your actual paper account with live market
data during this build session. The automation will build on top of this
starting point, not reset it.

## Known limitation worth knowing about
Two strategies (`earnings_surprise_drift`, `short_squeeze_candidate`) use
`yfinance`, an unofficial Yahoo Finance scraper — not a supported API. If
Yahoo changes their page format, these two specifically could start
silently returning nothing (they're built to degrade safely, not crash the
whole run) rather than erroring loudly. Worth spot-checking every few
weeks if those two strategies seem to never hold anything.
