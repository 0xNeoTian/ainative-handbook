# 推荐用的判定表

`/ainative:recommend` 用这些表做判断。每一项都给"一个推荐 + 一个替代"，并写清依据是查到的事实还是用户的回答。内容截至 2026-10，来自手册：https://ainative.jubao.ai/docs/tiers 、https://ainative.jubao.ai/docs/product/platform 、https://ainative.jubao.ai/docs/workflow

## 1. 先查事实，再问问题

能查到的自己查，查不到的才问。最多问 3 个问题。

| 要判断的 | 去哪查（只读） |
|---|---|
| 技术栈 | `package.json`（依赖里有没有 `next`、`react`）、`go.mod`、`pyproject.toml`、锁文件（`bun.lock` 说明用 bun） |
| 是不是纯静态 | `next.config.*` 里有没有 `output: 'export'`；有没有 `app/api/`、`route.ts`、`"use server"`、`middleware.ts` |
| 已选的平台 | `vercel.json` 或 `.vercel/` → Vercel；`wrangler.toml`、`wrangler.json`、`wrangler.jsonc` → Cloudflare |
| 有没有数据库 | `supabase/`、`prisma/`、`drizzle.config.*`、`docker-compose.yml` 里的数据库服务、环境变量模板里的 `DATABASE_URL` |
| 是否已有流程 | `docs/specs`、`docs/plans`、`docs/adr` 是否存在；CLAUDE.md 里有没有流程规则 |
| 当前引擎和插件 | `/ainative:doctor` 的 `plugins.items`（哪些 `enabled`）、`user_skills.suites` |
| 协作情况 | `git shortlog -sn --all \| head`（贡献者数量）；`.github/CODEOWNERS` |
| 仓库数量 | 用户的其他仓库要问，除非能看到同级目录里的相关仓库 |

查不到、只能问的通常是：有没有真实用户、要不要国内访问、有没有不写代码的协作者。

## 2. 档位

| 档位 | 判定信号 | 规则和文档放哪 |
|---|---|---|
| 小工具 | 一个人、一个仓库、没有长期用户 | README + 一页 CLAUDE.md |
| 产品 | 有真实用户、要持续迭代，通常一个仓库 | 仓库内 `docs/`：specs、plans、adr、runbooks、retros，加 `.claude/` |
| 组织 | 满足下面任意一条 | 独立 ops 仓 + 代码仓保留 spec、plan 和跟代码绑定的 runbook |

升到组织档的四个信号（任一即可）：

1. 同一组织有 2 个以上代码仓，需要共用规则和决策
2. 有不该让所有写代码的人看到的内容（权限、客户、商业、事故细节），或代码仓是 fork、将来要开源
3. 有不写代码的协作者（运营、市场、商务）
4. 有决策跨越多个代码版本长期有效

推荐与替代的写法：推荐给"符合信号的最低档"，替代给"再高一档"（并说明什么时候该升）。手册原则：小工具不需要 ops，组织不能只靠一个 CLAUDE.md。

## 3. 部署平台

| 情况 | 推荐 | 替代 |
|---|---|---|
| Next.js 全功能（SSR、ISR、Server Actions、图片优化），想要每个 PR 一个预览 | Vercel 跑应用，Cloudflare 管 DNS 等底座 | 全放 Cloudflare（OpenNext 适配），代价是 Next.js 新特性要等适配 |
| 纯静态（文档站、落地页、报告，`output: 'export'`） | Cloudflare（Workers 静态资源） | Vercel |
| 边缘 API、Webhook、定时任务、WebSocket、有状态 agent | Cloudflare Workers | 应用放 Vercel，这部分单独放 Workers |
| 大文件分发 | Cloudflare R2（没有流量费） | — |
| 需要国内访问、成本敏感 | 全放 Cloudflare | Vercel 应用 + Cloudflare 底座，接受访问速度的代价 |

两条硬规则：一个域名只挂一个平台（https://ainative.jubao.ai/docs/pitfalls/one-domain-one-platform ）；DNS 统一放 Cloudflare 管。

## 4. 流程引擎

