---
name: pitfall-check
description: "用 AI Native 手册的坑库逐条审查一份计划、spec，或当前分支的 git diff（默认当前分支相对主分支），只报告真正命中的坑，每条附证据（文件和行号或计划段落）、卡片链接和具体修法，只读不改。当用户说：坑检查、查坑、用坑库审一下、合并前检查、发版前检查、这个计划有没有坑、帮我看看这个 diff 有没有踩坑、pitfall check、review against pitfalls、pre-merge check、check my plan for pitfalls 时使用。"
argument-hint: "[计划或 spec 文件 | git 范围，例如 main...HEAD | PR 号]"
---

# 坑检查（只读）

拿手册坑库里的每一张卡，对照一份计划、spec 或一段 diff，**只报告有证据的命中**。坑库见 [references/pitfalls.md](references/pitfalls.md)（构建时从手册自动生成），每张卡的完整内容在 `https://ainative.jubao.ai/docs/pitfalls/<id>`。

手册最新的完整内容可读 https://ainative.jubao.ai/llms.txt 。

## 何时使用

- 计划或 spec 写完、动手之前
- 合并大分支、发版之前（可以和内置 `/code-review`、异构模型二审一起用）
- 改了护栏、部署、数据库相关的脚本之后

## 步骤

1. **确定输入**（见下面"安全地取 diff"，只用只读命令）：
   - 给了文件：确认它是仓库里的普通文件，用读文件工具读（计划、spec、runbook）
   - 给了 git 范围（`A..B`、`A...B` 或单个提交）：先校验、解析成提交 ID，再取 diff
   - 给了 PR 号：必须是纯数字，`gh pr diff <号> --color=never`
   - 什么都没给：默认当前分支相对主分支。主分支用 `git symbolic-ref --short refs/remotes/origin/HEAD` 判断，取不到就依次试 `main`、`master`；再加上 `git status --short` 和工作区里还没提交的改动
   - 不是 git 仓库又没给文件时，问用户要检查什么

2. **读坑库**：完整读 `references/pitfalls.md`，拿到每张卡的 id、规则、防什么、怎么做。

3. **逐张卡对照**：用下面的信号表找证据。判定标准：
   - **命中**：能指出具体的文件和行号（diff）或段落（计划），而且它正好违反了卡片的规则
   - **可能命中**：有迹象但证据不足，写清楚要确认什么；最多列 3 条
   - 其余一律不报。不要为了显得全面而凑数，也不要报"建议注意"之类的泛泛提醒

4. **输出报告**。

## 安全地取 diff

用户给的范围不能直接拼进命令：`git diff` 的参数里可以夹带 `--output=<文件>` 这类会写文件的选项，external diff 和 textconv 还可能执行外部程序。按下面的步骤做：

