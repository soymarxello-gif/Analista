\
from __future__ import annotations

import math
import pandas as pd


def _num(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _clip01(x: float) -> float:
    return max(0.0, min(float(x), 1.0))


def _score_growth(x):
    if x is None:
        return 0.5
    # revenue/earnings growth usually arrives as decimal, e.g. 0.15 = 15%.
    return _clip01((x + 0.05) / 0.35)


def _score_margin(x):
    if x is None:
        return 0.5
    return _clip01((x + 0.02) / 0.30)


def _score_debt_to_equity(x):
    if x is None:
        return 0.5
    # yfinance debtToEquity usually uses percentage units, e.g. 100 = 100%.
    if x <= 50:
        return 1.0
    if x <= 100:
        return 0.75
    if x <= 200:
        return 0.45
    return 0.20


def _score_roe(x):
    if x is None:
        return 0.5
    return _clip01((x + 0.02) / 0.25)


def score_fundamentals(meta_row, config):
    """
    Tactical fundamentals score for swing trading.
    It is not a full valuation model; it mainly avoids weak quality and earnings event risk.
    """
    revenue_growth = _num(meta_row.get("revenue_growth"))
    earnings_growth = _num(meta_row.get("earnings_growth") or meta_row.get("earnings_quarterly_growth"))
    operating_margin = _num(meta_row.get("operating_margins"))
    profit_margin = _num(meta_row.get("profit_margins"))
    debt_to_equity = _num(meta_row.get("debt_to_equity"))
    roe = _num(meta_row.get("return_on_equity"))
    days_to_earnings = _num(meta_row.get("days_to_earnings"))

    growth_score = 0.55 * _score_growth(revenue_growth) + 0.45 * _score_growth(earnings_growth)
    margin_score = 0.55 * _score_margin(operating_margin) + 0.45 * _score_margin(profit_margin)
    balance_score = _score_debt_to_equity(debt_to_equity)
    profitability_score = _score_roe(roe)

    score = (
        0.35 * growth_score +
        0.25 * margin_score +
        0.20 * balance_score +
        0.20 * profitability_score
    )

    warning = meta_row.get("fundamental_warning") or ""
    veto_earnings = False
    earnings_penalty = False

    erisk = config.get("fundamentals", {}).get("earnings_risk", {})
    veto_days = erisk.get("veto_if_days_to_earnings_lte", 3)
    penalty_days = erisk.get("penalize_if_days_to_earnings_lte", 7)

    if days_to_earnings is not None:
        if days_to_earnings >= 0 and days_to_earnings <= veto_days:
            veto_earnings = True
            score *= 0.20
            warning = (warning + "; " if warning else "") + f"earnings en {int(days_to_earnings)} días: veto"
        elif days_to_earnings >= 0 and days_to_earnings <= penalty_days:
            earnings_penalty = True
            score *= 0.65
            warning = (warning + "; " if warning else "") + f"earnings en {int(days_to_earnings)} días: penalización"

    return {
        "fundamental_score": round(_clip01(score), 4),
        "earnings_date": meta_row.get("earnings_date"),
        "days_to_earnings": int(days_to_earnings) if days_to_earnings is not None else None,
        "earnings_veto": veto_earnings,
        "earnings_penalty": earnings_penalty,
        "revenue_growth": revenue_growth,
        "earnings_growth": earnings_growth,
        "operating_margins": operating_margin,
        "profit_margins": profit_margin,
        "debt_to_equity": debt_to_equity,
        "return_on_equity": roe,
        "fundamental_warning": warning,
    }
