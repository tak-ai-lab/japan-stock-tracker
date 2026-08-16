import os
import sys
import time
from datetime import datetime
import pytz
import yfinance as yf
import pandas as pd
import numpy as np

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

def format_num(val, decimals=2):
    if pd.isna(val) or val is None:
        return None
    val_float = float(val)
    if decimals == 0 or val_float.is_integer():
        return int(val_float)
    return round(val_float, decimals)

def calculate_technical_indicators(df):
    """
    株価データ (date, open, high, low, close, volume, adj_close) から
    MA5, MA25, MA75, MA200, RSI(14), MACD(12,26,9), ボリンジャーバンド(20, 2σ), ATR(14) を一括計算
    """
    if df.empty or len(df) == 0:
        return df

    # 日付昇順ソートを保証
    df = df.sort_values(by="date").reset_index(drop=True)

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # 1. 移動平均線 (SMA: 5, 25, 75, 200日)
    df["ma5"] = close.rolling(window=5, min_periods=1).mean().round(2)
    df["ma25"] = close.rolling(window=25, min_periods=1).mean().round(2)
    df["ma75"] = close.rolling(window=75, min_periods=1).mean().round(2)
    df["ma200"] = close.rolling(window=200, min_periods=1).mean().round(2)

    # 2. RSI (14日・Wilder指数平滑化方式)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    df["rsi14"] = (100 - (100 / (1 + rs))).round(2)
    df["rsi14"] = df["rsi14"].fillna(50.0)

    # 3. MACD (12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line

    df["macd"] = macd_line.round(2)
    df["macd_signal"] = signal_line.round(2)
    df["macd_hist"] = macd_hist.round(2)

    # 4. ボリンジャーバンド (20日, ±2σ)
    bb_mid = close.rolling(window=20, min_periods=1).mean()
    bb_std = close.rolling(window=20, min_periods=1).std(ddof=0)
    df["bb_upper"] = (bb_mid + (bb_std * 2)).round(2)
    df["bb_mid"] = bb_mid.round(2)
    df["bb_lower"] = (bb_mid - (bb_std * 2)).round(2)

    # 5. ATR (14日・Average True Range)
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr14"] = tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean().round(2)

    return df

