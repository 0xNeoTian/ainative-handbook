# 坑库（自动生成，请勿手改）

> 由 `scripts/build-plugin.mjs` 从手册 `content/docs/pitfalls/` 生成，共 25 张。完整内容见 https://ainative.jubao.ai/docs/pitfalls

## 切换工具会整份覆盖设置

- id：`config-overwrite`
- 阶段：day0；档位：tool, product；可信度：lived
- 规则：用过配置切换工具，先查权限、hook、插件三项；关键护栏放托管设置
- 防什么：用模型供应商切换工具切回官方后，权限规则、hook、插件启用状态全丢了，表面症状只是“插件都关了”
- 链接：https://ainative.jubao.ai/docs/pitfalls/config-overwrite

怎么做：

**切换前备份，切换后只比护栏字段**。这个文件的 `env` 里可能有供应商的密钥，备份设成只有自己能读，对比时也只取护栏相关的字段，别把密钥打到屏幕或日志里：

```bash
# 切换前：备份，权限 600
install -m 600 ~/.claude/settings.json ~/.claude/settings.backup.json
# 切换后：只比较 permissions、hooks、enabledPlugins
diff <(jq -S '{permissions, hooks, enabledPlugins}' ~/.claude/settings.backup.json) \
     <(jq -S '{permissions, hooks, enabledPlugins}' ~/.claude/settings.json)
```

**没有备份时，至少看一眼这三项**。哪一项变成 `null`，就是被冲掉了：

```bash
jq '{permissions, hooks, enabledPlugins}' ~/.claude/settings.json
```

**最关键的护栏放进托管设置**。它优先级最高，写入要管理员权限，切换工具改不到。macOS 是 `/Library/Application Support/ClaudeCode/managed-settings.json`，Linux 是 `/etc/claude-code/managed-settings.json`：

```json
{
  "permissions": {
    "deny": ["Bash(rm -rf ~)", "Bash(git push --force origin main *)"]
  }
}
```

在 Claude Code 里运行 `/status`，Setting sources 一行能确认它已生效。

**体检 hook 别放在会被覆盖的文件里**。放在 `~/.claude/settings.json` 的体检 hook，会和护栏一起被冲掉。放进项目级 `.claude/settings.json` 或托管设置，每次开会话自动检查。

## 同一时间只让一套流程自动接管

- id：`one-process-engine`
- 阶段：day0；档位：product；可信度：industry
- 规则：只让一套流程引擎自动触发，其余框架只留手动调用
- 防什么：两套流程框架同时开着，一句“帮我 debug”可能被不同框架抢走。只留一套自动触发，其余改成手动调用
- 链接：https://ainative.jubao.ai/docs/pitfalls/one-process-engine

怎么做：

**定一个主引擎负责自动触发**，其余框架降为只能手动调用。我现在的主引擎是 Matt Pocock skills（试用中）。<Evidence kind="trial" />

**推荐：按项目只启用一套**。在项目的 `.claude/settings.json`（团队共享）或 `.claude/settings.local.json`（只对你生效）里，用 `enabledPlugins` 把另一套设为 `false`：

```json
{
  "enabledPlugins": {
    "mattpocock-skills@claude-plugins-official": true,
    "superpowers@claude-plugins-official": false
  }
}
```

插件整个关掉，它的 skill 和 hook 都不会再加载。

**想保留手动调用、只禁止模型自动触发**：在 `permissions.deny` 里按插件名拦住 Skill 工具。模型调不了，你手动输入 `/superpowers:brainstorming` 这类命令仍然可用：

```json
{
  "permissions": {
    "deny": ["Skill(superpowers:*)"]
  }
}
```

注意这条规则只拦 Skill 调用，superpowers 的 SessionStart hook 照常运行、照常注入引导。想彻底安静，用上一步的做法。

**`skillOverrides` 只管普通 skill**。它对插件里的 skill 无效，只作用于放在 `~/.claude/skills/` 或项目 `.claude/skills/` 下的 skill。比如 gstack 装在 `~/.claude/skills/` 下，设成 `user-invocable-only` 后模型看不到它，你仍然可以手动敲 `/investigate`：

```json
{
  "skillOverrides": {
    "investigate": "user-invocable-only",
    "review": "user-invocable-only"
  }
}
```

**写进 CLAUDE.md 并验证**。写明“本项目的流程引擎是哪一套、实质改动先走哪个命令”。改完开一个新会话，说一句“帮我 debug”，看接手的是不是你指定的那个 skill。

## 插件不是越多越好

- id：`plugin-bloat`
- 阶段：day0；档位：tool, product；可信度：lived
- 规则：按真实调用数据定期精简插件和 subagent，用不到的就停用
- 防什么：装了 39 个插件、72 个 subagent，最近 30 天被调用过的 skill 只有二十个左右：按调用数据和常驻成本做减法
- 链接：https://ainative.jubao.ai/docs/pitfalls/plugin-bloat

怎么做：

**先看成本**。`/skill-doctor` 列出每个 skill 的上下文开销和使用频率，标出从没用过的，也列出最近没用的插件；单个插件看常驻成本：

```bash
claude plugin details mattpocock-skills@claude-plugins-official
```

它会列出组件清单和“每个会话常驻多少 token”（截至 2026-10，这个插件约 1.6k）。

**再看调用**。这段脚本只统计名字、不读内容，同时算上模型自动触发的 skill 和你手动敲的 `/` 命令，只靠前者会低估那些只能手动调用的 skill：

