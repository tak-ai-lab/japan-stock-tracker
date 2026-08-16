"""
init_history.py: 過去日足データ安全補完 & テクニカル指標一括計算スクリプト
- 既存の data/daily/{ticker}.csv にあるデータ（2026/1/1以降等）を1行も消さずに保護します。
- 200日移動平均などの計算に必要な過去日足（2年分）をYahoo Financeから安全に補完マージします。
- 全期間の日足に対して MA5/25/75/200, RSI14, MACD, BB, ATR を一括計算してCSVを最新化します。
"""
import os
import sys
import time
from fetch_daily import load_tickers, fetch_and_update_ticker, SUMMARY_PATH, DAILY_DIR
import pandas as pd

def main():
    print("🚀 Initializing & Backfilling historical daily stock data...")
    os.makedirs(DAILY_DIR, exist_ok=True)
    tickers = load_tickers()
    summary_rows = []

    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(2)
        print(f"\n[{i+1}/{len(tickers)}] Processing {ticker}...")
        res = fetch_and_update_ticker(ticker)
        if res:
            summary_rows.append(res)

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_csv(SUMMARY_PATH, index=False)
        print(f"\n🎉 Complete! All {len(tickers)} tickers updated with technical indicators.")

if __name__ == "__main__":
    main()