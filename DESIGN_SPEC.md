# ソフトウェア設計仕様書：日本株価自動蓄積システム (japan-stock-tracker)

## 1. システム概要

### 1.1 目的
本システムは、GitHub Actionsを活用して主要日本株10銘柄の株価データ（日足・5分足）および主要テクニカル指標を完全自動で収集・計算・蓄積するサーバーレスデータパイプラインである。
特に、**LLM（Claude / ChatGPT / Gemini等）の無料枠におけるトークン消費量を極小化**し、AIによるテクニカル分析の計算精度向上と低コスト運用を両立させることを主目的とする。

### 1.2 コア設計思想
1. **銘柄別ファイル分離**: 全銘柄を1ファイルに合体させず、`data/daily/{ticker}.csv` および `data/intraday/{ticker}.csv` に完全分離。AIへ渡す入力トークン数を約1/10に削減し、銘柄混同ミス（ハルシネーション）を原理的に排除する。
2. **テクニカル指標の事前計算 (Pre-Calculated Indicators)**:
   - MA(5/25/75/200), RSI(14), MACD(12,26,9), ボリンジャーバンド(20, ±2σ), ATR(14) をPython（pandas/numpy）側で厳密に計算してCSV列に格納。
   - AIに計算させないことで、AIの計算ミスを100%防止し、わずか直近数行のプロンプト入力で高度なチャート診断を実現。
3. **既存CSVデータ保護 ＆ 過去データ安全マージ**:
   - すでに蓄積された過去データを壊さず、新規営業日のみを安全に追記・マージ。
4. **超低トークンサマリー自動生成**: 全監視銘柄の当日概況・RSI・乖離率を10行に集約した `data/latest_summary.csv`（約300トークン）を同時生成。

---

## 2. ディレクトリ・ファイル構成

```text
japan-stock-tracker/
│
├── .github/
│   └── workflows/
│       ├── fetch_daily.yml          # 【ワークフロー】日足自動収集＆指標計算（平日 16:00 JST / 07:00 UTC）
│       └── fetch_intraday.yml       # 【ワークフロー】分足自動収集（平日 11:20 JST / 02:20 UTC）
│
├── scripts/
│   ├── fetch_daily.py               # 【Python】日足データ取得・指標一括計算・個別更新・サマリー生成
│   ├── init_history.py              # 【Python】過去2年分日足安全補完＆全指標初期化スクリプト
│   └── fetch_intraday.py            # 【Python】5分足データ取得・個別上書き
│
├── config/
│   └── tickers.txt                  # 【設定ファイル】監視対象銘柄コード一覧
│
├── data/
│   ├── daily/                       # 【データ】日足＋全テクニカル指標CSV（毎日追記・更新）
│   │   ├── 8058.T.csv               # 三菱商事
│   │   ├── 8306.T.csv               # 三菱ＵＦＪ
│   │   ├── 8766.T.csv               # 東京海上
│   │   ├── 9432.T.csv               # ＮＴＴ
│   │   ├── 9434.T.csv               # ソフトバンク
│   │   ├── 4502.T.csv               # 武田薬品工業
│   │   ├── 8593.T.csv               # 三菱ＨＣキャピタル
│   │   ├── 3861.T.csv               # 王子ホールディングス
│   │   ├── 1605.T.csv               # ＩＮＰＥＸ
│   │   └── 9984.T.csv               # ソフトバンクグループ
│   │
│   ├── intraday/                    # 【データ】分足CSV格納ディレクトリ（毎回上書き）
│   │   ├── 8058.T.csv               # 三菱商事（直近5日分5分足）
│   │   └── ... (全10銘柄)
│   │
│   └── latest_summary.csv           # 【データ】全銘柄当日サマリー（10行・主要指標付き）
│
├── requirements.txt                 # 【環境定義】Python依存ライブラリ一覧
├── DATA_SPEC.md                     # 【プロンプト仕様書】AI向けデータ構造解説
├── DESIGN_SPEC.md                   # 【設計書】本ソフトウェア設計仕様書
└── README.md                        # 【ドキュメント】リポジトリ概要とセットアップガイド
```

---

## 3. 設定ファイル仕様

### 3.1 監視対象銘柄リスト (`config/tickers.txt`)
```text
# 日本株自動収集対象銘柄（10銘柄）
8058.T    # 三菱商事
8306.T    # 三菱ＵＦＪフィナンシャル・グループ
8766.T    # 東京海上ホールディングス
9432.T    # 日本電信電話 (NTT)
9434.T    # ソフトバンク (通信)
4502.T    # 武田薬品工業
8593.T    # 三菱ＨＣキャピタル
3861.T    # 王子ホールディングス
1605.T    # ＩＮＰＥＸ
9984.T    # ソフトバンクグループ
```

### 3.2 依存関係定義 (`requirements.txt`)
```text
yfinance>=0.2.38
pandas>=2.0.0
numpy>=1.24.0
pytz>=2024.1
```

---

## 4. データフォーマット定義

