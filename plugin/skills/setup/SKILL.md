---
name: setup
description: "按 AI Native 手册给 Claude Code 落地配置：根据档位（小工具/产品/组织）和主引擎（Matt Pocock skills 或 superpowers）安装、启用、停用插件，合并权限规则和 hook，设置个人 skill 开关。会改配置，但一定先体检、出变更计划、做 dry-run、等你明确确认，执行前自动备份，从不删除你已有的规则。当用户说：帮我配置 Claude Code、按手册配置、应用体检建议、加护栏、装推荐插件、精简插件、切换流程引擎、setup、configure Claude Code、apply doctor fixes、install recommended plugins 时使用。"
argument-hint: "[tool|product|org] [matt|superpowers]"
---

# 安装与配置（写操作，先计划后执行）

按手册的档位和主引擎，把插件、权限规则、hook 和 skill 开关配到位。**任何写操作之前都要先给出计划并等用户明确确认**；执行时自动备份，可以一键撤销。

手册最新的完整内容可读 https://ainative.jubao.ai/llms.txt 。推荐配置见 [references/profiles.md](references/profiles.md)。

## 何时使用

- `/ainative:doctor` 报告了问题，要按建议修
- 新机器或新项目，要一次配好推荐的插件和护栏
- 要从 superpowers 切到 Matt Pocock skills（或反过来）
- 用过模型供应商切换工具，设置被覆盖了，要恢复护栏

## 步骤

### 1. 拿到事实

本会话里刚跑过 doctor 就直接用它的结果；否则运行（只读）：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/doctor/scripts/doctor.py" --days 90 --project "<当前工作目录的绝对路径>"
```

路径没被替换或找不到脚本时，用 `ls "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/plugins/cache/*/ainative/*/skills/doctor/scripts/doctor.py` 定位。

### 2. 确定档位和主引擎

- 用户在参数或对话里给了就直接用
- 没给：根据 doctor 的 `project.signals`、已装插件和 https://ainative.jubao.ai/docs/tiers 先推荐一个，再请用户确认。一次最多问两个问题（档位、主引擎）
- 主引擎默认推荐 Matt Pocock skills（手册当前主推，🧪 试用中）；用户正在用 superpowers 且满意，就按 superpowers 配（✅ 作者用过一年）。两种都按 profiles.md 完整支持

### 3. 生成变更计划

读 profiles.md，对照 doctor 结果，只列**需要变化**的项：

