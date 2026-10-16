# doctor 解读规则（rubric）

`doctor.py` 输出的每条 `findings[]` 都有 `id` 和默认 `severity`。本文件按 `id` 给出：为什么重要、怎么修、手册链接。生成报告时逐条查表，不要自己编修法。

## 严重度

| 级别 | 含义 | 处理时限 |
|---|---|---|
| P0 | 密钥可能泄露，或护栏已经失效而你以为它还在 | 今天就修 |
| P1 | 明显的风险或浪费，迟早出事 | 这周修 |
| P2 | 值得改进，不改也不会马上出事 | 有空再改 |
| info | 观察，不算问题 | 写进报告末尾即可 |

可以根据项目档位调整严重度（例如小工具档的 `docs-layout` 不算问题），但调整时要在报告里写一句理由。不要因为"看起来不严重"就把 P0 降级。

## 两条容易写错的事实（截至 2026-10）

1. **`skillOverrides` 对插件里的 skill 不生效**。官方文档原文：Plugin skills are not affected by `skillOverrides`. Manage those through `/plugin` instead（已在 Claude Code 2.1.301 上实测确认）。它只管 `~/.claude/skills/`、`.claude/skills/` 里的普通 skill（例如 gstack）。控制插件 skill 有两种办法：用 `enabledPlugins` 按项目停用整个插件；或者在 `permissions.deny` 里加 `Skill(<插件名>:*)`，禁止模型自动调用、保留你手动 `/插件名:skill` 调用。另外，插件本身不能携带 permissions 规则，通用的 deny、ask 只能合并进用户或项目的 settings。
2. **bypass 权限模式**：deny 规则在任何模式下都生效，allow 规则在 bypass 下不起作用；按官方文档，ask 规则在任何模式下（含 bypass）都会弹确认。不同版本的行为有过变化，🧪 建议用一条无害命令自测；最致命的操作仍然放 deny。

另外：doctor 不输出 hook 的命令全文（命令行里可能带凭据），只给程序名和确定会被执行的脚本路径（命令本身，或解释器后面的脚本）及其是否存在；权限规则经过参数级打码。报告里不要试图还原这些内容。

托管设置：doctor 只读取文件形式的托管设置，先读 `managed-settings.json`，再按字母顺序合并 `managed-settings.d/*.json`（规则同官方：单值以后读的为准、列表合并去重、嵌套块逐键合并）。MDM 配置描述文件和服务端下发的托管设置它看不到；用户说"公司有统一配置"时，提醒以 `/status` 显示的来源为准。

## P0

### `bypass-without-deny`
- 为什么：默认以 bypass 模式启动又没有任何 deny 规则，任何命令都会直接执行，没有任何东西能拦住 `rm -rf` 或强推。官方建议 bypass 只在隔离的容器或虚拟机里用
- 怎么修：先补最小 deny 规则（见 setup 的 `profiles.md`「最小规则集」），再把 `~/.claude/settings.json` 里的 `permissions.defaultMode` 改回默认；需要 bypass 时只在沙箱里单次用 `claude --permission-mode bypassPermissions`
- 链接：https://ainative.jubao.ai/docs/guardrails/permissions

### `hook-script-missing`
- 为什么：hook 引用的脚本不存在时，Claude Code 只报一个非阻塞错误，动作照常执行。你以为有兜底，实际从来没有
- 怎么修：从 git 或备份恢复脚本，或删掉这条 hook；在 `/hooks` 里确认挂载状态；策略类 hook 可以加 `"onFailure": "block"`（需要 Claude Code v2.1.295 及以上），让脚本缺失时直接拦下动作；之后定期跑 `/ainative:doctor`
- 链接：https://ainative.jubao.ai/docs/pitfalls/guardrails-decay 、https://ainative.jubao.ai/docs/guardrails/hooks

### `secret-in-shared-settings`
- 为什么：`.claude/settings.json` 是要提交到 git 的共享文件，里面的 `env` 值会跟着仓库走
- 怎么修：已经提交过的密钥按泄露处理，先去服务商处轮换；从文件里删掉，改成本机环境变量或钥匙串；只给自己用的设置放 `.claude/settings.local.json`
- 链接：https://ainative.jubao.ai/docs/guardrails/secrets