```python
import collections, glob, json, os, re
c, tag = collections.Counter(), re.compile(r'<command-name>/?([^<]+)</command-name>')
for f in glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl')):
    for line in open(f, encoding='utf-8', errors='ignore'):
        if '"Skill"' not in line and 'command-name' not in line:
            continue
        try:
            content = (json.loads(line).get('message') or {}).get('content')
        except ValueError:
            continue
        if isinstance(content, str):
            c.update('/' + n for n in tag.findall(content))
        for b in content if isinstance(content, list) else []:
            if isinstance(b, dict) and b.get('name') == 'Skill':
                c[(b.get('input') or {}).get('skill')] += 1
for name, n in c.most_common():
    print(n, name)
```

subagent 同理，统计 `Agent` 工具调用里的 `subagent_type`。注意会话记录默认只保留 30 天（`cleanupPeriodDays`），想看 90 天要提前调大。

**做减法**。插件先停用、观察两周再卸载：

```bash
claude plugin disable <name>@<marketplace>
claude plugin uninstall <name>@<marketplace>
```

个人 skill 用 `skillOverrides` 设为 `off`，或设为 `name-only` 只留名字；用不到的 subagent 定义文件移出 `~/.claude/agents/`。

**定期复查**。每个季度跑一次，或直接用本手册插件的 `/ainative:doctor`。

## “之前是这样的”先查 git

- id：`memory-vs-git`
- 阶段：design；档位：product；可信度：lived
- 规则：谁说“之前是 X”，都先查 git 历史，再决定要不要把它当约束
- 防什么：人的记忆会把想过的设计当成做过的功能。防止 agent 把“以前有过”当约束，照着不存在的旧版去“恢复”
- 链接：https://ainative.jubao.ai/docs/pitfalls/memory-vs-git

怎么做：

**先查历史，再当约束**：

```bash
git log --oneline -- <文件路径>          # 这个文件的所有提交
git log --all --oneline -S '<关键词>'    # 哪些提交加过或删过这段代码，含其他分支
git show <commit> --stat                 # 某次提交改了哪些文件
```

**查不到，就让人明确选**：是“记错了”，还是“这是新设计”。agent 不替人选，也不默认按“恢复”处理。

**选了新设计，就按新需求走**：先写 spec 再动手，不要顶着“恢复”的名义直接改（见[实质改动先留文档再动手](/docs/pitfalls/process-before-code)）。

**写进 CLAUDE.md**：

```markdown
- 任何人（包括我）说“之前是 X”，先用 git log 查证；查不到就按新需求处理，并向我确认
```

## 实质改动先留文档再动手

- id：`process-before-code`
- 阶段：design；档位：product；可信度：lived
- 规则：实质改动先写 spec 和 plan 再按 TDD 实现，一行级修复也留句记录
- 防什么：结果是对的，但 agent 直接改了代码、没留 spec 和 plan，事后没法审计、没法交接、没法请人 review
- 链接：https://ainative.jubao.ai/docs/pitfalls/process-before-code

怎么做：

**在 CLAUDE.md 写成硬规则，附上判定标准**：

```markdown

## 不让 agent 动 git 历史

- id：`git-history-no-surgery`
- 阶段：build；档位：product, org；可信度：lived
- 规则：改写 git 历史的操作一律不让 agent 自主执行
- 防什么：agent 为了“恢复状态”会自作主张 reset、rebase。用权限规则和提示词把改写历史留给人
- 链接：https://ainative.jubao.ai/docs/pitfalls/git-history-no-surgery

怎么做：

**用权限规则挡住常见写法**。写进 `.claude/settings.json`（项目级，进 git）；想对所有项目生效，就在 `~/.claude/settings.json` 再写一份：

```json
{
  "permissions": {
    "deny": [
      "Bash(git reset --hard *)",
      "Bash(git push --force *)",
      "Bash(git push -f *)"
    ],
    "ask": [
      "Bash(git rebase *)",
      "Bash(git commit --amend *)"
    ]
  }
}
```

rebase 和 amend 放 ask 不放 deny，是因为整理还没推送的本地提交是正常需求，只是每次都要你点头。

**子 agent 提示词里写 CRITICAL do-not 段**。权限规则匹配的是命令文本，换个写法（比如 `git push origin main --force`）就拦不住，所以提示词这一层不能省：

```text
CRITICAL — 不要做：
- 不要运行 git reset、git rebase、git push --force、git commit --amend
- 工作区有未提交的改动时，不要 checkout 或切换分支
- 觉得状态不对：停下，贴出 git status 和 git log --oneline -5，等我决定
```

**确需改写历史，人在自己的终端里做，先留两条退路**。只打一个 tag 不够：tag 只保住提交，之后的 `git reset --hard` 照样会冲掉工作区里没提交的改动；固定名字的 tag 第二次创建还会失败。

```bash
git stash push -u -m "before-rewrite"     # 没提交的改动和未跟踪的文件先存起来
git stash list                            # 最上面一条应该是 before-rewrite；没有就说明本来没改动
git branch "rescue/$(date +%Y%m%d-%H%M%S)"  # 当前提交留一个带时间戳的分支
```

也可以把整个工作目录复制一份。出了问题：rebase 还没做完就 `git rebase --abort`；已经做完了，`git reset --hard rescue/<时间戳>` 回到原来的提交。最后再 `git stash pop` 取回改动，前提是第一步确实存了东西，否则会弹出一条更早的旧 stash。

**已经丢了，先查 reflog**：`git reflog` 能看到 reset 之前 HEAD 指向哪里，找到哈希后 `git branch rescue/found <哈希>` 就能捞回来。reflog 只记得提交过的东西；没提交的改动被 `git reset --hard` 覆盖之后，基本就找不回了，这也是上一步要先 stash 的原因。

## 本地数据库也要按生产对待

- id：`local-db-is-prod`
- 阶段：build；档位：product；可信度：lived
- 规则：任何破坏性数据库操作之前先 dump，备份失败就不执行
- 防什么：本地库里攒着别处没有的配置和演示数据时，它就是生产。防止一条破坏性命令把它们清空且无从恢复
- 链接：https://ainative.jubao.ai/docs/pitfalls/local-db-is-prod

怎么做：

**reset 目标先备份，备份失败就退出**。make 遇到失败的命令会直接停下，走不到后面的 reset。“备份失败就不执行”靠的就是这一层：

```makefile
BACKUP_DIR ?= $(HOME)/db-backups