### 4.1 日足＋テクニカル指標データ (`data/daily/{ticker}.csv`)
- **更新方針**: 既存日足を保持しつつ新規営業日を追記し、全期間のテクニカル指標を再計算して保存。
- **列数**: 19列

| 列名 | データ型 | 例 | 数式・定義 | 説明 |
|---|---|---|---|---|
| `date` | String | `2026-08-14` | YYYY-MM-DD | 取引営業日 |
| `open, high, low, close` | Number | `3120, 3160...` | 四本値 | 始値・高値・安値・大引け終値 (円) |
| `volume` | Integer | `8500000` | 出来高 | 取引株数 |
| `adj_close` | Number | `3150` | 調整後終値 | 株式分割等調整後 |
| `ma5, ma25, ma75, ma200` | Number | `3130.0` | `SMA(Close, N)` | 5日・25日・75日・200日移動平均線 |
| `rsi14` | Number | `58.4` | `100 - (100 / (1 + RS))` (Wilder) | 14日RSI (30以下売られすぎ/70以上買われすぎ) |
| `macd` | Number | `24.5` | `EMA(12) - EMA(26)` | MACD線 |
| `macd_signal` | Number | `21.0` | `EMA(MACD, 9)` | シグナル線 |
| `macd_hist` | Number | `3.5` | `MACD - Signal` | MACDヒストグラム（モメンタム） |
| `bb_upper, bb_mid, bb_lower` | Number | `3220.4...` | `SMA(20) ± 2σ` | ボリンジャーバンド (20日, ±2σ) |
| `atr14` | Number | `45.2` | `EWM(TR, 14)` | 14日ATR (1日の想定ボラティリティ値幅) |

```csv
date,open,high,low,close,volume,adj_close,ma5,ma25,ma75,ma200,rsi14,macd,macd_signal,macd_hist,bb_upper,bb_mid,bb_lower,atr14
2026-08-13,3100,3140,3090,3120,7800000,3120,3110.0,3045.0,2975.0,2845.0,55.2,22.0,20.2,1.8,3210.0,3045.0,2880.0,44.0
2026-08-14,3120,3160,3110,3150,8500000,3150,3130.0,3050.2,2980.5,2850.0,58.4,24.5,21.0,3.5,3220.4,3050.2,2880.0,45.2
```

### 4.2 分足データ (`data/intraday/{ticker}.csv`)
- **更新方針**: 実行ごとに**直近5営業日分の5分足データで全行上書き**（過去データの蓄積による肥大化を防止）。
- **列数**: 6列（ヘッダー行含む）

| 列名 | データ型 | 例 | 説明 |
|---|---|---|---|
| `datetime` | String | `2026-08-14 09:00:00` | 取引時刻（JST、YYYY-MM-DD HH:MM:SS） |
| `open` | Number | `3120` | 足の始値（円） |
| `high` | Number | `3135` | 足の高値（円） |
| `low` | Number | `3115` | 足の安値（円） |
| `close` | Number | `3130` | 足の終値（円） |
| `volume` | Integer | `150000` | 足の出来高（株） |

```csv
datetime,open,high,low,close,volume
2026-08-14 09:00:00,3120,3135,3115,3130,150000
2026-08-14 09:05:00,3130,3140,3125,3135,110000
...
```

### 4.3 全銘柄当日サマリー (`data/latest_summary.csv`)
- **更新方針**: 日足取得時（16:00）に全銘柄の当日指標（主要テクニカル指標含む）を1行ずつ上書き出力。
- **列数**: 12列（ヘッダー行 + 10行）

| 列名 | データ型 | 例 | 説明 |
|---|---|---|---|
| `ticker` | String | `8058.T` | 銘柄コード |
| `date` | String | `2026-08-14` | 取引営業日（YYYY-MM-DD） |
| `close` | Number | `3150` | 当日確定終値（円） |
| `change` | Number | `45` | 前日比（円） |
| `change_pct` | Number | `1.45` | 騰落率（%） |
| `volume` | Integer | `8500000` | 当日出来高（株） |
| `ma25_div_pct` | Number | `3.27` | 25日線乖離率（%） |
| `rsi14` | Number | `58.4` | 14日RSI |
| `macd_hist` | Number | `3.5` | MACDヒストグラム |
| `bb_pos_pct` | Number | `79.2` | ボリンジャーバンド位置（%） |
| `atr14` | Number | `45.2` | 14日ATR |
| `trend_status` | String | `Bullish` | トレンド総合判定 |

---

## 5. プログラム詳細設計 (Python)

### 5.1 日足＆指標一括計算スクリプト (`scripts/fetch_daily.py`)

#### 堅牢性・通信制御設計
1. **通信ディレイ制御**:
   - 銘柄間に `time.sleep(2)`（2秒待機）を挿入し、Yahoo! Financeサーバーへの過負荷およびサイレントな帯域制限（出来高のみ返して四本値がNaNになる現象）を抑止。
2. **自動リトライ機構 (`fetch_single_ticker_with_retry`)**:
   - 最大3回試行。四本値のいずれかが `None`、`NaN`、または `0` 以下の場合は2秒待機して再取得。
