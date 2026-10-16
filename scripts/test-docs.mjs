#!/usr/bin/env node
// Checks every fenced code block in content/docs/**/*.mdx, so "the commands and configs on the page
// are correct" is verified by a machine on every push instead of only by the author.
//   json / jsonc       must parse (jsonc may contain comments; duplicate keys are errors). Objects that
//                      look like Claude Code settings are validated with ajv against the vendored schema
//                      in schemas/ (a partial snippet is validated for what it contains)
//   bash / sh / shell  shellcheck -S warning, after turning placeholders such as <名字> into plain words.
//                      Skipped with a notice when shellcheck is not installed (CI installs it)
//   yaml / yml         must parse
// Deliberate pseudo-code can opt out with "nocheck" in the fence meta (```bash nocheck); skipped blocks
// are counted and printed. Exits 1 when anything fails.
// Usage: node scripts/test-docs.mjs [file-or-dir ...]   (default: content/docs)
import { spawnSync } from 'node:child_process';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Ajv } from 'ajv';
import addFormats from 'ajv-formats';
import { frontmatter } from 'fumadocs-core/content/md/frontmatter';
import { findNodeAtLocation, getNodeValue, parseTree, printParseErrorCode } from 'jsonc-parser';
import remarkGfm from 'remark-gfm';
import remarkMdx from 'remark-mdx';
import remarkParse from 'remark-parse';
import { unified } from 'unified';
import { parseAllDocuments } from 'yaml';

const root = fileURLToPath(new URL('..', import.meta.url));
const inputs = process.argv.length > 2 ? process.argv.slice(2).map((p) => resolve(p)) : [join(root, 'content/docs')];
const schemaPath = join(root, 'schemas/claude-code-settings.schema.json');

const findings = [];
const report = (file, line, lang, message) => findings.push({ file: relative(root, file), line, lang, message });

// ---------- Claude Code settings schema ----------
const schema = JSON.parse(readFileSync(schemaPath, 'utf8'));
// The schema is vendored from schemastore and carries editor-only keywords (allowTrailingCommas), so
// strict mode stays off; formats such as "uri" are still validated.
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
ajv.addSchema(schema);
const validators = {
  settings: ajv.getSchema(schema.$id),
  permissions: ajv.getSchema(`${schema.$id}#/properties/permissions`),
  hooks: ajv.getSchema(`${schema.$id}#/properties/hooks`),
};
const settingsKeys = new Set(Object.keys(schema.properties));
// Top-level keys too generic to mark a JSON object as Claude Code settings on their own.
const genericKeys = new Set(['$schema', 'model', 'language', 'theme', 'agent', 'verbose']);
const permissionKeys = new Set(Object.keys(schema.properties.permissions.properties));
const hookEvents = new Set(Object.keys(schema.properties.hooks.properties));
// A fence title naming a settings file, e.g. ```json title=".claude/settings.local.json"
const settingsTitle = /(^|\/)(settings(\.local)?|managed-settings)\.json$|(^|\/)managed-settings\.d\/[^/]+\.json$/;

// Decides which schema (if any) a parsed JSON value is checked against.
function settingsKind(value, title) {
  if (title !== undefined) return settingsTitle.test(title) ? 'settings' : null;
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return null;
  const keys = Object.keys(value);
  if (keys.length === 0) return null;
  if (keys.some((k) => settingsKeys.has(k) && !genericKeys.has(k))) return 'settings';
  // Bare inner blocks: just the contents of "permissions" or of "hooks".
  if (keys.every((k) => permissionKeys.has(k)) && keys.some((k) => ['allow', 'deny', 'ask'].includes(k))) return 'permissions';
  if (keys.every((k) => hookEvents.has(k))) return 'hooks';
  return null;
}

// ---------- JSON / JSONC ----------
const jsonErrorText = {
  InvalidSymbol: '无法识别的符号',
  InvalidNumberFormat: '数字格式错误',
  PropertyNameExpected: '这里应是属性名（多余的逗号？）',
  ValueExpected: '这里应是一个值（多余的逗号？）',
  ColonExpected: '缺少冒号',
  CommaExpected: '缺少逗号',
  CloseBraceExpected: '缺少 }',
  CloseBracketExpected: '缺少 ]',
  EndOfFileExpected: '结尾有多余的内容',
  InvalidCommentToken: 'json 代码块里不能有注释（需要注释就标成 jsonc）',
  UnexpectedEndOfComment: '注释没有结束',
  UnexpectedEndOfString: '字符串没有结束',
  UnexpectedEndOfNumber: '数字没有结束',
  InvalidUnicode: '非法的 Unicode 转义',
  InvalidEscapeCharacter: '非法的转义字符',
  InvalidCharacter: '字符串里有非法字符',
};