db-reset:
	@test -n "$(DATABASE_URL)" || { echo "DATABASE_URL 未设置"; exit 1; }
	@mkdir -p $(BACKUP_DIR)
	@pg_dump -Fc -d "$(DATABASE_URL)" -f $(BACKUP_DIR)/pre-reset-$$(date +%Y%m%d-%H%M%S).dump
	./scripts/reset-db.sh
```

行首的 `@` 让 make 不回显命令。没有它，展开后的连接串会原样打进终端、CI 日志和 agent 的对话。密码也不要放进命令参数：写进 `~/.pgpass`（格式 `主机:端口:库名:用户:密码`，前四个字段可以写 `*`；权限必须是 600，否则会被忽略），连接串里只留用户、主机和库名；也可以用 `PGPASSFILE` 环境变量指向一个不进 git 的密码文件。

**破坏性命令设成 ask**，agent 执行前必须你点头。写进项目的 `.claude/settings.json`，这个文件进 git，被改动时能在 diff 里看到：

```json
{
  "permissions": {
    "ask": [
      "Bash(make db-reset *)",
      "Bash(supabase db reset *)",
      "Bash(docker compose down -v *)",
      "Bash(docker volume rm *)"
    ]
  }
}
```

**再加一层尽力而为的兜底**：PreToolUse hook 匹配到这些命令时先 `pg_dump` 一份，永远 `exit 0`，备份失败也照样放行。它替代不了第一步的 reset 脚本。写法见[用 hook 兜底](/docs/guardrails/hooks)。

**定期演练恢复**。`pg_restore --list` 只能列出归档里有什么，证明不了能恢复。真正的验证是找一个临时库（别用原来的库）实际恢复一次，再抽查关键数据：

```bash
createdb restore_check
pg_restore --no-owner -d restore_check <备份文件>.dump     # 自定义格式（-Fc）用 pg_restore
# 纯 SQL 格式的备份用 psql 恢复：psql -d restore_check -f <备份文件>.sql
psql -d restore_check -c 'select count(*) from <关键表>'   # 抽查关键数据
dropdb restore_check
```

能脚本化的资产，比如演示数据、agent 配置，顺手导出成 seed 脚本放进 git。

后来我把这三层都加上了，半年后才发现它们已经悄悄失效，见[防护规则会悄悄失效](/docs/pitfalls/guardrails-decay)。

## 计划和执行分开会话

- id：`split-plan-exec`
- 阶段：build；档位：product, org；可信度：lived
- 规则：大任务的计划和执行分开会话：计划落成文件、审完，再开新会话执行
- 防什么：大任务在同一个会话里先计划后执行，计划会把上下文烧光。防止执行阶段带着残余上下文越做越差
- 链接：https://ainative.jubao.ai/docs/pitfalls/split-plan-exec

怎么做：

先估规模。别在当前工作区里试合并：手上有没提交的改动时，`git merge --abort` 不保证能把它们原样恢复。开一个临时 worktree 去试，数完就删，当前工作区不受影响：

```bash
git fetch upstream
git worktree add --detach ../merge-probe HEAD
git -C ../merge-probe merge --no-commit --no-ff upstream/main
git -C ../merge-probe diff --name-only --diff-filter=U | wc -l   # 冲突文件数
git -C ../merge-probe merge --abort
git worktree remove ../merge-probe
```

冲突 30 个以上建议拆，50 个以上必须拆。别的大任务同理：估计一个会话装不下，就拆。

**会话一只出计划**。用 Plan mode（`Shift+Tab`）探索，产出 `docs/plans/YYYY-MM-DD_<slug>-plan.md`：按模块分组，每组写清处理原则、顺序和验证命令。

**审计划，合并进仓库，关掉会话**。这一步就可以请另一个模型家族审一遍计划。

**会话二只读计划执行**。开新会话（或者 `/clear`），第一句话就交代清楚：读计划文件，从第 1 组开始，每组做完跑验证、提交，不要重新规划。

**执行中发现计划不对，就停下来回去改计划**，不在执行会话里临场重新规划。组数多就一组一个会话，交接可以用 `/mattpocock-skills:handoff` 压缩成交接文档。<Evidence kind="trial" />

## 子 agent 别为省钱降级

- id：`subagent-strongest-model`
- 阶段：build；档位：product, org；可信度：lived
- 规则：有工程不变量的任务，子 agent 默认用最强模型；纯机械任务例外
- 防什么：子 agent 一律用最强模型：项目里跨字段的约束多，降级单次看不出问题，累积起来审查兜不住
- 链接：https://ainative.jubao.ai/docs/pitfalls/subagent-strongest-model

怎么做：

**有不变量的子 agent 写死模型**。实现、重构、迁移、审查这类任务，在 `.claude/agents/<name>.md` 里写 `model: inherit`（跟主会话一致）或 `model: opus`：

```markdown
---
name: implementer
description: 按 plan 实现改动，遵守仓库里的不变量
model: inherit
---
```

**拦住按次降级**。在权限规则里给小模型加 ask，主会话想降级时你要确认：

```json
{
  "permissions": {
    "ask": ["Agent(model:*haiku*)"]
  }
}
```

想一刀切，可以设环境变量 `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`（v2.1.257 起），除内置的 Explore 外，所有子 agent 都跑主会话的模型。

**纯机械任务单独开口子**。批量重命名、移动文件、格式化这类不需要判断的活，单独定义一个 `model: haiku` 的子 agent，提示词里写清楚“只做机械操作，遇到需要判断的就停下来报告”。

注意它和上一步的 FORCE 互斥：开了 FORCE，Claude Code 会忽略子 agent 定义里的 `model` 字段，这个例外不会生效。要么统一强制，要么只在需要强制的会话里用 `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1 claude` 启动，机械任务放在没开 FORCE 的会话里跑。

**这是保守默认，用评测来调**。这是我在当前工作负载下的选择：跨字段不变量多、返工贵，宁可多花 token。预算有限时，非交互运行可以用 `claude -p --max-budget-usd <金额>` 封顶，子 agent 的花费也计入。哪些子 agent 能降级，拿几个有代表性的历史任务，强模型和小模型各跑一遍，比较一次通过审查的比例和返工次数再定。运行中用 `/tasks` 核对实际模型。

## 临时方案要写明撤销条件

- id：`temp-fix-revert-trigger`
- 阶段：build；档位：product；可信度：lived
- 规则：任何临时绕路，都在 PR 里写明撤销条件，并记入待撤清单
- 防什么：临时绕路很容易变成永久，还会自己埋新坑。写明撤销条件和负责人，它才不会被忘掉
- 链接：https://ainative.jubao.ai/docs/pitfalls/temp-fix-revert-trigger

怎么做：

适用范围：`--no-verify` 提交、硬编码的兜底值、为赶时间加的绕路、临时关掉的检查。

**在代码里标出来**，写明为什么加、什么条件下撤：

```ts
// TEMP(#123): 安装时绕过 X，为赶 v1.4 发版
// 撤销条件：上游修复 X 并发版后，删除本段
```

**PR 描述里单列一节**：

```markdown

