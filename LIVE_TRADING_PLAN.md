# Live trading plan (staged, not yet started)

No real capital is deployed by any part of this repository. This document
outlines the staged path under consideration once the paper-trading phase
(see `METHODOLOGY.md`) has produced a defensible shortlist.

## Why staged, not a direct switch

Moving straight from "50 strategies paper trading" to "fully autonomous
live execution" skips a validation step every live system needs: paper
trading doesn't capture slippage, partial fills, real transaction costs,
or the psychological pressure of watching a bug affect real money before
it's caught. The staged approach below treats each stage as a genuine
checkpoint, not a formality.

## Stage 1 — Advisory (no capital at risk)

Once a shortlist of top strategies exists (ranked by alpha and
effective-N jointly, per `METHODOLOGY.md`, with a minimum 6-month real
track record), combine their daily signals into a single human-readable
recommendation per symbol, with a defensible confidence score — e.g. "5 of
8 shortlisted strategies currently hold NVDA; those 5 have averaged a 58%
historical win rate" — rather than an unexplained percentage. Delivered
daily, acted on manually. This stage alone provides weeks-to-months of
"would this have been a good call" feedback before any dollar moves
automatically.

## Stage 2 — Semi-automated, small capital, human-approved

Switch to live Alpaca credentials, but gate every trade behind manual
confirmation. Start with a small fraction (10-20%) of intended capital —
this stage is what actually tests live execution behavior (slippage,
partial fills, real fees) that paper trading cannot fully replicate.

## Stage 3 — Fully autonomous

Only after Stage 2 has run cleanly for a sustained period. Requires, at
minimum: a max position size per trade, a max daily loss that halts
trading and alerts a human, and a remote kill switch checked before every
trade. Deposit handling is straightforward at this stage — query the live
account's current cash/buying power before each day's run; newly added
funds simply appear as available cash and get deployed per the existing
allocation logic, no special "add funds" feature required.

## Before any real capital moves

- **Account eligibility** — live brokerage accounts generally require the
  account holder to be a legal adult or use a custodial structure; confirm
  directly with Alpaca rather than assuming.
- **Tax treatment** — frequent trading in a taxable account has real
  consequences (short-term capital gains rates, wash sale rules) with no
  paper-trading equivalent. Worth a real conversation with a tax
  professional before Stage 2, not after.
- Nothing in this document constitutes financial or legal advice.
