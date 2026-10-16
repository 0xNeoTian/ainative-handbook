# 第 0 步：清单与模板

`/ainative:new-project` 照这份清单逐步执行。占位符：`<slug>` 项目目录名（小写连字符），`<owner>` GitHub 用户或组织，`<org>` 组织名，`<date>` 今天的日期 `YYYY-MM-DD`。手册原文：https://ainative.jubao.ai/docs/tool 、https://ainative.jubao.ai/docs/product/day-0 、https://ainative.jubao.ai/docs/org

默认技术栈：Next.js（App Router）+ TypeScript + Tailwind CSS + bun。纯静态站部署到 Cloudflare；需要服务端能力的 Next.js 应用部署到 Vercel。

## 1. 各档位清单

每一步都标了是否会写文件。会写的步骤，执行前先给用户看要执行的命令或要写的内容，确认后再做。

### 小工具（30 分钟内完成）

| # | 做什么 | 命令 / 产物 | 写操作 |
|---|---|---|---|
| 1 | 体检当前环境（可选） | `/ainative:doctor` | 否 |
| 2 | 建目录和仓库 | `mkdir <slug> && cd <slug> && git init` | 是 |
| 3 | 忽略密钥文件 | `.gitignore` 写入第 2 节的片段 | 是 |
| 4 | 一页 CLAUDE.md | 第 3 节模板，删到一页以内 | 是 |
| 5 | 最小护栏 | 用户级 deny 规则（交给 `/ainative:setup` 合并），或 `/hookify 禁止提交 .env* 文件；禁止 git push --force 到 main` | 是 |
| 6 | 推到远端（可选） | `gh repo create <owner>/<slug> --private --source=. --push` | 是 |
| 7 | 动手前先出计划 | `Shift+Tab` 切到 Plan mode，确认计划后再改代码 | 否 |

### 产品

| # | 做什么 | 命令 / 产物 | 写操作 |
|---|---|---|---|
| 1 | 体检当前环境 | `/ainative:doctor` | 否 |
| 2 | 建项目 | `bun create next-app <slug> --ts --tailwind --app --use-bun --yes` 然后 `cd <slug>`（`--yes` 避免交互提问卡住；脚手架默认会初始化 git） | 是 |
| 3 | 检查 `.gitignore` | 确认含 `.env*`，没有就补第 2 节的片段 | 是 |
| 4 | 推到远端 | `gh repo create <owner>/<slug> --private --source=. --push` | 是 |
| 5 | 一页 CLAUDE.md | 第 3 节模板。脚手架已生成 CLAUDE.md 或 AGENTS.md 的，在原文件上改，不要覆盖 | 是 |
| 6 | 文档目录 | `mkdir -p docs/specs docs/plans docs/adr docs/runbooks docs/retros` | 是 |
| 7 | 流程引擎 | Matt：`/mattpocock-skills:setup-matt-pocock-skills`；superpowers：在 CLAUDE.md 写明 spec 和 plan 的路径（第 3 节） | 是 |
| 8 | 插件与护栏 | `/ainative:setup`（产品档） | 是 |
| 9 | 部署平台 | 用 `/ainative:recommend` 判断；静态站见第 6 节 | 视情况 |
| 10 | 第一份 spec | 先 `/mattpocock-skills:grill-me` 把需求问清楚（装了 Matt 时），再写 `docs/specs/<date>_<slug>.md`，第一节是 intent（第 4、5 节） | 是 |
| 11 | 可选 | 有界面的项目：`claude plugin marketplace add yannikzz/ui-contract` 后 `claude plugin install ui-contract@yannikzz --scope project`；想要一份自动推荐：`claude-code-setup` 插件扫描一次 | 是 |

### 组织（在产品档基础上）

| # | 做什么 | 命令 / 产物 | 写操作 |
|---|---|---|---|
| 1 | 建 ops 仓 | `gh repo create <owner>/<org>-ops --private --clone`，目录：`decisions/`（`ADR-NNN_<topic>.md`）、`playbooks/`、`research/`、`retros/` | 是 |
| 2 | 代码仓指向 ops 仓 | 代码仓 CLAUDE.md 写一行指针，用完整 URL，不用 `../` 相对链接 | 是 |
| 3 | 让会话读到 ops 仓 | 代码仓 `.claude/settings.json`：`"permissions": { "additionalDirectories": ["../<org>-ops"] }`（交给 `/ainative:setup` 合并） | 是 |
| 4 | 共用一份自动记忆 | 各仓库 `.claude/settings.local.json`：`"autoMemoryDirectory": "~/.claude/org-memory/<org>"` | 是 |
| 5 | 关键 deny 进托管设置 | 只给命令，由用户本人用管理员权限执行（见 setup 的 profiles.md 第 3.3 节） | 用户执行 |

