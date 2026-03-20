"""
ingestion/loader.py
Reads uploaded CSV or Excel reconciliation report into a clean DataFrame.
All processing happens in-memory — no files saved to disk.
"""

import io
import pandas as pd
from pathlib import Path

REQUIRED_COLUMNS = [
    "Reconciliation Order Status",
    "Return Type",
    "UC Selling Price",
    "Expected Net Settlement",
    "Actual Net Settlement",
    "Channel Code",
    "Channel Created Time",
]

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def load_from_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Please upload CSV or Excel.")

    if ext == ".csv":
        df = pd.read_csv(io.BytesIO(file_bytes))
    else:
        df = pd.read_excel(io.BytesIO(file_bytes))

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    return _clean(df)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Channel Created Time"] = pd.to_datetime(df["Channel Created Time"], errors="coerce")
    for col in ["UC Selling Price", "Expected Net Settlement", "Actual Net Settlement"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["Difference"]    = df["Expected Net Settlement"] - df["Actual Net Settlement"]
    df["Channel Group"] = df["Channel Code"].apply(_map_channel)
    return df


def _map_channel(code: str) -> str:
    c = str(code).upper()
    if "MYNTRA"   in c: return "Myntra"
    if "AMAZON"   in c: return "Amazon"
    if "FLIPKART" in c: return "Flipkart"
    if "MEESHO"   in c: return "Meesho"
    if "AJIO"     in c: return "Ajio"
    return "Other"


def get_date_range(df: pd.DataFrame) -> dict:
    valid = df["Channel Created Time"].dropna()
    if valid.empty:
        return {"min": "N/A", "max": "N/A"}
    return {"min": valid.min().strftime("%d %b %Y"),
            "max": valid.max().strftime("%d %b %Y")}
