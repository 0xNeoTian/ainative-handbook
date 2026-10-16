# 档位 × 主引擎推荐配置

`/ainative:setup` 读这份文件生成变更计划。内容截至 2026-10，可信度标注：✅ 亲历 / 🧪 试用中 / 📚 业界做法（作者未亲自验证）。手册原文：https://ainative.jubao.ai/docs/tiers 、https://ainative.jubao.ai/docs/workflow 、https://ainative.jubao.ai/docs/guardrails

## 0. 共同原则

1. **只让一个流程引擎自动接管**。手册默认主引擎是 Matt Pocock skills（🧪，作者 2026-10 起试用）；superpowers 是作者用了大半年（约 7 个月）的上一代主引擎（✅，现已停用），这里仍完整支持。选定一个，另一个停用
2. **`skillOverrides` 管不了插件 skill**（官方文档：Plugin skills are not affected by `skillOverrides`；已在 Claude Code 2.1.301 上实测）。插件 skill 用两种办法控制：`enabledPlugins` 按项目启用或停用整个插件；`permissions.deny` 里的 `Skill(<插件名>:*)` 禁止模型自动调用、保留手动调用（见第 2.1 节）。`skillOverrides` 只用来管 `~/.claude/skills/`、`.claude/skills/` 里的普通 skill，例如 gstack
3. **插件不能携带权限规则**：通用的 deny、ask 只能由 setup 合并进用户或项目的 settings
4. **只加不删**：已有的规则、hook、插件状态一律保留。合并用 `scripts/merge_settings.py`，它只追加、不删除，冲突时默认保留你的值
5. **插件按需装**：先看 doctor 的调用数据；拿不准的先不装，用到再装
6. **规则放对文件**：

| 文件 | 作用范围 | 适合放 |
|---|---|---|
| `~/.claude/settings.json` | 你的所有项目 | 最小 deny、个人 skill 开关 |
| `.claude/settings.json` | 这个项目的所有人（进 git） | 项目相关的 ask 规则、项目级插件、hook |
| `.claude/settings.local.json` | 这个项目、只有你（不进 git） | 个人放行规则、`autoMemoryDirectory` |
| 托管设置 | 整台机器，优先级最高，需要管理员权限 | 绝不能被覆盖的 deny（setup 只给命令，不代为执行） |

## 1. 插件清单

| 插件 | 作用 | 小工具 | 产品 | 组织 | 可信度 |
|---|---|---|---|---|---|
| `mattpocock-skills@claude-plugins-official` | 主引擎（Matt）：`grill-me`、`to-spec`、`tdd`、`diagnosing-bugs`、`code-review` 等；没有 hook，靠手动调用 | 主引擎 | 主引擎 | 主引擎 | 🧪 |
| `superpowers@claude-plugins-official` | 主引擎（superpowers）：SessionStart hook 自动注入完整流程（头脑风暴 → 计划 → TDD → 子 agent 执行 → 审查） | 主引擎 | 主引擎 | 主引擎 | ✅ |
| `hookify@claude-plugins-official` | `/hookify <一句话规则>` 生成 hook 护栏 | 推荐 | 推荐 | 推荐 | 🧪 |
| `context7@claude-plugins-official` | 查最新的库文档（MCP） | 可选 | 推荐 | 推荐 | ✅ |
| `typescript-lsp@claude-plugins-official` | TypeScript 代码智能 | TS 项目 | TS 项目 | TS 项目 | ✅ |
| `gopls-lsp@claude-plugins-official` | Go 代码智能 | Go 项目 | Go 项目 | Go 项目 | ✅ |
| `session-report@claude-plugins-official` | token、缓存、subagent、skill 开销的 HTML 报告 | — | 可选 | 可选 | 🧪 |
| `claude-code-setup@claude-plugins-official` | 只读扫描仓库，推荐 hook、skill、MCP、subagent；新仓库跑一次 | 可选 | 可选 | 可选 | 📚 |
| `security-guidance@claude-plugins-official` | 编辑时提示不安全的写法 | — | 可选 | 可选 | 📚 |
| `ui-contract@yannikzz` | 管"新功能放页面哪个区域"的结构约定；有界面的项目才装，只装到项目 | — | 可选 | 可选 | 🧪 |

