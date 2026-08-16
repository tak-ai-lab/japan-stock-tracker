import os
import sys
import time
from datetime import datetime
import pytz
import yfinance as yf
import pandas as pd

TICKERS_PATH = "config/tickers.txt"
INTRADAY_DIR = "data/intraday"
JST = pytz.timezone("Asia/Tokyo")

def load_tickers():
    if not os.path.exists(TICKERS_PATH):
        print(f"Error: {TICKERS_PATH} not found.")
        sys.exit(1)
    tickers = []
    with open(TICKERS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            ticker = line.strip()
            if ticker and not ticker.startswith("#"):
                tickers.append(ticker)
    return tickers

def format_price(val):
    if pd.isna(val) or val is None:
        return None
    val_float = float(val)
    if val_float <= 0:
        return None
    if val_float.is_integer():
        return int(val_float)
    return round(val_float, 2)

def fetch_intraday_ticker(ticker, max_retries=3):
    """直近5営業日分の5分足を取得"""
    for attempt in range(1, max_retries + 1):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d", interval="5m")
            if hist.empty:
                print(f"[{ticker}] Attempt {attempt}: Empty intraday data. Retrying...")
                time.sleep(2)
                continue

            rows = []
            for dt_idx, row in hist.iterrows():
                dt_jst = dt_idx.astimezone(JST) if dt_idx.tzinfo else dt_idx
                dt_str = dt_jst.strftime("%Y-%m-%d %H:%M:%S")
                
                open_p = format_price(row["Open"])
                high_p = format_price(row["High"])
                low_p = format_price(row["Low"])
                close_p = format_price(row["Close"])
                vol = int(row["Volume"]) if not pd.isna(row["Volume"]) else 0

                if close_p is not None and close_p > 0:
                    rows.append({
                        "datetime": dt_str,
                        "open": open_p,
                        "high": high_p,
                        "low": low_p,
                        "close": close_p,
                        "volume": vol
                    })

            if rows:
                df = pd.DataFrame(rows)
                df = df.sort_values(by="datetime").reset_index(drop=True)
                return df

        except Exception as e:
            print(f"[{ticker}] Attempt {attempt} error: {e}")
            time.sleep(2)

    return None

def fetch_intraday():
    now_jst = datetime.now(JST)
    print(f"[{now_jst.strftime('%Y-%m-%d %H:%M:%S')}] Starting intraday fetch (5m)...")

    os.makedirs(INTRADAY_DIR, exist_ok=True)
    tickers = load_tickers()

    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(2)

        df = fetch_intraday_ticker(ticker)
        if df is not None and not df.empty:
            csv_file = os.path.join(INTRADAY_DIR, f"{ticker}.csv")
            df.to_csv(csv_file, index=False)
            print(f"✅ {ticker}: Intraday 5m saved ({len(df)} rows) -> {csv_file}")
        else:
            print(f"❌ {ticker}: Failed to fetch intraday data.")

if __name__ == "__main__":
    fetch_intraday()