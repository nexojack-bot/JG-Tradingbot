"""
Turns SEC EDGAR company facts + a live price into a fixed set of
fundamental metrics for one ticker. Any metric that can't be computed
(missing tag, zero/negative denominator that would make the ratio
meaningless) is returned as None rather than guessed — the scoring layer
is responsible for handling missing metrics honestly, not this one.
"""

import sec_edgar as se

REVENUE_TAGS = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"]
EPS_TAGS = ["EarningsPerShareDiluted", "EarningsPerShareBasic"]
EQUITY_TAGS = ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
SHARES_TAGS = ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"]
NET_INCOME_TAGS = ["NetIncomeLoss"]
LIABILITIES_TAGS = ["Liabilities"]
ASSETS_TAGS = ["Assets"]
DIVIDEND_TAGS = ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"]
OCF_TAGS = ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]
CAPEX_TAGS = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]


def get_fundamentals(ticker: str, current_price: float) -> dict:
    """
    Returns a dict with the raw figures used, the fiscal period they came
    from, and the derived ratios. `current_price` must come from a live
    price source (this module never fetches price itself, since price
    isn't in SEC filings) — pass it in from wherever the caller gets
    quotes (Alpaca, in this project).
    """
    out = {
        "ticker": ticker.upper(), "resolved": False, "error": None,
        "fiscal_period_end": None, "price": current_price,
        "metrics": {}, "raw": {},
    }

    facts = se.get_company_facts(ticker)
    if facts is None:
        out["error"] = "No SEC filer found for this ticker (not a US-listed filer, or a typo)."
        return out
    out["resolved"] = True

    eps = se.latest_annual_value(facts, EPS_TAGS)
    equity = se.latest_annual_value(facts, EQUITY_TAGS, value_type="instant")
    shares = se.latest_annual_value(facts, SHARES_TAGS, value_type="instant")
    net_income = se.latest_annual_value(facts, NET_INCOME_TAGS)
    liabilities = se.latest_annual_value(facts, LIABILITIES_TAGS, value_type="instant")
    if liabilities is None:
        # Some filers (e.g. Coca-Cola) don't tag a consolidated "Liabilities"
        # figure at all. Derive it from the balance-sheet identity
        # (Assets = Liabilities + Equity) using the two nearly-universal
        # tags instead of leaving this metric silently unavailable for
        # otherwise well-covered large-cap filers.
        assets = se.latest_annual_value(facts, ASSETS_TAGS, value_type="instant")
        if assets and equity and assets["end"] == equity["end"]:
            liabilities = {"val": assets["val"] - equity["val"], "end": assets["end"],
                            "tag": "derived: Assets - StockholdersEquity", "unit": "USD"}
    dividend = se.latest_annual_value(facts, DIVIDEND_TAGS)
    ocf = se.latest_annual_value(facts, OCF_TAGS)
    capex = se.latest_annual_value(facts, CAPEX_TAGS)
    revenue = se.latest_annual_value(facts, REVENUE_TAGS)
    revenue_prior = None
    if revenue:
        revenue_prior = se.prior_annual_value(facts, REVENUE_TAGS, before_end=revenue["end"])

    # Anchor "fiscal_period_end" on whichever core figure we actually got,
    # so the frontend can show the user how current this data really is.
    anchor = eps or equity or revenue
    out["fiscal_period_end"] = anchor["end"] if anchor else None

    out["raw"] = {
        "eps": eps["val"] if eps else None,
        "stockholders_equity": equity["val"] if equity else None,
        "shares_outstanding": shares["val"] if shares else None,
        "net_income": net_income["val"] if net_income else None,
        "total_liabilities": liabilities["val"] if liabilities else None,
        "dividend_per_share": dividend["val"] if dividend else None,
        "operating_cash_flow": ocf["val"] if ocf else None,
        "capex": capex["val"] if capex else None,
        "revenue": revenue["val"] if revenue else None,
        "revenue_prior_year": revenue_prior["val"] if revenue_prior else None,
    }

    price = current_price
    m = {}

    # P/E — lower is (traditionally) cheaper. None if EPS <= 0: a
    # negative-earnings P/E is not meaningful and showing e.g. "-14.2"
    # would read as a value opportunity when it's the opposite.
    m["pe_ratio"] = (price / eps["val"]) if (eps and eps["val"] > 0 and price) else None

    # P/B
    book_value_per_share = None
    if equity and shares and shares["val"] > 0:
        book_value_per_share = equity["val"] / shares["val"]
    m["pb_ratio"] = (price / book_value_per_share) if (book_value_per_share and book_value_per_share > 0 and price) else None

    # Dividend yield — 0 (not None) when the company simply pays no
    # dividend, since that's a real, known value, not missing data.
    m["dividend_yield"] = (dividend["val"] / price) if (dividend and price) else (0.0 if dividend is None else None)

    # Debt/Equity, using total liabilities as the numerator (a total
    # liabilities-to-equity ratio, not just interest-bearing debt — SEC
    # filings don't tag "total debt" uniformly enough to extract reliably
    # across companies, so this is the honest, consistently-available
    # proxy; labeled as such in the API response, not just called "D/E").
    m["liabilities_to_equity"] = (liabilities["val"] / equity["val"]) if (liabilities and equity and equity["val"] > 0) else None

    # ROE — undefined (None) for negative/zero equity, not a huge
    # misleading negative-of-a-negative number.
    m["roe"] = (net_income["val"] / equity["val"]) if (net_income and equity and equity["val"] > 0) else None

    # FCF yield = (operating cash flow - capex) / market cap
    market_cap = (price * shares["val"]) if (price and shares) else None
    if ocf and capex is not None and market_cap and market_cap > 0:
        fcf = ocf["val"] - capex["val"]
        m["fcf_yield"] = fcf / market_cap
    else:
        m["fcf_yield"] = None
    out["raw"]["market_cap"] = market_cap

    # Revenue growth YoY
    if revenue and revenue_prior and revenue_prior["val"] > 0:
        m["revenue_growth"] = (revenue["val"] - revenue_prior["val"]) / revenue_prior["val"]
    else:
        m["revenue_growth"] = None

    out["metrics"] = m
    return out