### `secret-in-mcp-json`
- 为什么：项目根目录的 `.mcp.json` 通常会提交到 git，`env` 或 `headers` 里的明文值等于公开
- 怎么修：轮换密钥；把值改成 `${VAR}` 形式引用环境变量，真实值放本机环境变量
- 链接：https://ainative.jubao.ai/docs/guardrails/secrets

### `env-file-tracked`
- 为什么：`.env` 类文件已经进了 git 历史，删文件不等于删历史
- 怎么修：轮换里面所有密钥；`git rm --cached <文件>` 后把它加进 `.gitignore`；要不要改写历史由你决定并亲自执行，不要交给 agent（改写历史属于高危操作）
- 链接：https://ainative.jubao.ai/docs/guardrails/secrets 、https://ainative.jubao.ai/docs/pitfalls/git-history-no-surgery

### `env-file-not-ignored`
- 为什么：文件还没提交，但下一次 `git add .` 就会进仓库
- 怎么修：`.gitignore` 加上 `.env*` 和 `!.env.example`（保留模板文件）
- 链接：https://ainative.jubao.ai/docs/tool/guardrails

## P1

### `no-deny-rules`
- 为什么：没有 deny 规则，最致命的误操作（删目录、强推、硬重置）只能靠模型自觉
- 怎么修：在 `~/.claude/settings.json` 加最小 deny 规则集（见 `profiles.md`），可以运行 `/ainative:setup` 自动合并
- 链接：https://ainative.jubao.ai/docs/tool/guardrails 、https://ainative.jubao.ai/docs/guardrails/permissions

### `bypass-default`
- 为什么：默认 bypass 时，除了 deny、ask 规则和少数内置保护之外，所有操作都直接执行，allow 规则也不再起作用。官方文档说 ask 规则在 bypass 下仍会弹确认，但不同版本的行为有过变化（🧪 建议自测）
- 怎么修：确认 deny 覆盖了关键命令（见 `core-deny-gaps`）；不在隔离环境时，把默认模式改回去，按需单次开启
- 链接：https://ainative.jubao.ai/docs/guardrails/permissions

### `hooks-disabled`
- 触发条件：按设置优先级（托管 > 本地 > 项目 > 用户）计算，`disableAllHooks` 的有效值是 `true`。证据里的 `set_in` 是生效的那份文件
- 为什么：配置里的 hook（含插件 hook）都还在，但一条都不会运行，自动备份、拦截之类的护栏全部失效。非托管设置里的 `true` 不影响托管 hook；托管设置里的 `true` 连托管 hook 也一起关掉
- 怎么修：确认是不是临时关掉后忘了开。不需要关时，从 `set_in` 那份文件里删掉 `disableAllHooks`，或改成 `false`；然后在 `/hooks` 里确认
- 链接：https://ainative.jubao.ai/docs/guardrails/hooks 、https://ainative.jubao.ai/docs/pitfalls/guardrails-decay

### `hook-script-relative-missing`
- 为什么：hook 用的是相对路径，在当前项目下找不到。用户级 hook 写相对路径时，换个目录启动就会失效
- 怎么修：改成绝对路径，或项目内用 `"$CLAUDE_PROJECT_DIR"/.claude/hooks/<脚本>`
- 链接：https://ainative.jubao.ai/docs/guardrails/hooks

### `settings-possibly-overwritten`
- 为什么：装了不少插件，但用户设置里既没有启用插件，也没有权限规则和 hook，典型症状是设置文件被切换工具整份重写了
- 怎么修：看 `ls -la ~/.claude/settings.json*` 和切换工具自己的备份目录，找回旧版本对比恢复；然后运行 `/ainative:setup` 重新合并
- 链接：https://ainative.jubao.ai/docs/pitfalls/config-overwrite

### `cc-switch-detected`
- 默认 P1；已有托管设置时降为 P2
- 为什么：这类模型供应商切换工具切换时会整份重写 `~/.claude/settings.json`，权限规则、hook、插件启用状态可能一起丢失
- 怎么修：每次切换后跑一次 `/ainative:doctor`；关键 deny 规则放进托管设置（需要管理员权限，只给命令，见 `profiles.md`「组织档」）；切换前先备份设置文件
- 链接：https://ainative.jubao.ai/docs/pitfalls/config-overwrite

