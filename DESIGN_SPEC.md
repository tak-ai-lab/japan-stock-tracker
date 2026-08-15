# ソフトウェア設計仕様書：日本株価自動蓄積システム (japan-stock-tracker)

## 1. システム概要

### 1.1 目的
本システムは、GitHub Actionsを活用して主要日本株10銘柄の株価データ（日足・5分足）を完全自動で収集・蓄積するサーバーレスデータパイプラインである。
特に、**LLM（Claude / ChatGPT / Gemini等）の無料枠におけるトークン消費量を極小化**し、AIによるテクニカル分析の計算精度向上と低コスト運用を両立させることを主目的とする。

### 1.2 コア設計思想
1. **銘柄別ファイル分離**: 全銘柄を1ファイルに合体させず、`data/daily/{ticker}.csv` および `data/intraday/{ticker}.csv` に完全分離。AIへ渡す入力トークン数を約1/10に削減し、銘柄混同ミス（ハルシネーション）を原理的に排除する。
2. **無駄なメタデータの徹底排除**: ファイル名やコンテキストから自明な列（`ticker`, `source`, `fetched_at`, `session`）を削除し、データ密度を最大化。
3. **分足データの直近5営業日上書き運用**: 分足データは長期蓄積せず、実行ごとに直近5日分（5分足・約300行・約8KB）で上書き更新。データの肥大化を防止。
4. **超軽量サマリーファイルの自動生成**: 全監視銘柄の当日概況を10行に集約した `data/latest_summary.csv`（約300トークン）を同時生成。

---

## 2. ディレクトリ・ファイル構成

```text
japan-stock-tracker/
│
├── .github/
│   └── workflows/
│       ├── fetch_daily.yml          # 【ワークフロー】日足自動収集（平日 16:00 JST / 07:00 UTC）
│       └── fetch_intraday.yml       # 【ワークフロー】分足自動収集（平日 11:20 JST / 02:20 UTC）
│
├── scripts/
│   ├── fetch_daily.py               # 【Python】日足データ取得・個別追記・サマリー生成
│   └── fetch_intraday.py            # 【Python】5分足データ取得・個別上書き
│
├── config/
│   └── tickers.txt                  # 【設定ファイル】監視対象銘柄コード一覧
│
├── data/
│   ├── daily/                       # 【データ】日足CSV格納ディレクトリ（毎日追記）
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
│   └── latest_summary.csv           # 【データ】全銘柄当日サマリー（10行）
│
├── requirements.txt                 # 【環境定義】Python依存ライブラリ一覧
├── DATA_SPEC.md                     # 【プロンプト仕様書】AI向けデータ構造解説
├── DESIGN_SPEC.md                   # 【設計書】本ソフトウェア設計仕様書
└── README.md                        # 【ドキュメント】リポジトリ概要とセットアップガイド
```

---

## 3. 設定ファイル仕様

### 3.1 監視対象銘柄リスト (`config/tickers.txt`)
- **フォーマット**: 1行に1銘柄のティッカーシンボル（東証コード + `.T`）を記述。
- **コメント機能**: `#` 以降の文字列はコメントとして無視される。

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
pytz>=2024.1
```

---

## 4. データフォーマット定義

### 4.1 日足データ (`data/daily/{ticker}.csv`)
- **更新方針**: 毎日大引け後に最新の1営業日分を末尾に追記（重複日は自動スキップ）。
- **列数**: 7列（ヘッダー行含む）

| 列名 | データ型 | 例 | 説明 |
|---|---|---|---|
| `date` | String | `2026-08-14` | 取引営業日（YYYY-MM-DD） |
| `open` | Number | `3120` | 始値（円） |
| `high` | Number | `3160` | 高値（円） |
| `low` | Number | `3110` | 安値（円） |
| `close` | Number | `3150` | 大引け確定終値（円） |
| `volume` | Integer | `8500000` | 出来高（株） |
| `adj_close`| Number | `3150` | 株式分割等調整後終値（円） |

```csv
date,open,high,low,close,volume,adj_close
2026-08-13,3100,3140,3090,3120,7800000,3120
2026-08-14,3120,3160,3110,3150,8500000,3150
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
- **更新方針**: 日足取得時（16:00）に全銘柄の当日指標を1行ずつ上書き出力。
- **列数**: 6列（ヘッダー行 + 10行）

| 列名 | データ型 | 例 | 説明 |
|---|---|---|---|
| `ticker` | String | `8058.T` | 銘柄コード |
| `date` | String | `2026-08-14` | 取引営業日（YYYY-MM-DD） |
| `close` | Number | `3150` | 当日確定終値（円） |
| `change` | Number | `45` | 前日比（円） |
| `change_pct` | Number | `1.45` | 騰落率（%） |
| `volume` | Integer | `8500000` | 当日出来高（株） |

