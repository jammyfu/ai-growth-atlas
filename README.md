# AI Growth Atlas

AI 相关项目按「近期涨星速度」排序，而不是总星数。

按「解决什么问题」清晰分类，每个项目用短视频风格的人话解释：对比强、有钩子、一眼明白。

## 为什么这个项目存在

现有列表几乎都按总星排，老项目长期霸榜，新涨起来的项目被淹没。  
这里只看近 7 天 / 30 天的星数增长和加速度，让人快速看到「最近在涨什么」。

数据在 `data/` 目录，可以自己拉去做网站或周报。星数快照会逐清补充。

---

## 编程助手

让 AI 帮你写代码、改代码、跑命令。

| 项目 | 一句话解释 | 备注 |
|------|------------|------|
| [morluto/rea](https://github.com/morluto/rea) | 别人逆向要盯几天汇编，这个让 AI 直接告诉你程序在干什么。接 Ghidra，原来看不懂的二进制一句话讲清楚。 | 近期涨星极快的 AI 逆向工具 |
| [anomalyco/opencode](https://github.com/anomalyco/opencode) | 终端里直接用 AI 写代码，不用开网页。支持多种模型，对标 Claude Code 和 Codex，免费开源。 | 终端编程助手里涨星最稳的之一 |
| [stablyai/orca](https://github.com/stablyai/orca) | 一个桌面同时跑好几个 AI 编程助手，比看谁写得好。每个助手独立工作区，不互相干扰。 | 多 Agent 并行的实用工具 |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | 不是聊天机器人，是真能帮你干活的 AI。跨系统跑，本地部署，数据不出你电脑。 | 总星极高的个人 AI 助手 |

## 技能与运行时

给编程助手加技能包、记忆、审计、安全。

| 项目 | 一句话解释 | 备注 |
|------|------------|------|
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | 专治 AI 写代码加一堆废话。让它学会像懒惰老手一样：能不写就不写，写就写对。 | 反 AI-slop 方向代表项目 |

## 记忆与知识

让 Agent 记住上下文、代码库、文档。

| 项目 | 一句话解释 | 备注 |
|------|------------|------|
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | 把整个代码库变成一张地图，AI 一眼就看懂哪些文件互相调用。大项目再也不用从头看到尾。 | 代码库记忆/知识图谱方向热门 |

## 视频与媒体

AI 生成或处理视频。

| 项目 | 一句话解释 | 备注 |
|------|------------|------|
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | 用写网页的方式写视频，AI 直接渲染出来。编程助手也能用，不用再学剪辑软件。 | AI 视频生成方向涨得快 |

## 安全与审计

检查代码或 Agent 行为的风险。

| 项目 | 一句话解释 | 备注 |
|------|------------|------|
| [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) | 让 AI 自己查自己的代码漏洞，还要再叫另一个 AI 来打脸。专治编程助手写出来的代码不安全。 | 近期周涨星常居前列 |

---

## 分类说明

| 分类 | 解决什么问题 |
|------|-------------|
| 编程助手 | 让 AI 帮你写代码、改代码、跑命令 |
| 技能与运行时 | 给编程助手加技能包、记忆、审计 |
| 记忆与知识 | 让 Agent 记住上下文、代码库、文档 |
| 浏览器与电脑控制 | 让 Agent 操作浏览器或桌面 |
| 文档与内容 | 把 PDF/PPT/视频转成可给 LLM 用的格式 |
| 视频与媒体 | AI 生成或处理视频 |
| 安全与审计 | 检查代码或 Agent 行为的风险 |
| 本地模型与推理 | 在自己机器上跑模型 |
| 工作流自动化 | 把多个工具串成流程 |
| 其他 AI 工具 | 不属于上面类别但在涨的 AI 项目 |

## 贡献

欢迎提交新项目。在 `data/projects.json` 里加一条即可，格式：

```json
{
  "name": "owner/repo",
  "url": "https://github.com/owner/repo",
  "category": "coding-agents",
  "desc": "短视频风格：对比强、有钩子、一眼明白地说清楚它干什么",
  "stars_note": "为什么现在在涨（可选）"
}
```

分类 id 见 `data/categories.json`。