## 性能修复先问六个问题

- id：`perf-fix-six-questions`
- 阶段：test；档位：product；可信度：lived
- 规则：性能修复上线前先答完六个问题，答不出就不上线
- 防什么：性能修复最容易“看起来快了”就放行。上线前用六个问题查它有没有砍掉保护、改漏地方、没法观测
- 链接：https://ainative.jubao.ai/docs/pitfalls/perf-fix-six-questions

怎么做：

把下面六个问题写进 PR 模板，性能相关的改动逐条回答：

| 问题 | 要回答什么 |
|---|---|
| ① 修 bug 还是砍保护 | 变快是因为去掉了多余的工作，还是去掉了校验、锁、重试、限流 |
| ② 有没有竞态 | 引入了缓存、并发或异步吗；两个请求同时到会怎样 |
| ③ 覆盖范围 | 同样的慢写法在代码库里还有几处，改全了吗（先搜一遍再回答） |
| ④ 能观测到生效吗 | 上线后看哪个指标、哪条日志，能确认新逻辑真的在跑 |
| ⑤ 边界情况 | 空值、超大输入、unicode、错误输入，分别测过吗 |
| ⑥ 怎么失败 | 失败时是报错、变慢还是静默返回错误结果；谁、多久能发现 |

审查时，让另一个模型家族的 agent 拿着这六问逐条核对 PR，而不是只看 diff 顺不顺。任何一条答不出来，就不上线。

## 亲眼看到才算完成

- id：`see-it-to-ship`
- 阶段：test；档位：tool, product；可信度：lived
- 规则：UI 改动必须真启动、真打开、亲眼看到结果，才算完成
- 防什么：测试验证的是状态，用户看到的是渲染结果。防止“测试全绿、界面没变”就报告完成
- 链接：https://ainative.jubao.ai/docs/pitfalls/see-it-to-ship

怎么做：

**把“亲眼看到”写进 CLAUDE.md 的完成标准**：

