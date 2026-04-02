"""
=============================================================
 AJIO LEDGER DASHBOARD — BACKEND (ajio_ledger_backend.py)
=============================================================

HOW THE CSV IS STRUCTURED
--------------------------
Each row = one SAP financial posting. Key columns:

  DOCDATE     – DD.MM.YYYY  – when the posting was created
  DUEDATE     – DD.MM.YYYY  – when settlement is expected
  VENDORCODE  – which warehouse/fulfillment zone
  AMOUNT      – signed float (negative = debit to vendor)
  DD          – ALREADY_CLEARED | DUE_LATER | blank
  TYPE        – transaction sub-type (see below)
  UTRNO       – UTR number when payment was made
  CLEARINGDOC – internal clearing document reference

TRANSACTION TYPES (TYPE column)
---------------------------------
  IC Invoice Credit Note   -> SALES posted to vendor's account
                              AMOUNT is always POSITIVE
                              Net sale values Ajio credits to vendor.

  G4 Dropship vendor IV    -> CUSTOMER RETURNS debited from vendor
                              AMOUNT is always NEGATIVE
                              Vendor bears cost of returned items.

  ZK Cust.& vend.Postings  -> PLATFORM FEE / MARKETING / SCM DEDUCTIONS
                              AMOUNT is POSITIVE (Ajio charging vendor)
                              DT column = 'DN' (Debit Note)
                              TEXT = invoice ref like "INV_SCMF-01-11-I'26 NJ"

  KG GST Retention Doc     -> GST TDS RETENTION held by Ajio
                              AMOUNT is POSITIVE (charged to vendor)

  KP Outgoing Pymt - Auto  -> ACTUAL BANK TRANSFER to vendor
                              AMOUNT is POSITIVE (money sent to vendor)
                              DT column = 'PA'

  AB Account Clearing      -> INTERNAL NETTING ENTRIES (net to zero; ignore)

VENDOR CODE -> ZONE MAPPING
---------------------------
  DV00343684  ->  HS    (Hyderabad / South)
  DV00343685  ->  HSWB  (West Bengal)
  DV00343686  ->  HSHR  (Haryana)
  DV00343687  ->  HSMAH (Maharashtra)

KEY CALCULATIONS
----------------
  gross_sales        = SUM(AMOUNT)        where TYPE = 'IC Invoice Credit Note'
  gross_returns      = SUM(ABS(AMOUNT))   where TYPE = 'G4 Dropship vendor IV'
  net_revenue        = gross_sales - gross_returns
  zk_deductions      = SUM(ABS(AMOUNT))   where TYPE contains 'ZK'
  kg_deductions      = SUM(ABS(AMOUNT))   where TYPE contains 'KG'
  total_deductions   = zk_deductions + kg_deductions
  expected_payout    = net_revenue - total_deductions
  payments_made      = SUM(AMOUNT)        where TYPE = 'KP Outgoing Pymt - Auto'
  outstanding        = expected_payout - payments_made
  return_ratio_pct   = gross_returns / gross_sales * 100

NOTE ON HIGH RETURN RATIOS
---------------------------
Jan 2026 shows a 481% return ratio (returns of Rs 9.57M vs sales of Rs 1.99M).
This is expected: returns from Oct-Dec 2025 holiday season are processed/posted
in Jan. The ledger is a rolling account. The overall balance is near-zero
(-Rs 2,640) confirming the ledger is fully reconciled.
"""

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


VENDOR_CODE_MAP = {
    "DV00343684": "HS",
    "DV00343685": "HSWB",
    "DV00343686": "HSHR",
    "DV00343687": "HSMAH",
}

VENDOR_ZONE_LABEL = {
    "HS":    "Hyderabad / South",
    "HSWB":  "West Bengal",
    "HSHR":  "Haryana",
    "HSMAH": "Maharashtra",
}


def parse_amount(raw: str) -> float:
    return float(raw.replace(",", "").replace('"', "").strip()) if raw.strip() else 0.0


def parse_date(raw: str):
    try:
        return datetime.strptime(raw.strip(), "%d.%m.%Y")
    except ValueError:
        return None


def classify(row_type: str) -> str:
    t = row_type.strip()
    if t == "IC Invoice Credit Note":
        return "sales"
    if t == "G4 Dropship vendor IV":
        return "returns"
    if "ZK" in t:
        return "zk_deduction"
    if "KG" in t:
        return "kg_deduction"
    if "KP" in t:
        return "payment"
    return "other"


