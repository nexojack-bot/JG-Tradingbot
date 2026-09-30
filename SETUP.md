# Fundamentals Screener — backend setup

This is the live piece the rest of the site doesn't have: instead of being
baked into the daily build, `fundamentals.html` calls this backend directly
from your browser, every time you run it, so you can type in any tickers
you want on the spot.

That means it needs to live somewhere that's actually running all the
time (or close to it) — GitHub Pages can't run it, since Pages only
serves static files. These steps put it on Render's free tier.

## 1. Push this folder to your repo

Add the whole `screener_backend/` folder to the root of your `JG-Tradingbot`
repo (same level as `config.py`, `run_experiment_day.py`, etc.), commit,
and push. Nothing here runs automatically — it just needs to be in the
repo so Render can build from it.

## 2. Create the Render service

1. Go to [render.com](https://render.com) and sign up (free — no card
   needed for the free tier).
2. **New +** → **Blueprint**, and point it at your `JG-Tradingbot` GitHub
   repo. Render will find `screener_backend/render.yaml` automatically and
   pre-fill everything (root directory, build command, start command).
   If Render doesn't offer the Blueprint option for some reason, create a
   **Web Service** manually instead with these settings:
   - **Root directory:** `screener_backend`
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
3. Before the first deploy finishes, add these **environment variables**
   (Render will prompt for them since `render.yaml` marks them
   `sync: false`, meaning "ask, don't guess"):
   - `ALPACA_API_KEY` — same value as the GitHub secret you already have
   - `ALPACA_SECRET_KEY` — same value as the GitHub secret you already have
   - `SEC_USER_AGENT` — any string with a way to reach you, e.g.
     `"JG-Tradingbot Jack <your-email-here>"`. SEC asks for this on their
     public API so they can identify who's calling it if something needs
     following up — it's not sent anywhere else, just to SEC's own
     servers, the same as it would be if you called their API directly.
4. Deploy. First build takes a few minutes. When it's done, Render gives
   you a URL like `https://jg-tradingbot-fundamentals-api.onrender.com`.

## 3. Wire the URL into the site

Add one line to `config.py` at the repo root:

```python
FUNDAMENTALS_API_BASE_URL = "https://jg-tradingbot-fundamentals-api.onrender.com"
```

(use your actual Render URL, no trailing slash). Commit and push — the
next daily build (or a manual "rebuild site only" run, if you have that
workflow) will bake this URL into `fundamentals.html`, and the page will
start working.

## 4. One real trade-off to know about

Render's free tier **sleeps the service after ~15 minutes with no
requests**, and takes 20-50 seconds to wake back up on the next one. The
page already accounts for this — the status message says so — but the
first click after a while idle will feel slow. That's expected, not
broken. If it's still failing after a minute or two, something else is
wrong (check the Render service's logs for the actual error).

## What this does NOT touch

This backend is completely separate from the daily GitHub Actions run —
it doesn't read or write `experiment.db`, doesn't affect the 50
strategies, and going down doesn't break anything else on the site. It
only powers this one page.