```markdown

## CI 绿了不等于能发版

- id：`ci-green-not-ready`
- 阶段：ship；档位：product；可信度：lived
- 规则：发版前在本地跑完全量验证，CI 只是下限
- 防什么：红着也照发的检查会让人对红灯麻木，CI 本身也只覆盖一部分。防止拿 CI 状态代替发版前的全量验证
- 链接：https://ainative.jubao.ai/docs/pitfalls/ci-green-not-ready

怎么做：

**红灯不能常驻**：要么限期修好，要么明确隔离，在 CI 配置里把它改成非必需，同时开 Issue 写清负责人和恢复条件（见[临时方案要写明撤销条件](/docs/pitfalls/temp-fix-revert-trigger)）。不接受“心里知道它是红的”。

**红了先看日志，不靠猜**：

```bash
gh pr checks                        # 当前分支 PR 的全部检查
gh run view <run-id> --log-failed   # 只看失败步骤的日志
```

**发版前本地跑全量验证四件套**：单测、全量测试（含集成或 e2e）、类型检查、lint。串成一条命令，任何一步失败就停（脚本名按项目改）：

```bash
bun test && bun run test:e2e && bunx tsc --noEmit && bun run lint
```

**关键检查在分支保护里设为 required**，红着就合不进去。

## 自己审自己等于没审

- id：`cross-model-review`
- 阶段：ship；档位：product, org；可信度：lived
- 规则：重大改动由另一个模型家族独立二审，人最后拍板
- 防什么：主力模型自审时倾向于认同自己。防止把自审当成独立审查，用异构二审和人工批准补上
- 链接：https://ainative.jubao.ai/docs/pitfalls/cross-model-review

怎么做：

**主力模型写完，换一个模型家族审**。我用 Codex CLI：

```bash
codex review --base main -c model_reasoning_effort=medium
```

推理强度 medium 就够，xhigh 可能卡很久。装了 gstack 也可以直接用 `/codex`。Kimi、Gemini 也行，关键是不共享上下文，也不共享同一套模型偏见。

**审查者只拿 diff 和 spec，不拿对话记录**。它要知道“要做什么”和“改了什么”，不需要知道主力模型当时是怎么想的。

**plan 阶段就可以审一次**。跨字段的不变量问题，在计划里就能抓到，比写完代码再返工便宜得多。

**人最后拍板**。审查意见按严重程度列出，改哪些、不改哪些由人决定，结论留在 PR 里。涉及对外内容的改动，再加一轮人工通读。

**用数据评估这个组合值不值**。这一步我还没有系统做过。如果要长期用，建议每次二审记几笔：抓到几个主力模型漏掉的真问题，提了几个误报，花了多少时间和钱；再加上线后才暴露、两边都没审出来的漏报。攒一段时间，再决定换不换模型、是不是每次都审。

## 本机代理会让 DNS 检查失真

- id：`dns-fake-ip`
- 阶段：ship；档位：tool, product；可信度：lived
- 规则：开着本机代理时别信 dig，用 DoH 或换个网络验证 DNS
- 防什么：本机代理的 fake-ip 模式劫持了 DNS 查询，dig 返回的全是假地址，差点误报 DNS 没生效
- 链接：https://ainative.jubao.ai/docs/pitfalls/dns-fake-ip

怎么做：

**先识别**：`dig +short example.com` 返回 198.18 开头的地址，就别再排查 DNS 记录了，问题在本机。

**用 DoH（DNS over HTTPS）查**。它走 443 端口的 HTTPS，不经过 53 端口，拿到的是真实记录：

```bash
curl -s 'https://dns.google/resolve?name=example.com&type=A' | jq -r '.Answer[].data'
curl -s -H 'accept: application/dns-json' \
  'https://cloudflare-dns.com/dns-query?name=example.com&type=CNAME'