const lineAt = (text, offset) => text.slice(0, offset).split('\n').length; // 1-based, within the block

function* duplicateKeys(node) {
  if (node.type === 'object') {
    const seen = new Set();
    for (const prop of node.children ?? []) {
      const key = prop.children?.[0];
      if (!key) continue;
      if (seen.has(key.value)) yield key;
      seen.add(key.value);
    }
  }
  for (const child of node.children ?? []) yield* duplicateKeys(child);
}

const pointerToPath = (pointer) =>
  pointer
    .split('/')
    .slice(1)
    .map((s) => s.replace(/~1/g, '/').replace(/~0/g, '~'))
    .map((s) => (/^\d+$/.test(s) ? Number(s) : s));

// With allErrors, a failed anyOf/oneOf reports every branch. Keep only the closest branch (fewest errors);
// when the closest branches differ only in the expected type, report one error listing those types.
function pruneBranches(errors) {
  let out = errors.filter((e) => e.keyword !== 'if');
  for (const branch of errors.filter((e) => e.keyword === 'anyOf' || e.keyword === 'oneOf')) {
    const prefix = `${branch.schemaPath}/`;
    // The same $ref'd anyOf can fail at several places; only group the errors of this instance.
    const inside = (e) => e.instancePath === branch.instancePath || e.instancePath.startsWith(`${branch.instancePath}/`);
    const subs = out.filter((e) => e.schemaPath.startsWith(prefix) && inside(e));
    if (subs.length === 0) continue;
    const byBranch = new Map();
    for (const e of subs) {
      const idx = e.schemaPath.slice(prefix.length).split('/')[0];
      byBranch.set(idx, [...(byBranch.get(idx) ?? []), e]);
    }
    const fewest = Math.min(...[...byBranch.values()].map((errs) => errs.length));
    const closest = [...byBranch.values()].filter((errs) => errs.length === fewest);
    let keep = closest[0];
    const typeOnly = closest.flat().filter((e) => e.keyword !== 'not');
    if (closest.length > 1 && fewest === 1 && typeOnly.length > 0 && typeOnly.every((e) => e.keyword === 'type' && e.instancePath === branch.instancePath)) {
      keep = [{ ...typeOnly[0], params: { type: typeOnly.map((e) => e.params.type).join(' 或 ') } }];
    }
    out = out.filter((e) => e !== branch && !subs.includes(e));
    out.push(...keep);
  }
  const seen = new Set();
  return out.filter((e) => {
    const key = `${e.instancePath}|${e.keyword}|${JSON.stringify(e.params)}`;
    return seen.has(key) ? false : (seen.add(key), true);
  });
}

function describeSchemaError(e, value) {
  const at = e.instancePath || '/';
  const shown = JSON.stringify(value)?.slice(0, 80);
  switch (e.keyword) {
    case 'additionalProperties':
      return `${at}：schema 里没有键 "${e.params.additionalProperty}"`;
    case 'required':
      return `${at}：缺少必填字段 "${e.params.missingProperty}"`;
    case 'type':
      return `${at}：类型应为 ${e.params.type}，实际是 ${shown}`;
    case 'enum':
      return `${at}：${shown} 不是允许的值（${e.params.allowedValues.join(' / ')}）`;
    case 'const':
      return `${at}：应为 ${JSON.stringify(e.params.allowedValue)}，实际是 ${shown}`;
    case 'pattern':
      return `${at}：${shown} 不符合 schema 规定的格式`;
    default:
      return `${at}：${e.message}`;
  }
}

