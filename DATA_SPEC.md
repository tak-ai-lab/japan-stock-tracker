# 日本株価データ仕様書 (AI Token-Optimized Spec)

このリポジトリ（`tak-ai-lab/japan-stock-tracker`）は、AI（Claude / ChatGPT / Gemini等）の**無料枠・トークン消費量を極限まで抑えつつ、最高精度のテクニカル分析を行うため**に最適化された株価データセットです。

Pythonスクリプト（GitHub Actions）側で **MA(5/25/75/200), RSI(14), MACD(12,26,9), ボリンジャーバンド(20, ±2σ), ATR(14)** を事前計算してCSVに列として保持しているため、**AI側での計算ハルシネーション（計算ミス）が原理的にゼロ**となり、わずか数行のデータ指定で高度な診断が可能です。

---

## 1. ディレクトリ構造と実ファイル一覧

```text
https://github.com/tak-ai-lab/japan-stock-tracker/tree/main/data/
├── daily/                        # 日足＋全テクニカル指標CSV（平日16:00大引け後に自動更新）
│   ├── 8058.T.csv                # 三菱商事
│   ├── 8306.T.csv                # 三菱ＵＦＪフィナンシャル・グループ
│   ├── 8766.T.csv                # 東京海上ホールディングス
│   ├── 9432.T.csv                # 日本電信電話 (NTT)
│   ├── 9434.T.csv                # ソフトバンク (通信)
│   ├── 4502.T.csv                # 武田薬品工業
│   ├── 8593.T.csv                # 三菱ＨＣキャピタル
│   ├── 3861.T.csv                # 王子ホールディングス
│   ├── 1605.T.csv                # ＩＮＰＥＸ
│   └── 9984.T.csv                # ソフトバンクグループ
├── intraday/                     # 5分足CSV（平日11:20に直近5営業日分で上書き更新）
│   ├── 8058.T.csv                # 三菱商事（5分足）
│   └── ... (全10銘柄)
└── latest_summary.csv            # 全10銘柄の当日概況＆主要指標サマリー（わずか10行）
```

---

## 2. 銘柄別 Raw URL 一覧（AIコピペ用）

### ■ 日足＋テクニカル指標データ (`data/daily/`)
AI（ClaudeやChatGPT）に直接読み込ませる際は、以下のRaw URLをそのまま指定してください。

| 銘柄名 | コード | GitHub Raw CSV URL |
|---|---|---|
| **三菱商事** | 8058.T | `https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/8058.T.csv` |
| **三菱ＵＦＪ** | 8306.T | `https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/8306.T.csv` |
| **東京海上** | 8766.T | `https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/8766.T.csv` |
| **ＮＴＴ** | 9432.T | `https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/9432.T.csv` |
| **ソフトバンク** | 9434.T | `https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/9434.T.csv` |
| **武田薬品工業** | 4502.T | `https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/4502.T.csv` |
| **三菱ＨＣキャピタル** | 8593.T | `https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/8593.T.csv` |
| **王子ホールディングス** | 3861.T | `https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/3861.T.csv` |
| **ＩＮＰＥＸ** | 1605.T | `https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/1605.T.csv` |
| **ソフトバンクグループ** | 9984.T | `https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/9984.T.csv` |

### ■ 全銘柄サマリー (`data/latest_summary.csv`)
`https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/latest_summary.csv`

---

## 3. CSVフォーマット詳細

### ① 日足＋テクニカル指標データ (`data/daily/{ticker}.csv`)
全19列。AIが複雑な計算を行うことなく、直近数行を見るだけで正確な判定ができるよう完全事前計算されています。

```csv
date,open,high,low,close,volume,adj_close,ma5,ma25,ma75,ma200,rsi14,macd,macd_signal,macd_hist,bb_upper,bb_mid,bb_lower,atr14
2026-08-14,3120,3160,3110,3150,8500000,3150,3130.0,3050.2,2980.5,2850.0,58.4,24.5,21.0,3.5,3220.4,3050.2,2880.0,45.2
```

