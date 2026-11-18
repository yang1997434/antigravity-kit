---
name: deep-research
description: 深度/多跳网络调研 —— 走 Parallel.ai 检索 + 正文抓取，比内置 WebSearch 更适合"需要多个来源交叉验证""要读原文""要限定时间或域名"的问题。Use when the user asks for 深度调研 / 多跳调研 / 竞品调研 / 技术选型对比 / 需要引用原文出处的研究, or when WebSearch results are too shallow to answer. 也用于抓取指定 URL 的完整正文。
---

用 `parallel_search.py` 调 Parallel.ai。Key 是 `PARALLEL_API_KEY`，脚本内部用 `flow-cred` 取，**永远不要打印 key**。

> `~/.pi/web-search.json` 里的 `parallelApiKey` 是 `!command` 引用形式，不是明文 key，直接拿去调会 401。

## 命令

```bash
S=~/.gemini/config/plugins/claude-stack/skills/deep-research/parallel_search.py

# 检索：一次可发多条 query（并行覆盖不同角度），--objective 说明总目标
python3 $S search "query A" "query B" --objective "整体调研目标" -n 8

# 限定时间 / 域名
python3 $S search "query" --after 2026-01-01 --include docs.anthropic.com,github.com

# 抓正文（拿到 URL 之后读原文，别只靠摘要下结论）
python3 $S extract <url> [<url> ...] --objective "我要从中确认什么"

# 需要原始 JSON 时加 --json
```

## 调研方法

1. **先拆问题**：把用户的问题拆成 3-5 个互不重叠的检索角度，一次 `search` 全发出去，别一条条试。
2. **看摘要选源**：检索结果只给标题 + 摘录，用它筛出真正相关的 3-5 个 URL。
3. **抓正文再下结论**：关键结论必须来自 `extract` 出的原文，不能只凭摘要。摘要与原文冲突时以原文为准。
4. **交叉验证**：重要事实（版本号、价格、API 契约、时间点）至少两个独立来源一致才当作事实；只有单一来源就标注「单来源，未交叉验证」。
5. **补一轮**：读完发现新的关键词或新的分歧点，再发一轮 `search`。通常两轮够。

## 输出

- 结论在前，证据在后。每条事实后面跟来源 URL。
- 明确区分「查到的事实」「多个来源的分歧」「我的推断」。
- 查不到就说查不到，给出已排除的方向，不要用似是而非的内容填充。
- 时效性强的话题（价格、版本、政策）注明来源日期。

## 失败处理

- 401 → key 取错了（大概率读了 `web-search.json`，没用 `flow-cred`）。
- 429 / 5xx → 报告状态码并停下，不要循环重试。
- 结果为空 → 换检索词重试一次；仍为空就如实说明。