def parse_ledger(filepath: str) -> dict:
    months = defaultdict(lambda: {
        "gross_sales":     0.0,
        "gross_returns":   0.0,
        "zk_deductions":   0.0,
        "kg_deductions":   0.0,
        "payments_made":   0.0,
        "already_cleared": 0.0,
        "due_returns":     0.0,
        "vendors":         defaultdict(lambda: {"sales": 0.0, "returns": 0.0}),
        "transactions":    [],
    })

    with open(filepath, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            dt = parse_date(row.get("DOCDATE", ""))
            if not dt:
                continue

            mk     = dt.strftime("%Y-%m")
            amount = parse_amount(row.get("AMOUNT", "0"))
            kind   = classify(row.get("TYPE", ""))
            dd     = row.get("DD", "").strip()
            vs     = VENDOR_CODE_MAP.get(row.get("VENDORCODE", "").strip(), row.get("VENDORCODE", "").strip())
            m      = months[mk]

            if kind == "sales":
                m["gross_sales"] += amount
                m["vendors"][vs]["sales"] += amount
                if dd == "ALREADY_CLEARED":
                    m["already_cleared"] += amount

            elif kind == "returns":
                m["gross_returns"] += abs(amount)
                m["vendors"][vs]["returns"] += abs(amount)
                if dd == "DUE_LATER":
                    m["due_returns"] += abs(amount)

            elif kind == "zk_deduction":
                m["zk_deductions"] += abs(amount)

            elif kind == "kg_deduction":
                m["kg_deductions"] += abs(amount)

            elif kind == "payment":
                m["payments_made"] += amount

            m["transactions"].append({
                "date":      dt.strftime("%d %b %Y"),
                "reference": row.get("REFERENCE", ""),
                "vendor":    vs,
                "type":      kind,
                "raw_type":  row.get("TYPE", "").strip(),
                "amount":    amount,
                "status":    dd,
                "doc_no":    row.get("DOCNO", ""),
                "utr":       row.get("UTRNO", ""),
                "text":      row.get("TEXT", ""),
            })

    result_months = {}
    for mk, m in sorted(months.items()):
        gs  = m["gross_sales"]
        gr  = m["gross_returns"]
        net = gs - gr
        zk  = m["zk_deductions"]
        kg  = m["kg_deductions"]
        ded = zk + kg
        exp = net - ded
        kp  = m["payments_made"]
        rr  = (gr / gs * 100) if gs > 0 else 0.0

        vb = {
            vs: {
                "sales":   round(vals["sales"], 2),
                "returns": round(vals["returns"], 2),
                "net":     round(vals["sales"] - vals["returns"], 2),
                "zone":    VENDOR_ZONE_LABEL.get(vs, vs),
            }
            for vs, vals in m["vendors"].items()
        }

        result_months[mk] = {
            "label":             _month_label(mk),
            "gross_sales":       round(gs, 2),
            "gross_returns":     round(gr, 2),
            "net_revenue":       round(net, 2),
            "zk_deductions":     round(zk, 2),
            "kg_deductions":     round(kg, 2),
            "total_deductions":  round(ded, 2),
            "expected_payout":   round(exp, 2),
            "payments_made":     round(kp, 2),
            "outstanding":       round(exp - kp, 2),
            "already_cleared":   round(m["already_cleared"], 2),
            "due_returns":       round(m["due_returns"], 2),
            "return_ratio_pct":  round(rr, 2),
            "vendor_breakdown":  vb,
            "transaction_count": len(m["transactions"]),
            "transactions":      m["transactions"],
        }

    total_sales   = sum(v["gross_sales"]      for v in result_months.values())
    total_returns = sum(v["gross_returns"]    for v in result_months.values())
    total_net     = sum(v["net_revenue"]      for v in result_months.values())
    total_ded     = sum(v["total_deductions"] for v in result_months.values())
    total_payout  = sum(v["expected_payout"]  for v in result_months.values())
    total_kp      = sum(v["payments_made"]    for v in result_months.values())

    return {
        "months":  result_months,
        "summary": {
            "total_sales":         round(total_sales, 2),
            "total_returns":       round(total_returns, 2),
            "total_net":           round(total_net, 2),
            "total_deductions":    round(total_ded, 2),
            "total_payout":        round(total_payout, 2),
            "total_payments_made": round(total_kp, 2),
            "overall_balance":     round(total_payout - total_kp, 2),
            "months_sorted":       sorted(result_months.keys()),
        },
    }


def _month_label(key: str) -> str:
    return datetime.strptime(key, "%Y-%m").strftime("%B %Y")


def generate_summary_text(md: dict) -> str:
    rr_flag = " (NOTE: includes prior-season returns)" if md["return_ratio_pct"] > 100 else ""
    return (
        f"For {md['label']}, gross sales: Rs {md['gross_sales']:,.2f}; "
        f"returns: Rs {md['gross_returns']:,.2f} "
        f"(return ratio {md['return_ratio_pct']:.1f}%{rr_flag}); "
        f"net revenue: Rs {md['net_revenue']:,.2f}. "
        f"ZK Platform/SCM fee: Rs {md['zk_deductions']:,.2f}; "
        f"KG GST retention: Rs {md['kg_deductions']:,.2f}. "
        f"Expected payout: Rs {md['expected_payout']:,.2f}. "
        f"Payments already made: Rs {md['payments_made']:,.2f}. "
        f"Outstanding balance: Rs {md['outstanding']:,.2f}."
    )


def run_api_server(csv_path: str, port: int = 5000):
    """Optional: serve parsed data as REST API. Requires flask flask-cors."""
    try:
        from flask import Flask, jsonify
        from flask_cors import CORS
    except ImportError:
        print("pip install flask flask-cors")
        return

    app = Flask(__name__)
    CORS(app)
    data = parse_ledger(csv_path)

    @app.route("/api/ledger")
    def full_ledger():
        return jsonify({
            "summary": data["summary"],
            "months": {
                mk: {k: v for k, v in md.items() if k != "transactions"}
                for mk, md in data["months"].items()
            }
        })

    @app.route("/api/ledger/<month_key>")
    def month_detail(month_key):
        if month_key not in data["months"]:
            return jsonify({"error": "not found"}), 404
        md = data["months"][month_key]
        return jsonify({**{k: v for k, v in md.items() if k != "transactions"},
                        "summary_text": generate_summary_text(md)})

    @app.route("/api/ledger/<month_key>/transactions")
    def month_txns(month_key):
        if month_key not in data["months"]:
            return jsonify({"error": "not found"}), 404
        return jsonify(data["months"][month_key]["transactions"])

    print(f"\nAjio Ledger API at http://localhost:{port}")
    app.run(port=port, debug=True)


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "ledger.csv"
    serve = "--serve" in sys.argv

    if not Path(csv_path).exists():
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)

    if serve:
        run_api_server(csv_path)
    else:
        data = parse_ledger(csv_path)
        for mk in data["summary"]["months_sorted"]:
            md = data["months"][mk]
            print(f"\n{'='*54}\n  {md['label']}\n{'='*54}")
            print(f"  Gross Sales         Rs {md['gross_sales']:>14,.2f}")
            print(f"  Gross Returns       Rs {md['gross_returns']:>14,.2f}")
            print(f"  Net Revenue         Rs {md['net_revenue']:>14,.2f}")
            print(f"  ZK Platform Fee     Rs {md['zk_deductions']:>14,.2f}")
            print(f"  KG GST Retention    Rs {md['kg_deductions']:>14,.2f}")
            print(f"  Expected Payout     Rs {md['expected_payout']:>14,.2f}")
            print(f"  Payments Made (KP)  Rs {md['payments_made']:>14,.2f}")
            print(f"  Outstanding         Rs {md['outstanding']:>14,.2f}")
            print(f"  Return Ratio         {md['return_ratio_pct']:>13.1f}%")
            for vs, v in sorted(md["vendor_breakdown"].items()):
                print(f"    {vs:<6} Sales Rs {v['sales']:>10,.2f}  "
                      f"Returns Rs {v['returns']:>10,.2f}  Net Rs {v['net']:>10,.2f}")
            print(f"\n  {generate_summary_text(md)}")

        s = data["summary"]
        print(f"\n{'='*54}\n  OVERALL SUMMARY\n{'='*54}")
        for k, v in s.items():
            if k != "months_sorted":
                print(f"  {k:<26} Rs {v:>14,.2f}" if isinstance(v, float) else f"  {k}: {v}")

        out = Path(csv_path).with_suffix(".json")
        with open(out, "w") as jf:
            json.dump(data, jf, indent=2, default=str)
        print(f"\nJSON written -> {out}\n")