- **A. 插件**：要安装、启用、停用的插件，每条附命令和理由。不做卸载，除非用户明确要求。切换或共存流程引擎时按 profiles.md 第 2.1 节：推荐用 `enabledPlugins` 只启用一套（只影响当前项目就写 `.claude/settings.local.json`）；用户还想手动用另一套时，改为在 `permissions.deny` 合并 `Skill(<插件名>:*)`
- **B. 设置合并**：每个目标文件一份 JSON 片段。产品档的 ask 规则按项目实际裁剪（没有 Docker 就去掉 docker 规则）。对每个文件先跑 dry-run，把它输出的变更清单、diff 和 `plan id` 放进计划：

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/merge_settings.py" --scope user --dry-run --patch - <<'JSON'
  { "permissions": { "deny": ["Bash(rm -rf ~)"] } }
  JSON
  ```

  - 项目文件用 `--scope project` 或 `--scope local` 加 `--project <路径>`；`--scope user` 会按 `CLAUDE_CONFIG_DIR`（默认 `~/.claude`）定位
  - 输出里 env、headers 的值、已有 hook 的命令和疑似密钥都已隐藏，照原样展示，不要去原文件里补全
  - **冲突**：现值和建议值不同时，默认保留现值（`= kept`）。用户同意覆盖哪个值，就只为那个路径加一个 `--overwrite <路径>`（路径就是输出里的 JSON Pointer，例如 `--overwrite /permissions/defaultMode`、`--overwrite /enabledPlugins/superpowers@claude-plugins-official`），然后**重新跑 dry-run**，把新的 diff 和新的 `plan id` 给用户确认。没有被点名的冲突一律保留
- **C. skill 开关**：`skillOverrides` 只针对 `~/.claude/skills/`、`.claude/skills/` 里真实存在的普通 skill（例如 gstack）。插件 skill 写进 `skillOverrides` 不会生效，要用 A 里的 `enabledPlugins` 或 `Skill(<插件名>:*)` deny。插件本身也不能携带权限规则，通用的 deny、ask 都要在 B 里合并进用户或项目的 settings
- **D. hook（可选）**：要新建的脚本（展示完整内容）和挂载片段
- **E. 需要用户本人执行的命令**：托管设置（需要管理员权限）
- **F. 不会改的地方**：例如冲突时保留了用户现有的值

### 4. 展示计划和影响，等待确认

按下面的格式展示，然后**停下来等用户回复**。只有明确的同意（"确认""执行""可以，执行吧""yes, go ahead"）才算确认；含糊回复或提出修改，就改计划后重新展示。用户可以只确认其中几部分。

### 5. 执行（只做已确认的部分）

1. 插件：逐条执行 `claude plugin install|enable|disable <插件>@<市场>`（项目级加 `--scope project`）。任何一步失败就停下报告
2. 设置：用**和用户确认的那次 dry-run 完全相同的参数**（同一个目标、同样的 patch 内容、同样的 `--overwrite` 列表、同样的备份目录），去掉 `--dry-run`，加上 `--expect-plan <确认过的 plan id>`。脚本最先核对 plan id：文件内容、patch、`--overwrite` 或备份目录只要有一处和 dry-run 时不同，就拒绝写入（退出码 4），这时重新 dry-run、重新确认，不要换参数硬写。写入前先把原文件备份到 dry-run 里列出的备份目录（默认 `<配置目录>/backups/ainative/`，目录权限 0700，文件 0600）；备份目录位于任何 git 仓库内时（例如 `CLAUDE_CONFIG_DIR` 指向仓库里），脚本在 dry-run 阶段就会拒绝，这时请用户选一个仓库外的目录，用 `--backup-dir <目录>` 重新 dry-run。然后原子写入并自检；如果在替换前发现文件被别人改过，它什么都不写、也不恢复（退出码 5）
3. hook 脚本：写入计划里展示过的内容，`chmod +x`
4. 记下每个文件的备份路径和撤销命令（脚本输出的 `undo:` 行，已做 shell 转义）

### 6. 复核

- 再跑一次 doctor，对比前后的 `findings`：该消失的应已消失，没有新增 P0
- `claude plugin list` 确认插件状态
- 新建了 `.claude/settings.local.json` 的，确认它不会被 git 提交（`git check-ignore -v .claude/settings.local.json`）

### 7. 收尾提醒

- 重启 Claude Code，让插件和设置变更完整生效（插件也可以先运行 `/reload-plugins`）
- 列出全部备份文件和撤销命令。备份目录不在任何 git 仓库里（脚本会检查），不会被 `git add` 带走；但里面是原文件的完整内容（包括其中的密钥），确认无误后删除
- 用了模型供应商切换工具（CC Switch 这类）的：切换时可能再次整份覆盖 `~/.claude/settings.json`，每次切换后重跑 `/ainative:doctor`；关键 deny 可以按 profiles.md 第 3.3 节放进托管设置
- 主引擎是 Matt 的：提醒每个仓库跑一次 `/mattpocock-skills:setup-matt-pocock-skills`，30 天后用 doctor 数据复查
- 项目 `.claude/settings.json` 有改动的：请用户自己看过 diff 再提交

## 计划的输出格式

````markdown
## 变更计划（尚未执行）

档位：<小工具 / 产品 / 组织>　主引擎：<Matt Pocock skills 🧪 / superpowers ✅>　依据：<一句话>

### A. 插件
| 操作 | 插件 | 范围 | 理由 |
|---|---|---|---|
| 安装 | `hookify@claude-plugins-official` | 用户 | 一句话生成 hook 护栏 |
| 停用 | `superpowers@claude-plugins-official` | 用户 | 只留一个流程引擎 |

### B. 设置合并
**`~/.claude/settings.json`**（执行前自动备份到 `<dry-run 列出的备份目录>`）　plan id：`<dry-run 输出的 plan id>`
```diff
<dry-run 输出的 diff（已隐藏敏感值）>
```
冲突（默认保留你现在的值）：<JSON Pointer 路径：现值 / 建议值>。要覆盖哪一个，请点名路径，我会只为它重新生成计划

### C. skill 开关
### D. hook（可选）
### E. 需要你本人执行（管理员权限）
### F. 不会改的地方

### 影响
- 改动文件：<n> 个；新增规则 <n> 条；插件状态变化 <n> 个；需要重启 Claude Code
- 每个文件都有备份，执行后会列出撤销命令

请回复「确认执行」开始，也可以只执行其中几部分（例如「只执行 A 和 B」），或告诉我要改哪里。
````

## 安全约束

- **没有明确确认，不做任何写操作**，包括安装插件
- **只增不删**：不删除、不改写用户已有的规则、hook、插件条目和 skill 开关；冲突默认保留用户的值，覆盖只能按用户点名的路径逐个授权（`--overwrite <JSON Pointer>`）
- **执行等于确认**：真正写入时的参数必须和用户确认的那次 dry-run 完全一致，并带上它的 `--expect-plan`；任何改动都要重新 dry-run、重新确认
- **设置文件只通过 `merge_settings.py` 修改**，不要用编辑工具直接改 `settings.json`，这样才能保证严格校验、备份、只增不删和写后自检
- **不碰托管设置**：不写 `managed-settings.json`，不用 `sudo`，只给出命令由用户执行
- **不写入密钥**：需要密钥的插件或 MCP，让用户用环境变量提供；计划和输出里不出现任何密钥值
- 不改 `~/.claude.json`；要加 MCP 用 `claude mcp add`，并且同样先列进计划
- 不执行 git 提交、推送；不卸载插件，除非用户明确要求
- 出错立即停止，说明已完成和未完成的步骤，并给出撤销命令