```

查 CNAME 往往比查 A 记录更能看出域名指向了哪个平台。

**需要完整的 `dig` 输出时**，临时关掉代理，或者换个网络（比如手机热点）再查。也可以把你常要验证的域名加进代理工具的 fake-ip 排除名单，让它们走真实解析。

**让 agent 也知道**。在 CLAUDE.md 写一句“本机开着 fake-ip 代理，验证 DNS 用 DoH，不要用 dig”，免得它根据假地址得出“部署失败”的结论，再自作主张去改配置。

## 一个域名只挂一个平台

- id：`one-domain-one-platform`
- 阶段：ship；档位：product；可信度：lived
- 规则：一个域名只挂一个平台；删除前先查同一主域下的全部依赖
- 防什么：子域名在旧平台上留着从没生效的绑定，清理时差点连主域名一起删，殃及另一个还在服务的子域名
- 链接：https://ainative.jubao.ai/docs/pitfalls/one-domain-one-platform

怎么做：

**定规则**：一个域名（包括每个子域名）只挂一个平台；DNS 统一在 Cloudflare 管，DNS 记录就是“谁在服务哪个域名”的唯一清单。

**删除前先列出主域下的全部记录**，看每条指向哪个平台。在 Cloudflare 后台的 DNS 页面看，或者用 API。记录多时要翻页，只看第一页就可能漏掉还在服务的子域名；每页都检查返回状态，并先确认操作的是哪个账号：

```bash
#!/usr/bin/env bash
# 列出一个 zone 的全部 DNS 记录：先确认账号，逐页拉取，每页检查 success
set -euo pipefail
cf() { curl -s "https://api.cloudflare.com/client/v4/$1" -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN"; }
ok() { jq -e '.success' >/dev/null <<<"$1" || { jq '.errors' <<<"$1" >&2; exit 1; }; }

zone=$(cf "zones/$ZONE_ID"); ok "$zone"
jq -r '.result | "zone: \(.name)  account: \(.account.name)"' <<<"$zone"

page=1
while :; do
  resp=$(cf "zones/$ZONE_ID/dns_records?per_page=100&page=$page"); ok "$resp"
  jq -r '.result[] | "\(.type)\t\(.name)\t\(.content)"' <<<"$resp"
  [ "$page" -ge "$(jq -r '.result_info.total_pages' <<<"$resp")" ] && break
  page=$((page + 1))
done
```

**再去旧平台看还有谁在用**。以 Vercel 为例，先确认登录的账号和团队，再按域名拉全部别名。`vercel alias ls` 一次最多列 100 条，用 `vercel api` 的 `--paginate` 取全：

```bash
vercel whoami
vercel api "/v4/aliases?domain=example.com" --paginate --scope your-team \
  | jq -r '.. | .alias? | strings' | sort -u
```

任何一步报错就停下，不要在不完整的结果上做删除决定。

**由小到大地删**：先解绑确认不用的子域名，观察几天访问日志或监控，确认没有流量了，再考虑删主域名。

**迁移清单里写上“旧平台解绑”**。新平台上线和旧平台解绑放在同一张清单里，一起打勾，别留到“以后再说”。

## 发版靠清单，不靠感觉

- id：`release-checklist`
- 阶段：ship；档位：product；可信度：lived
- 规则：发布产物逐项打勾验证，清单固化进 skill
- 防什么：发版由一组互相独立的动作组成，漏掉一步不会报错。防止“看起来发完了”其实少了一块
- 链接：https://ainative.jubao.ai/docs/pitfalls/release-checklist

怎么做：

**把清单写下来，每一项都带验证方法**：

```markdown

## 网络报错先查远端

- id：`verify-remote-first`
- 阶段：ship；档位：product, org；可信度：lived
- 规则：网络类状态变更失败后，先确认远端真实状态，再决定重试还是放弃
- 防什么：超时和 503 只说明“结果未知”，不说明“失败”。先查远端再决定下一步，免得重复推送或把 tag 打错地方
- 链接：https://ainative.jubao.ai/docs/pitfalls/verify-remote-first

怎么做：

**先查远端，再决定**。分支、tag、release、流水线各有查法：

```bash
git ls-remote origin refs/heads/main    # 远端分支指向哪个提交，和 git rev-parse HEAD 对比
git ls-remote origin refs/tags/v1.4.2   # 远端有没有这个 tag
gh release view v1.4.2                  # release 建了没有
gh run list --limit 5                   # 发布流水线是不是已经跑起来了
```

**按结果分三条路**。加上 `--exit-code`，“没找到”和“连不上”的退出码就不一样了：

```bash
tag=v1.4.2
git ls-remote --exit-code origin "refs/tags/$tag" >/dev/null
case $? in
  0) echo "远端已有 $tag，不要重试" ;;
  2) echo "远端没有 $tag，用同一个名字重推" ;;
  *) echo "远端也查不到，等网络恢复，什么都别动" ;;
esac
```

**写进 CLAUDE.md 和子 agent 提示词**：网络类状态变更（push、打 tag、建 release、部署）失败后，先查远端；不许换名重试，不许用 `--force` 绕过。

## 分段审过了，还要整分支终审

- id：`whole-branch-review`
- 阶段：ship；档位：product, org；可信度：lived
- 规则：分段做的功能，合并前必须对整个分支做一次终审
- 防什么：每个阶段单独审过，不代表合在一起没问题。防止跨阶段、跨文件的交互 bug 混进主干
- 链接：https://ainative.jubao.ai/docs/pitfalls/whole-branch-review

怎么做：

**合并前看整个分支**。三个点表示“从分叉点算起”的全部改动：

```bash
git diff --stat main...HEAD   # 先看范围
codex review --base main      # 整个分支交给另一个模型家族审
```

`codex review --base` 不能再附加自定义提示词，它会按自带的审查标准看整个分支。内置的 `/code-review` 后面跟 PR 号，也能审整个 PR。

**换一个新会话来审**。做阶段审查的会话装满了各阶段的细节，也容易沿用之前“已经审过”的结论。

**点名要看的交互**：共享状态、调用约定、错误处理链路，以及阶段之间的假设有没有被后来的改动推翻。这些写进终审的提示词里（用 `codex exec` 或 gstack 的 `/codex` 发起；`codex review --base` 带不了自定义提示词）。

**把终审写进 PR 模板，作为合并关卡**：

```markdown
- [ ] 整分支终审：已做，发现 N 个问题，已处理 N 个
```

## 跨仓链接用完整地址

- id：`absolute-cross-repo-links`
- 阶段：maintain；档位：org；可信度：lived
- 规则：跨仓引用一律写完整 URL，并让园丁定期检查失效链接
- 防什么：指向 ops 仓的相对链接，换到 worktree、GitHub 网页或云端 agent 就全断，而且不报错
- 链接：https://ainative.jubao.ai/docs/pitfalls/absolute-cross-repo-links

怎么做：

**跨仓引用写完整 URL**，指向分支或固定的 commit：

```markdown
详见 [ADR-007](https://github.com/your-org/ops/blob/main/decisions/ADR-007_auth.md)
```

**让 CI 拦住仓外的相对链接**。CI 里只检出代码仓，`lychee --offline` 只检查本地文件链接，任何跳出仓库的相对链接都会因为目标不存在而报错：

```yaml
# .github/workflows/links.yml 里的一个 step
- uses: lycheeverse/lychee-action@v2
  with:
    args: --offline --no-progress './**/*.md'
```

**完整 URL 交给园丁定期查**。私有仓的链接匿名访问是 404，用带权限的 `gh api` 逐条确认，累计所有失败，最后统一用退出码报告：

```bash
#!/usr/bin/env bash
# 检查文档里所有指向 ops 仓的完整 URL
fail=0
while read -r url; do
  url=${url%%#*}                       # 去掉页内锚点
  rest=${url#https://github.com/}      # your-org/ops/blob/main/decisions/ADR-007_auth.md
  repo=${rest%%/blob/*}                # your-org/ops
  ref=${rest#*/blob/}; path=${ref#*/}; ref=${ref%%/*}
  gh api "repos/$repo/contents/$path?ref=$ref" --silent \
    || { echo "失效：$url" >&2; fail=1; }
done < <(grep -rhoE 'https://github\.com/your-org/ops/blob/[^)[:space:]]+' docs/ | sort -u)
exit $fail
```

这一步适合放进每周的园丁任务，和过期 review 日期一起查。我的园丁任务还在搭，这一步还没跑起来。<Evidence kind="trial" />

**agent 要读 ops 仓，显式接进来**。代码仓的 CLAUDE.md 只写一句指针（ops 仓的完整地址）；本机会话需要读写 ops 仓时，用 `permissions.additionalDirectories` 把它加进来，而不是靠相对路径碰运气。

## 跟代码绑定的文档跟代码放一起

- id：`code-coupled-docs`
- 阶段：maintain；档位：org；可信度：lived
- 规则：会随代码改的文档放代码仓，文档里的检查步骤改成 CI
- 防什么：恢复手册在 ops 仓里写着“Makefile 会先备份”，代码早被上游合并改掉，手册毫不知情
- 链接：https://ainative.jubao.ai/docs/pitfalls/code-coupled-docs

怎么做：

**用一句话判断归属**：这份内容会不会因为改代码而需要跟着改？会，放代码仓的 `docs/runbooks/`；不会（决策、商业背景、跨仓剧本），留在 ops 仓。ops 仓原来的位置只留一行完整 URL 指过去。

**文档里的检查步骤搬进 CI**，每个 PR 都跑，而且查行为、不查关键字。只 grep 到 `pg_dump` 不代表备份真的先跑、失败了会停。下面模拟备份失败，断言删库那一步不会执行：

```bash
#!/usr/bin/env bash
# scripts/check-db-reset-backup.sh
# 假的 pg_dump 直接失败，假的 dropdb 只记录自己被调用过
set -u
stub=$(mktemp -d)
printf '#!/bin/sh\nexit 1\n' > "$stub/pg_dump"
printf '#!/bin/sh\ntouch "%s/dropdb-called"\n' "$stub" > "$stub/dropdb"
chmod +x "$stub/pg_dump" "$stub/dropdb"
if PATH="$stub:$PATH" make db-reset >/dev/null 2>&1; then
  echo "备份失败时 db-reset 不该成功" >&2; exit 1
fi
[ ! -e "$stub/dropdb-called" ] || { echo "备份失败后仍执行了删库" >&2; exit 1; }
```

桩命令按你的 Makefile 实际调用的命令替换。平时想快速看一眼步骤顺序，用 `make -n db-reset`：它只打印要执行的命令、不真跑，前置目标里的命令也会列出来。

**fork 的共享文件重点守**。上游也会改的文件（Makefile、部署脚本、配置模板）里的定制改动，每一处都配一条 CI 断言，否则下一次合并照样无声冲掉。

**手册里只写“怎么做”，不写“代码会怎样”**。描述代码行为的句子最容易过时；能用脚本断言的，就别用文字承诺。

## 防护规则会悄悄失效

- id：`guardrails-decay`
- 阶段：maintain；档位：product, org；可信度：lived
- 规则：护栏要有体检：用脚本定期确认规则、hook 和备份步骤都还在
- 防什么：护栏被上游合并冲掉、被工具整份覆盖时不会报错。用体检脚本和 CI 断言，让它失效时有人知道
- 链接：https://ainative.jubao.ai/docs/pitfalls/guardrails-decay

怎么做：

这套体检是事故之后补上的，还在打磨。<Evidence kind="trial" />

要检查行为，不要只检查文本。`grep` 到 `pg_dump` 不代表备份还会执行，它可能躺在注释里，也可能属于别的 target；脚本文件还在，也不代表 hook 会被触发。

**写体检脚本**，放在项目的 `.claude/hooks/guardrail-check.sh`。三项都看行为，缺一项报一项，全部通过时不输出：

```bash
#!/usr/bin/env bash
s="$HOME/.claude/settings.json"   # 规则写在哪个文件，就查哪个
hook="$HOME/.claude/hooks/db-backup.sh"
miss() { echo "护栏缺失：$1"; }

# 1. ask 规则：按原文精确匹配
jq -e '(.permissions.ask // []) | index("Bash(make db-reset *)")' "$s" >/dev/null || miss "make db-reset 的 ask 规则"

# 2. 备份 hook：已挂载，并且喂一条模拟输入时真的会调用 pg_dump（pg_dump 和 HOME 都换成临时的）
jq -e '[.hooks.PreToolUse[]?.hooks[]?.command | strings] | any(test("db-backup"))' "$s" >/dev/null \
  || miss "备份 hook 没挂到 PreToolUse"
t=$(mktemp -d); printf '#!/bin/sh\ntouch "%s/called"\n' "$t" > "$t/pg_dump"; chmod +x "$t/pg_dump"
echo '{"tool_input":{"command":"make db-reset"}}' \
  | HOME="$t" PATH="$t:$PATH" DATABASE_URL=postgres://guard-check "$hook" >/dev/null 2>&1
[ -f "$t/called" ] || miss "备份 hook 收到 reset 命令时没有调用 pg_dump"
rm -rf "$t"

# 3. reset 目标：用 make -n 看实际步骤，pg_dump 必须排在 reset 之前
steps=$(make -n --no-print-directory -C "$CLAUDE_PROJECT_DIR" db-reset 2>/dev/null | grep -v '^[[:space:]]*#')
d=$(grep -n 'pg_dump' <<<"$steps" | head -1 | cut -d: -f1)
r=$(grep -n 'reset-db' <<<"$steps" | head -1 | cut -d: -f1)   # 换成你的 reset 命令
[ -n "$d" ] && [ -n "$r" ] && [ "$d" -lt "$r" ] || miss "db-reset 不再先备份"
exit 0
```

`make -n` 只打印、不执行，但带 `+` 前缀或含 `$(MAKE)` 的行照样会执行，reset 目标里别这么写。

**挂到项目级 `.claude/settings.json` 的 SessionStart 上**。每次开会话跑一次，输出直接进入 Claude 的上下文。这个文件进 git，切换工具不会动它，有人改了也能在 diff 里看到：

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guardrail-check.sh" }] }
    ]
  }
}
```

**上游也会改的文件，在 CI 里模拟一次备份失败**。CI 用的是一次性数据库，可以真跑：把 `pg_dump` 换成必然失败的假命令，断言 reset 停了下来。合并把定制改动冲掉，CI 就红：

```yaml
- name: 护栏断言：备份失败时 reset 必须停下
  run: |
    # DATABASE_URL 指向 CI 里的一次性数据库
    make -n db-reset > /dev/null
    psql "$DATABASE_URL" -c 'create table guard_marker (id int)'
    shim=$(mktemp -d) && printf '#!/bin/sh\nexit 1\n' > "$shim/pg_dump" && chmod +x "$shim/pg_dump"
    PATH="$shim:$PATH" make db-reset && { echo "备份失败了，reset 却照样执行"; exit 1; }
    psql "$DATABASE_URL" -c 'select 1 from guard_marker'   # 标记表还在，说明 reset 没跑
