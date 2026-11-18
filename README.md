# Antigravity Kit (`claude-stack` + 3-Line HUD)

一套开箱即用的 **Google Antigravity (`agy`) 全局工程配置包**：包含 **全屏无闪烁终端模式（`altscreen`）**、**3 行 4 列高对比度实时 HUD 状态栏**、**黄金混搭多模型分工（Swarm + 7 个专职子代理）**、**工程铁律全局规则（`AGENTS.md`）**、**8 个渐进式加载 Skills** 以及 **测试门禁防吞退出码钩子**。

---

## 一句话安装（直接发给你的反重力 AI）

你不需要手动改任何配置文件，直接打开你的 Antigravity，复制下面这句话发给它即可自动装好并完成自检：

```text
请读取 https://github.com/yang1997434/antigravity-kit 的 README.md，按照里面的「给反重力 AI 的直读安装规范」帮我把全局插件和 HUD 状态栏安装到本机并跑完验证。
```

或者手动在终端一行跑完：

```bash
git clone https://github.com/yang1997434/antigravity-kit.git /tmp/antigravity-kit && bash /tmp/antigravity-kit/install.sh && rm -rf /tmp/antigravity-kit
```

---

## 这套配置包含什么？

### 1. 全屏无闪烁渲染（`altscreen`）+ 3 行 4 列固定列宽 HUD 状态栏（`hud/hud.mjs`）

默认开启终端备用屏幕全屏渲染（`"altScreenMode": "always"`，对齐 Claude Code 的 `/tui fullscreen`，支持鼠标滚轮滚动、独立滚动条、点击直接展开工具调用与思考块，彻底告别长会话闪烁）。同时替换默认单行底栏，前 3 列严格锁定列宽（数值从 `9%` 跳到 `100%` 绝不左右晃动），默认针对浅底终端采用**加粗深墨色**高对比度调色板（可在 `~/.gemini/antigravity-cli/hud/config.json` 设 `{"theme": "dark"}` 切深色模式）：

```text
Ultra      ⋮ ctx      28% ⋮ cpu   13% ⋮ Gemini ●○○○○  11% ↻3h00m · 周  3%
medium     ⋮ tok/s     61 ⋮ mem   64% ⋮ Claude ○○○○○   0% ↻4h53m · 周  0%
Carbon 4   ⋮ Cache  94.3% ⋮ disk  58% ⋮ 📁 ~/workspace/my-project  ⎇ main*  ⚙ 2 sub · 1 bg
```

- **第 1 列（身份与模型）**：当前订阅档位（如 `Ultra` / `Pro`）、思考程度（`low` / `medium` / `high` / `xhigh`）、精简模型名（如 `Carbon 4`）。
- **第 2 列（会话效率）**：上下文窗口占比 `ctx %`、排除人工阅读停顿后的真实生成速率 `tok/s`、前缀缓存命中率 `Cache %`（越高越绿，闲置超 1 小时变暗提示缓存已冷）。
- **第 3 列（本机负载）**：实时 `cpu %`（支持事件触发冷启动 40ms 双采样，不显示空横杠）、`mem %`（macOS 活动监视器算法）、`disk %`。
- **第 4 列（双池限额与工作区）**：
  - 同时展示 **`Gemini` 池** 与 **`Claude (3p)` 第三方池** 的 **5 小时滚动已用百分比 + 重置倒计时 + 7 天周限额占比**（若触发周限自动橙色高亮）；
  - 当前目录缩写 + Git 分支与脏标记 `*` + 正在运行的子代理/后台任务数（空闲时自动隐藏任务后缀）。

---

### 2. 黄金混搭多模型分工（智能默认 Swarm + 7 个专职子代理）

充分利用 Google 官方模型定位（**Carbon 做规划主脑、Hydrogen 氢模型做执行主力、Flash 做轻量核对**）以及个人订阅账号**互相独立的 `Gemini` 池与 `Claude (3p)` 池**：

| 角色 | 职责边界 | 默认模型分工 | 优势 |
| :--- | :--- | :--- | :--- |
| **主对话 (`Coordinator`)** | 澄清需求、架构规划、写 brief、核对 diff、跑最终门禁 | `Gemini 4 Carbon (Medium/High)` | 审题稳、不阻塞，随时响应你的插话 |
| **`coder` / `tester` / `worker` / `reporter`** | 按 brief 写码自查、写能变红的 E2E spec、通用重活、图文汇报 | Swarm: `gemini-4-hydrogen-high`<br>*(复杂并发/算法升 `xhigh`)* | 代码执行快且准，独立 `share` 工作树互不冲突 |
| **`reviewer`** | 计费/权限/并发/迁移等关键改动的**对抗式找茬二审** | Swarm: **`claude-opus-4-6-thinking`** | **跨厂商异构挑刺**（避免同模型思维盲区）+ **走独立 Claude 配额池，不占 Gemini 额度** |
| **`researcher`** | 只读查代码、跨模块追根因（严禁改文件） | Swarm: `gemini-4-hydrogen-medium` | 快速定位证据（带 `file:line`） |
| **`checker`** | 看截图对照清单、核日志/服务/CI 状态 | `gemini-3.8-flash-low`（单调 `flash`） | 秒回、最省配额 |

- **智能默认触发规则**：单文件 `≤ 10` 行顺手小改由主会话直接完成；1–2 个简单独立任务走单子代理；**多模块并行开发，或需要 `coder ↔ tester / reviewer` 写码+二审接力的任务，无需手动敲 `/swarm`，主会话自动拉起 Swarm 分工**（按 `Alt + S` 或输 `/swarm board` 可随时打开实时蜂群看板）。