def fetch_and_update_ticker(ticker, max_retries=3):
    """
    既存CSVの日足データを100%保持しつつ、Yahoo Financeから取得したデータとマージして
    全テクニカル指標を計算・更新する
    """
    csv_file = os.path.join(DAILY_DIR, f"{ticker}.csv")
    
    # 1. 既存CSVが存在する場合は読み込み（2026/1/1以降等の既存日足を保持）
    existing_df = pd.DataFrame()
    if os.path.exists(csv_file):
        try:
            existing_df = pd.read_csv(csv_file)
            if not existing_df.empty and "close" in existing_df.columns:
                existing_df = existing_df[existing_df["close"] > 0]
                existing_df["date"] = existing_df["date"].astype(str)
        except Exception as e:
            print(f"[{ticker}] Note: Could not read existing CSV: {e}")

    # 2. Yahoo Financeから過去日足データを取得（200MA等の計算に必要な期間を確保）
    fetched_df = pd.DataFrame()
    for attempt in range(1, max_retries + 1):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2y", interval="1d")
            
            if not hist.empty:
                hist = hist.dropna(subset=["Open", "High", "Low", "Close"])
                hist = hist[hist["Close"] > 0]
                
                rows = []
                for idx, row in hist.iterrows():
                    d_str = idx.strftime("%Y-%m-%d")
                    c_val = float(row["Close"])
                    o_val = float(row["Open"])
                    h_val = float(row["High"])
                    l_val = float(row["Low"])
                    v_val = int(row["Volume"]) if not pd.isna(row["Volume"]) else 0
                    adj_c = float(row.get("Adj Close", c_val))
                    
                    if c_val > 0 and o_val > 0:
                        rows.append({
                            "date": d_str,
                            "open": format_num(o_val),
                            "high": format_num(h_val),
                            "low": format_num(l_val),
                            "close": format_num(c_val),
                            "volume": v_val,
                            "adj_close": format_num(adj_c)
                        })
                
                if rows:
                    fetched_df = pd.DataFrame(rows)
                    break

            print(f"[{ticker}] Attempt {attempt}: No valid history. Retrying in 2s...")
            time.sleep(2)
        except Exception as e:
            print(f"[{ticker}] Attempt {attempt} error: {e}")
            time.sleep(2)

    # 3. データの結合（既存の有効データを最優先し、足りない過去分＆最新分を安全にマージ）
    if existing_df.empty and fetched_df.empty:
        print(f"❌ {ticker}: No data available to write.")
        return None

    base_cols = ["date", "open", "high", "low", "close", "volume", "adj_close"]
    
    if not existing_df.empty:
        valid_existing_cols = [c for c in base_cols if c in existing_df.columns]
        existing_base = existing_df[valid_existing_cols].copy()
    else:
        existing_base = pd.DataFrame(columns=base_cols)

    # 既存データを優先して重複排除（既存日足は消さずに保持）
    combined = pd.concat([existing_base, fetched_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["date"], keep="first")
    combined = combined.sort_values(by="date").reset_index(drop=True)

    # 4. 全テクニカル指標の計算
    final_df = calculate_technical_indicators(combined)

    # 5. CSVファイルへ保存
    final_df.to_csv(csv_file, index=False)
    latest_row = final_df.iloc[-1]
    trade_date = str(latest_row["date"])
    latest_close = float(latest_row["close"])
    print(f"✅ {ticker}: Updated {trade_date} (Total {len(final_df)} days, Close={latest_close}, RSI14={latest_row.get('rsi14')}, MA200={latest_row.get('ma200')})")

    # サマリー用の指標計算
    prev_close = float(final_df.iloc[-2]["close"]) if len(final_df) >= 2 else latest_close
    change = latest_close - prev_close
    change_pct = round((change / prev_close * 100), 2) if prev_close > 0 else 0
    ma25 = float(latest_row["ma25"]) if "ma25" in latest_row and latest_row["ma25"] > 0 else latest_close
    ma25_div = round(((latest_close - ma25) / ma25 * 100), 2)
    
    # BB位置判定（標準偏差換算）
    bb_upper = float(latest_row.get("bb_upper", latest_close))
    bb_lower = float(latest_row.get("bb_lower", latest_close))
    bb_mid = float(latest_row.get("bb_mid", latest_close))
    bb_width = bb_upper - bb_lower
    bb_pos = round(((latest_close - bb_mid) / (bb_width / 4)), 2) if bb_width > 0 else 0.0

    return {
        "ticker": ticker,
        "date": trade_date,
        "close": format_num(latest_close),
        "change": format_num(change),
        "change_pct": change_pct,
        "volume": int(latest_row["volume"]),
        "rsi14": float(latest_row.get("rsi14", 50.0)),
        "ma25_div_pct": ma25_div,
        "macd_hist": float(latest_row.get("macd_hist", 0.0)),
        "bb_pos": f"{bb_pos:+.1f}σ"
    }

def fetch_daily():
    now_jst = datetime.now(JST)
    print(f"[{now_jst.strftime('%Y-%m-%d %H:%M:%S')}] Starting daily stock & technical indicators pipeline...")

    os.makedirs(DAILY_DIR, exist_ok=True)
    tickers = load_tickers()
    summary_rows = []

    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(2)  # レートリミット回避

        summary_item = fetch_and_update_ticker(ticker)
        if summary_item:
            summary_rows.append(summary_item)

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_csv(SUMMARY_PATH, index=False)
        print(f"📊 Updated technical summary: {SUMMARY_PATH}")

if __name__ == "__main__":
    fetch_daily()