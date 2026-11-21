---
name: delegate
description: 在 Antigravity 中派子代理（invoke_subagent / run_workflow / swarm）、写 brief、组织 Swarm 接力与合并之前加载：三层编排选型、方案 B1 双池固定模型班底、并行与工作树规则、brief 小节、7 个专职角色细则与二审发现处置。Use before dispatching subagents, launching a workflow or swarm, or writing a brief.
---

# Antigravity 委派与 Swarm 协作细则

谁该派给谁看全局规则 `AGENTS.md`「委派」表；门禁、验收顺序、打回三次停下、`tasks.md`、批次收口也在那里。本手册管「怎么派」。

## 一、三层编排选型

1. **`invoke_subagent`（1–2 个轻量独立任务或串行接力）**：
   - `checker` 传 `Model: "flash"`，其余传 `Model: "inherit"`（或按角色默认）。
   - 并行改同一仓时设 `Workspace: "share"`（共享对象库、独立工作树），不能隔离就串行。
   - 派完后无需轮询，系统会在子代理回信时自动唤醒主会话。
2. **`run_workflow`（≥ 3 路清单扇出或多阶段批处理）**：
   - 先读内置 `run-workflow` skill，用 Python 脚本编排并行扇出与聚合。
   - 按互相独立的单元拆（一个文件簇、一个仓、一份文档），不按「计划 / 实现 / 测试」拆。
   - 跑门禁的阶段结构化校验 `check_passed`、`check_tail`、`unowned_files_touched`、`amendments`，按 `{done, failed}` 汇总返回，绝不用过滤丢掉失败项，主会话按 `failed` 重派。
3. **`swarm`（多模块并行开发、复杂代码攻坚、或 `coder ↔ tester / reviewer` 接力）**：
   - 无需等用户输 `/swarm`，主会话直接起 `swarm`（先读内置 `swarm` skill）。
   - 若用户当轮未另点名模型，按**方案 B1（Gemini 主力高质写码 + Claude 5.5 异构测试与二审）**传 `model`：
     - `coder`：`gemini-4-neon-high`（高难并发 / 算法 / 深重构升 `gemini-4-neon-xhigh`），`workspace: "share"`
     - `reviewer`：`claude-opus-5-5-high`（跨厂商顶配异构二审 + 独立 Claude 3p 配额池），`workspace: "inherit"`
     - `tester`：`claude-sonnet-5-5-high`（异构写可变红 E2E 测试 + 分摊配额），`workspace: "share"`
     - `researcher`：`gemini-4-neon-medium`，`workspace: "inherit"`
     - `worker` / `reporter`：`gemini-4-hydrogen-high`（需要完整继承主会话上下文时优先传 `fork: "coordinator"`）
     - `checker`：`gemini-3.8-flash-medium`，`workspace: "inherit"`
   - 成员交接时只 `@` 下一棒同行，仅在最终就绪、遇阻或需拍板时 `@coordinator`。
   - **kill 前必先落盘**：`swarm(action="kill")` 会永久删除 `share` / `branch` 工作树，必须先合并或拣选提交后再 kill。

## 二、并行隔离铁律

- 并行的 `coder` 不碰 lockfile、依赖声明、数据库迁移文件、跨包公共接口；需要改动时写进回报的「要主会话做的改动」（文件、原样、新样、理由），由主会话合并前串行改一次。
- 不使用 `git stash`；测试库、端口和临时目录各自隔离。

## 三、7 个专职角色细则

- **`coder`**：改 HTML / CSS / 模板 / 前端 JS 时，brief「要做」第一条写「加载 `frontend-check`」。一份 brief ≤ 8 条、一个文件簇（写进「只许改」），超了拆；单文件 ≤ 10 行主会话直接改。前端改动它只看自己拼的联络表并回报截图路径，主会话派 `checker` 对照定稿逐条核对；用户否掉的样式写进该仓「禁用样式清单」。
- **`tester`**：门禁绿后派，只给「验收」「接口约定」、diff 范围和测试环境，**不给「要做」和实现细节**；该仓须有「E2E 入口」一节；审阅留下的 spec 后提交，报的产品问题回派 `coder`。
- **`reviewer`**：只读、全新上下文，只给 diff 范围和要盯的风险，**不给 brief 理由和设计讨论**。
- **`researcher`**：多路一次派出；起服务、建测试库、压测的不派它，派 `coder` 或 `worker`。
- **`checker`**：带明确清单派，只回结论（一次派发 ≤ 20 张图，多图先拼联络表或拆分多个 `checker`）；要因果推理的归 `researcher`。
- **`worker`**：依赖主会话上下文的多步重活；Swarm 里优先 `fork: "coordinator"`，单路时在 brief 写全上下文。
- **`reporter`**：给提纲文件路径；本机默认产出结构化 Antigravity Artifact，有 `report-publish` 环境时发 `/_r/` 链接。

## 四、brief 小节模板

按需保留非空小节：`环境` / `为什么` / `已排除` / `接口约定` / `要做` / `只许改` / `验收` / `风险点` / `门禁` / `回报`。

- **环境**：写仓库绝对路径，第一步读该仓 `AGENTS.md` / `CLAUDE.md`。
- **已排除**：写否掉的做法和原因，防子代理再踩一遍。
- **要做**：每条带异常流。
- **只许改**：列具体文件或目录 glob，主会话核 diff 先 `git diff --name-only` 对清单。
- **验收**：逐条对应「要做」。
- **风险点**：≤ 8 条，只写代码推不出的（计费、配额、外部副作用、测试收集规则、上线含义），没核实的标「待 coder 核实」。

## 五、二审发现怎么处置

`reviewer` 的发现在收口时写清去向：已修的合成一句；误报 / 故意 / 不重要的逐条写为什么（均算「不修」）；误报和不重要的追加进该仓 `REVIEW.md` 末节，攒到三条同类就收进它的「别报」。
