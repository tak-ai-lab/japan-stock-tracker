# 日本株価データ仕様書 (AI Token-Optimized Spec)

このリポジトリは、AI（Claude / ChatGPT / Gemini等）の**無料枠・トークン消費量を極限まで抑えつつ、最高精度のテクニカル分析を行うため**に最適化された株価データセットです。

---

## 1. ディレクトリ構造

```text
data/
├── daily/
│   ├── 8058.T.csv       # 三菱商事（日足・毎日16:00追記）
│   ├── 8306.T.csv       # 三菱UFJ
│   ├── 8766.T.csv       # 東京海上
│   ├── 9432.T.csv       # NTT
│   ├── 9434.T.csv       # ソフトバンク
│   ├── 4502.T.csv       # 武田薬品
│   ├── 8593.T.csv       # 三菱HCキャピタル
│   ├── 3861.T.csv       # 王子HD
│   ├── 1605.T.csv       # INPEX
│   └── 9984.T.csv       # ソフトバンクグループ
├── intraday/
│   ├── 8058.T.csv       # 三菱商事（15分足・直近5営業日分上書き・毎日11:20実行）
│   └── ... (全10銘柄)
└── latest_summary.csv   # 全10銘柄の当日概況（わずか10行の超軽量サマリー）
```

---

## 2. CSVフォーマット詳細

### ① 日足データ (`data/daily/{ticker}.csv`)
無駄なメタデータ列を完全排除した7列構成です。
```csv
date,open,high,low,close,volume,adj_close
2026-08-14,3120,3160,3110,3150,8500000,3150
```
- **date**: 営業日 (YYYY-MM-DD)
- **open / high / low / close**: 始値・高値・安値・大引け終値 (円)
- **volume**: 出来高 (株)
- **adj_close**: 調整後終値 (円)

### ② 分足データ (`data/intraday/{ticker}.csv`)
直近5日間の15分足（約120行・約6KB）を上書き更新します。
```csv
datetime,open,high,low,close,volume
2026-08-14 09:00:00,3120,3135,3115,3130,150000
```

### ③ 全体サマリー (`data/latest_summary.csv`)
10銘柄の当日終値・騰落を1行ずつ集約（約300トークンで全体概況をAI分析可能）。
```csv
ticker,date,close,change,change_pct,volume
8058.T,2026-08-14,3150,45,1.45,8500000
8306.T,2026-08-14,1680,22,1.33,12400000
...
```

---

## 3. Claude / ChatGPT へのコピペ用プロンプト例

### ■ 特定銘柄の日足分析（例：三菱商事）
```text
以下の三菱商事（8058.T）の日足CSVを読み込んで、テクニカル分析を行ってください。
URL: https://raw.githubusercontent.com/<YOUR_USER>/japan-stock-tracker/main/data/daily/8058.T.csv

【分析依頼】
1. 直近の値動きトレンド（上昇/下降/レンジ）
2. 5日・25日・75日移動平均線との位置関係
3. 上値抵抗線（レジスタンス）と下値支持線（サポート）の具体的価格帯
4. 今後の想定シナリオ
```

### ■ 特定銘柄の日中モメンタム分析（例：ソフトバンクG）
```text
以下のソフトバンクG（9984.T）の直近5日間の15分足データを分析してください。
URL: https://raw.githubusercontent.com/<YOUR_USER>/japan-stock-tracker/main/data/intraday/9984.T.csv

【分析依頼】
1. 今週の日中値動きの傾向（寄り付き高/引け安など）
2. 商いが集中している価格帯（ボリュームゾーン）
3. 短期的なエントリーポイントの考察
```

### ■ 監視10銘柄全体のサマリー診断（超低トークン消費）
```text
以下の当日サマリーCSVを読み込み、今日最も強かったセクター・銘柄と、調整に入った銘柄を要約してください。
URL: https://raw.githubusercontent.com/<YOUR_USER>/japan-stock-tracker/main/data/latest_summary.csv
```