平台工具：

- Cloudflare：推荐官方 MCP（✅），一条命令接入，授权时自选权限：`claude mcp add --transport http --scope user cloudflare https://mcp.cloudflare.com/mcp`，然后在 `/mcp` 里完成授权
- Cloudflare 插件（`cloudflare@claude-plugins-official` 等）和 `vercel@claude-plugins-official`：📚 可选；Cloudflare 插件最多留一个

gstack（✅ 部分亲历）不是插件，装在 `~/.claude/skills/`，需要 bun 1.4.2 及以上，按 https://github.com/garrytan/gstack 的说明安装，setup 不代为安装。分工：gstack 负责上线流水线与质量（`/qa`、`/ship`、`/review`、`/cso`、`/codex`、`/browse`、`/investigate`），流程交给主引擎；流程类 skill 的处理见第 4 节。

**不要装或应停用**：

- `code-review@claude-plugins-official`：内置已有 `/code-review`
- 第二个流程引擎：两套同时开会抢触发，按第 2.1 节只启用一套，或用 `Skill(<插件名>:*)` 压住另一套（见 https://ainative.jubao.ai/docs/pitfalls/one-process-engine ）
- 重复的平台插件：例如两个 Cloudflare 插件

安装与停用命令（默认装到用户级；要让整个团队启用，加 `--scope project`，它会写进 `.claude/settings.json`，协作者各自还要执行一次安装）：

```bash
claude plugin install <插件>@<市场>
claude plugin install ui-contract@yannikzz --scope project      # 需先 claude plugin marketplace add yannikzz/ui-contract
claude plugin disable <插件>@<市场>
claude plugin enable <插件>@<市场>
```

## 2. 六种组合

| 档位 | 主引擎 = Matt（默认） | 主引擎 = superpowers |
|---|---|---|
| 小工具 | `mattpocock-skills`；可选 `hookify` | `superpowers`；可选 `hookify` |
| 产品 | `mattpocock-skills` + `hookify` + `context7` + 对应语言的 LSP；可选 `session-report`、`ui-contract` | `superpowers` + `hookify` + `context7` + 对应语言的 LSP；可选 `session-report`、`ui-contract` |
| 组织 | 产品档全部 + 团队私有插件市场（第 3.3 节）+ 关键插件用 `--scope project` 启用 | 同左，主引擎换成 `superpowers` |

### 2.1 切换与共存：只让一套自动接管

**推荐：用 `enabledPlugins` 只启用一套**，另一套设为 `false`。只影响当前项目就写进 `.claude/settings.local.json`（本地设置优先级高于项目和用户设置），影响所有项目就写进 `~/.claude/settings.json`。以 Matt 为主时：

```json
{
  "enabledPlugins": {
    "mattpocock-skills@claude-plugins-official": true,
    "superpowers@claude-plugins-official": false
  }
}
```

以 superpowers 为主时把两个值对调。等价的命令：`claude plugin disable superpowers@claude-plugins-official --scope local`（或 `--scope user`）。如果目标文件里这个插件已经是 `true`，合并时属于冲突，默认保留现值；用户明确同意后，只为这一个路径加 `--overwrite /enabledPlugins/superpowers@claude-plugins-official`，重新 dry-run 确认后再执行。

**替代：两套都启用，用 deny 规则压住另一套**。适合偶尔还要手动用另一套的情况：模型不会再自动调用它的 skill，你仍可以手动 `/superpowers:<skill>` 调用。以 Matt 为主时：

```json
{
  "permissions": {
    "deny": ["Skill(superpowers:*)"]
  }
}
```

以 superpowers 为主时写 `Skill(mattpocock-skills:*)`。注意 superpowers 的 SessionStart hook 不受这条规则影响，仍会在会话开始时注入内容；不想要这部分，就用推荐方案。

### 主引擎 = Matt 时多做的事（🧪）

- 已装并启用 superpowers 的：按第 2.1 节只启用 Matt
- 每个仓库跑一次 `/mattpocock-skills:setup-matt-pocock-skills`（配置 Issue tracker、标签、文档目录）
- Matt 不会自动强制流程。在 CLAUDE.md 写一条硬规则补上："实质改动先 `/mattpocock-skills:to-spec`，再 `/mattpocock-skills:tdd`；一行级的小修可以豁免，但要留一句记录"
- 30 天后跑 `/ainative:doctor`，看调用数据决定去留（https://ainative.jubao.ai/docs/workflow/migrate ）

