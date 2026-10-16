# CLAUDE.md

AI Native 手册（https://ainative.jubao.ai）：Fumadocs 16 + Next.js 16 静态站，同时打包一个 Claude Code 插件 `ainative`。

## 技术栈与命令

- 包管理用 bun；内容在 `content/docs/`（MDX），插件源码在 `plugin/`
- `bun run dev` 本地预览 · `bun run scan` 敏感信息扫描 · `bun run build` 生成插件包 + 静态站到 `out/` · `bun run deploy` 部署到 Cloudflare

## 规则

- 写或改内容前先读 `STANDARDS.md`，合并前按第 10 节验收清单自查
- 每次构建或部署前必须先跑 `bun run scan`，不通过不发布
- 公开站点：不写任何组织名、客户、同事、服务器与账号信息，不写密钥；私有词表在 `.sensitive-terms.txt`（不进 git）
- 可信度标签必须诚实：没亲自验证过的不标 `lived`
- `public/plugin/` 和 `public/marketplace.json` 是构建产物，不要手改
- 部署走 `wrangler deploy`（在 ask 规则里，需要人确认）

## 指针

- 写作标准：`STANDARDS.md`
- 插件说明：`plugin/README.md`
- 推特草稿：`marketing/launch-thread.md`（发布前需作者确认）
