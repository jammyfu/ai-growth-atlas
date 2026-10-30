[English](HOW_IT_WORKS.md) | **简体中文** | [繁體中文](HOW_IT_WORKS.zh-Hant.md) | [日本語](HOW_IT_WORKS.ja.md) | [한국어](HOW_IT_WORKS.ko.md)

# GitHub 飙升榜是怎么做的

[← 返回榜单](../README.zh-Hans.md)

多数榜单按总星标数排序，老项目长期占据榜首，正在爆发的新项目反而被埋没。GitHub 飙升榜按“每天新增多少星标”来排：统计近 7 天、30 天和 365 天的日均涨星，并按分类展示，AI 是默认置顶的主榜。每个分类先看“7 天新晋”榜（最近 7 天内创建的仓库），再看周、月、年涨星榜，总星标榜放在最后。数据全部来自 GitHub API。分类规则见 [docs/CATEGORIES.md](CATEGORIES.md)。

每天更新两次：北京时间 0 点（UTC+8）和美西洛杉矶时间 0 点（America/Los_Angeles，随夏令时变化）。每次更新都会按各自的时段单独存档。

README 里每张榜只列前 10 名；每张榜完整的前 20 名（来自 70 个已收录项目）在 latest/ 文件里。

下方表格为最新榜单。每次更新还会按时段另存一份：[榜单历史](../rankings/README.zh-Hans.md) · [latest/rankings.zh-Hans.md](../latest/rankings.zh-Hans.md)。

每个分类里每张榜的第 1 名，由脚本根据下方的真实数据自动生成。“无”表示本次运行该榜没有条目。

## 分类

| | |
|---|---|
| 人工智能 ★ 主榜 | 大模型、智能体、MCP、编程助手与生成式 AI |
| 开发者工具 | 命令行、编辑器、包管理、代码检查与构建工具 |
| 安全 | 漏洞扫描、静态分析、供应链与运行时安全 |
| Web / 前端 | 前端框架、UI 组件库、CSS 与浏览器工具 |
| 基础设施 | 容器、Kubernetes、云、网络与可观测性 |
| 设计 / 创意 | 设计系统、绘图、动画与创意工具 |
| 数据 | 数据库、分析、ETL 与数据工程 |

## 最热新仓库（近 7 天内创建）

本分类下最近 7 天内创建的仓库，通过 GitHub 搜索 API（按 topic 匹配：仓库自己必须带有该分类的 topic）找出，按创建以来的日均星标排序。已出现在本分类其他榜单（或本分类已收录项目）中的仓库，以及已被更靠前分类（AI 优先）占位的仓库，不会重复列入。简介取自仓库自己的 GitHub 简介；译文库见 [data/translation_library.json](../data/translation_library.json)。规则见 [docs/NEW_ARRIVALS.md](NEW_ARRIVALS.md)。

## 数据是如何得出的

- 总星标数：`GET /repos/{owner}/{repo}` → `stargazers_count`。
- 新增星标：`GET /repos/{owner}/{repo}/stargazers/history`（GitHub 提供的、保护隐私的按周/按日星标数）。新增数为今天之前 N 个完整 UTC 日的总和（不含今天），星标/天 = 新增数 ÷ N。
- GitHub 说明，周/日统计区间的边界不保证与 UTC 对齐，且之后被取消的星标不会计入，因此窗口边缘的数字可能有小幅偏差。
- 星标历史曲线是以 URL 嵌入的 `star-history.com` SVG 图片。本仓库不含任何分析或追踪脚本。
- 原始数据见 [`data/stats.json`](../data/stats.json)；每日星标数快照追加到 [`data/stars.json`](../data/stars.json)。

## 参与贡献

在 `data/projects.json` 中添加条目（`desc` 需包含全部五种语言），然后运行 `python tools/update_stars.py`。每日更新说明见 [docs/DAILY_UPDATE.md](DAILY_UPDATE.md)。