### `local-settings-tracked`
- 为什么：`.claude/settings.local.json` 是个人本机设置，被 git 跟踪后会把你的放行规则和路径推给所有人
- 怎么修：`git rm --cached .claude/settings.local.json`，并加进 `.gitignore`
- 链接：https://ainative.jubao.ai/docs/guardrails/secrets

### `not-git-repo`
- 为什么：没有 git，就没有回滚点，也没法让另一个模型审 diff
- 怎么修：先写 `.gitignore`（含 `.env*`），再 `git init` 并提交；需要远端时用 `gh repo create <owner>/<名字> --private --source=. --push`
- 链接：https://ainative.jubao.ai/docs/tool

### `no-claude-md`
- 为什么：没有 CLAUDE.md（也没有 AGENTS.md），每个会话都要重新解释技术栈、命令和禁区
- 怎么修：`/init` 生成后删到一页以内，或用 `/ainative:new-project` 里的一页模板
- 链接：https://ainative.jubao.ai/docs/templates/claude-md

### `env-file-unprotected`
- 为什么：项目还不是 git 仓库，但 `.env` 类文件不在 `.gitignore` 里，一旦 `git init && git add .` 就会进仓库
- 怎么修：先把 `.env*` 和 `!.env.example` 写进 `.gitignore`，再初始化仓库
- 链接：https://ainative.jubao.ai/docs/tool/guardrails

### `dual-process-engine`
- 触发条件：superpowers 和 mattpocock-skills 都处于启用状态，且 deny 规则里没有 `Skill(superpowers:*)` 或 `Skill(mattpocock-skills:*)` 压住其中一套
- 为什么：superpowers 带 SessionStart hook，会话一开始就注入流程；mattpocock-skills 也有能自动触发的 skill。两套同时开着，一句"帮我 debug"会被不同框架抢走，同一个项目里流程前后不一致
- 怎么修（推荐）：用 `enabledPlugins` 按项目只启用一套，另一套设为 `false`。只影响当前项目时写进 `.claude/settings.local.json`，影响所有项目时写进 `~/.claude/settings.json`。例如以 Matt 为主：`{"enabledPlugins": {"superpowers@claude-plugins-official": false}}`（可以交给 `/ainative:setup` 合并，或运行 `claude plugin disable superpowers@claude-plugins-official --scope local`）
- 怎么修（替代）：两套都要能手动调用时，在 `permissions.deny` 里加非主引擎的 `Skill(<插件名>:*)`，例如 `Skill(superpowers:*)`。模型不会再自动调用它的 skill，你仍可手动 `/superpowers:<skill>`。注意 superpowers 的 SessionStart hook 仍会运行；不想要它注入的内容，就用推荐方案
- 注意：`skillOverrides` 管不了插件 skill，不要用它来"关掉另一套"
- 链接：https://ainative.jubao.ai/docs/pitfalls/one-process-engine 、https://ainative.jubao.ai/docs/workflow/migrate

### `unused-plugins`
- 5 个以上为 P1，否则 P2
- 为什么：已启用的插件即使不用，也会在每个会话里占用 skill 列表和上下文，还会抢触发
- 怎么修：先用 `claude plugin details <插件@市场>` 看常驻 token 成本，再 `claude plugin disable <插件@市场>`；确定不要了再 `claude plugin uninstall`。证据里的插件只统计了 skill 和 command 调用，纯 MCP、LSP、hook 类插件要另行判断
- 链接：https://ainative.jubao.ai/docs/pitfalls/plugin-bloat

## P2

### `core-deny-gaps`
- 为什么：已有 deny 规则，但没覆盖 `rm -rf`、`git push --force`、`git reset --hard` 中的某几类
- 怎么修：补上 `profiles.md` 里对应的规则。权限规则是前缀匹配，挡不住所有写法（例如 `git -C . push --force`），关键护栏再加 hook 兜底
- 链接：https://ainative.jubao.ai/docs/guardrails/permissions

### `bypass-prompt-accepted`
- 为什么：你接受过一次 bypass 警告，`skipDangerousModePermissionPrompt` 被写成 `true`，之后任何以 bypass 启动的会话都不会再提醒
- 怎么修：不再使用 bypass 时，删掉这个键或改成 `false`；团队可在托管设置里用 `permissions.disableBypassPermissionsMode: "disable"` 彻底禁止
- 链接：https://ainative.jubao.ai/docs/guardrails/permissions