## 2. `.gitignore` 片段

```gitignore
# 密钥与本地配置
.env*
!.env.example
.claude/settings.local.json
```

## 3. 一页 CLAUDE.md 模板

只放每次都要遵守的规则：技术栈、命令、工作方式、禁区、指针。细节放 `docs/`，这里只留指针。整页不超过一屏到两屏。

```markdown
# <项目名>

<一句话：这是什么，给谁用>

## 技术栈
- Next.js（App Router）+ TypeScript（strict）+ Tailwind CSS
- 包管理：bun
- 部署：<Vercel / Cloudflare>

## 常用命令
- 开发：`bun run dev`
- 构建：`bun run build`
- 类型检查：<例如 `bunx tsc --noEmit`>
- 测试：<例如 `bun test`>

## 工作方式
- 实质改动先写 spec（`docs/specs/YYYY-MM-DD_<slug>.md`，第一节是 intent），再按测试先行实现；一行级小修可以豁免，但要在提交说明里写一句
- 先用 Plan mode 出计划，我确认后再改代码
- 界面改动必须真的启动、亲眼看到效果才算完成
- 有人说"以前是这样的"，先查 git 历史再当成约束

## 禁区
- 不提交 `.env*`，密钥只放环境变量
- 不执行 `git push --force`、`git reset --hard`、`git rebase`、`git commit --amend`；需要时停下来问我
- 不手改 <锁文件 / 生成目录>

## 指针
- 规格与计划：`docs/specs/`、`docs/plans/`
- 架构决策：`docs/adr/`
- 运维手册：`docs/runbooks/`
```

按主引擎在"工作方式"里加一行：

- Matt：`实质改动先 /mattpocock-skills:to-spec，再 /mattpocock-skills:tdd`
- superpowers：`spec 写到 docs/specs/YYYY-MM-DD_<slug>.md，计划写到 docs/plans/YYYY-MM-DD_<slug>-plan.md，不要用 docs/superpowers/`

小工具档可以只留"技术栈、常用命令、禁区"三节。

## 4. intent 模板

```markdown
## Intent: <slug>

### 做什么（一句话）
### 为什么（谁的什么问题，为什么是现在）
### 约束（技术 / 合规 / 预算 / 时间）
### 不做什么
### 成功指标（上线后看哪个数）
### 来源（想法 / 工单 / 告警）
```

## 5. spec 骨架（`docs/specs/<date>_<slug>.md`）

```markdown
# <标题>

- 日期：<date>
- 状态：草稿
- 关联：<Issue 或 PR 链接>

## 1. Intent
（第 4 节的六个小节，必须先填完）

## 2. 需求
- <用户能做什么，按优先级排>

## 3. 设计
- <数据、接口、页面结构；拿不准的点列出来>

## 4. 验收标准
- 当 <触发条件> 时，系统应 <可观察的行为>
- 如果 <异常情况>，那么系统应 <可观察的行为>
- 在 <某个状态> 期间，系统应 <可观察的行为>

## 5. 风险与回滚
- <最可能出问题的地方，出问题怎么发现、怎么撤回>

## 6. 实现计划
见 `docs/plans/<date>_<slug>-plan.md`
```

## 6. 静态站部署到 Cloudflare

`next.config.mjs` 改成静态导出：

```js
/** @type {import('next').NextConfig} */
const nextConfig = { output: 'export' };
export default nextConfig;
```

项目根目录新建 `wrangler.jsonc`：

```jsonc
{
  "name": "<slug>",
  "compatibility_date": "<date>",
  "assets": { "directory": "./out" }
}
```

构建并发布（发布属于生产操作，执行前问用户）：

```bash
bun run build
bunx wrangler deploy
```

需要 SSR、Server Actions 或每个 PR 一个预览环境的，改用 Vercel，见 https://ainative.jubao.ai/docs/product/platform 。

## 7. 完成标准

- 仓库已建好（需要远端的已推到私有仓库）
- `.env*` 在 `.gitignore` 里，密钥只在环境变量里
- CLAUDE.md 不超过一页，里面没有任何密钥
- 至少一条护栏已生效（deny 规则或 hookify）
- 产品档：`docs/` 目录齐全，第一份 spec 的 intent 已填完；部署平台已选定
- 组织档：ops 仓已建好，代码仓 CLAUDE.md 用完整 URL 指向它
