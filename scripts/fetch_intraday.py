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
        return ["8058.T", "8306.T", "8766.T", "9432.T", "9434.T", "4502.T", "8593.T", "3861.T", "1605.T", "9984.T"]
    tickers = []
    with open(TICKERS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # #以降のコメントや余計な空白・タブを除去し、銘柄コード（例: 8058.T）のみを抽出
            ticker_code = line.split("#")[0].strip()
            if ticker_code:
                ticker = ticker_code.split()[0].strip()
                if ticker:
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
                print(f"[{ticker}] Attempt {attempt}: Empty intraday data. Retrying in 2s...")
                time.sleep(2)
                continue

            rows = []
            for dt_idx, row in hist.iterrows():
                # タイムゾーンをJST（日本時間）に変換
                if getattr(dt_idx, "tzinfo", None):
                    dt_jst = dt_idx.astimezone(JST)
                else:
                    dt_jst = JST.localize(dt_idx)
                dt_str = dt_jst.strftime("%Y-%m-%d %H:%M:%S")
                
                open_p = format_price(row.get("Open"))
                high_p = format_price(row.get("High"))
                low_p = format_price(row.get("Low"))
                close_p = format_price(row.get("Close"))
                vol = int(row.get("Volume", 0)) if not pd.isna(row.get("Volume", 0)) else 0

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
                # 重複日時の除去とソート
                df = df.drop_duplicates(subset=["datetime"], keep="last")
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
    print(f"Loaded {len(tickers)} tickers: {tickers}")

    success_count = 0
    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(2)

        df = fetch_intraday_ticker(ticker)
        if df is not None and not df.empty:
            csv_file = os.path.join(INTRADAY_DIR, f"{ticker}.csv")
            df.to_csv(csv_file, index=False)
            print(f"✅ [{i+1}/{len(tickers)}] {ticker}: Intraday 5m saved ({len(df)} rows) -> {csv_file}")
            success_count += 1
        else:
            print(f"❌ [{i+1}/{len(tickers)}] {ticker}: Failed to fetch intraday data.")

    print(f"🎉 Intraday fetch completed: {success_count}/{len(tickers)} tickers succeeded.")

if __name__ == "__main__":
    fetch_intraday()