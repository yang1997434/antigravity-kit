---
name: frontend-check
description: 改 HTML / CSS / 模板 / 前端 JS 时的视觉自查流程：先加载 better-ui，沿用仓库已有 token，每条改动用 playwright 截 375 与 1280 两档、拼成联络表自己看一眼（一次运行读图 ≤ 20 张），对照仓库「禁用样式清单」，回报每条带截图路径。coder 的 brief 碰前端文件时第一步加载；主会话自己改前端时也照此做，截图派 checker 看、不自己 Read。
---

# 前端自查

按 brief 逐条做，不自造 token。

- 先读仓库 `CLAUDE.md` / `AGENTS.md` 里的前端规矩（一件作业一个画卡处、加入口先列旧入口、样例 slug 三处同改之类），再动手。
- 写法：动手前按改动涉及的能力（弹窗、表单、回车提交、动效、深色模式、HTML 消毒之类，一个能力查一次，2–5 个英文词、不带框架名和业务名）查 modern-web-guidance，照取回的指南写、按它的降级要求做；命令一律带 `DISABLE_TELEMETRY=1`（默认会把搜索词发给 Google）：`DISABLE_TELEMETRY=1 npx -y modern-web-guidance@latest search "<query>"`，再 `DISABLE_TELEMETRY=1 npx -y modern-web-guidance@latest retrieve "<id>[,<id>]"`。没合适的就照常写。用了哪篇在回报里写一行 id 和据它改了什么。仓里有 `.mwgrc`（浏览器范围）的照它。处理键盘回车提交时必须判 `event.isComposing`（中文输入法选词的回车不算提交）。
- 视觉：先加载 `better-ui` skill。沿用仓库已有的 CSS 变量、组件、字号、间距；动效走 CSS，克制。375px 手机宽与 1280px 桌面各看一遍，不许横向滚动、溢出、遮挡。逐项看：同一行元素对齐在一条线上、同排按钮同形同高、上层文字比下层大且深、卡片和背景一眼分得开。
- 仓库 `CLAUDE.md` 或 brief 里有「禁用样式清单」的，逐条对照，清单上的一条都不许出现。
- 每条改动做完必须渲图：Bash 驱动 `npx playwright` headless，截 375 与 1280 两档存到 `$TMPDIR`。
  - 自己看图一次运行最多 20 张（`subagent-budget.py` 钩子到数就拦，2026-11-09 定：同一批截图 coder、checker、reporter 各看一遍，coder 一次最多读过 48 张）。
  - 省着看的办法：自查用的图只截改动所在的那块（`locator.screenshot()`，不拿整页长图自查）；同一条改动的 375 和 1280 写进一个本地 HTML 并排，再截成一张联络表，Read 这一张确认没错位再进下一条；改完重截只重看改过的那条。
  - 给 checker 看的图按区块（`locator.screenshot()`）或一屏视口（`fullPage: false`）截，每条改动 375 和 1280 各一张，照样回路径，自己不逐张 Read——逐张细看是 checker 的事（主会话用本 skill 时全部交 checker，自己不 Read）。不给 checker 整页长图：375 宽的长页会被缩到几十像素宽、读不出字，固定定位的条在整页图里位置也是假的（2026-11-09 两个 checker 16 张里大半回「无法确认」）。遮挡、吸底、焦点这类和滚动位置有关的，一律截视口。整页图只在评审页要用时另截，路径单列。
  - 截图不贴进回复，只回路径；主会话派 checker 核对、交 reporter 放进评审页。
- 门禁：有 e2e 就跑与改动相关的 spec，不跑全量；其余照仓库规范门禁。
- 回报在 coder 的格式上多一列：每条 brief 对应的截图路径。
