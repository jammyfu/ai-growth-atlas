[English](HOW_IT_WORKS.md) | [简体中文](HOW_IT_WORKS.zh-Hans.md) | [繁體中文](HOW_IT_WORKS.zh-Hant.md) | **日本語** | [한국어](HOW_IT_WORKS.ko.md)

# GitHub Risers の仕組み

[← ランキングに戻る](../README.ja.md)

総スター数順のリストでは古い大物が居座り、いま伸びているものが埋もれます。GitHub Risers は 1 日あたりの増加スター数（直近 7・30・365 日）で並べ、カテゴリごとに表示します。AI がメインのランキングです。各カテゴリは、直近 7 日以内に作られたリポジトリの「新着」ランキング、週・月・年の増加ランキング、最後に総スター数の順です。数値はすべて GitHub API から取得しています。分類ルール：[docs/CATEGORIES.md](CATEGORIES.md)。

1 日 2 回更新：北京時間 0 時（UTC+8）とロサンゼルス時間 0 時（America/Los_Angeles、夏時間に追従）。更新ごとに時間帯別に保存されます。

README では各ランキングの上位 10 件を表示します。各ランキングの上位 20 件の全体（収録 70 プロジェクトから）は latest/ のファイルにあります。

以下が最新のランキングです。更新のたびに時間帯ごとにも保存しています：[ランキング履歴](../rankings/README.ja.md) · [latest/rankings.ja.md](../latest/rankings.ja.md)。

各カテゴリの各ランキングの 1 位を、下の実データからスクリプトで自動生成しています。「なし」は今回その枠に該当がないことを示します。

## カテゴリ

| | |
|---|---|
| AI ★ メイン | LLM・エージェント・MCP・コーディング助手・生成 AI |
| 開発者ツール | CLI・エディタ・パッケージマネージャ・リンタ・ビルドツール |
| セキュリティ | 脆弱性スキャン・SAST・サプライチェーン・ランタイムセキュリティ |
| Web / フロントエンド | フロントエンド枠組み・UI キット・CSS・ブラウザツール |
| インフラ | コンテナ・Kubernetes・クラウド・ネットワーク・可観測性 |
| デザイン / クリエイティブ | デザインシステム・描画・アニメーション・制作ツール |
| データ | データベース・分析・ETL・データエンジニアリング |

## 7 日以内の新着で最も熱いリポジトリ（作成から 7 日以内）

このカテゴリで直近 7 日以内に作成されたリポジトリを GitHub 検索 API（topic で判定：リポジトリ自身がそのカテゴリの topic を持つこと）で探し、作成からの 1 日あたりスター数で並べます。このカテゴリの他のランキング（または収録プロジェクト）に載っているもの、および先のカテゴリ（AI 優先）ですでに載ったものは除外します。説明文は各リポジトリ自身の GitHub 説明；翻訳ライブラリは [data/translation_library.json](../data/translation_library.json)。ルール：[docs/NEW_ARRIVALS.md](NEW_ARRIVALS.md)。

## 数値の出どころ

- 総スター数：`GET /repos/{owner}/{repo}` の `stargazers_count`。
- 増加数：`GET /repos/{owner}/{repo}/stargazers/history`（GitHub が提供する、ユーザー情報を含まない週次/日次のスター数）。今日より前の N 日分（UTC、今日は含まない）の合計で、スター/日 = 増加数 ÷ N。
- GitHub は週/日の区切りが UTC と一致する保証はないとしており、後から外されたスターは数えられないため、期間の端では多少の誤差が出ます。
- スター推移は `star-history.com` の SVG 画像を URL で参照しています。このリポジトリに解析・トラッキング用スクリプトは一切ありません。
- 生データは [`data/stats.json`](../data/stats.json)、日次スナップショットは [`data/stars.json`](../data/stars.json) に追記されます。

## コントリビュート

`data/projects.json` に項目を追加し（`category` と 5 言語の `desc`）、`python tools/update_stars.py` を実行。カテゴリ：[docs/CATEGORIES.md](CATEGORIES.md)。毎日の更新：[docs/DAILY_UPDATE.md](DAILY_UPDATE.md)。