function checkJson(block, file, lang) {
  const errors = [];
  const tree = parseTree(block.value, errors, {
    disallowComments: lang !== 'jsonc',
    allowTrailingComma: false,
    allowEmptyContent: false,
  });
  if (errors.length > 0) {
    for (const err of errors) {
      const code = printParseErrorCode(err.error);
      report(file, block.start + lineAt(block.value, err.offset), lang, `JSON 解析失败：${jsonErrorText[code] ?? code}`);
    }
    return { parsed: false };
  }
  if (lang === 'json') {
    try {
      JSON.parse(block.value);
    } catch (err) {
      report(file, block.start + 1, lang, `JSON 解析失败：${err.message}`);
      return { parsed: false };
    }
  }
  for (const key of duplicateKeys(tree)) {
    report(file, block.start + lineAt(block.value, key.offset), lang, `重复的键 "${key.value}"（后一个会覆盖前一个）`);
  }

  const value = getNodeValue(tree);
  const kind = settingsKind(value, block.attrs.title);
  if (!kind) return { parsed: true, kind: null };
  const validate = validators[kind];
  if (!validate(value)) {
    for (const e of pruneBranches(validate.errors)) {
      const path = pointerToPath(e.instancePath);
      if (e.keyword === 'additionalProperties') path.push(e.params.additionalProperty);
      const node = findNodeAtLocation(tree, path);
      const offset = node?.parent?.type === 'property' ? node.parent.offset : (node?.offset ?? 0);
      const prefix = kind === 'settings' ? '' : `（按 ${kind} 局部校验）`;
      report(file, block.start + lineAt(block.value, offset), lang, `设置不符合 schema${prefix}：${describeSchemaError(e, node ? getNodeValue(node) : undefined)}`);
    }
  }
  // The schema allows unknown top-level keys, but STANDARDS.md says only real settings may appear.
  if (kind === 'settings' && value && typeof value === 'object' && !Array.isArray(value)) {
    for (const key of Object.keys(value).filter((k) => !settingsKeys.has(k))) {
      const node = findNodeAtLocation(tree, [key]);
      report(
        file,
        block.start + lineAt(block.value, node?.parent?.offset ?? 0),
        lang,
        `未知的顶层设置项 "${key}"：拼写错误，或 schemas/ 里的 schema 需要更新`,
      );
    }
  }
  return { parsed: true, kind };
}

// ---------- YAML ----------
function checkYaml(block, file, lang) {
  const docs = parseAllDocuments(block.value, { prettyErrors: true });
  for (const doc of Array.isArray(docs) ? docs : []) {
    for (const err of doc.errors) {
      const line = err.linePos?.[0]?.line ?? 1;
      const reason = err.message.split('\n')[0].replace(/ at line \d+, column \d+:?$/, '');
      report(file, block.start + line, lang, `YAML 解析失败：${reason}`);
    }
  }
}

// ---------- shell ----------
const probe = spawnSync('shellcheck', ['--version'], { encoding: 'utf8' });
const shellcheckVersion = !probe.error && probe.status === 0 ? (/version:\s*(\S+)/.exec(probe.stdout)?.[1] ?? '?') : null;