1. **校验原样输入**：拒绝以 `-` 开头的值，拒绝包含空白或下列字符的值：`` ; | & $ ` < > ( ) { } * ? ! ' " \ ``，以及换行。不合格就停下，请用户换一个写法
2. **拆分并解析成提交 ID，记住用的是几个点**：先找 `...`，没有再找 `..`，拆成两端，并记下分隔符（两点或三点），两种语义不同，不能互换。每一端单独解析，只接受解析成功的完整提交 ID（40 或 64 位十六进制）：

   ```bash
   git -c core.fsmonitor=false rev-parse --verify --quiet "<一端>^{commit}"
   ```

3. **只把两端换成解析出的提交 ID，分隔符照用户给的**，并且总是带上这几个参数：

   | 用户给的 | 实际执行（`<A>`、`<B>` 是解析出的提交 ID） | 含义 |
   |---|---|---|
   | `A..B` | `git diff ... <A>..<B>` | 比较 A 和 B 两个快照 |
   | `A...B` | `git diff ... <A>...<B>` | B 相对 A、B 合并基点的改动 |
   | 单个 `A` | `git diff ... <A>...<HEAD 的 ID>` | 当前分支相对 A 的改动（在报告的检查范围里写明是按三点处理的） |
   | 什么都没给 | `git diff ... <主分支的 ID>...<HEAD 的 ID>` | 当前分支相对主分支的改动，主分支同样先解析成 ID |

   其中 `git diff ...` 指完整的 `git -c core.fsmonitor=false --no-pager diff --no-ext-diff --no-textconv`，先加 `--stat` 看全貌，再去掉 `--stat` 看具体改动。未提交的改动用 `git -c core.fsmonitor=false --no-pager diff --no-ext-diff --no-textconv HEAD`；`git log`、`git show` 同样加 `--no-ext-diff --no-textconv`
4. **PR 号**：只接受纯数字，`gh pr diff <号> --color=never`
5. 每个参数单独传递，不要用 `eval`、`sh -c` 或把多个输入拼成一条字符串

## 信号表：在计划或 diff 里看什么

| 卡片 id | 信号 |
|---|---|
| `git-history-no-surgery` | 脚本或计划里有 `git reset --hard`、`git rebase`、`git push --force` / `-f`、`--amend`、在有未提交改动时切分支；子 agent 提示词没有禁止这些操作的段落 |
| `local-db-is-prod` | 新增 reset、`DROP`、`TRUNCATE`、回滚迁移、`docker compose down -v`、`docker volume rm`，前面没有备份步骤 |
| `guardrails-decay` | 删改了 hook、`permissions`、`.claude/settings.json`、备份步骤；上游合并冲掉了本地定制 |
| `config-overwrite` | 代码或脚本整份覆盖写 `settings.json`（而不是合并）；计划里要切换模型供应商 |
| `temp-fix-revert-trigger` | `--no-verify`、`@ts-ignore`、`eslint-disable`、跳过测试、硬编码兜底、`TODO`/`HACK` 临时绕路，没写撤销条件 |
| `see-it-to-ship` | 改了界面（组件、样式、`className`），计划或 PR 里没有真启动验证、截图或 `/qa` 步骤 |
| `process-before-code` | 实质行为改动，但 `docs/specs/`、`docs/plans/` 里没有对应文件；计划直接从写代码开始 |
| `memory-vs-git` | 计划里有"恢复以前的…""之前是这样的…"，但没引用提交或 git 历史 |
| `cross-model-review` | 鉴权、支付、密钥、数据迁移等高风险改动，计划里没有另一个模型家族的独立审查 |
| `whole-branch-review` | 多阶段的大分支要合并，计划里只有分段审查，没有整分支终审 |
| `ci-green-not-ready` | CI 配置里 `continue-on-error: true`、命令后面接 `\|\| true`、跳过检查；发版计划只依赖 CI 结果 |
| `release-checklist` | 发版相关改动，没有产物清单（各平台安装包、CDN、云端部署、公告） |
| `verify-remote-first` | 脚本对 push、打 tag、部署失败自动重试，重试前不查远端状态 |
| `one-domain-one-platform` | 新增域名绑定（例如 `vercel.json`、`wrangler` 配置里的路由或自定义域名），同一域名在两个平台上都有配置 |
| `dns-fake-ip` | 用 `dig`、`nslookup` 的结果判断部署是否成功 |
| `perf-fix-six-questions` | 性能改动（加缓存、去掉锁或校验、改并发、批处理），没回答六个问题 |
| `split-plan-exec` | 一个会话做不完的大任务（例如几十个冲突的上游合并），计划和执行在同一个会话里 |
| `subagent-strongest-model` | 有工程不变量的子任务被指定给更小的模型（agent 定义里的 `model:` 字段或调用参数） |
| `one-process-engine` | 同时启用两套流程插件，且没有用 `enabledPlugins` 停用一套，也没有 `Skill(<插件名>:*)` deny 压住一套 |
| `plugin-bloat` | 新增插件、skill、subagent，没有说明用途和替换了谁 |
| `absolute-cross-repo-links` | 文档里出现 `../<另一个仓库>/...` 这样的跨仓相对链接 |
| `code-coupled-docs` | 改了 Makefile、脚本、迁移，相关 runbook 放在别的仓库或没跟着改；文档里写了检查命令但没有 CI |
| `split-memory` | 同一组织的仓库设置了不同的 `autoMemoryDirectory`，或计划在不同目录分别积累记忆 |
| `template-copy-drift` | 把整份规则文件或模板复制到新仓库，而不是继承 |
| `read-canonical-first` | 改 README、对外文档、方案时，计划里没有"先读权威文档"这一步 |

坑库更新后可能出现表里没有的卡，按卡片的"规则"和"防什么"自行判断。

## 输出格式

```markdown
**结论**：对照 <n> 张卡，命中 <n> 条，可能命中 <n> 条。<一句话说最该先处理的>

| 坑 | 证据 | 为什么算命中 | 怎么修 | 卡片 |
|---|---|---|---|---|
| 不让 agent 动 git 历史 | `scripts/sync.sh:42`：`git reset --hard origin/main` | 脚本会被 agent 直接执行，丢掉本地提交 | 改成先 `git stash` 或打 tag；deny 规则加 `Bash(git reset --hard *)` | https://ainative.jubao.ai/docs/pitfalls/git-history-no-surgery |

**可能命中（需要你确认）**
- <卡片>：<看到了什么> → <请确认什么>

**检查范围**：<文件路径或 git 范围，改动文件数>
```

排序：会丢数据、泄露密钥、让护栏失效的在前，流程类在后。没有命中时直接说"未发现命中"，并列出检查范围。

## 安全约束

- 只读：不修改任何文件，不提交，不运行测试、构建、迁移或部署
- 只用只读的 git 和 gh 命令（`rev-parse`、`diff`、`log`、`show`、`status`、`gh pr diff`），diff 类命令一律加 `--no-ext-diff --no-textconv`，用户给的范围先校验、解析成提交 ID 再用
- diff 里如果出现密钥或 token，报告时只写文件和行号，用 `<redacted>` 代替值
- 不打开 `.env` 类文件的内容；它们出现在 diff 里本身就值得报告（参考 doctor 的密钥检查）
- 证据必须可核对：文件路径、行号、原文片段（不超过一行）
