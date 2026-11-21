# Antigravity Kit (`claude-stack` v2 + 3-Line Multi-Pool HUD)

一套开箱即用的 **Google Antigravity (`agy`) 全局工程配置包**：包含 **全屏无闪烁终端模式（`altscreen`）**、**3 行 4 列固定列宽多池 HUD 状态栏**、**高质低返工双池 Swarm 多模型分工（7 个原生子代理）**、**工程全局规则（`AGENTS.md`）**、**4 个轻量同步安全与提醒钩子** 以及 **10 个渐进式加载的 Antigravity 原生 Skills**。

---

## 一句话安装（直接发给你的反重力 AI）

```text
请读取 https://github.com/yang1997434/antigravity-kit 的 README.md，按照里面的「给反重力 AI 的直读安装规范」帮我把全局插件和 HUD 状态栏安装到本机并跑完验证。
```

或者手动在终端一行跑完：

```bash
git clone https://github.com/yang1997434/antigravity-kit.git /tmp/antigravity-kit && bash /tmp/antigravity-kit/install.sh && rm -rf /tmp/antigravity-kit
```

---

## 这套配置包含什么？

### 1. 全屏无闪烁渲染（`altscreen`）+ 3 行 4 列多池 HUD 状态栏（`hud/hud.mjs`）

默认开启 `"altScreenMode": "always"` 与 `"contextWindow": "512K"`。前 3 列严格锁定列宽并在输出阶段将空格转为 NBSP（`\u00a0`），杜绝数值跳变或终端折叠导致的左右晃动；默认针对浅底终端采用**加粗深墨色**高对比度调色板（可在 `~/.gemini/antigravity-cli/hud/config.json` 设 `{"theme": "dark"}` 切深色模式，也可配 `{"label": "Ultra"}` 自定义首格身份标签）：

```text
Ultra      ⋮ ctx      28% ⋮ cpu   13% ⋮ ▸Gemini ●○○○○  11% ↻3h04m · 周  3% ↻6d22h
high       ⋮ tok/s     71 ⋮ mem   64% ⋮  Claude ○○○○○   0% ↻4h57m · 周  1% ↻3d15h
Neon 4     ⋮ Cache  95.4% ⋮ disk  58% ⋮ 📁 ~/workspace/my-project  ⎇ main*  ⚙ 2 sub · 1 bg
```

- **第 1 列（身份与模型）**：订阅档位、思考程度（`low` / `medium` / `high` / `xhigh` / `max`）、精简模型名（`Neon 4`、`Carbon 4`、`Hydrogen 4`、`Opus 5.5`、`Sonnet 5.5`、`Flash 3.8`，按旗舰/主力/轻量分色）。
- **第 2 列（会话效率）**：上下文占比 `ctx %`、排除人工停顿的真实生成速率 `tok/s`、前缀缓存命中率 `Cache %`（冷缓存自动变暗提示）。
- **第 3 列（本机负载）**：实时 `cpu %`（冷启动 40ms 双采样，兼容 macOS / Linux）、`mem %`（macOS `vm_stat` + Linux `/proc/meminfo`）、`disk %`。
- **第 4 列（多池限额与工作区）**：
  - 用 `▸` 高亮标出**当前活跃模型正在消耗的配额池**；
  - 同时展示 **`Gemini` 池** 与 **`Claude (3p)` 第三方池** 的 **5 小时滚动已用百分比 + 重置倒计时 + 7 天周限占比 + 周限重置倒计时**（终端宽度 `< 88` 时自动收起非告警的周重置倒计时防折行；若未来出现独立 `Flash` 等第 3 池自动动态展示不丢桶）；
  - 目录缩写（支持 `repo:wt/<name>` 紧凑 worktree 展示）+ Git 分支与脏标记 `*` + 运行中的子代理/后台任务计数。

---

### 2. 高质低返工双池 Swarm 多模型分工（方案 B1 + 7 个 AGY 原生子代理）

以额度最充裕的 **Gemini 4 Neon** 为核心规划与写码主力，用独立的 **Claude 5.5 (3p) 配额池** 承担跨厂商异构测试与对抗二审，减少复杂代码返工并打破同模型思维盲区：

