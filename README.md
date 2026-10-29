# AI Growth Atlas

AI 相关项目按「近期涨星速度」排序，而不是总星数。

按「解决什么问题」清晰分类，每个项目用一句人话解释：它干什么、对应哪个闭源产品、为什么现在在涨。

## 为什么这个项目存在

现有列表几乎都按总星排，老项目长期霸榜，新涨起来的项目被淹没。  
这里只看近 7 天 / 30 天的星数增长和加速度，让人快速看到「最近在涨什么」。

数据在 `data/` 目录，可以自己拉去做网站或周报。星数快照会逐清补充。

---

## 编程助手

让 AI 帮你写代码、改代码、跑命令。

| 项目 | 一句话解释 | 备注 |
|------|------------|------|
| [morluto/rea](https://github.com/morluto/rea) | 用 AI Agent 逆向工程任意东西：从应用行为一直到二进制。接 Ghidra/Hopper，让代码助手能看懂原来看不懂的程序。 | 近期涨星极快的 AI 逆向工具 |
| [anomalyco/opencode](https://github.com/anomalyco/opencode) | 开源的 AI 编程助手，在终端里用。支持多种模型，有桌面版正在测试。对标 Claude Code / Codex。 | 终端编程助手里涨星最稳的之一 |
| [stablyai/orca](https://github.com/stablyai/orca) | 桌面端同时跑多个编程助手（Claude Code、Codex、OpenCode等），每个在独立的 git 工作区。 | 多 Agent 并行的实用工具 |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | 可以真正干活的 AI：跨系统、跨平台的个人助手。支持本地部署。 | 总星极高的个人 AI 助手 |

## 技能与运行时

给编程助手加技能包、记忆、审计、安全。

| 项目 | 一句话解释 | 备注 |
|------|------------|------|
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | 让 AI Agent 像懒惰的资深开发一样思考：能不写就不写。一个反「AI 水」的技能包。 | 反 AI-slop 方向代表项目 |

## 记忆与知识

让 Agent 记住上下文、代码库、文档。

| 项目 | 一句话解释 | 备注 |
|------|------------|------|
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | 把代码库、文档、SQL、配置转成可查询的知识图谱。让 Agent 能快速理解大项目结构。 | 代码库记忆/知识图谱方向热门 |

## 视频与媒体

AI 生成或处理视频。

| 项目 | 一句话解释 | 备注 |
|------|------------|------|
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | 用 HTML 写视频，再渲染出来。为 Agent 设计，可以让编程助手直接生成视频。 | AI 视频生成方向涨得快 |

## 安全与审计

检查代码或 Agent 行为的风险。

| 项目 | 一句话解释 | 备注 |
|------|------------|------|
| [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) | 给编程 Agent 加一个安全审计技能：多阶段扫描代码漏洞，再用另一个 Agent 尝试证伪每个发现。输出可机器读的结构化报告。 | 近期周涨星常居前列 |

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
  "desc": "一句人话：它干什么，对应哪个闭源产品或场景",
  "stars_note": "为什么现在在涨（可选）"
}
```

分类 id 见 `data/categories.json`。
