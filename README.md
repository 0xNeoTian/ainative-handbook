# AI Native 手册 · AI Native Handbook

[![CI](https://github.com/0xNeoTian/ainative-handbook/actions/workflows/ci.yml/badge.svg)](https://github.com/0xNeoTian/ainative-handbook/actions/workflows/ci.yml)

> Claude Code 实战：从小工具到组织协同。规则来自 70 多篇真实复盘，每条都标明可信度和出处。

网站：<https://ainative.jubao.ai> · 内容 CC BY 4.0 · 代码与插件 MIT

带着几位协作者、主要靠 Claude Code 运营两个组织、十几个代码仓库和几十个 agent，把半年里的 70 多篇复盘整理成的实战手册（首选 Claude Code，方法也适用于 Codex 等 AI 编程工具）：

- **三档路径**：小工具、产品（AI-native 六阶段）、组织（ops 仓、组织级 ops agent、记忆分层、进化回路）
- **专题**：流程引擎（superpowers 与 Matt Pocock skills 的对比与迁移）、护栏与安全
- **坑库**：25 张来自真实复盘的卡片
- **模板库**、**启动器**（交互式清单）
- **Claude Code 插件** `ainative`：doctor、setup、recommend、new-project、pitfall-check、harvest

## 安装插件

```bash
claude plugin marketplace add https://ainative.jubao.ai/marketplace.json
claude plugin install ainative@ainative
```

## 本地开发

```bash
bun install
bun run dev        # http://localhost:3000
bun run scan       # 敏感信息扫描（需要本地 .sensitive-terms.txt）
bun run build      # 生成插件包 + 静态站到 out/
bun run deploy     # 部署到 Cloudflare（wrangler）
```

内容在 `content/docs/`，写作前请读 [STANDARDS.md](./STANDARDS.md)。插件源码在 `plugin/`，构建时由 `scripts/build-plugin.mjs` 打包到 `public/plugin/` 并生成 `public/marketplace.json`。

## 质量保证

“页面里的命令和配置都是对的”不靠作者自述，每次 push 和 pull request 都由 GitHub Actions（[`.github/workflows/ci.yml`](./.github/workflows/ci.yml)）按顺序检查，任何一步失败 CI 就变红：

| 检查 | 命令 | 检查什么 |
|---|---|---|
| 敏感信息 | `bun run scan` | 通用模式 + 私有词表。CI 从 secret `SENSITIVE_TERMS` 写出 `.sensitive-terms.txt`，没配置时只查通用模式 |
| 密钥历史 | `gitleaks git` | 全部提交历史里有没有密钥 |
| 页面代码块 | `bun run test:docs` | `content/docs` 里的 json / jsonc 能解析、没有重复键；Claude Code 设置片段符合官方 schema（[`schemas/`](./schemas/)）；bash / sh 通过 `shellcheck -S warning`；yaml 能解析 |
| 插件脚本 | `bun run test:plugin` | `merge_settings.py` 和 `doctor.py` 的行为测试（`tests/plugin/`），全程在临时目录里跑，不碰真实的 `~/.claude` |
| 构建 | `bun run build` | 已发布的插件包不可变 + 静态站能构建 |
| 外链 | lychee | `content/` 正文里的外链（代码块里的示例地址不查）；openai.com 的 403、mcp.cloudflare.com 的 401 视为正常 |
| 插件清单 | `claude plugin validate --strict` | `plugin/`、仓库根的插件市场、构建生成的 `public/marketplace.json` |

本地运行：

```bash
bun run check        # scan + test:docs + test:plugin + 类型检查，提交前跑这一条
bun run test:docs    # 只查代码块；也可以只查一页：node scripts/test-docs.mjs content/docs/tool/ship.mdx
bun run test:plugin  # 需要 python3（3.8 及以上）
```

- `test:docs` 需要 shellcheck（`brew install shellcheck`）；本机没装时跳过 shell 代码块并打印提示，CI 里一定会装
- 刻意写的伪代码，在代码块开头的语言标记后加 `nocheck` 跳过检查，例如 `` ```bash nocheck ``；跳过的数量和位置会打印出来
- 设置片段的判断：代码块 `title` 是 `settings.json` / `settings.local.json`，或者顶层有 `permissions`、`hooks`、`enabledPlugins`、`env` 这类设置项。schema 里没有的顶层键会报错，Claude Code 新增设置后按 [`schemas/README.md`](./schemas/README.md) 更新 schema
- 命令里的占位符（`<名字>`、`<name>@<marketplace>`）会先替换成普通单词再交给 shellcheck；没有 shebang 的代码块按“在终端里逐条输入”处理，不报 SC2164（`cd` 后没写 `|| exit`）

## 许可

- 文字内容：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- 代码与插件：[MIT](./LICENSE)
- 字体 `assets/fonts/og-sc-*.ttf`：Noto Sans SC 子集，[SIL OFL 1.1](./assets/fonts/OFL.txt)
