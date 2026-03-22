#!/usr/bin/env python3
"""
stock_analysis.py

End‑to‑end pipeline that:
1. Accepts a list of Indian stock symbols.
2. Retrieves OHLCV data (and optional MF data) from external APIs.
3. Cleans & validates the data.
4. Computes technical indicators & fundamental ratios.
5. Sends the enriched data to an AI analysis endpoint.
6. Writes per‑ticker JSON output and a human‑readable markdown report.

Usage:
    python stock_analysis.py --symbols RELIANCE,TCS,INFY --output-dir ./out
    python stock_analysis.py -s RELIANCE,TCS -o ./out --include-mf
"""
import argparse
import base64
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ta import add_all_ta_features
from ta.utils import dropna as ta_dropna
from dotenv import load_dotenv
from tabulate import tabulate
import matplotlib.pyplot as plt
import io

# --------------------------------------------------------------------------- #
# Configuration & Logging
# --------------------------------------------------------------------------- #
# load_dotenv()  # loads .env into os.environ

# STOCK_API_KEY = (Path(__file__).parent / ".env").exists() and \
    # __import__("os").environ.get("STOCK_API_KEY")
# AI_API_TOKEN = __import__("os").environ.get("AI_API_TOKEN")

AI_API_TOKEN = "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"
# Placeholder URLs – replace with real endpoints
STOCK_PRICE_URL = "https://api.example.com/v1/quotes"
MF_PRICE_URL = "https://api.mfapi.in/mf/"
AI_ANALYSIS_URL = "https://integrate.api.nvidia.com/v1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Helper Functions
# --------------------------------------------------------------------------- #
def validate_symbols(symbols: List[str]) -> List[str]:
    """Upper‑case symbols, strip whitespace, remove empties."""
    cleaned = [s.strip().upper() for s in symbols if s.strip()]
    if not cleaned:
        raise ValueError("At least one ticker symbol must be provided.")
    return cleaned