```

**最关键的几条放进托管设置**。macOS 上是 `/Library/Application Support/ClaudeCode/managed-settings.json`，优先级最高，写入要管理员权限，普通工具改不到。在 Claude Code 里运行 `/status`，Setting sources 一行能看到它有没有生效。

本手册插件里的 `/ainative:doctor` 也会做这类检查。

## 同一个组织的记忆不要按目录分裂

- id：`split-memory`
- 阶段：maintain；档位：org；可信度：lived
- 规则：同一组织统一一个自动记忆目录，别让记忆按启动目录分家
- 防什么：在父目录启动有 200 多条记忆，进子仓库只剩 7 条：自动记忆按启动位置分家，两边互相看不到
- 链接：https://ainative.jubao.ai/docs/pitfalls/split-memory

怎么做：

**选一个统一目录，各仓库都指过去**。在这个组织每个仓库（包括父目录）的 `.claude/settings.local.json` 里写：

```json
{
  "autoMemoryDirectory": "~/.claude/org-memory/<组织名>"
}
```

路径写绝对路径或以 `~/` 开头。推荐放在各仓库的 `.claude/settings.local.json`（不进 git）或用户级设置；部分版本会忽略项目级 `.claude/settings.json` 里的这个设置，出于安全考虑也不建议把它提交进仓库。放用户级 `~/.claude/settings.json` 时要注意，那样所有项目共用一份，两个组织的记忆会混在一起。

**合并已有记忆**。先整体备份，再用 `ls ~/.claude/projects/` 找到父目录和各子仓库对应的目录，把各自 `memory/` 下的主题文件拷进新目录。几份 `MEMORY.md` 索引让 Claude 合并去重，控制在 200 行以内。

**验证**。在子仓库开一个新会话，用 `/memory` 打开自动记忆文件夹，确认指向的是统一目录；再问一个只在父目录记过的坑，看它是否知道。

**不要再加新的存储**。团队结论进 ops 仓（经审查），个人判断留在这份自动记忆里。

## 模板复制后会各自漂移

- id：`template-copy-drift`
- 阶段：maintain；档位：org；可信度：lived
- 规则：共用规则做成可继承的模板（插件），不要复制
- 防什么：第二个组织的规则文件复制自第一个，半年后 6 处引用指向不存在的文件，复审日期也过期半年
- 链接：https://ainative.jubao.ai/docs/pitfalls/template-copy-drift

怎么做：

**通用部分抽成一个 ops 插件**（下面叫 `ops-kit`）：agent 定义、`/new-adr` 和 `/new-retro` 这类 SOP skill、审查流程、通用的拦截和备份 hook、体检脚本。插件带不了 deny / ask 规则，这部分交给 hook，或者由 setup skill 写进各仓库的设置。放进团队私有的插件市场，一个 git 仓库就够。

**各组织只写差异，用 `dependencies` 继承模板**。每个组织建一个自己的 ops 插件（比如 `org-a-ops`），在它的 `.claude-plugin/plugin.json` 里用 `dependencies` 声明依赖 `ops-kit`，启用组织插件时通用模板会一起启用（结构见[让 ops 和项目一起进化](/docs/org/evolve)）。再在 ops 仓的 `.claude/settings.json`（进 git）里声明市场、启用组织插件：

```json
{
  "extraKnownMarketplaces": {
    "team-tools": {
      "source": { "source": "github", "repo": "your-org/claude-plugins" }
    }
  },
  "enabledPlugins": {
    "org-a-ops@team-tools": true
  }
}
```

插件用相对路径放在市场仓库里时，成员信任这个目录后就会自动加载。模板升级只改 `ops-kit` 一处，各组织运行 `claude plugin update ops-kit@team-tools` 拿到新版。

**给规则文件加一道引用体检**，放进 CI 或园丁任务，引用的文件不存在就报出来：

```bash
grep -oE '`[A-Za-z0-9_./-]+\.(md|json|sh)`' CLAUDE.md | tr -d '`' | sort -u \
  | while read -r p; do [ -e "$p" ] || echo "引用失效: $p"; done