| 角色 | 职责边界 | 常驻 Swarm 模型分工 | 说明 |
| :--- | :--- | :--- | :--- |
| **主对话 (`Coordinator`)** | 澄清需求、架构规划、写 brief、核对 diff、跑最终门禁 | `gemini-4-neon-high`<br>*(超复杂架构可切 `xhigh`)* | 深度推理审题稳，减少源头走歪 |
| **`coder`** | 按 brief 写码、重构、补单测、跑门禁自查 | `gemini-4-neon-high`<br>*(复杂并发/算法升 `xhigh`)* | 独立 `share` 工作树，一次过门禁率高 |
| **`reviewer`** | 计费/权限/支付/删除/迁移/并发的**对抗式找茬二审** | **`claude-opus-5-5-high`** | 跨厂商顶配挑刺 + 走独立 Claude 3p 池 |
| **`tester`** | 只拿验收与接口约定、写可变红 E2E spec 独立验行为 | **`claude-sonnet-5-5-high`** | 跨厂商异构找边界 + 分摊 Gemini 配额 |
| **`researcher`** | 只读审计、跨模块追根因（严禁改文件） | `gemini-4-neon-medium` | 调用链追得深、证据带 `file:line` |
| **`worker` / `reporter`** | 多步重活 / 结构化 Artifact（或 HTML）汇报 | `gemini-4-hydrogen-high` | 需主会话上下文的重活优先 `fork: "coordinator"` |
| **`checker`** | 看截图对照清单、核日志/服务/CI 状态 | `gemini-3.8-flash-medium`<br>*(单路 `invoke_subagent` 用 `flash`)* | 不漏截图细节、高速低成本 |

---

### 3. 全局工程规则（`rules/AGENTS.md`）+ 4 个轻量同步钩子 + 10 个原生 Skills

- **全局规则 (`rules/AGENTS.md`)**：聚焦目标与外在行为的可读性汇报、开头一句话落点与拍板置顶、单作者仓自动提交/推主干/合并、跨会话到期任务登记、调 Bug 先造变红复现、文档与代码冲突以代码为准、改行为必补可变红单测。
- **4 个 Antigravity 同步钩子 (`hooks.json`)**：
  - `gate-log-guard.py`（`PreToolUse: run_command`）：防 `pytest | tail` 等管道吞测试退出码，自动改写为 `pipefail + tee`。
  - `due-tasks.py`（`SessionStart` + `PreInvocation`）：扫描 `~/.gemini/due/<YYYY-MM-DD>-<名>.md`，跨会话原子认领到期任务并带 `.ack` 防丢重试。
  - `bg-shell-guard.py`（`PreToolUse: run_command`）：在 Rex 会话内拦截 `deploy/migrate/rsync/ffmpeg` 等中断有代价的后台命令，提醒放 Rex `jobs`。
  - `agent-image-guard.py`（`PreToolUse: invoke_subagent|run_workflow|swarm`）：拦截重型模型批量看截图，强制分流给 `checker`（`flash`）。
- **10 个按需渐进加载的 AGY 原生 Skills (`skills/`)**：`delegate`、`merge-rules`、`brainstorming`、`deep-research`（基于内置 `search_web` 的多跳交叉验证）、`better-ui`、`frontend-check`、`retro`、`agent-browser`、`agent-desktop`、`rex`。

---

## 给反重力 AI 的直读安装规范（AI-Readable Setup Spec）

> **致正在阅读本文档的 Antigravity AI Agent**：当用户要求你读取本仓库并安装配置时，请严格按以下 5 步执行（不要覆盖用户已有的其他配置项）：

1. **拉取仓库到临时目录**（收尾必须删除该临时目录）：
   ```bash
   tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/agy-kit.XXXXXX")"
   git clone --depth 1 https://github.com/yang1997434/antigravity-kit.git "$tmpdir"
   ```
2. **安装 `claude-stack` 全局插件**：
   - 将 `"$tmpdir/plugins/claude-stack"` 完整复制到 `~/.gemini/config/plugins/claude-stack`（**绝不要**改动用户原有的 `~/.gemini/config/hooks.json` 或 `mcp_config.json`）。
3. **安装 HUD 状态栏脚本**（要求 Node.js >= 18）：
   - 将 `"$tmpdir/hud/hud.mjs"` 和 `"$tmpdir/hud/test_hud.mjs"` 复制到 `~/.gemini/antigravity-cli/hud/`，并执行 `chmod +x ~/.gemini/antigravity-cli/hud/hud.mjs`。
   - 深色背景终端在 `~/.gemini/antigravity-cli/hud/config.json` 写入 `{"theme": "dark"}`；浅色背景无需配置。
4. **无损合并 `~/.gemini/antigravity-cli/settings.json`**：
   - 保留用户原有的 `model`、`trustedWorkspaces` 等所有字段，仅写入/更新 `altScreenMode: "always"`、`contextWindow: "512K"` 与 `statusLine`。
5. **跑完全部门禁验证并清理临时目录**：
   ```bash
   for t in ~/.gemini/config/plugins/claude-stack/hooks/test_*.py; do python3 "$t"; done
   node --test ~/.gemini/antigravity-cli/hud/test_hud.mjs
   agy plugin validate ~/.gemini/config/plugins/claude-stack --strict
   rm -rf "$tmpdir"
   ```
   全部退出码为 `0` 后，提示用户重启一次 `agy`（如退出后运行 `agy -c`）即可生效。