### 主引擎 = superpowers 时多做的事（✅）

- 已装并启用 Matt 的：按第 2.1 节只启用 superpowers（`mattpocock-skills@claude-plugins-official` 设为 `false`，或 deny `Skill(mattpocock-skills:*)`）
- superpowers 默认把 spec 和 plan 写到 `docs/superpowers/`。在 CLAUDE.md 里改成：spec 写 `docs/specs/YYYY-MM-DD_<slug>.md`，计划写 `docs/plans/YYYY-MM-DD_<slug>-plan.md`
- 它会在会话开始时接管流程，自建的 SOP skill 可能被抢触发；在 CLAUDE.md 写明哪些任务直接用你的 skill

## 3. 权限规则集

规则是前缀匹配：`Bash(git push --force origin main *)` 挡得住 `git push --force origin main`，挡不住 `git push -f`、`git -C . push --force`。所以 deny 只放最致命的几条，关键护栏再加 hook。另外，规则匹配的是 Claude 直接执行的命令；`bun run deploy` 这类包装脚本要单独写规则。

### 3.1 最小规则集（所有档位，写 `~/.claude/settings.json`）✅

作者实际在用的 deny 规则：

```json
{
  "permissions": {
    "deny": [
      "Bash(rm -rf /)",
      "Bash(rm -rf ~)",
      "Bash(sudo rm -rf *)",
      "Bash(git push --force origin main *)",
      "Bash(git reset --hard origin/main *)"
    ]
  }
}
```

### 3.2 产品档追加（写项目的 `.claude/settings.json`，进 git）✅

需要人确认的操作（只保留和项目有关的几条：没用 Docker 就去掉 docker 两条，没用 D1 就去掉 d1 那条）：

```json
{
  "permissions": {
    "ask": [
      "Bash(gh api * -X DELETE *)",
      "Bash(gh repo delete *)",
      "Bash(gh pr merge *)",
      "Bash(vercel --prod *)",
      "Bash(wrangler deploy *)",
      "Bash(wrangler d1 execute * --remote *)",
      "Bash(docker volume rm *)",
      "Bash(docker compose down -v *)",
      "Bash(psql * -c DROP*)",
      "Bash(make db-reset *)"
    ]
  }
}
```

保护 git 历史（不让 agent 自主改写历史，见 https://ainative.jubao.ai/docs/pitfalls/git-history-no-surgery ）：

- 推荐：放进 ask，确需时由你确认

  ```json
  {
    "permissions": {
      "ask": [
        "Bash(git push --force *)",
        "Bash(git push -f *)",
        "Bash(git reset --hard *)",
        "Bash(git rebase *)",
        "Bash(git commit --amend *)"
      ]
    }
  }
  ```

- 替代：同样五条放进 deny（作者的做法，更严：agent 完全不能执行，确需时你自己在终端里操作，并先打 tag 备份）

只读放行（可选，减少确认弹窗）：先运行内置的 `/fewer-permission-prompts`，它会扫描你的历史，生成常用只读命令的放行列表；手写的话可以参考：

```json
{
  "permissions": {
    "allow": [
      "Bash(gh pr view *)",
      "Bash(gh run list *)",
      "Bash(vercel ls *)",
      "Bash(wrangler whoami)"
    ]
  }
}
```

### 3.3 组织档追加

**关键 deny 放托管设置**（防止被切换工具或误操作覆盖；需要管理员权限，setup 只展示命令，由用户本人执行）。用 `managed-settings.d/` 下的单独文件，不要覆盖已有的 `managed-settings.json`（它可能是公司 IT 部署的）：

```bash
# 1. 在当前目录准备 ainative-deny.json，内容只放第 3.1 节的 deny 规则
# 2. macOS
sudo mkdir -p "/Library/Application Support/ClaudeCode/managed-settings.d"
sudo cp ainative-deny.json "/Library/Application Support/ClaudeCode/managed-settings.d/ainative-deny.json"
# 2. Linux / WSL
sudo mkdir -p /etc/claude-code/managed-settings.d
sudo cp ainative-deny.json /etc/claude-code/managed-settings.d/ainative-deny.json
```