# ---------------------------------------------------------------------------
# In-memory entry point for Flask (added for ReconTool integration)
# ---------------------------------------------------------------------------

def parse_ledger_from_bytes(file_bytes: bytes) -> dict:
    """
    Parse an Ajio SAP ledger CSV from raw bytes.
    Wraps parse_ledger() without requiring a file on disk.
    """
    import io as _io
    import csv as _csv
    from collections import defaultdict
    from datetime import datetime

    months = defaultdict(lambda: {
        "gross_sales":     0.0,
        "gross_returns":   0.0,
        "zk_deductions":   0.0,
        "kg_deductions":   0.0,
        "payments_made":   0.0,
        "already_cleared": 0.0,
        "due_returns":     0.0,
        "vendors":         defaultdict(lambda: {"sales": 0.0, "returns": 0.0}),
        "transactions":    [],
    })

    text   = file_bytes.decode("utf-8-sig", errors="replace")
    reader = _csv.DictReader(_io.StringIO(text))

    for row in reader:
        dt = parse_date(row.get("DOCDATE", ""))
        if not dt:
            continue

        mk     = dt.strftime("%Y-%m")
        amount = parse_amount(row.get("AMOUNT", "0"))
        kind   = classify(row.get("TYPE", ""))
        dd     = row.get("DD", "").strip()
        vs     = VENDOR_CODE_MAP.get(row.get("VENDORCODE", "").strip(),
                                     row.get("VENDORCODE", "").strip())
        m      = months[mk]

        if kind == "sales":
            m["gross_sales"] += amount
            m["vendors"][vs]["sales"] += amount
            if dd == "ALREADY_CLEARED":
                m["already_cleared"] += amount
        elif kind == "returns":
            m["gross_returns"] += abs(amount)
            m["vendors"][vs]["returns"] += abs(amount)
            if dd == "DUE_LATER":
                m["due_returns"] += abs(amount)
        elif kind == "zk_deduction":
            m["zk_deductions"] += abs(amount)
        elif kind == "kg_deduction":
            m["kg_deductions"] += abs(amount)
        elif kind == "payment":
            m["payments_made"] += amount

        m["transactions"].append({
            "date":      dt.strftime("%d %b %Y"),
            "reference": row.get("REFERENCE", ""),
            "vendor":    vs,
            "type":      kind,
            "raw_type":  row.get("TYPE", "").strip(),
            "amount":    amount,
            "status":    dd,
            "doc_no":    row.get("DOCNO", ""),
            "utr":       row.get("UTRNO", ""),
            "text":      row.get("TEXT", ""),
        })

    result_months = {}
    for mk, m in sorted(months.items()):
        gs  = m["gross_sales"]
        gr  = m["gross_returns"]
        net = gs - gr
        zk  = m["zk_deductions"]
        kg  = m["kg_deductions"]
        ded = zk + kg
        exp = net - ded
        kp  = m["payments_made"]
        rr  = (gr / gs * 100) if gs > 0 else 0.0

        vb = {
            vs: {
                "sales":   round(vals["sales"], 2),
                "returns": round(vals["returns"], 2),
                "net":     round(vals["sales"] - vals["returns"], 2),
                "zone":    VENDOR_ZONE_LABEL.get(vs, vs),
            }
            for vs, vals in m["vendors"].items()
        }

        result_months[mk] = {
            "label":             _month_label(mk),
            "gross_sales":       round(gs, 2),
            "gross_returns":     round(gr, 2),
            "net_revenue":       round(net, 2),
            "zk_deductions":     round(zk, 2),
            "kg_deductions":     round(kg, 2),
            "total_deductions":  round(ded, 2),
            "expected_payout":   round(exp, 2),
            "payments_made":     round(kp, 2),
            "outstanding":       round(exp - kp, 2),
            "already_cleared":   round(m["already_cleared"], 2),
            "due_returns":       round(m["due_returns"], 2),
            "return_ratio_pct":  round(rr, 2),
            "vendor_breakdown":  vb,
            "transaction_count": len(m["transactions"]),
            "transactions":      m["transactions"],
        }

    total_sales   = sum(v["gross_sales"]      for v in result_months.values())
    total_returns = sum(v["gross_returns"]    for v in result_months.values())
    total_net     = sum(v["net_revenue"]      for v in result_months.values())
    total_ded     = sum(v["total_deductions"] for v in result_months.values())
    total_payout  = sum(v["expected_payout"]  for v in result_months.values())
    total_kp      = sum(v["payments_made"]    for v in result_months.values())

    return {
        "months": result_months,
        "summary": {
            "total_sales":         round(total_sales, 2),
            "total_returns":       round(total_returns, 2),
            "total_net":           round(total_net, 2),
            "total_deductions":    round(total_ded, 2),
            "total_payout":        round(total_payout, 2),
            "total_payments_made": round(total_kp, 2),
            "overall_balance":     round(total_payout - total_kp, 2),
            "months_sorted":       sorted(result_months.keys()),
        },
    }