### `project-mode-ignored`
- 为什么：`auto` 和 `bypassPermissions` 写在项目级或本地设置里不生效，配置和实际行为不一致
- 怎么修：从项目设置里删掉；需要时写进 `~/.claude/settings.json` 或启动时加 `--permission-mode`
- 链接：https://ainative.jubao.ai/docs/guardrails/permissions

### `unmounted-hook-scripts`
- 为什么：hooks 目录里有脚本没挂到任何事件上。这正是"护栏悄悄失效"的典型形态：文件还在，但从没运行
- 怎么修：确认它是否应该生效；应该就挂回去（`/hooks` 或 `/ainative:setup`），不需要就移到归档目录。被别的脚本间接调用的可以忽略
- 链接：https://ainative.jubao.ai/docs/pitfalls/guardrails-decay

### `secret-in-user-settings`
- 为什么：用户设置的 `env` 里有明文密钥，各种备份文件和切换工具的副本里也会有同样的明文
- 怎么修：能放 shell 环境变量或钥匙串就挪过去；至少 `chmod 600 ~/.claude/settings.json`；不再需要的设置备份及时删除
- 链接：https://ainative.jubao.ai/docs/guardrails/secrets

### `mcp-insecure-http`
- 为什么：用明文 http 连接非本机的 MCP 服务器，凭据和数据都在明文传输
- 怎么修：换成 https 地址
- 链接：https://ainative.jubao.ai/docs/guardrails/secrets

### `claude-md-long`
- 为什么：CLAUDE.md 每个会话都会整份加载。太长会挤占上下文，关键规则也容易被淹没
- 怎么修：只留每次都要遵守的规则（技术栈、命令、禁区、指针），细节移到 `docs/` 并在 CLAUDE.md 里写指针
- 链接：https://ainative.jubao.ai/docs/templates/claude-md

### `no-gitignore` / `gitignore-env-gap`
- 为什么：没有 `.gitignore`，或者它没覆盖 `.env`、`.env.production` 这类文件（只写 `.env*.local` 是常见漏洞）
- 怎么修：加上 `.env*` 和 `!.env.example`
- 链接：https://ainative.jubao.ai/docs/tool/guardrails

### `agents-md-unconfirmed`
- 为什么：项目只有 AGENTS.md、没有 CLAUDE.md。Claude Code 是否加载 AGENTS.md 取决于版本和设置，doctor 无法确认它真的生效
- 怎么修：新建一页 CLAUDE.md，第一行写 `@AGENTS.md` 导入它（两边共用一份规则），再补 Claude Code 专用的内容
- 链接：https://ainative.jubao.ai/docs/templates/claude-md

### `skilloverrides-plugin-keys`
- 为什么：这些 `skillOverrides` 条目针对的是插件里的 skill，不会生效，给人"已经关掉了"的错觉
- 怎么修：删掉这些条目。要停用整个插件，用 `enabledPlugins`（或 `claude plugin disable`）；只想禁止模型自动调用、保留手动调用，在 `permissions.deny` 加 `Skill(<插件名>:*)`
- 链接：https://ainative.jubao.ai/docs/pitfalls/one-process-engine

### `multiple-cloudflare-plugins`
- 为什么：多个 Cloudflare 插件功能重叠，描述互相抢触发
- 怎么修：留一个，其余 `claude plugin disable <插件@市场>`。如果已经接了 Cloudflare 官方 MCP，插件还可以再少
- 链接：https://ainative.jubao.ai/docs/pitfalls/plugin-bloat

### `code-review-plugin-overlap`
- 为什么：Claude Code 内置了 `/code-review`（审查当前 diff 或 PR，`--comment` 可发到 PR），插件版功能重叠
- 怎么修：没有特别理由就停用插件版
- 链接：https://ainative.jubao.ai/docs/reference/toolchain

### `enabled-not-installed`
- 为什么：设置里启用了，但本机没装，启动时会报错或提示安装
- 怎么修：需要就 `claude plugin install <插件@市场>`，不需要就从 `enabledPlugins` 里删掉
- 链接：https://ainative.jubao.ai/docs/reference/toolchain