| 情况 | 推荐 | 替代 |
|---|---|---|
| 默认（新项目、想先对齐再动手、希望 spec 和决策跨会话留在仓库里） | Matt Pocock skills（🧪 作者 2026-10 起的主引擎） | superpowers |
| 需要强制完整流程、经常让 agent 长时间自主运行、团队流程纪律弱 | superpowers（✅ 作者用了大半年（约 7 个月）） | Matt + CLAUDE.md 硬规则 + hook 补"强制" |
| 已经在用 superpowers 且满意 | 继续用 superpowers，别同时开 Matt | 按 https://ainative.jubao.ai/docs/workflow/migrate 迁移，30 天后用数据评估 |
| 有大量自建 SOP skill，不想被抢触发 | Matt（没有 hook，不自动注入） | superpowers，并在 CLAUDE.md 写清哪些任务走自建 skill |

两者的本质区别：superpowers 用 SessionStart hook 在会话开始时自动注入流程；Matt 没有 hook，靠你手动调用，强调"先对齐、再沉淀"。不管选哪个，同一时间只让一套自动接管：推荐用 `enabledPlugins` 按项目只启用一套；还想手动用另一套时，在 `permissions.deny` 加 `Skill(<插件名>:*)`。`skillOverrides` 对插件 skill 不生效（https://ainative.jubao.ai/docs/pitfalls/one-process-engine ）。

## 5. 插件组合

按档位和主引擎查 setup 的 `references/profiles.md` 第 2 节。推荐时只列"要装的"和"要停用的"，并给出一行理由。共同的停用建议：

- 第二个流程引擎
- `code-review` 插件（内置已有 `/code-review`）
- 重复的 Cloudflare 插件
- doctor 报告里长期 0 调用的插件

gstack（不是插件）：产品档以上可选，负责上线流水线与质量（`/qa`、`/ship`、`/review`、`/cso`、`/codex`、`/browse`），和主引擎重叠的流程类 skill 设为只能手动调用（https://ainative.jubao.ai/docs/workflow/gstack ）。

## 6. 护栏强度

| 强度 | 适用 | 内容 |
|---|---|---|
| 最小 | 小工具 | 5 条 deny（profiles.md 第 3.1 节）、`.env*` 进 `.gitignore`、至少 1 条 hookify 护栏 |
| 标准 | 产品 | 最小 + 项目 ask 规则（发布、删库、合并 PR）+ git 历史保护 + 有数据库时的自动备份 hook + 合并前异构模型二审 |
| 组织 | 组织 | 标准 + 关键 deny 进托管设置 + 定期护栏体检（`/schedule`）+ 共用规则做成插件继承，不复制 |

推荐与本档对应的强度，替代给高一档（风险高、有生产数据时）或低一档（一次性实验，并写明到期时间）。

## 7. 可以问的问题（最多 3 个，每题带推荐答案）

1. "这个项目现在或三个月内会有真实用户吗？"（推荐答案依据：有部署配置、有数据库 → 默认"会"）
2. "会不会有第二个代码仓或不写代码的协作者一起用这套规则？"（默认"不会"）
3. "需要在国内稳定访问吗？"（只在平台选择会因此改变时才问）

## 8. 输出示例

| 项 | 推荐 | 替代 | 理由（事实 / 回答） | 手册 |
|---|---|---|---|---|
| 档位 | 产品 | 组织（出现第二个仓库时） | 有 `wrangler.jsonc`、有读者，单仓库 | https://ainative.jubao.ai/docs/tiers |
| 平台 | Cloudflare 静态资源 | Vercel | `next.config.mjs` 静态导出，无服务端路由 | https://ainative.jubao.ai/docs/product/platform |
| 流程引擎 | Matt Pocock skills | superpowers | 新项目，希望 spec 留在仓库里 | https://ainative.jubao.ai/docs/workflow/superpowers-vs-matt |
| 插件组合 | mattpocock-skills + hookify + context7 + typescript-lsp | 只装 mattpocock-skills | TypeScript 项目 | https://ainative.jubao.ai/docs/reference/toolchain |
| 护栏强度 | 标准 | 最小 | 有部署、有读者 | https://ainative.jubao.ai/docs/guardrails |
