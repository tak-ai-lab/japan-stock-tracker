import os
import sys
from datetime import datetime
import pytz
import yfinance as yf
import pandas as pd

TICKERS_PATH = "config/tickers.txt"
DAILY_DIR = "data/daily"
SUMMARY_PATH = "data/latest_summary.csv"
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
    # 整数で表現可能な場合は整数、小数点がある場合は第1位〜2位まで丸め
    val_float = float(val)
    if val_float.is_integer():
        return int(val_float)
    return round(val_float, 2)

def fetch_daily():
    now_jst = datetime.now(JST)
    fetched_at_str = now_jst.strftime("%Y-%m-%d %H:%M:%S")
    tickers = load_tickers()
    print(f"[{fetched_at_str}] Starting fetch_daily for {len(tickers)} tickers: {tickers}")

    os.makedirs(DAILY_DIR, exist_ok=True)
    summary_rows = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # 直近5日分の日足を取得
            hist = stock.history(period="5d", interval="1d")
            if hist.empty:
                print(f"⚠️ Warning: No history returned for {ticker}")
                continue

            last_row = hist.iloc[-1]
            trade_date = hist.index[-1].strftime("%Y-%m-%d")

            csv_file = os.path.join(DAILY_DIR, f"{ticker}.csv")
            
            # 既存ファイルの読み込みまたは初期化
            if os.path.exists(csv_file):
                df = pd.read_csv(csv_file)
            else:
                df = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "adj_close"])

            # 重複チェック（同一dateがすでに存在するか）
            if not df.empty and trade_date in df["date"].values:
                print(f"⏩ {ticker}: {trade_date} is already up to date. Skipping.")
            else:
                new_row = {
                    "date": trade_date,
                    "open": format_price(last_row["Open"]),
                    "high": format_price(last_row["High"]),
                    "low": format_price(last_row["Low"]),
                    "close": format_price(last_row["Close"]),
                    "volume": int(last_row["Volume"]),
                    "adj_close": format_price(last_row.get("Adj Close", last_row["Close"]))
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df = df.sort_values(by="date").reset_index(drop=True)
                df.to_csv(csv_file, index=False)
                print(f"✅ {ticker}: Appended {trade_date} Close={new_row['close']} Vol={new_row['volume']}")

            # 全体サマリー用の行を作成
            prev_close = float(hist.iloc[-2]["Close"]) if len(hist) >= 2 else float(last_row["Close"])
            current_close = float(last_row["Close"])
            change = current_close - prev_close
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0

            summary_rows.append({
                "ticker": ticker,
                "date": trade_date,
                "close": format_price(current_close),
                "change": format_price(change),
                "change_pct": round(change_pct, 2),
                "volume": int(last_row["Volume"])
            })

        except Exception as e:
            print(f"❌ Error fetching daily for {ticker}: {e}", file=sys.stderr)

    # 全体サマリーCSVの更新（わずか10行の超軽量ファイル）
    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_csv(SUMMARY_PATH, index=False)
        print(f"📊 Updated daily summary: {SUMMARY_PATH}")

if __name__ == "__main__":
    fetch_daily()