```

**复审日期交给园丁**。每周扫一遍过期的“下次 review 日期”，过期就提醒或直接提 PR。<Evidence kind="trial" />

## 对外内容先读权威文档

- id：`read-canonical-first`
- 阶段：cross；档位：product, org；可信度：lived
- 规则：写长期对外的文档之前，先读相关的权威文档
- 防什么：凭记忆写的对外材料，定位和细节都可能停在旧版本。防止过时的说法进入长期对外的文档
- 链接：https://ainative.jubao.ai/docs/pitfalls/read-canonical-first

怎么做：

**动笔前先列出权威文档**：当前的 README、相关的 spec、最近的 ADR、CHANGELOG、官方文档。哪份算数，写之前就说清楚。

**把要求写进提示词**：

```text
写之前先读：README.md、docs/specs/ 下对应的 spec、docs/adr/ 里最近的决策、CHANGELOG.md。
写完附一张事实表：每个数字、版本号、名称后面写出处（文件路径或 URL）。
找不到出处的标“待核实”，不要凭印象补。
```

**第三方库和工具的用法查最新文档**：用 context7 这类查文档的 MCP，或者直接读官方文档，不靠模型记忆。

**写进 CLAUDE.md**，让每次会话都照做：写对外文档前先读权威文档，凭记忆写的内容一律标“待核实”。

这本手册的写作规范里也有同一条：命令、版本号、日期和数字都要有出处，查不到就不写。