### `unused-user-skills`
- 为什么：`~/.claude/skills/` 里长期不用的 skill 照样占 skill 列表的预算；列表超预算时，描述会被截掉，常用 skill 反而更难被正确触发
- 怎么修：这些是个人 skill，`skillOverrides` 对它们有效。不用的设 `"off"` 或 `"name-only"`；和主引擎重叠的流程类 skill（例如 gstack 的 `office-hours`、`plan-ceo-review`、`autoplan`）设 `"user-invocable-only"`，仍可手动 `/名字` 调用。内置的 `/skill-doctor` 也能看每个 skill 的成本和使用次数
- 链接：https://ainative.jubao.ai/docs/pitfalls/plugin-bloat 、https://ainative.jubao.ai/docs/workflow/gstack

### `agents-unused`
- 为什么：subagent 太多时，选择会变难，定义也容易过时
- 怎么修：把长期不用的 agent 文件移到归档目录（不要直接删），三个月后再清理
- 链接：https://ainative.jubao.ai/docs/pitfalls/plugin-bloat

## info

| id | 写进报告的方式 |
|---|---|
| `docs-layout` | 产品档项目缺 `docs/specs` 等目录时，升为 P2，修法：`mkdir -p docs/{specs,plans,adr,runbooks,retros}`，链接 https://ainative.jubao.ai/docs/product/day-0 ；小工具档忽略 |
| `agents-md-not-imported` | 同时有 CLAUDE.md 和 AGENTS.md，但 CLAUDE.md 没有 `@AGENTS.md`；两份规则可能不一致，建议导入或合并 |
| `dual-engine-suppressed` | 两套流程引擎都启用，但其中一套已用 `Skill(<插件名>:*)` deny 压住，不算冲突；提醒 superpowers 的 SessionStart hook 仍会运行 |
| `superpowers-docs-dir` | 存在 superpowers 默认输出目录。切到 Matt 时，按 `docs/specs/YYYY-MM-DD_<slug>.md`、`docs/plans/YYYY-MM-DD_<slug>-plan.md` 统一命名，链接 https://ainative.jubao.ai/docs/workflow/migrate |
| `usage-skipped` | 说明冗余判断不含调用数据 |
| `claude-cli-missing` | 说明版本号和启用状态是从设置文件推断的 |
| `collector-errors` | 把 `errors[]` 原样列在报告末尾 |
| `project-not-found` | 提示检查 `--project` 路径 |

## 需要你自己判断的项

脚本只给事实，下面几项由你结合项目判断：

- **档位**：看 `project.signals`、`project.ci_workflows`、仓库数量和是否有真实用户，按 https://ainative.jubao.ai/docs/tiers 判断。查不到的事实，最多问 1 个问题
- **gstack 是否与主引擎重叠**：`user_skills.suites.gstack` 大于 0 时，按 https://ainative.jubao.ai/docs/workflow/gstack 的分工建议，流程类 skill 交给主引擎，gstack 只留上线流水线与质量相关的
- **插件常驻成本**：对 `unused-plugins` 里最可疑的 2–3 个，可以运行 `claude plugin details <插件@市场>`（只读）补充 token 数据
- **hook 的质量**：脚本只检查路径是否存在，不判断逻辑。看到 PreToolUse 拦截类 hook，提醒用户用一条无害命令实测一次

## 推荐方案与替代方案

报告最后只给一个推荐方案和一个替代方案，不要平铺三个以上。常见组合：

| 主要问题 | 推荐 | 替代 |
|---|---|---|
| 有 P0 | 逐条修完 P0，再运行 `/ainative:setup` 补齐护栏 | 先只修密钥类 P0（今天必须做），其余排进这周 |
| 护栏缺失（无 deny、hook 失效） | `/ainative:setup` 按档位合并最小规则集并修复 hook | 手动把 `profiles.md` 的最小规则集贴进 `~/.claude/settings.json` |
| 插件与 skill 冗余 | 按调用数据停用不用的插件，个人 skill 设 `name-only` 或 `off` | 只停用重复的插件（双引擎、多个 Cloudflare），其余观察 30 天再定 |
| 双流程引擎 | 用 `enabledPlugins` 按项目只启用主引擎（另一套设 `false`） | 两套都启用，`permissions.deny` 加非主引擎的 `Skill(<插件名>:*)`，保留手动调用 |
