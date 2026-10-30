[English](HOW_IT_WORKS.md) | [简体中文](HOW_IT_WORKS.zh-Hans.md) | **繁體中文** | [日本語](HOW_IT_WORKS.ja.md) | [한국어](HOW_IT_WORKS.ko.md)

# GitHub 飆升榜是怎麼做的

[← 回到榜單](../README.zh-Hant.md)

多數榜單依總星號數排序，老專案長期霸占榜首，正在爆發的新專案反而被埋沒。GitHub 飆升榜依「每天新增多少星號」來排：統計近 7 天、30 天和 365 天的日均漲星，並依分類呈現，AI 是預設置頂的主榜。每個分類先看「7 天新晉」榜（最近 7 天內建立的儲存庫），再看週、月、年漲星榜，總星號榜放在最後。資料全部來自 GitHub API。分類規則請見 [docs/CATEGORIES.md](CATEGORIES.md)。

每天更新兩次：北京時間 0 點（UTC+8）和美西洛杉磯時間 0 點（America/Los_Angeles，隨夏令時間變動）。每次更新都會依各自的時段單獨存檔。

README 裡每張榜只列前 10 名；每張榜完整的前 20 名（來自 70 個已收錄專案）在 latest/ 檔案裡。

下方表格為最新榜單。每次更新還會依時段另存一份：[榜單歷史](../rankings/README.zh-Hant.md) · [latest/rankings.zh-Hant.md](../latest/rankings.zh-Hant.md)。

每個分類裡每張榜的第 1 名，由腳本根據下方的真實資料自動產生。「無」表示本次執行該榜沒有項目。

## 分類

| | |
|---|---|
| 人工智慧 ★ 主榜 | 大型語言模型、代理、MCP、程式設計助手與生成式 AI |
| 開發者工具 | 命令列、編輯器、套件管理、程式碼檢查與建置工具 |
| 資安 | 弱點掃描、靜態分析、供應鏈與執行時資安 |
| Web / 前端 | 前端框架、UI 元件庫、CSS 與瀏覽器工具 |
| 基礎建設 | 容器、Kubernetes、雲端、網路與可觀測性 |
| 設計 / 創意 | 設計系統、繪圖、動畫與創意工具 |
| 資料 | 資料庫、分析、ETL 與資料工程 |

## 最熱新儲存庫（近 7 天內建立）

本分類下最近 7 天內建立的儲存庫，透過 GitHub 搜尋 API（依 topic 比對：儲存庫自己必須帶有該分類的 topic）找出，並依建立以來的日均星號排序。已出現在本分類其他榜單（或本分類已收錄專案）中的儲存庫，以及已被更前面分類（AI 優先）佔位的儲存庫，不會重複列入。簡介取自儲存庫自己的 GitHub 簡介；譯文庫見 [data/translation_library.json](../data/translation_library.json)。規則請見 [docs/NEW_ARRIVALS.md](NEW_ARRIVALS.md)。

## 資料是如何得出的

- 總星號數：`GET /repos/{owner}/{repo}` → `stargazers_count`。
- 新增星號：`GET /repos/{owner}/{repo}/stargazers/history`（GitHub 提供、保護隱私的每週/每日星號數）。新增數為今天之前 N 個完整 UTC 日的總和（不含今天），星號/天 = 新增數 ÷ N。
- GitHub 表示，週/日統計區間的邊界不保證與 UTC 對齊，且之後被取消的星號不會計入，因此區間邊緣的數字可能有小幅誤差。
- 星號歷史曲線是以 URL 嵌入的 `star-history.com` SVG 圖片。本儲存庫不含任何分析或追蹤指令碼。
- 原始資料請見 [`data/stats.json`](../data/stats.json)；每日星號數快照會追加到 [`data/stars.json`](../data/stars.json)。

## 參與貢獻

在 `data/projects.json` 中新增項目（需含 `category` 與五種語言的 `desc`），然後執行 `python tools/update_stars.py`。分類：[docs/CATEGORIES.md](CATEGORIES.md)。每日更新：[docs/DAILY_UPDATE.md](DAILY_UPDATE.md)。
