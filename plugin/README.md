# ainative：AI Native 手册的 Claude Code 插件

[AI Native 手册](https://ainative.jubao.ai) 的配套插件。装好之后，Claude 可以按手册的方法帮你做六件事：给环境体检、按档位配置工具链、推荐方案、起新项目、拿坑库审查改动、把复盘提炼成坑卡。插件刚发布，🧪 试用中。

## 安装

```bash
claude plugin marketplace add https://ainative.jubao.ai/marketplace.json
claude plugin install ainative@ainative
```

装完重启 Claude Code。体检和配置用到的两个脚本需要 `python3`（3.8 及以上，只用标准库）。

更新与卸载：

```bash
claude plugin marketplace update ainative
claude plugin update ainative@ainative
claude plugin uninstall ainative@ainative
```

## 六个 skill

| 调用 | 做什么 | 会不会改你的东西 |
|---|---|---|
| `/ainative:doctor` | 体检：插件和 skill 是否冗余或互相抢触发、权限规则和 hook 是否还在、配置有没有被切换工具覆盖、`.env` 和密钥是否安全、项目文档是否齐全；输出 P0/P1/P2 问题表 | 只读 |
| `/ainative:setup` | 按档位（小工具/产品/组织）和主引擎（Matt Pocock skills 或 superpowers）装好推荐插件、合并权限规则和 hook、设置 skill 开关 | 会改，但先出计划、先备份，等你确认后才执行 |
| `/ainative:recommend` | 根据项目情况推荐档位、部署平台、流程引擎、插件组合和护栏强度，每项一个推荐、一个替代 | 只读 |
| `/ainative:new-project` | 按档位走完第 0 步：建仓库、一页 CLAUDE.md、第一份 spec、最小护栏 | 会改，每个写操作先确认 |
| `/ainative:pitfall-check` | 用坑库逐条审查计划、spec 或分支改动，只报告真正命中的问题 | 只读 |
| `/ainative:harvest` | 把一篇复盘提炼成坑卡草稿，并做脱敏检查 | 只把草稿写到你指定的目录 |

## 用法示例

```text
/ainative:doctor
/ainative:doctor --days 30 --no-usage
/ainative:recommend
/ainative:setup product matt
/ainative:new-project my-tool tool
/ainative:pitfall-check main...HEAD
/ainative:harvest docs/retros/2026-10-16_deploy-failure.md ./pitfall-drafts
```

也可以直接用自然语言，例如"帮我体检一下 Claude Code 配置""这个分支合并前用坑库查一遍"。

## 隐私与安全

- **不联网、不上传**：插件没有 hook、没有 MCP 服务器，不会在后台运行，只在你或 Claude 调用某个 skill 时执行。脚本的输出会进入你当前的 Claude Code 会话，和让 Claude 读一个本地文件一样
- **体检只读**：统计调用次数时，脚本逐行读取本机的会话记录文件，但只解析事件元数据（Skill、Task 工具调用和斜杠命令事件）；只输出已安装或内置的 skill、命令、agent 名字和次数，其他值只计总数，**不输出、不保存任何对话内容**。加 `--no-usage` 可以完全跳过这一步。hook 只报告程序名、脚本路径和脚本是否存在，不输出命令全文；环境变量和 MCP 配置只输出键名；权限规则会打码
- **写操作先确认**：setup、new-project、harvest 都先给出计划，等你明确同意才执行
- **改设置前先预演、先备份**：setup 通过 `merge_settings.py` 合并设置：严格校验 JSON 和字段类型，只追加、不删除，冲突时默认保留你的值，覆盖只能按你点名的字段逐个授权；先 `--dry-run` 给出脱敏后的 diff、备份目录和 plan id，真正写入时必须带同一个 plan id，文件、参数或备份目录变了就拒绝。写入前把原文件备份到 `~/.claude/backups/ainative/`（目录 0700、文件 0600；位于任何 git 仓库内的备份目录会被拒绝），原子写入、写后自检，并给出撤销命令
- **托管设置只给命令**：需要管理员权限的操作由你本人执行
- **插件不携带权限规则**：通用的 deny 和 ask 规则只会在你确认后合并进你的用户或项目设置
- 两个脚本都可以直接阅读：`skills/doctor/scripts/doctor.py`、`skills/setup/scripts/merge_settings.py`

## 目录结构

```text
plugin/
├── .claude-plugin/plugin.json
├── README.md
└── skills/
    ├── doctor/          SKILL.md、scripts/doctor.py、references/rubric.md
    ├── setup/           SKILL.md、scripts/merge_settings.py、references/profiles.md
    ├── recommend/       SKILL.md、references/decision-tables.md
    ├── new-project/     SKILL.md、references/day0.md
    ├── pitfall-check/   SKILL.md、references/pitfalls.md（构建时从手册坑库生成）
    └── harvest/         SKILL.md、references/card-format.md
```

## 更多

- 手册：https://ainative.jubao.ai
- 插件说明页：https://ainative.jubao.ai/docs/reference/plugin
- 最新完整内容（给 AI 读）：https://ainative.jubao.ai/llms.txt
- 许可：MIT