def get_http_session() -> requests.Session:
    """Return a Session with retry strategy and default timeout."""
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.headers.update({"User-Agent": "stock-analysis/1.0"})
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_stock_data(session: requests.Session, symbol: str) -> pd.DataFrame:
    """
    Pull raw OHLCV JSON for a single ticker and return a DataFrame.
    Expected JSON shape:
        {
            "symbol": "...",
            "timestamp": "...",   # ISO 8601
            "open": ...,
            "high": ...,
            "low": ...,
            "close": ...,
            "volume": ...
        }
    """
    params = {"symbol": symbol}
    headers = {"X-API-KEY": STOCK_API_KEY}
    try:
        resp = session.get(STOCK_PRICE_URL, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error(f"Failed to fetch data for {symbol}: {exc}")
        raise

    # Convert single record to DataFrame; API could return a list – handle both.
    if isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame([data])

    # Normalize column names
    df.rename(columns=lambda x: x.strip().lower(), inplace=True)
    return df


def fetch_mf_data(session: requests.Session, symbol: str) -> pd.DataFrame:
    """Optional mutual‑fund data fetch – very similar to fetch_stock_data."""
    params = {"symbol": symbol}
    # headers = {"X-API-KEY": STOCK_API_KEY}
    resp = session.get(MF_PRICE_URL, params=params,  timeout=10) #headers=headers,
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame([data])
    df.rename(columns=lambda x: x.strip().lower(), inplace=True)
    return df


def clean_ohlcv_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Parse dates, enforce numeric types, forward‑fill missing prices."""
    if "timestamp" not in df.columns:
        raise KeyError("Expected column 'timestamp' not found.")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)

    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Forward fill price columns, drop rows where all OHLCV are NaN
    df[numeric_cols] = df[numeric_cols].ffill()
    df.dropna(subset=numeric_cols, how="all", inplace=True)
    return df.sort_index()


def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a suite of technical indicators using `ta`. Returns a DataFrame that
    contains the original OHLCV plus the new columns.
    """
    df_clean = ta_dropna(df)  # remove rows with NaN needed for indicators
    df_ta = add_all_ta_features(
        df_clean,
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        fillna=True
    )
    # Keep a subset for brevity
    indicator_cols = [
        "trend_sma_fast", "trend_ema_fast",
        "momentum_rsi", "volume_obv",
        "trend_macd", "trend_macd_signal"
    ]
    return df_ta[indicator_cols]


def compute_fundamental_ratios(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Derive simple fundamentals; placeholder implementation.
    Real data may need EPS, Book Value, etc. from a separate endpoint.
    """
    # Example: use latest close price as "price"
    latest = df.iloc[-1]
    price = latest.get("close")
    eps = latest.get("eps")  # may be missing
    book_val = latest.get("book_value")
    fundamentals = {
        "price": price,
        "eps": eps,
        "book_value": book_val,
        "pe_ratio": price / eps if eps else None,
        "pb_ratio": price / book_val if book_val else None,
    }
    return fundamentals


def prepare_ai_payload(
    ticker: str,
    ohlcv_df: pd.DataFrame,
    fundamentals: Dict[str, Any],
    technical: pd.DataFrame
) -> Dict[str, Any]:
    """Serialise data into JSON‑compatible structures for the AI endpoint."""
    # Convert OHLCV to list of dicts (ISO timestamp string)
    ohlcv_records = [
        {
            "timestamp": ts.isoformat(),
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
        }
        for ts, row in ohlcv_df.iterrows()
    ]

    # Technical – only latest values for brevity
    latest_tech = technical.iloc[-1].to_dict() if not technical.empty else {}

    payload = {
        "ticker": ticker,
        "ohlcv": ohlcv_records,
        "fundamentals": fundamentals,
        "technical": latest_tech,
    }
    return payload


def call_ai_analysis(session: requests.Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST payload to AI analysis endpoint and return the parsed JSON."""
    headers = {
        "Authorization": f"Bearer {AI_API_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        resp = session.post(
            AI_ANALYSIS_URL,
            json=payload,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error(f"AI analysis failed for {payload.get('ticker')}: {exc}")
        raise


def dataframe_to_csv_string(df: pd.DataFrame) -> str:
    """Return CSV representation of a DataFrame (index included)."""
    return df.to_csv(index=True)


def plot_price_series(df: pd.DataFrame, ticker: str) -> str:
    """
    Generate a line chart of close prices, encode as base64 PNG.
    Returns the data URI string suitable for markdown embedding.
    """
    plt.figure(figsize=(8, 4))
    plt.plot(df.index, df["close"], label="Close")
    plt.title(f"{ticker} Close Price")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    return f"data:image/png;base64,{b64}"


def generate_markdown_report(
    ticker: str,
    ohlcv_df: pd.DataFrame,
    fundamentals: Dict[str, Any],
    technical: pd.DataFrame,
    ai_result: Dict[str, Any],
    include_plots: bool = True
) -> str:
    """Compose markdown report."""
    lines = [f"# {ticker} – Stock Analysis\n"]

    # AI analysis block
    analysis = ai_result.get("analysis", "No analysis returned.")
    score = ai_result.get("score")
    lines.append("## AI Generated Summary\n")
    lines.append(f"{analysis}\n")
    if score is not None:
        lines.append(f"*Model confidence score*: {score:.2%}\n")

    # Fundamental table
    lines.append("\n## Fundamental Snapshot\n")
    fund_table = tabulate(fundamentals.items(), tablefmt="github", headers=["Metric", "Value"])
    lines.append(fund_table + "\n")

    # Technical indicators (latest row)
    lines.append("\n## Latest Technical Indicators\n")
    if not technical.empty:
        tech_latest = technical.iloc[-1].to_dict()
        tech_table = tabulate(tech_latest.items(), tablefmt="github", headers=["Indicator", "Value"])
        lines.append(tech_table + "\n")
    else:
        lines.append("_No technical indicators computed._\n")

    # Price plot
    if include_plots:
        lines.append("\n## Price Chart\n")
        img_uri = plot_price_series(ohlcv_df, ticker)
        lines.append(f"![Close price]({img_uri})\n")

    # Full OHLCV CSV (as code block)
    lines.append("\n## OHLCV Data (CSV)\n")
    csv_str = dataframe_to_csv_string(ohlcv_df)
    lines.append("```csv\n")
    lines.append(csv_str)
    lines.append("\n```\n")

    return "\n".join(lines)


def save_json(data: Dict[str, Any], path: Path) -> None:
    """Write JSON with indentation."""
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def ensure_output_dir(dir_path: Path) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


# --------------------------------------------------------------------------- #
# Main orchestration
# --------------------------------------------------------------------------- #
def process_symbol(symbol: str, session: requests.Session, include_mf: bool,
                  compute_tech: bool) -> Dict[str, Any]:
    """Fetch, clean, enrich, analyse and return the aggregated dict for one ticker."""
    # 1) raw market data
    raw_df = fetch_stock_data(session, symbol)

    # 2) optional MF data – not integrated further in this demo
    if include_mf:
        try:
            mf_df = fetch_mf_data(session, symbol)
            logger.info(f"Fetched MF data for {symbol} (rows: {len(mf_df)})")
        except Exception as exc:
            logger.warning(f"MF fetch failed for {symbol}: {exc}")

    # 3) cleaning
    ohlcv_df = clean_ohlcv_dataframe(raw_df)

    # 4) fundamentals
    fundamentals = compute_fundamental_ratios(ohlcv_df)

    # 5) technical indicators
    technical_df = pd.DataFrame()
    if compute_tech:
        technical_df = compute_technical_indicators(ohlcv_df)

    # 6) prepare AI payload
    payload = prepare_ai_payload(symbol, ohlcv_df, fundamentals, technical_df)

    # 7) AI analysis
    ai_result = call_ai_analysis(session, payload)

    # 8) Assemble final dict
    result = {
        "ticker": symbol,
        "ohlcv": ohlcv_df.reset_index().to_dict(orient="records"),
        "fundamentals": fundamentals,
        "technical": technical_df.reset_index().to_dict(orient="records") if not technical_df.empty else [],
        "ai_analysis": ai_result,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock analysis pipeline")
    parser.add_argument(
        "-s", "--symbols",
        required=True,
        help="Comma‑separated list of ticker symbols (e.g., RELIANCE,TCS,INFY)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="output",
        help="Directory where JSON & markdown files will be written"
    )
    parser.add_argument(
        "--include-mf",
        action="store_true",
        help="Fetch Mutual‑Fund data in addition to equity quotes"
    )
    parser.add_argument(
        "--no-technical",
        action="store_true",
        help="Skip technical indicator computation"
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Do not embed price plots in the markdown report"
    )
    args = parser.parse_args()

    symbols = validate_symbols(args.symbols.split(","))
    output_dir = ensure_output_dir(Path(args.output_dir))

    session = get_http_session()

    for sym in symbols:
        logger.info(f"Processing ticker: {sym}")
        try:
            aggregated = process_symbol(
                sym,
                session,
                include_mf=args.include_mf,
                compute_tech=not args.no_technical,
            )
        except Exception as exc:
            logger.error(f"Failed to process {sym}: {exc}")
            continue

        # Write JSON
        json_path = output_dir / f"{sym}.json"
        save_json(aggregated, json_path)
        logger.info(f"Wrote JSON to {json_path}")

        # Write markdown
        md_content = generate_markdown_report(
            ticker=sym,
            ohlcv_df=pd.DataFrame(aggregated["ohlcv"]).set_index("timestamp"),
            fundamentals=aggregated["fundamentals"],
            technical=pd.DataFrame(aggregated["technical"]).set_index("timestamp")
                        if aggregated["technical"] else pd.DataFrame(),
            ai_result=aggregated["ai_analysis"],
            include_plots=not args.no_plots,
        )
        md_path = output_dir / f"{sym}_report.md"
        md_path.write_text(md_content, encoding="utf-8")
        logger.info(f"Wrote markdown report to {md_path}")

    logger.info("All done.")


if __name__ == "__main__":
    main()
