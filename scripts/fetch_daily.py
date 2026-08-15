import os
import sys
import time
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
        return None
    val_float = float(val)
    if val_float <= 0:
        return None
    if val_float.is_integer():
        return int(val_float)
    return round(val_float, 2)

def fetch_single_ticker_with_retry(ticker, max_retries=3):
    """通信ディレイとリトライを備えた安全な取得関数"""
    for attempt in range(1, max_retries + 1):
        try:
            stock = yf.Ticker(ticker)
            # 直近5営業日分を取得
            hist = stock.history(period="5d", interval="1d")
            
            if hist.empty:
                print(f"[{ticker}] Attempt {attempt}: Empty data returned. Retrying...")
                time.sleep(2)
                continue

            last_row = hist.iloc[-1]
            trade_date = hist.index[-1].strftime("%Y-%m-%d")
            
            open_p = format_price(last_row["Open"])
            high_p = format_price(last_row["High"])
            low_p = format_price(last_row["Low"])
            close_p = format_price(last_row["Close"])
            vol = int(last_row["Volume"]) if not pd.isna(last_row["Volume"]) else 0

            # 🛡️ 四本値のいずれかが取得できていない（NaNや0）の場合はリトライ
            if None in (open_p, high_p, low_p, close_p) or close_p <= 0:
                print(f"[{ticker}] Attempt {attempt}: Price was invalid (Open={open_p}, Close={close_p}). Retrying...")
                time.sleep(2)
                continue

            # 前営業日の終値（前日比計算用）
            prev_close = None
            if len(hist) >= 2:
                prev_close = format_price(hist.iloc[-2]["Close"])

            return {
                "ticker": ticker,
                "date": trade_date,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol,
                "adj_close": format_price(last_row.get("Adj Close", close_p)) or close_p,
                "prev_close": prev_close
            }

        except Exception as e:
            print(f"[{ticker}] Attempt {attempt} failed with error: {e}")
            time.sleep(2)

    return None

def fetch_daily():
    now_jst = datetime.now(JST)
    today_str = now_jst.strftime("%Y-%m-%d")
    print(f"[{now_jst.strftime('%Y-%m-%d %H:%M:%S')}] Starting fetch_daily for {today_str}")

    os.makedirs(DAILY_DIR, exist_ok=True)
    tickers = load_tickers()
    summary_rows = []

    for i, ticker in enumerate(tickers):
        # 🛡️ Yahoo Financeの通信負荷軽減のため、銘柄間に2秒のディレイを挿入
        if i > 0:
            time.sleep(2)

        data = fetch_single_ticker_with_retry(ticker)
        
        if not data:
            print(f"❌ {ticker}: Failed to fetch valid prices after retries. Skipping.")
            continue

        trade_date = data["date"]
        close_val = data["close"]
        csv_file = os.path.join(DAILY_DIR, f"{ticker}.csv")

        # 既存CSVの読み込み
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
        else:
            df = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "adj_close"])

        # 既存ファイル内の「過去に混入した不正な0行」を自動クリーニング
        if not df.empty and "close" in df.columns:
            df = df[df["close"] > 0]

        # 同一日付がすでに記録済みかチェック
        if not df.empty and trade_date in df["date"].values:
            print(f"⏩ {ticker}: {trade_date} is already recorded (Close={close_val}). Skipping write.")
        else:
            new_row = {
                "date": trade_date,
                "open": data["open"],
                "high": data["high"],
                "low": data["low"],
                "close": close_val,
                "volume": data["volume"],
                "adj_close": data["adj_close"]
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df = df.sort_values(by="date").reset_index(drop=True)
            df.to_csv(csv_file, index=False)
            print(f"✅ {ticker}: Successfully saved {trade_date} -> Close={close_val}, Vol={data['volume']}")

        # 全体サマリー行の作成
        prev_close = data["prev_close"] or close_val
        change = close_val - prev_close
        change_pct = round((change / prev_close * 100), 2) if prev_close > 0 else 0

        summary_rows.append({
            "ticker": ticker,
            "date": trade_date,
            "close": close_val,
            "change": change,
            "change_pct": change_pct,
            "volume": data["volume"]
        })

    # サマリーCSV保存
    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_csv(SUMMARY_PATH, index=False)
        print(f"📊 Updated summary file: {SUMMARY_PATH}")

if __name__ == "__main__":
    fetch_daily()