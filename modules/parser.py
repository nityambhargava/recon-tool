"""
modules/parser.py
TXT to TSV converter.
Accepts multiple .txt files or a single .zip containing .txt files.
Returns a zip of converted .tsv files as bytes.
"""

import io
import os
import zipfile
import pandas as pd


def convert_txt_to_tsv(files: list) -> tuple[bytes, int, list]:
    """
    files: list of (filename, file_bytes) tuples

    Returns:
        zip_bytes  : bytes of a zip containing all .tsv files
        count      : number of files successfully converted
        errors     : list of (filename, error_message) for failed files
    """
    txt_files = _extract_txt_files(files)

    converted = []
    errors    = []

    for fname, data in txt_files:
        try:
            df = _parse_txt(fname, data)
            tsv_name  = os.path.splitext(fname)[0] + ".tsv"
            tsv_bytes = df.to_csv(sep="\t", index=False).encode("utf-8")
            converted.append((tsv_name, tsv_bytes))
        except Exception as exc:
            errors.append((fname, str(exc)))

    zip_bytes = _build_zip(converted)
    return zip_bytes, len(converted), errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_txt_files(files: list) -> list:
    """
    If a single .zip is uploaded, extract .txt files from it.
    Otherwise return all uploaded .txt files directly.
    """
    txt_files = []

    if len(files) == 1 and files[0][0].lower().endswith(".zip"):
        fname, data = files[0]
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            for member in zf.namelist():
                if member.lower().endswith(".txt") and not member.endswith("/"):
                    base = os.path.basename(member)
                    txt_files.append((base, zf.read(member)))
    else:
        for fname, data in files:
            if fname.lower().endswith(".txt"):
                txt_files.append((fname, data))

    return txt_files


def _parse_txt(fname: str, data: bytes) -> pd.DataFrame:
    """
    Try to auto-detect delimiter. Falls back to one-column TSV.
    """
    try:
        df = pd.read_csv(
            io.BytesIO(data),
            sep=None,
            engine="python",
            dtype=str,
        )
        if df.shape[1] > 1:
            return df
    except Exception:
        pass

    # Fallback: treat each line as a single text column
    text = data.decode("utf-8", errors="ignore")
    lines = [ln.rstrip("\n") for ln in text.splitlines()]
    return pd.DataFrame({"text": lines})


def _build_zip(converted: list) -> bytes:
    """
    Pack all (tsv_name, tsv_bytes) into a zip and return as bytes.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for tsv_name, tsv_bytes in converted:
            zf.writestr(tsv_name, tsv_bytes)
    buf.seek(0)
    return buf.read()
