---
name: new-project
description: "按 AI Native 手册的第 0 步起一个新项目：确定档位和技术栈（默认 Next.js + TypeScript + Tailwind + bun，纯静态站部署到 Cloudflare），然后逐步建仓库、写一页 CLAUDE.md、建 docs 目录、写第一份以 intent 开头的 spec、配最小护栏；每个写操作前都先确认。当用户说：新项目、起个项目、开个新仓库、从零开始、初始化项目、搭脚手架、第 0 步、new project、start a new repo、bootstrap a project、scaffold、day 0 时使用。"
argument-hint: "[项目名] [tool|product|org]"
---

# 新项目：第 0 步

按档位把新项目的骨架和护栏在第一天配好：仓库、一页 CLAUDE.md、`.gitignore`、文档目录、第一份 spec、最小护栏。**每个写操作执行前都先展示命令或内容，等用户确认。**

手册最新的完整内容可读 https://ainative.jubao.ai/llms.txt 。清单和模板见 [references/day0.md](references/day0.md)。

## 何时使用

- 要从零开始一个新项目或新仓库
- 想照着手册把一个空仓库补齐第 0 步
- 组织档：新开一个代码仓，需要接上 ops 仓

## 步骤

1. **定档位和技术栈**
   - 用户给了项目名和档位就用；没给就问。不确定档位时，先按 `/ainative:recommend` 的方法判断（或直接调用它）
   - 默认技术栈：Next.js（App Router）+ TypeScript + Tailwind CSS + bun。纯静态站（文档、落地页、报告）部署到 Cloudflare；需要 SSR、Server Actions、PR 预览的部署到 Vercel
   - 确认工作目录：新项目建在哪个父目录下，目录名 `<slug>` 是什么。目标目录已存在且非空时，停下来问，不要覆盖
   - 确认主引擎：默认 Matt Pocock skills（🧪），用户在用 superpowers 就按 superpowers（✅）

2. **展示清单**：从 day0.md 第 1 节取对应档位的清单，把占位符换成真实值，整体给用户看一遍，说明哪些步骤会写文件。用户可以删减步骤。

3. **逐步执行**：一次做一步。
   - 写操作（建目录、`git init`、脚手架、写文件、`gh repo create`、改设置）执行前，展示具体命令或完整文件内容，等用户确认
   - 用户说"后面的都直接做"时，可以连续执行剩下已列出的步骤，但遇到推送到远端、改用户级设置、发布这三类操作仍要单独确认
   - 每步完成后报告结果；失败就停下，说明原因和建议，不要跳过继续

4. **生成一页 CLAUDE.md**：用 day0.md 第 3 节模板，按项目的真实命令填好；按主引擎加那一行流程规则。脚手架已生成 CLAUDE.md 或 AGENTS.md 时，在原文件上补充，不要覆盖。

5. **写第一份 spec**（产品档、组织档）：
   - 装了 mattpocock-skills 时，建议先运行 `/mattpocock-skills:grill-me` 把需求问清楚，再写 spec
   - 文件：`docs/specs/<今天的日期>_<slug>.md`，用 day0.md 第 5 节骨架，第一节 intent 的六个小节先填完；用户没答上来的小节写"待定"，不要替用户编
   - 小工具档可以跳过 spec，只在 CLAUDE.md 里写清要做什么

6. **配最小护栏**：交给 `/ainative:setup`（它会先出计划、备份、等确认）；或者用户只要一条 hook 时，提示运行 `/hookify 禁止提交 .env* 文件；禁止 git push --force 到 main`。

7. **收尾**：按 day0.md 第 7 节逐项核对，输出结果。

## 输出格式

```markdown
## 第 0 步完成情况：<项目名>（<档位>）

| 步骤 | 状态 | 产物 |
|---|---|---|
| 建仓库 | ✅ | `<路径>` |
| .gitignore | ✅ | 含 `.env*` |
| CLAUDE.md | ✅ | <n> 行 |
| docs 目录 | ✅ / 跳过 | … |
| 第一份 spec | ✅ / 待写 | `docs/specs/<date>_<slug>.md` |
| 护栏 | ✅ / 待确认 | … |

**还没做的**：<列出跳过或失败的步骤>
**下一步**：<例如"用 Plan mode 出第一版实现计划"或"运行 /ainative:setup 配插件和护栏">
```

## 安全约束

- 每个写操作先确认；推送到远端、修改用户级设置（`~/.claude/settings.json`）、发布部署，即使用户说过"都直接做"也要单独确认
- 不覆盖已存在的非空目录和已有文件；要改已有文件时，展示 diff 再写
- 仓库默认建成私有（`--private`）；要公开仓库必须用户明确说
- 不把任何密钥写进 CLAUDE.md、spec、设置文件或代码；需要密钥时只写环境变量名，并提示用户自己设置
- 设置文件的修改交给 `/ainative:setup` 和它的 `merge_settings.py`，这里不直接编辑 `settings.json`
- 不执行 `git push --force`、`git reset --hard` 之类改写历史的命令