// <名字>、<name>@<marketplace>、<URL|路径|owner/repo>: a word in angle brackets is a placeholder for the
// reader to fill in, not a redirection. Replace it with a plain word of the same length.
const neutralisePlaceholders = (text) =>
  text.replace(/<([^<>\s"'`$(){};&]+)>/g, (_, inner) => `_${inner.replace(/[^\p{L}\p{N}._@:+,=/-]/gu, '_')}_`);

// A block without a shebang is a sequence of commands typed into a terminal, not a script. There,
// SC2164's advice ("cd ... || exit") would close the reader's shell, so it only applies to scripts.
const interactiveExcludes = ['SC2164'];

function checkShell(block, file, lang) {
  const args = ['--format=json1', '--severity=warning', '--norc'];
  if (!block.value.startsWith('#!')) args.push(`--shell=${lang === 'sh' ? 'sh' : 'bash'}`, `--exclude=${interactiveExcludes.join(',')}`);
  args.push('-');
  const r = spawnSync('shellcheck', args, { input: neutralisePlaceholders(block.value), encoding: 'utf8' });
  if (r.error || (r.status !== 0 && r.status !== 1)) {
    report(file, block.start, lang, `shellcheck 运行失败：${r.error?.message ?? r.stderr.trim()}`);
    return;
  }
  const sourceLines = block.value.split('\n');
  for (const c of JSON.parse(r.stdout).comments) {
    const src = (sourceLines[c.line - 1] ?? '').trim();
    report(file, block.start + c.line, lang, `SC${c.code}（${c.level}）${c.message}\n      ${src.length > 100 ? `${src.slice(0, 100)}…` : src}`);
  }
}

// ---------- walk content/docs ----------
function* walk(path) {
  if (!statSync(path).isDirectory()) {
    yield path;
    return;
  }
  for (const entry of readdirSync(path, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const p = join(path, entry.name);
    if (entry.isDirectory()) yield* walk(p);
    else if (/\.mdx?$/.test(entry.name)) yield p;
  }
}

function parseMeta(meta) {
  const flags = new Set();
  const attrs = {};
  for (const m of (meta ?? '').matchAll(/([\w-]+)(?:=("[^"]*"|'[^']*'|\S+))?/g)) {
    if (m[2] === undefined) flags.add(m[1]);
    else attrs[m[1]] = m[2].replace(/^(["'])(.*)\1$/, '$2');
  }
  return { flags, attrs };
}

const langOf = { json: 'json', jsonc: 'jsonc', bash: 'shell', sh: 'shell', shell: 'shell', yaml: 'yaml', yml: 'yaml' };
const processor = unified().use(remarkParse).use(remarkMdx).use(remarkGfm);
const stats = { pages: 0, blocks: 0, json: 0, jsonc: 0, yaml: 0, shell: 0, settings: 0, nocheck: [], shellSkipped: 0, other: {} };

for (const file of inputs.flatMap((p) => [...walk(p)])) {
  stats.pages++;
  const source = readFileSync(file, 'utf8');
  let matter;
  try {
    // Same frontmatter handling as fumadocs-mdx, and the same line-preserving replacement.
    matter = frontmatter(source);
  } catch (err) {
    report(file, (err.linePos?.[0]?.line ?? 0) + 1, 'frontmatter', `YAML 解析失败：${err.message.split('\n')[0]}`);
    continue;
  }
  const body = '\n'.repeat(matter.matter.split('\n').length - 1) + matter.content;
  let tree;
  try {
    tree = processor.parse(body);
  } catch (err) {
    report(file, err.line ?? err.place?.line ?? 1, 'mdx', `MDX 解析失败：${err.reason ?? err.message}`);
    continue;
  }

  const blocks = [];
  const collect = (node) => {
    if (node.type === 'code') blocks.push(node);
    for (const child of node.children ?? []) collect(child);
  };
  collect(tree);

  for (const node of blocks) {
    stats.blocks++;
    const rawLang = (node.lang ?? '').toLowerCase();
    const kind = langOf[rawLang];
    const { flags, attrs } = parseMeta(node.meta);
    // block.start + n = the file line of the block's n-th content line (the fence is block.start).
    const block = { value: node.value, start: node.position.start.line, attrs };
    if (!kind) {
      const label = rawLang || '（无语言）';
      stats.other[label] = (stats.other[label] ?? 0) + 1;
      continue;
    }
    if (flags.has('nocheck')) {
      stats.nocheck.push(`${relative(root, file)}:${block.start} [${rawLang}]`);
      continue;
    }
    if (kind === 'json' || kind === 'jsonc') {
      stats[kind]++;
      if (checkJson(block, file, rawLang).kind) stats.settings++;
    } else if (kind === 'yaml') {
      stats.yaml++;
      checkYaml(block, file, rawLang);
    } else {
      stats.shell++;
      if (shellcheckVersion) checkShell(block, file, rawLang);
      else stats.shellSkipped++;
    }
  }
}

// CI installs shellcheck; if it is missing there, the shell check would silently do nothing.
if (!shellcheckVersion && process.env.CI && stats.shell > 0) {
  findings.push({ file: '(环境)', line: 0, lang: 'shell', message: 'CI 环境里没有 shellcheck，shell 代码块没有被检查' });
}

// ---------- summary ----------
console.log(
  `[test-docs] ${stats.pages} 个页面，${stats.blocks} 个代码块：json ${stats.json}、jsonc ${stats.jsonc}、yaml ${stats.yaml}、shell ${stats.shell}`,
);
console.log(`[test-docs] 其中 Claude Code 设置片段 ${stats.settings} 个，已按 schemas/claude-code-settings.schema.json 校验`);
console.log(
  shellcheckVersion
    ? `[test-docs] shell 代码块用 shellcheck ${shellcheckVersion} 检查`
    : `[test-docs] ⚠️  shell 代码块 ${stats.shellSkipped} 个：跳过（本机未安装 shellcheck）`,
);
const others = Object.entries(stats.other)
  .sort((a, b) => b[1] - a[1])
  .map(([k, v]) => `${k} ${v}`)
  .join('、');
if (others) console.log(`[test-docs] 不检查的语言：${others}`);
console.log(`[test-docs] nocheck 显式跳过 ${stats.nocheck.length} 个${stats.nocheck.length ? '：' : ''}`);
for (const s of stats.nocheck) console.log(`  ${s}`);

if (findings.length > 0) {
  findings.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line);
  console.error(`[test-docs] ❌ 发现 ${findings.length} 处问题：`);
  for (const f of findings) console.error(`  ${f.file}:${f.line}  [${f.lang}] ${f.message}`);
  process.exit(1);
}
console.log('[test-docs] ✅ 通过');