```csv
ticker,date,close,change,change_pct,volume
8058.T,2026-08-14,3150,45,1.45,8500000
8306.T,2026-08-14,1680,22,1.33,12400000
...
```

---

## 5. プログラム詳細設計 (Python)

### 5.1 日足取得スクリプト (`scripts/fetch_daily.py`)

#### 処理フロー
1. `config/tickers.txt` を読み込み、監視銘柄リストを取得。
2. `data/daily/` ディレクトリの存在を確認（なければ自動作成）。
3. 各銘柄について `yfinance.Ticker(ticker).history(period="5d", interval="1d")` を実行。
4. 取得データの最終行（最新営業日）を抽出。
5. 既存の `data/daily/{ticker}.csv` をロードし、`trade_date` が存在するか検証（重複抑止）。
6. 未記録の場合のみ、フォーマット済み行を追記し、日付昇順でソートして保存。
7. 前日比・騰落率を計算し、サマリー用リストに追加。
8. 全銘柄巡回後、`data/latest_summary.csv` を上書き保存。

### 5.2 分足取得スクリプト (`scripts/fetch_intraday.py`)

#### 処理フロー
1. `config/tickers.txt` を読み込み、監視銘柄リストを取得。
2. `data/intraday/` ディレクトリの存在を確認（なければ自動作成）。
3. 各銘柄について `yfinance.Ticker(ticker).history(period="5d", interval="5m")` を実行。
4. インデックスのタイムゾーンを `Asia/Tokyo` (JST) に変換。
5. 6列構成の行データを生成し、日時昇順でソート。
6. `data/intraday/{ticker}.csv` に対し、新規作成（上書き保存）を実行。

---

## 6. GitHub Actions ワークフロー設計

### 6.1 日足自動収集ワークフロー (`.github/workflows/fetch_daily.yml`)
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

AI（Claude / ChatGPT等）にGitHubのPublic RAW URLを直接渡すことで、最小限のトークンで高精度な分析を行わせるプロンプト仕様。

### ① 特定銘柄の日足分析プロンプト
```text
以下の日足CSVデータを読み込み、テクニカル分析を行ってください。
URL: https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/daily/8058.T.csv

【データ仕様】
- 列: date, open, high, low, close, volume, adj_close (毎日16:00大引け後に自動追記)

【分析依頼】
1. 直近の値動きトレンド（上昇/下降/レンジ）
2. 5日・25日・75日移動平均線との位置関係
3. 上値抵抗線（レジスタンス）と下値支持線（サポート）の具体的価格帯
4. 出来高の推移と今後の想定シナリオ
```

### ② 特定銘柄の5分足日中モメンタム分析プロンプト
```text
以下の直近5営業日分（5分足）の株価CSVを読み込み、日中モメンタム分析を行ってください。
URL: https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/intraday/9984.T.csv

【データ仕様】
- 列: datetime, open, high, low, close, volume (平日11:20に最新5日分で上書き更新)

【分析依頼】
1. 今週の日中値動きの傾向（寄り付き高/前引け前の攻防など）
2. 出来高が集中している価格帯（ボリュームゾーン）
3. 短期デイトレ・スイング視点での注目ポイント
```

### ③ 全監視銘柄の当日概況要約プロンプト（超低トークン・約300トークン）
```text
以下の当日サマリーCSV（全10銘柄）を読み込み、全体概況を診断してください。
URL: https://raw.githubusercontent.com/tak-ai-lab/japan-stock-tracker/main/data/latest_summary.csv

【分析依頼】
1. 本日最も強かった銘柄・セクターと弱かった銘柄
2. 相場全体の資金循環や市場心理の考察
3. 明日以降に注目すべき押し目・ブレイク候補銘柄
```

---

## 8. 運用上の留意事項・セキュリティ

1. **GitHub Actions 権限設定**:
   - リポジトリの **Settings** > **Actions** > **General** > **Workflow permissions** で **「Read and write permissions」** を有効化する必要がある（コミット＆Push権限の付与）。
2. **API制限・レートリミット対策**:
   - `yfinance` は非公式APIのため、短時間に大量リクエストを投げるのを防ぐ必要がある。本システムでは1日あたり日足1回（16:00）・分足1回（11:20）の計2回のみ実行されるため、レートリミットに引っかかるリスクは極めて低い。
3. **祝日・休場日の挙動**:
   - 東証が休場（祝日・年末年始）の場合、`yfinance` は新規データを返さないため、既存CSVとの差分が発生せず `No changes to commit` として安全にスキップされる。