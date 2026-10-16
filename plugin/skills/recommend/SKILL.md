---
name: recommend
description: "根据当前项目的真实情况推荐档位（小工具/产品/组织）、部署平台（Vercel/Cloudflare）、流程引擎（Matt Pocock skills/superpowers）、插件组合和护栏强度；每项给一个推荐、一个替代，附理由和手册链接。先自己查项目事实，只对查不到的问 1–3 个问题，只读不改。当用户说：推荐、我该用什么、该装哪些插件、选哪个平台、Vercel 还是 Cloudflare、这个项目算哪一档、要不要换流程引擎、Matt 还是 superpowers、recommend、which plugins should I use、what tier is this project 时使用。"
argument-hint: "[项目路径]"
---

# 推荐方案（只读）

根据项目事实给出五项推荐：档位、部署平台、流程引擎、插件组合、护栏强度。每项**一个推荐 + 一个替代**，不平铺多个选项。

手册最新的完整内容可读 https://ainative.jubao.ai/llms.txt 。判定规则见 [references/decision-tables.md](references/decision-tables.md)。

## 何时使用

- 开新项目前，定档位、平台和流程
- 老项目想知道"现在这套配置合不合适"
- 犹豫要不要从 superpowers 换到 Matt Pocock skills
- `/ainative:new-project` 和 `/ainative:setup` 之前，先拿到建议

## 步骤

1. **查事实**（只读）：按 decision-tables.md 第 1 节逐项查，例如读 `package.json`、`next.config.*`、`vercel.json`、`wrangler.*`、`docs/` 目录、贡献者数量。需要插件和 skill 现状时，运行：

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/doctor/scripts/doctor.py" --days 90 --project "<项目绝对路径>"
   ```

   找不到脚本时用 `ls "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/plugins/cache/*/ainative/*/skills/doctor/scripts/doctor.py` 定位。

2. **只问查不到的**：最多 3 个问题，一次问完，每题附上你的推荐答案（见第 7 节），用户回"是"即可采纳。所有事实都查得到时，不问问题。

3. **逐项判定**：按第 2–6 节的表给出推荐和替代。每条理由标明依据：`事实：<文件或命令>` 或 `回答：<用户说的>`。表里没有覆盖的情况，写"手册未覆盖"，并给出你的判断和理由。

4. **输出**，然后告诉用户下一步。

## 输出格式

```markdown
**结论**：<一句话，例如"产品档，Cloudflare 静态部署，Matt Pocock skills 为主引擎，标准护栏">

| 项 | 推荐 | 替代 | 理由 | 手册 |
|---|---|---|---|---|
| 档位 | … | … | 事实：… | https://ainative.jubao.ai/docs/tiers |
| 部署平台 | … | … | … | https://ainative.jubao.ai/docs/product/platform |
| 流程引擎 | … | … | … | https://ainative.jubao.ai/docs/workflow/superpowers-vs-matt |
| 插件组合 | 装：…；停用：… | … | … | https://ainative.jubao.ai/docs/reference/toolchain |
| 护栏强度 | … | … | … | https://ainative.jubao.ai/docs/guardrails |

**什么情况下改选替代方案**：<1–3 条触发条件，例如"出现第二个代码仓时升到组织档">

**下一步**：新项目运行 `/ainative:new-project`；已有项目运行 `/ainative:setup`（会先出计划、等你确认）。
```

## 安全约束

- 只读：不创建、不修改任何文件，不安装插件，不执行部署或任何有副作用的命令
- 不读取 `~/.claude/projects/` 下的会话记录；需要调用数据时只用 doctor 脚本的统计
- 不在输出里引用 `.env` 等文件中的密钥值；判断"有没有数据库"只看文件名和变量名
- 每项最多一个推荐、一个替代；不要为了显得全面而罗列更多选项
- 可信度照实写：Matt Pocock skills 标 🧪（作者试用中），superpowers 标 ✅（作者用过大半年（约 7 个月），已停用），作者没用过的标 📚