3. **厳格なゼロ値排除とデータ整合性保護**:
   - `format_price(val)` において、`NaN` または `0以下` の数値は即座に `None` を返却。
   - 有効な当日四本値が取得できない場合は、**CSVへの当日の追記を安全にスキップ**。
4. **過去の不正データ自動クリーニング**:
   - 既存CSV読み込み時、過去に混入してしまった `close <= 0` の異常行を自動フィルタリングして排除。

#### テクニカル指標計算エンジン (`calculate_technical_indicators`)
- **移動平均線**: `df['close'].rolling(window=n).mean()` (n=5, 25, 75, 200)
- **RSI (14日・Wilder法)**:
  - 差分 (`diff`) から上昇幅・下落幅を分離。
  - `ewm(alpha=1/14, adjust=False).mean()` で修正移動平均を算出して `100 - (100 / (1 + RS))` を計算。
- **MACD**:
  - `ema12 = close.ewm(span=12, adjust=False).mean()`
  - `ema26 = close.ewm(span=26, adjust=False).mean()`
  - `macd = ema12 - ema26`
  - `signal = macd.ewm(span=9, adjust=False).mean()`
  - `hist = macd - signal`
- **ボリンジャーバンド (20日, ±2σ)**:
  - `mid = close.rolling(window=20).mean()`
  - `std = close.rolling(window=20).std()`
  - `upper = mid + (std * 2)`, `lower = mid - (std * 2)`
- **ATR (14日)**:
  - `TR = max(High - Low, abs(High - PrevClose), abs(Low - PrevClose))`
  - `ATR = TR.ewm(alpha=1/14, adjust=False).mean()`

### 5.2 過去データ安全補完スクリプト (`scripts/init_history.py`)
1. `data/daily/{ticker}.csv` が既に存在する場合、既存データをロード。
2. Yahoo Financeから過去2年分の日足 (`period="2y", interval="1d"`) を取得。
3. `pd.concat([existing_df, fetched_df]).drop_duplicates(subset=['date'], keep='first')` により、既存の確定行を最優先で維持しつつ不足する過去履歴を補完。
4. 全行に対して `calculate_technical_indicators` を実行し、全列に計算値を埋めて上書き保存。

---

## 6. GitHub Actions ワークフロー設計

### 6.1 日足＆指標自動収集ワークフロー (`.github/workflows/fetch_daily.yml`)
- **トリガー**:
  - `cron: '0 7 * * 1-5'`（平日 16:00 JST / 07:00 UTC、東証大引け後）
  - `workflow_dispatch`（手動実行）
- **権限**: `contents: write`（リポジトリへのGit Push権限）

### 6.2 分足自動収集ワークフロー (`.github/workflows/fetch_intraday.yml`)
- **トリガー**:
  - `cron: '20 2 * * 1-5'`（平日 11:20 JST / 02:20 UTC、東証前場引け直前）
  - `workflow_dispatch`（手動実行）

---

## 7. AIプロンプト連携インターフェース (`DATA_SPEC.md`)

AIにGitHubのPublic RAW URLを渡し、事前計算された指標を活用して的確な投資診断を行わせるプロンプト仕様。

### ① 特定銘柄の日足・テクニカル総合診断プロンプト
```text
以下の日足CSVデータを読み込み、事前計算済みテクニカル指標を用いてテクニカル診断を行ってください。
URL: https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/8058.T.csv

【分析依頼】
1. 移動平均線（5/25/75/200日）との位置関係・トレンド状態
2. RSI(14)およびMACDヒストグラムから読み取れる過熱感・モメンタム
3. ボリンジャーバンド(±2σ)とATR(14)に基づく値幅リスクとサポート・レジスタンス
4. 今後のエントリー・利益確定の推奨シナリオ
```

### ② 全監視銘柄の当日サマリー診断プロンプト（超低トークン・約300トークン）
```text
以下の当日サマリーCSV（全10銘柄）を読み込み、全体概況を診断してください。
URL: https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/latest_summary.csv

【分析依頼】
1. RSI(14)や25日線乖離率(ma25_div_pct)から見た売られすぎ（反発候補）銘柄と過熱銘柄
2. MACDヒストグラムが好転しているモメンタム上位銘柄
3. 全体相場の資金循環と明日の注目候補
```

---

## 8. 運用上の留意事項・セキュリティ

1. **GitHub Actions 権限設定**:
   - リポジトリの **Settings** > **Actions** > **General** > **Workflow permissions** で **「Read and write permissions」** を有効化。
2. **レートリミットおよびデータ遅延対策**:
   - スクリプト内に **2秒ディレイ (`time.sleep(2)`)** と **最大3回のリトライ機構** を内包。
3. **既存日足データの完全保護**:
   - マージ処理において既存CSVの行を最優先するため、手動で修正した過去データや蓄積データが消失することはありません。
4. **祝日・休場日の挙動**:
   - 東証が休場の場合、差分が発生せず `No changes to commit` として安全に終了。