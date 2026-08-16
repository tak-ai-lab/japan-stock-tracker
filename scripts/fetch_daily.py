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
    株価データから全テクニカル指標を一括計算。
    ※株式分割による指標の歪み（MAやRSIの偽の暴落）を防ぐため、
      調整後終値(adj_close)が存在する場合はそれを基準に指標を計算します。
    """
    if df.empty or len(df) == 0:
        return df

    # 日付昇順ソートを保証
    df = df.sort_values(by="date").reset_index(drop=True)

    # 指標計算の基準となる終値（株式分割調整後を優先）
    if "adj_close" in df.columns and not df["adj_close"].isna().all():
        calc_close = df["adj_close"].astype(float)
    else:
        calc_close = df["close"].astype(float)

    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # 1. 移動平均線 (SMA: 5, 25, 75, 200日)
    df["ma5"] = calc_close.rolling(window=5, min_periods=1).mean().round(2)
    df["ma25"] = calc_close.rolling(window=25, min_periods=1).mean().round(2)
    df["ma75"] = calc_close.rolling(window=75, min_periods=1).mean().round(2)
    df["ma200"] = calc_close.rolling(window=200, min_periods=1).mean().round(2)

    # 2. RSI (14日・Wilder指数平滑化方式)
    delta = calc_close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi14"] = (100 - (100 / (1 + rs))).round(2)
    df["rsi14"] = df["rsi14"].fillna(50.0)

    # 3. MACD (12, 26, 9)
    ema12 = calc_close.ewm(span=12, adjust=False).mean()
    ema26 = calc_close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line

    df["macd"] = macd_line.round(2)
    df["macd_signal"] = signal_line.round(2)
    df["macd_hist"] = macd_hist.round(2)

    # 4. ボリンジャーバンド (20日, ±2σ)
    bb_mid = calc_close.rolling(window=20, min_periods=1).mean()
    bb_std = calc_close.rolling(window=20, min_periods=1).std(ddof=0)
    df["bb_upper"] = (bb_mid + (bb_std * 2)).round(2)
    df["bb_mid"] = bb_mid.round(2)
    df["bb_lower"] = (bb_mid - (bb_std * 2)).round(2)

    # 5. ATR (14日・Average True Range)
    prev_close = calc_close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr14"] = tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean().round(2)

    return df

def fetch_and_update_ticker(ticker, max_retries=3):
    """
    既存CSVの日足データを100%保持しつつ、Yahoo Financeから取得したデータ（株式分割調整済み含む）
    と安全にマージして全テクニカル指標を計算・更新する。
    戻り値として、サマリー用の「直近3営業日分の指標データ」のリストを返す。
    """
    csv_file = os.path.join(DAILY_DIR, f"{ticker}.csv")
    
    # 1. 既存CSVが存在する場合は読み込み
    existing_df = pd.DataFrame()
    if os.path.exists(csv_file):
        try:
            existing_df = pd.read_csv(csv_file)
            if not existing_df.empty and "close" in existing_df.columns:
                existing_df = existing_df[existing_df["close"] > 0]
                existing_df["date"] = existing_df["date"].astype(str)
        except Exception as e:
            print(f"[{ticker}] Note: Could not read existing CSV: {e}")

    # 2. Yahoo Financeから過去日足データを取得（2年分取得してMA200や株式分割を正確に反映）
    fetched_df = pd.DataFrame()
    for attempt in range(1, max_retries + 1):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2y", interval="1d", auto_adjust=False)
            
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
                    
                    if "Adj Close" in row and not pd.isna(row["Adj Close"]) and float(row["Adj Close"]) > 0:
                        adj_c = float(row["Adj Close"])
                    else:
                        adj_c = c_val
                    
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

    # 3. データの結合（既存の有効データを保持しつつ、不足分や最新日を安全にマージ）
    if existing_df.empty and fetched_df.empty:
        print(f"❌ {ticker}: No data available to write.")
        return []

    base_cols = ["date", "open", "high", "low", "close", "volume", "adj_close"]
    
    if not existing_df.empty:
        valid_existing_cols = [c for c in base_cols if c in existing_df.columns]
        existing_base = existing_df[valid_existing_cols].copy()
    else:
        existing_base = pd.DataFrame(columns=base_cols)

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
    print(f"✅ {ticker}: Updated {trade_date} (Total {len(final_df)} days, Close={latest_close}, AdjClose={latest_row.get('adj_close')}, RSI14={latest_row.get('rsi14')}, MA200={latest_row.get('ma200')})")

    # 6. 直近3営業日分のサマリー用データを生成
    recent_rows = final_df.tail(3)
    summary_items = []

    for i in range(len(recent_rows)):
        target_row = recent_rows.iloc[i]
        row_idx = final_df.index.get_loc(recent_rows.index[i])
        
        curr_close = float(target_row["close"])
        curr_date = str(target_row["date"])
        
        if row_idx > 0:
            prev_row = final_df.iloc[row_idx - 1]
            prev_c = float(prev_row["close"])
        else:
            prev_c = curr_close
            
        diff = curr_close - prev_c
        diff_pct = round((diff / prev_c * 100), 2) if prev_c > 0 else 0.0
        
        ma5 = float(target_row.get("ma5", curr_close))
        ma25 = float(target_row.get("ma25", curr_close))
        ma75 = float(target_row.get("ma75", curr_close))
        ma200 = float(target_row.get("ma200", curr_close))
        
        ma25_div = round(((curr_close - ma25) / ma25 * 100), 2) if ma25 > 0 else 0.0
        
        if curr_close > ma25 and ma25 > ma75:
            trend = "Bullish (上昇基調)"
        elif curr_close < ma25 and ma25 < ma75:
            trend = "Bearish (下降基調)"
        else:
            trend = "Range (保ち合い)"

        summary_items.append({
            "ticker": ticker,
            "date": curr_date,
            "close": format_num(curr_close),
            "change": format_num(diff),
            "change_pct": diff_pct,
            "volume": int(target_row["volume"]),
            "ma5": format_num(ma5),
            "ma25": format_num(ma25),
            "ma75": format_num(ma75),
            "ma200": format_num(ma200),
            "ma25_div_pct": ma25_div,
            "rsi14": float(target_row.get("rsi14", 50.0)),
            "macd": float(target_row.get("macd", 0.0)),
            "macd_signal": float(target_row.get("macd_signal", 0.0)),
            "macd_hist": float(target_row.get("macd_hist", 0.0)),
            "bb_upper": format_num(target_row.get("bb_upper", curr_close)),
            "bb_mid": format_num(target_row.get("bb_mid", curr_close)),
            "bb_lower": format_num(target_row.get("bb_lower", curr_close)),
            "atr14": format_num(target_row.get("atr14", 0.0)),
            "trend_status": trend
        })

    return summary_items

def fetch_daily():
    now_jst = datetime.now(JST)
    print(f"[{now_jst.strftime('%Y-%m-%d %H:%M:%S')}] Starting daily stock & technical indicators pipeline...")

    os.makedirs(DAILY_DIR, exist_ok=True)
    tickers = load_tickers()
    all_summary_rows = []

    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(2)

        ticker_summaries = fetch_and_update_ticker(ticker)
        if ticker_summaries:
            all_summary_rows.extend(ticker_summaries)

    if all_summary_rows:
        summary_df = pd.DataFrame(all_summary_rows)
        summary_df = summary_df.sort_values(by=["ticker", "date"]).reset_index(drop=True)
        summary_df.to_csv(SUMMARY_PATH, index=False)
        print(f"📊 Updated multi-day technical summary (3 days per ticker, {len(summary_df)} rows): {SUMMARY_PATH}")

if __name__ == "__main__":
    fetch_daily()