| 分類 | 列名 | 型 | 説明 |
|---|---|---|---|
| **基本価格** | `date` | String | 営業日 (YYYY-MM-DD) |
| | `open, high, low, close` | Number | 始値・高値・安値・大引け終値 (円) |
| | `volume` | Integer | 出来高 (株) |
| | `adj_close` | Number | 株式分割等調整後終値 (円) |
| **移動平均線** | `ma5, ma25, ma75, ma200` | Number | 5日・25日・75日・200日 単純移動平均線 (SMA) |
| **オシレーター** | `rsi14` | Number | 14日RSI (Wilder方式、30以下売られすぎ/70以上買われすぎ) |
| **モメンタム** | `macd` | Number | MACD線 (12日EMA - 26日EMA) |
| | `macd_signal` | Number | シグナル線 (MACDの9日EMA) |
| | `macd_hist` | Number | MACDヒストグラム (`macd - macd_signal`) |
| **ボラティリティ** | `bb_upper, bb_mid, bb_lower`| Number | ボリンジャーバンド (20日SMA, ±2σ) |
| | `atr14` | Number | 14日ATR (Average True Range: 日中想定リスク値幅) |

### ② 分足データ (`data/intraday/{ticker}.csv`)
直近5日間の5分足（約300行・約8KB）を平日11:20に上書き更新します。
```csv
datetime,open,high,low,close,volume
2026-08-14 09:00:00,3120,3135,3115,3130,150000
```

### ③ 全体サマリー (`data/latest_summary.csv`)
10銘柄の当日指標・RSI・25日乖離率・MACDヒストグラムを1行ずつ集約（約300トークン）。
```csv
ticker,date,close,change,change_pct,volume,rsi14,ma25_div_pct,macd_hist,bb_pos
8058.T,2026-08-14,3150,45,1.45,8500000,58.4,3.27,3.5,+1.2σ
8306.T,2026-08-14,1680,22,1.33,12400000,62.1,2.15,1.2,+0.8σ
...
```

---

## 4. Claude / ChatGPT へのコピペ用プロンプト例

### ■ 特定銘柄の日足・指標総合診断（例：三菱商事）
```text
以下の三菱商事（8058.T）の日足CSVデータを読み込み、事前計算されたテクニカル指標を活用して投資判断を分析してください。
URL: https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/8058.T.csv

【データ仕様】
- 列: date, open, high, low, close, volume, adj_close, ma5, ma25, ma75, ma200, rsi14, macd, macd_signal, macd_hist, bb_upper, bb_mid, bb_lower, atr14

【分析依頼】
1. トレンド判定: 株価とMA(5/25/75/200)の位置関係（パーフェクトオーダー/ゴールデンクロス状況）
2. 過熱感 & モメンタム: RSI(14)とMACDヒストグラムの推移から見た売買シグナル
3. リスク管理: ボリンジャーバンド(±2σ)とATR(14)に基づく損切り幅・目標利益の想定
4. 総合見通し: 今後の押し目買い/戻り売りシナリオ
```

### ■ 特定銘柄の日中モメンタム分析（例：ソフトバンクG）
```text
以下のソフトバンクG（9984.T）の直近5日間の5分足データを分析してください。
URL: https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/intraday/9984.T.csv

【分析依頼】
1. 今週の日中値動きの傾向（寄り付き高/引け安など）
2. 商いが集中している価格帯（ボリュームゾーン）
3. 短期的なエントリーポイントの考察
```

### ■ 監視10銘柄全体のサマリー診断（超低トークン消費・約300トークン）
```text
以下の当日サマリーCSV（全10銘柄・事前計算テクニカル指標付き）を読み込み、全体概況を診断してください。
URL: https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/latest_summary.csv

【分析依頼】
1. RSI(14)や25日線乖離率(ma25_div_pct)から見た売られすぎ（反発候補）銘柄と過熱銘柄
2. MACDヒストグラムが好転しているモメンタム上位銘柄
3. 全体相場の資金循環と明日の注目候補
```