import os
import sys
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
            ticker = line.split()[0].strip()
            tickers.append(ticker)
    return tickers

def format_price(val):
    if pd.isna(val):
        return 0
    val_float = float(val)
    if val_float.is_integer():
        return int(val_float)
    return round(val_float, 2)

def fetch_intraday():
    now_jst = datetime.now(JST)
    print(f"[{now_jst.strftime('%Y-%m-%d %H:%M:%S')}] Starting fetch_intraday (Overwrite mode)")

    os.makedirs(INTRADAY_DIR, exist_ok=True)
    tickers = load_tickers()

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # 直近5日間の5分足（5m）を取得
            hist = stock.history(period="5d", interval="5m")
            if hist.empty:
                print(f"⚠️ No intraday data returned for {ticker}")
                continue

            # タイムゾーンをJSTに変換
            if hist.index.tz is None:
                hist.index = hist.index.tz_localize("UTC").tz_convert(JST)
            else:
                hist.index = hist.index.tz_convert(JST)

            rows = []
            for timestamp, row in hist.iterrows():
                dt_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                rows.append({
                    "datetime": dt_str,
                    "open": format_price(row["Open"]),
                    "high": format_price(row["High"]),
                    "low": format_price(row["Low"]),
                    "close": format_price(row["Close"]),
                    "volume": int(row["Volume"])
                })

            df = pd.DataFrame(rows)
            df = df.sort_values(by="datetime").reset_index(drop=True)
            
            # 銘柄別CSVに上書き保存 (mode='w')
            csv_path = os.path.join(INTRADAY_DIR, f"{ticker}.csv")
            df.to_csv(csv_path, index=False)
            print(f"✅ {ticker}: Overwrote {len(df)} intraday rows -> {csv_path}")

        except Exception as e:
            print(f"❌ Error fetching intraday for {ticker}: {e}", file=sys.stderr)

if __name__ == "__main__":
    fetch_intraday()