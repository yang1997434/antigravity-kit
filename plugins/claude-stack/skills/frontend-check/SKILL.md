---
name: frontend-check
description: 改 HTML / CSS / 模板 / 前端 JS 时的视觉自查流程：先加载 better-ui，沿用仓库已有 token，每条改动用 playwright 截 375 与 1280 两档、拼成联络表自己看一眼（一次运行读图 ≤ 20 张），对照仓库「禁用样式清单」，回报每条带截图路径。coder 的 brief 碰前端文件时第一步加载；主会话自己改前端时也照此做，截图派 checker 看、不自己逐张读图。
---

# 前端自查

按 brief 逐条做，不自造 token。

- 先读仓库 `AGENTS.md` / `CLAUDE.md` 里的前端规矩与设计 token，再动手。
- 写法：动手前按改动涉及的能力（弹窗、表单、回车提交、动效、深色模式、HTML 消毒之类，一个能力查一次，2–5 个英文词、不带框架名和业务名）可按需查 modern-web-guidance；命令带 `DISABLE_TELEMETRY=1`：`DISABLE_TELEMETRY=1 npx -y modern-web-guidance@latest search "<query>"`。处理键盘回车提交时必须判 `event.isComposing`（中文输入法选词的回车不算提交）。
- 视觉：先加载 `better-ui` skill。沿用仓库已有的 CSS 变量、组件、字号、间距；动效走 CSS，克制。375px 手机宽与 1280px 桌面各看一遍，不许横向滚动、溢出、遮挡。逐项看：同一行元素对齐在一条线上、同排按钮同形同高、上层文字比下层大且深、卡片和背景一眼分得开。
- 仓库规则或 brief 里有「禁用样式清单」的，逐条对照，清单上的一条都不许出现。
- 每条改动做完必须渲图：用 `npx playwright` headless 截 375 与 1280 两档存到独立临时目录。
  - 自己看图一次运行严格控制在 ≤ 20 张。
  - 省着看的办法：自查用的图只截改动所在区块（`locator.screenshot()`，不拿整页长图自查）；同一条改动的 375 和 1280 拼进一张本地联络表，只读这一张确认没错位再进下一条；改完重截只重看改过的那条。
  - 给 `checker` 看的图按区块（`locator.screenshot()`）或一屏视口（`fullPage: false`）截，每条改动 375 和 1280 各一张，回报路径，自己不逐张细看——逐张核对是 `checker` 的事（主会话用本 skill 时全部交 `checker`，触发 `agent-image-guard.py` 规范分流）。遮挡、吸底、焦点这类和滚动位置有关的，一律截视口。整页图只在评审页要用时另截，路径单列。
  - 截图不贴进回复，只回路径；主会话派 `checker` 核对，需要评审时交 `reporter` 放进 Artifact 或评审页。
- 门禁：有 E2E 就跑与改动相关的 spec，不跑全量；其余照仓库规范门禁。
- 回报在 `coder` 的格式上多一列：每条 brief 对应的截图路径。
