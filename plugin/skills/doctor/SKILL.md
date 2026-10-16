---
name: doctor
description: "只读体检 Claude Code 环境和当前项目：插件与 skill 是否冗余或互相抢触发、权限规则和 hook 是否还在、配置是否被切换工具覆盖、.env 与密钥是否安全、CLAUDE.md 和 docs 是否到位，输出 P0/P1/P2 问题表和一推荐一替代的修复方案，不改任何东西。当用户说：体检、诊断、检查我的 Claude Code 配置、插件太多、skill 太多、护栏还在吗、为什么插件都没了、权限规则失效、doctor、audit setup、check my Claude Code config、health check、too many plugins 时使用。"
argument-hint: "[--days 90] [--project <路径>] [--no-usage]"
---

# 体检（只读）

按 AI Native 手册的标准，给本机的 Claude Code 配置和当前项目做一次只读体检，输出分级问题清单和修复建议。**不做任何修改**；要应用修复，交给 `/ainative:setup`。

手册最新的完整内容可读 https://ainative.jubao.ai/llms.txt （规则有疑问时以手册为准）。

## 何时使用

- 新电脑、新项目，或接手一个老项目时，先摸清现状
- 怀疑护栏失效：权限规则不拦了、hook 没反应、插件突然全关了
- 觉得插件、skill、subagent 太多，想按真实调用数据精简
- 用过模型供应商切换工具（CC Switch 这类）之后复查
- `/ainative:setup` 之前，先拿到事实

## 步骤

1. **运行采集脚本**（只读，约 1–3 秒）：

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/doctor/scripts/doctor.py" --days 90 --project "<当前工作目录的绝对路径>"
   ```

   - 用户给了 `--days N`、`--project <路径>`、`--no-usage`（不统计调用次数）、`--no-cli`（不调用 `claude` 命令）就原样传入
   - 如果命令里的路径没有被替换成真实路径，或提示文件不存在，先用 `ls "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/plugins/cache/*/ainative/*/skills/doctor/scripts/doctor.py` 定位脚本（有多个版本时取最新），不要猜路径
   - 需要 `python3`（3.8 及以上）。找不到时告诉用户怎么装，并停止体检，不要替用户安装
   - 脚本只输出 JSON，什么都不写

2. **读结果**：先看 `findings`、`summary`、`errors`，需要细节时再看对应的原始字段（`settings`、`hooks_state`、`plugins`、`user_skills`、`usage`、`project` 等）。`hooks_state.disabled` 为 `true` 时，配置里的 hook 都不会运行，即使脚本路径全部正常也不能说明护栏生效。`usage.unknown` 是没有对上任何已安装名字的调用，只有数量，没有名字。

3. **查规则**：逐条到 [references/rubric.md](references/rubric.md) 里按 `id` 取"为什么重要、怎么修、手册链接"。不要自己编修法；rubric 里没有的情况，写明"手册未覆盖"。

4. **补充判断**（按需）：
   - 结合 `project.signals` 判断项目档位（小工具/产品/组织），据此调整 `docs-layout` 这类项的严重度，并写明理由
   - 对 `unused-plugins` 里最可疑的 2–3 个，可以运行 `claude plugin details <插件@市场>`（只读）补充常驻 token 成本
   - `user_skills.suites.gstack` 大于 0 时，按 rubric「需要你自己判断的项」评估与主引擎的重叠

5. **按下面的格式输出报告**。

## 输出格式

```markdown
**一句话总结**：<最重要的 1–2 个问题 + 整体状态>

### 问题清单

| 级别 | 发现 | 为什么重要 | 怎么修 | 手册 |
|---|---|---|---|---|
| P0 | <具体发现，带证据：文件、规则、插件名、次数> | <一句话> | <可直接执行的命令或配置> | [卡片或页面](https://ainative.jubao.ai/docs/...) |
| P1 | … | … | … | … |
| P2 | … | … | … | … |

### 建议

- **推荐**：<一个方案，说清先做什么、再做什么>
- **替代**：<一个方案，以及什么情况下选它>

### 数据摘要

Claude Code <版本> · 插件 已装 <n> / 已启用 <n> · 个人 skill <n>（gstack <n>）· subagent <n> · 统计最近 <days> 天，扫描 <n> 个会话文件 · 耗时 <ms> ms

> 本次体检未做任何修改。要应用上面的修复，请运行 `/ainative:setup`。
```

写法要求：

- P0 在前；同一个 `id` 的多条证据合并成一行
- "怎么修"写成能直接执行的命令或配置片段，不写"建议优化"这类空话
- `info` 级别的观察在表格之后用一行列出
- 没有任何 P0/P1/P2 时，直接说明"未发现问题"，并给出下次体检的建议时机
- 推荐和替代各只给一个（选法见 rubric 末尾的对照表）
- 报告最后一行必须是"本次体检未做任何修改……"这句话

## 安全约束

- **只读**：不修改、不创建、不删除任何文件；不安装、不启用、不停用插件。用户中途说"顺便修了"，也先把报告写完，再引导到 `/ainative:setup`（setup 会先出计划、备份、等确认）
- **不碰对话内容**：调用次数只能来自脚本的统计结果。不要自己打开或搜索 `~/.claude/projects/` 下的会话文件
- **不泄露密钥**：脚本不输出 hook 命令全文（只给程序名、脚本路径和是否存在），env 和 MCP 配置只给键名，权限规则经过打码。报告里保持这种状态，不要去原文件里把值找回来
- 报告里的家目录统一写成 `~`
- 脚本报错或缺字段时，如实写进报告，不要用更"深"的方式补数据
- 隐私说明（用户问起时）：插件本身不联网、不上传任何数据。统计调用次数时，脚本逐行读取会话记录文件，但只解析事件元数据（Skill、Task 工具调用和斜杠命令事件），只输出已安装或内置的名字和次数，其他值只计总数，不输出、不保存任何对话内容；加 `--no-usage` 可以跳过。脚本输出会进入你当前的 Claude Code 会话，和让 Claude 读一个本地文件一样
