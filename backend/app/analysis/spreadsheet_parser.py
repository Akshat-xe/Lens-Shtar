from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

_DATE_HINTS = re.compile(
    r"date|txn|value\s*date|posting|transaction\s*date|trans\s*date",
    re.I,
)
_AMT_HINTS = re.compile(r"^amount$|withdrawal|deposit|debit|credit|txn\s*amt|balance", re.I)
_DESC_HINTS = re.compile(r"description|narration|particulars|remarks|details|payee|merchant", re.I)


def _pick_column(columns: list[str], pattern: re.Pattern[str]) -> str | None:
    for c in columns:
        if pattern.search(str(c)):
            return c
    return None


def _rows_from_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    df = df.dropna(how="all")
    if df.empty:
        return []

    cols = [str(c).strip() for c in df.columns]
    df.columns = cols

    date_col = _pick_column(cols, _DATE_HINTS)
    desc_col = _pick_column(cols, _DESC_HINTS)

    debit_col = None
    credit_col = None
    amount_col = None
    for c in cols:
        cl = c.lower()
        if "debit" in cl and "amount" not in cl.replace("debit", ""):
            debit_col = c
        elif "credit" in cl:
            credit_col = c
        elif _AMT_HINTS.search(cl) and "balance" not in cl:
            amount_col = c

    if not date_col:
        # first column that parses as mostly dates
        for c in cols:
            try:
                s = pd.to_datetime(df[c], errors="coerce")
                if s.notna().sum() >= max(3, int(len(df) * 0.4)):
                    date_col = c
                    break
            except Exception:
                continue

    out: list[dict[str, Any]] = []
    if not date_col:
        return out

    if amount_col and (debit_col is None or credit_col is None):
        for _, row in df.iterrows():
            amt = row.get(amount_col)
            if amt is None or (isinstance(amt, float) and pd.isna(amt)):
                continue
            try:
                raw = float(str(amt).replace(",", ""))
            except ValueError:
                continue
            flow = "credit" if raw >= 0 else "debit"
            text = ""
            if desc_col:
                text = str(row.get(desc_col) or "")
            out.append(
                {
                    "date": row.get(date_col),
                    "amount": abs(raw),
                    "flow": flow,
                    "merchant_raw": text,
                    "description": text,
                }
            )
        return out

    if debit_col or credit_col:
        for _, row in df.iterrows():
            dr = row.get(debit_col) if debit_col else None
            cr = row.get(credit_col) if credit_col else None
            dval = 0.0
            cval = 0.0
            try:
                if dr is not None and str(dr).strip() and not (isinstance(dr, float) and pd.isna(dr)):
                    dval = float(str(dr).replace(",", ""))
            except ValueError:
                dval = 0.0
            try:
                if cr is not None and str(cr).strip() and not (isinstance(cr, float) and pd.isna(cr)):
                    cval = float(str(cr).replace(",", ""))
            except ValueError:
                cval = 0.0
            if dval <= 0 and cval <= 0:
                continue
            if dval > 0 and cval > 0:
                # Prefer debit if both (unusual)
                flow = "debit"
                amt = dval
            elif dval > 0:
                flow = "debit"
                amt = dval
            else:
                flow = "credit"
                amt = cval
            text = ""
            if desc_col:
                text = str(row.get(desc_col) or "")
            out.append(
                {
                    "date": row.get(date_col),
                    "amount": abs(amt),
                    "flow": flow,
                    "merchant_raw": text,
                    "description": text,
                }
            )
        return out

    return out


def parse_csv(content: bytes) -> list[dict[str, Any]]:
    last_err: Exception | None = None
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(io.BytesIO(content), encoding=enc)
            return _rows_from_dataframe(df)
        except Exception as e:
            last_err = e
            continue
    raise ValueError(f"Could not parse CSV: {last_err}")


def parse_excel(content: bytes, suffix: str) -> list[dict[str, Any]]:
    suf = suffix.lower()
    buf = io.BytesIO(content)
    try:
        if suf.endswith("xlsx"):
            df = pd.read_excel(buf, engine="openpyxl", sheet_name=0)
        else:
            df = pd.read_excel(buf, engine="xlrd", sheet_name=0)
    except Exception:
        buf.seek(0)
        df = pd.read_excel(buf, sheet_name=0)
    return _rows_from_dataframe(df)
