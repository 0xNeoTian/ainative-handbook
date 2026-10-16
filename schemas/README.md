# schemas

`claude-code-settings.schema.json`：Claude Code 设置文件（`settings.json`）的 JSON Schema，`scripts/test-docs.mjs` 用它校验页面里的设置片段。JSON 不能写注释，来源记录在这里。

| 项 | 值 |
|---|---|
| 来源 | <https://json.schemastore.org/claude-code-settings.json>（SchemaStore，Apache-2.0） |
| 获取日期 | 2026-10-16（服务器 Last-Modified：2026-10-15 23:11:09 GMT） |
| SHA-256 | `0ad8cf34c55f31c4f29d621d43ae4078c462589d9b5c5bcf8d96694a5ae666ba` |
| 改动 | 原样保存，未做任何修改 |

固定一份而不是每次在线拉取：CI 结果只随仓库内容变化，不会因为上游更新突然变红。代价是 Claude Code 新增设置项后要手动更新，否则 `test:docs` 会报“未知的顶层设置项”。

更新方法：

```bash
curl -fsSL https://json.schemastore.org/claude-code-settings.json -o schemas/claude-code-settings.schema.json
shasum -a 256 schemas/claude-code-settings.schema.json   # 把结果和日期填回上表
bun run test:docs
```
