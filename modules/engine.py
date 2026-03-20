"""
modules/engine.py  -  All reconciliation computation logic.

Tracked statuses (% denominator):
    AWAITING_PAYMENT, PAYMENT_DISPUTED, PAYMENT_OVERDUE,
    RECONCILED, RECONCILED_BY_DELTA

Journey split via Return Type column:
    Forward -> NONE
    Return  -> CIR, RTO

Overpaid / Underpaid (disputed orders only):
    Difference = Expected Net Settlement - Actual Net Settlement
    Forward : positive -> overpaid  | negative -> underpaid
    Return  : VICE VERSA

Actionable threshold: Disputed > 25% OR Overdue > 25% -> warn
"""

import pandas as pd

TRACKED = [
    "AWAITING_PAYMENT",
    "PAYMENT_DISPUTED",
    "PAYMENT_OVERDUE",
    "RECONCILED",
    "RECONCILED_BY_DELTA",
]

CHANNELS  = ["All Channels", "Myntra", "Amazon", "Flipkart", "Meesho", "Ajio"]
THRESHOLD = 25.0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compute_dashboard(df: pd.DataFrame, date_range: dict) -> dict:
    return {
        "dateMin":  date_range["min"],
        "dateMax":  date_range["max"],
        "channels": {
            ch: _channel(
                df if ch == "All Channels" else df[df["Channel Group"] == ch]
            )
            for ch in CHANNELS
        },
    }


# ---------------------------------------------------------------------------
# Per-channel
# ---------------------------------------------------------------------------

def _channel(df: pd.DataFrame) -> dict:
    n = len(df[df["Reconciliation Order Status"].isin(TRACKED)])
    return {
        "totalOrders":  len(df),
        "trackedTotal": n,
        "overall":  _overall(df, n),
        "forward":  _journey(df, ["NONE"],       n, is_return=False),
        "return":   _journey(df, ["CIR", "RTO"], n, is_return=True),
    }


def _overall(df, n):
    dis = df[df["Reconciliation Order Status"] == "PAYMENT_DISPUTED"]
    return {
        "Awaiting":   _block(df, ["AWAITING_PAYMENT"],                  n),
        "Disputed":   _block(
                          df, ["PAYMENT_DISPUTED"], n,
                          op=_pos(dis["Difference"]),
                          up=_negabs(dis["Difference"]),
                      ),
        "Overdue":    _block(df, ["PAYMENT_OVERDUE"],                   n),
        "Reconciled": _block(df, ["RECONCILED", "RECONCILED_BY_DELTA"], n),
    }


def _journey(df, return_types, n, is_return):
    seg = df[df["Return Type"].isin(return_types)]
    dis = seg[seg["Reconciliation Order Status"] == "PAYMENT_DISPUTED"]

    if is_return:
        op = _negabs(dis["Difference"])
        up = _pos(dis["Difference"])
    else:
        op = _pos(dis["Difference"])
        up = _negabs(dis["Difference"])

    return {
        "Awaiting":   _block(seg, ["AWAITING_PAYMENT"],                  n),
        "Disputed":   _block(seg, ["PAYMENT_DISPUTED"],                  n, op=op, up=up),
        "Overdue":    _block(seg, ["PAYMENT_OVERDUE"],                   n),
        "Reconciled": _block(seg, ["RECONCILED", "RECONCILED_BY_DELTA"], n),
    }


def _block(df, statuses, denom, op=None, up=None):
    g   = df[df["Reconciliation Order Status"].isin(statuses)]
    cnt = len(g)
    b   = {
        "count": cnt,
        "ucSum": round(float(g["UC Selling Price"].sum()), 2),
        "pct":   round(cnt / denom * 100, 1) if denom else 0.0,
    }
    if op is not None:
        b["overpaid"]  = round(op, 2)
        b["underpaid"] = round(up, 2)
    return b


def _pos(s):
    return float(s[s > 0].sum())


def _negabs(s):
    return float(s[s < 0].abs().sum())


# ---------------------------------------------------------------------------
# Actionables
# ---------------------------------------------------------------------------

def build_actionables(overall: dict, channel: str) -> list:
    di  = overall["Disputed"]["pct"]
    ovp = overall["Overdue"]["pct"]
    items = []

    if di > THRESHOLD:
        items.append({
            "type":  "warn",
            "icon":  "\u26a0",
            "title": f"Disputed at {di}% \u2014 Action Required",
            "body": (
                f"Raise disputes with <b>{channel}</b> for "
                f"<b>{overall['Disputed']['count']} orders</b> "
                f"({_inr(overall['Disputed']['ucSum'])}). "
                f"Recover underpaid <b>{_inr(overall['Disputed']['underpaid'])}</b> first."
            ),
        })

    if ovp > THRESHOLD:
        items.append({
            "type":  "warn",
            "icon":  "\u23f0",
            "title": f"Overdue at {ovp}% \u2014 Escalate Now",
            "body": (
                f"<b>{overall['Overdue']['count']} overdue orders</b> worth "
                f"<b>{_inr(overall['Overdue']['ucSum'])}</b> \u2014 "
                f"escalate to the finance team immediately."
            ),
        })

    if overall["Disputed"]["overpaid"] > 0:
        items.append({
            "type":  "ok",
            "icon":  "\u2b06",
            "title": f"Surplus Receipt \u2014 Favourable",
            "body": (
                f"<b>{channel}</b> has paid "
                f"<b>{_inr(overall['Disputed']['overpaid'])}</b> "
                f"more than expected across disputed orders. "
                f"This is a net gain \u2014 no action needed, but verify "
                f"it reconciles correctly in your books."
            ),
        })

    if overall["Disputed"]["underpaid"] > 0:
        items.append({
            "type":  "info",
            "icon":  "\u2b07",
            "title": "Underpaid Shortfall Detected",
            "body": (
                f"<b>{_inr(overall['Disputed']['underpaid'])}</b> underpaid "
                f"across disputed orders. File a payment shortfall claim "
                f"with <b>{channel}</b>."
            ),
        })

    if overall["Awaiting"]["count"] > 0:
        items.append({
            "type":  "info",
            "icon":  "\u23f3",
            "title": f"Awaiting Payment \u2014 Follow Up",
            "body": (
                f"<b>{overall['Awaiting']['count']} orders</b> worth "
                f"<b>{_inr(overall['Awaiting']['ucSum'])}</b> are pending. "
                f"Follow up with <b>{channel}</b> on expected settlement dates."
            ),
        })

    if di <= THRESHOLD and ovp <= THRESHOLD:
        items.append({
            "type":  "ok",
            "icon":  "\u2713",
            "title": "Thresholds Within Limit",
            "body": (
                f"Disputed (<b>{di}%</b>) and Overdue (<b>{ovp}%</b>) "
                f"are both within the 25% threshold. "
                f"No critical escalation required."
            ),
        })

    if overall["Reconciled"]["pct"] >= 30:
        items.append({
            "type":  "ok",
            "icon":  "\u2713",
            "title": "Reconciliation Rate Healthy",
            "body": (
                f"<b>{overall['Reconciled']['pct']}%</b> reconciliation rate "
                f"\u2014 <b>{overall['Reconciled']['count']} orders</b> "
                f"settled successfully."
            ),
        })

    return items


def _inr(n: float) -> str:
    return f"\u20b9{abs(n):,.2f}"