---

### 3. 工程全局规则（`rules/AGENTS.md`）+ 门禁钩子 + 8 个 Skills

- **全局规则 (`AGENTS.md`)**：拍板事项置顶（附建议、理由、默认做法）、发现问题必写去向、调 Bug 先造变红复现命令并列可证伪假设、文档与代码冲突以代码为准、改行为必补变红单测。
- **门禁防吞退出码钩子 (`hooks/gate-log-guard.py`)**：拦截 `run_command` 中 `pytest | tail`、`npm test | head` 等会吞掉测试失败退出码的管道，自动改写为 `( set -o pipefail; <cmd> 2>&1 | tee ~/.cache/claude-gate-log/...log | tail ... )`。
- **8 个按需渐进加载 Skills (`skills/`)**：`brainstorming`、`deep-research`、`better-ui`、`frontend-check`、`retro`、`agent-browser`、`agent-desktop`、`rex`（平时只加载简短描述，不占上下文）。

---

## 给反重力 AI 的直读安装规范（AI-Readable Setup Spec）

> **致正在阅读本文档的 Antigravity AI Agent**：当用户要求你读取本仓库并安装配置时，请严格按以下 5 步执行（不要覆盖用户已有的其他配置项）：

1. **克隆仓库到临时目录**（收尾必须删除该临时目录）：
   ```bash
   tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/agy-kit.XXXXXX")"
   git clone --depth 1 https://github.com/yang1997434/antigravity-kit.git "$tmpdir"
   ```
2. **安装 `claude-stack` 全局插件**：
   - 目标路径：`~/.gemini/config/plugins/claude-stack`
   - 将 `"$tmpdir/plugins/claude-stack"` 完整复制到 `~/.gemini/config/plugins/claude-stack`（若用户已有同名目录，先用 `cp -R` 备份再替换；**绝不要**改动用户原有的 `~/.gemini/config/hooks.json` 或 `mcp_config.json`）。
3. **安装 HUD 状态栏脚本**（前置检查本机已装 `node`，要求 Node.js >= 18）：
   - 目标路径：`~/.gemini/antigravity-cli/hud/`
   - 将 `"$tmpdir/hud/hud.mjs"` 和 `"$tmpdir/hud/test_hud.mjs"` 复制进去，并执行 `chmod +x ~/.gemini/antigravity-cli/hud/hud.mjs`。
   - 如果用户的终端是**深色背景**（可询问用户或检查其现有 `theme` 配置），在 `~/.gemini/antigravity-cli/hud/config.json` 写入 `{"theme": "dark"}`；浅色背景无需额外配置。
4. **无损合并 `~/.gemini/antigravity-cli/settings.json`**：
   - 先用 `cp` 备份原文件（若存在），读取原 JSON 对象，**保留用户原有的 `model`、`trustedWorkspaces` 等所有字段**，仅写入/更新以下字段后写回并删除 `.bak`：
     ```json
     {
       "altScreenMode": "always",
       "contextWindow": "512K",
       "statusLine": {
         "type": "command",
         "command": "node ~/.gemini/antigravity-cli/hud/hud.mjs",
         "enabled": true,
         "padding": 0,
         "stack_with_default": false
       }
     }
     ```
5. **跑完三道门禁验证并清理临时目录**：
   ```bash
   python3 ~/.gemini/config/plugins/claude-stack/hooks/test_gate_log_guard.py -v
   node --test ~/.gemini/antigravity-cli/hud/test_hud.mjs
   agy plugin validate ~/.gemini/config/plugins/claude-stack --strict --json
   rm -rf "$tmpdir"
   ```
   全部退出码为 `0` 且 `validate` 为 `0 errors` 后，提示用户重启一次 `agy`（如退出后运行 `agy -c` 续接当前会话）即可同时生效全屏无闪烁模式（`altscreen`）、新 HUD 与全套子代理。

---

## 目录结构

```text
antigravity-kit/
├── install.sh                          # 一键安装与门禁自检脚本
├── hud/
│   ├── hud.mjs                         # 3 行 4 列固定宽度 HUD 状态栏
│   └── test_hud.mjs                    # HUD 单元测试（node --test）
└── plugins/
    └── claude-stack/
        ├── plugin.json                 # Antigravity 插件清单
        ├── hooks.json                  # PreToolUse(run_command) 门禁钩子配置
        ├── rules/
        │   └── AGENTS.md               # 全局工程与委派规则
        ├── agents/                     # 7 个原生注册专职子代理
        │   ├── checker.md              # 机械核对 (flash)
        │   ├── coder.md                # 写码与门禁自查
        │   ├── reporter.md             # 图文汇报页
        │   ├── researcher.md           # 只读调研与根因追踪
        │   ├── reviewer.md             # 对抗式二审
        │   ├── tester.md               # 可变红 E2E 测试验证
        │   └── worker.md               # 通用多步重活
        ├── hooks/
        │   ├── gate-log-guard.py       # 防 | tail 吞测试退出码钩子
        │   └── test_gate_log_guard.py  # 钩子单元测试
        └── skills/                     # 8 个渐进加载技能包
            ├── agent-browser/
            ├── agent-desktop/
            ├── better-ui/
            ├── brainstorming/
            ├── deep-research/
            ├── frontend-check/
            ├── retro/
            └── rex/
```