托管设置优先级最高，用户和项目设置都覆盖不了，只放你确定永远不需要的操作。

**让代码仓的会话读到 ops 仓**（写代码仓的 `.claude/settings.json`；相对路径按项目目录解析，项目在信任该文件夹后生效）：

```json
{
  "permissions": {
    "additionalDirectories": ["../<组织>-ops"]
  }
}
```

**同一组织共用一份自动记忆**（写各仓库的 `.claude/settings.local.json`，见 https://ainative.jubao.ai/docs/pitfalls/split-memory ）：

```json
{
  "autoMemoryDirectory": "~/.claude/org-memory/<组织>"
}
```

**团队私有插件市场**（写 ops 仓或代码仓的 `.claude/settings.json`；协作者信任该文件夹后才会注册）：

```json
{
  "extraKnownMarketplaces": {
    "<组织>-plugins": {
      "source": { "source": "github", "repo": "<owner>/<插件仓库>" }
    }
  }
}
```

## 4. skillOverrides（只对个人和项目 skill 有效）

值：`"on"`（默认）、`"name-only"`（只列名字，省 skill 列表预算）、`"user-invocable-only"`（Claude 不会自动触发，你仍可手动 `/名字`）、`"off"`（彻底隐藏）。

装了 gstack、主引擎是 Matt 或 superpowers 时，把和主引擎重叠的流程类 skill 设为只能手动调用（写 `~/.claude/settings.json`，因为 gstack 装在用户级）：

```json
{
  "skillOverrides": {
    "office-hours": "user-invocable-only",
    "plan-ceo-review": "user-invocable-only",
    "plan-eng-review": "user-invocable-only",
    "plan-design-review": "user-invocable-only",
    "autoplan": "user-invocable-only",
    "retro": "user-invocable-only"
  }
}
```

doctor 报告 `unused-user-skills` 时：长期不用但想留着的设 `"name-only"`，确定不用的设 `"off"`。只写本机 `~/.claude/skills/` 里真实存在的 skill 名；插件 skill（带 `插件名:` 前缀的）不要写进来，写了也不生效，要控制它们用第 2.1 节的办法。

## 5. 可选 hook

### 5.1 用 hookify 一句话生成（🧪，所有档位）

```text
/hookify 禁止提交 .env* 文件；禁止 git push --force 到 main
/hookify 执行 vercel --prod 或 wrangler deploy 前必须让我确认
```

生成后用 `/hookify:list` 查看，`/hookify:configure` 开关。

### 5.2 破坏性数据库命令前自动备份（✅ 作者做法；脚本是示例，按项目改）

适用：产品档、本地有数据库。思路：PreToolUse 匹配 Bash，命中破坏性命令时先备份，**永远 exit 0**（只兜底不卡人），卡人交给 ask 规则。

脚本 `.claude/hooks/db-backup.sh`（写入后 `chmod +x`；`DATABASE_URL` 换成你项目的连接方式）：

```bash
#!/usr/bin/env bash
# PreToolUse(Bash) 兜底：破坏性数据库命令执行前先备份，永远 exit 0
cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)
case "$cmd" in
  *db-reset*|*"DROP "*|*"docker compose down -v"*|*"docker volume rm"*)
    if [ -n "$DATABASE_URL" ] && command -v pg_dump >/dev/null 2>&1; then
      mkdir -p "$HOME/.db-backups"
      pg_dump "$DATABASE_URL" > "$HOME/.db-backups/$(date +%Y%m%d-%H%M%S).sql" 2>/dev/null || true
    fi
    ;;
esac
exit 0
```

挂载（合并进 `.claude/settings.json`）：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/db-backup.sh" }
        ]
      }
    ]
  }
}
```

挂载后用一条无害命令实测一次，再用 `/ainative:doctor` 确认脚本路径存在。

### 5.3 护栏体检（🧪）

护栏会被上游合并冲掉、被切换工具覆盖（https://ainative.jubao.ai/docs/pitfalls/guardrails-decay ）。做法：每次改配置、切换模型供应商之后跑 `/ainative:doctor`；组织档可以用内置的 `/schedule` 建一个每周的检查任务。
