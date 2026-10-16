#!/usr/bin/env node
// Builds the installable Claude Code plugin from the handbook content:
//   1. regenerates plugin/skills/pitfall-check/references/pitfalls.md from content/docs/pitfalls/*.mdx
//   2. zips plugin/ into public/plugin/ainative-<version>.zip
//   3. writes public/marketplace.json pointing at that archive (with sha256)
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { tmpdir } from 'node:os';
import { parse as parseYaml } from 'yaml';

const root = new URL('..', import.meta.url).pathname;
const siteUrl = 'https://ainative.jubao.ai';
const pluginDir = join(root, 'plugin');
const pitfallDir = join(root, 'content/docs/pitfalls');

if (!existsSync(join(pluginDir, '.claude-plugin/plugin.json'))) {
  console.log('[build-plugin] plugin/ not found, skipping');
  process.exit(0);
}

const manifest = JSON.parse(readFileSync(join(pluginDir, '.claude-plugin/plugin.json'), 'utf8'));
const version = manifest.version;

function readCard(file) {
  const raw = readFileSync(join(pitfallDir, file), 'utf8');
  const match = raw.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) return null;
  const data = parseYaml(match[1]) ?? {};
  const body = match[2];
  const howTo = body.match(/## 怎么做\n([\s\S]*?)(?=\n## |$)/)?.[1]?.trim() ?? '';
  return { id: file.replace(/\.mdx$/, ''), data, howTo };
}

const stageOrder = ['day0', 'plan', 'design', 'build', 'test', 'ship', 'maintain', 'cross'];
const cards = readdirSync(pitfallDir)
  .filter((f) => f.endsWith('.mdx') && f !== 'index.mdx')
  .map(readCard)
  .filter((c) => c && c.data.rule && c.data.rule !== 'TODO')
  .sort((a, b) => stageOrder.indexOf(a.data.stage) - stageOrder.indexOf(b.data.stage) || a.id.localeCompare(b.id));

const refPath = join(pluginDir, 'skills/pitfall-check/references/pitfalls.md');
if (cards.length > 0 && existsSync(join(pluginDir, 'skills/pitfall-check'))) {
  const lines = [
    '# 坑库（自动生成，请勿手改）',
    '',
    `> 由 \`scripts/build-plugin.mjs\` 从手册 \`content/docs/pitfalls/\` 生成，共 ${cards.length} 张。完整内容见 ${siteUrl}/docs/pitfalls`,
    '',
  ];
  for (const c of cards) {
    lines.push(`## ${c.data.title}`, '');
    lines.push(`- id：\`${c.id}\``);
    lines.push(`- 阶段：${c.data.stage ?? '-'}；档位：${(c.data.tier ?? []).join(', ') || '-'}；可信度：${c.data.evidence ?? '-'}`);
    lines.push(`- 规则：${c.data.rule}`);
    if (c.data.description) lines.push(`- 防什么：${c.data.description}`);
    lines.push(`- 链接：${siteUrl}/docs/pitfalls/${c.id}`, '');
    if (c.howTo) lines.push('怎么做：', '', c.howTo.replace(/<\/?Steps>|<\/?Step>/g, '').trim(), '');
  }
  const next = `${lines.join('\n').replace(/\n{3,}/g, '\n\n')}\n`;
  // Only touch the file when its content changes, so the plugin source stays byte-stable.
  if (!existsSync(refPath) || readFileSync(refPath, 'utf8') !== next) {
    writeFileSync(refPath, next);
    console.log(`[build-plugin] pitfalls.md regenerated (${cards.length} cards)`);
  }
}

// Keep earlier versions: a cached marketplace.json may still point at the previous archive.
const outDir = join(root, 'public/plugin');
mkdirSync(outDir, { recursive: true });
const zipName = `ainative-${version}.zip`;
const zipPath = join(outDir, zipName);
const srcHashPath = `${zipPath}.srchash`;

// Content hash of a plugin tree: relative paths + file bytes, independent of mtimes.
function treeHash(dir) {
  const files = [];
  const walk = (d) => {
    for (const entry of readdirSync(d, { withFileTypes: true })) {
      if (entry.name === '.DS_Store' || entry.name === '__pycache__') continue;
      const p = join(d, entry.name);
      if (entry.isDirectory()) walk(p);
      else files.push(p);
    }
  };
  walk(dir);
  const h = createHash('sha256');
  for (const f of files.sort()) h.update(relative(dir, f)).update('\0').update(readFileSync(f)).update('\0');
  return h.digest('hex');
}

const srcHash = treeHash(pluginDir);
// Published archives are immutable (served with a one-year cache): never rebuild an existing version.
if (existsSync(zipPath)) {
  let builtFrom = existsSync(srcHashPath) ? readFileSync(srcHashPath, 'utf8').trim() : null;
  if (builtFrom === null) {
    const tmp = join(tmpdir(), `ainative-verify-${process.pid}`);
    rmSync(tmp, { recursive: true, force: true });
    mkdirSync(tmp, { recursive: true });
    execFileSync('unzip', ['-q', zipPath, '-d', tmp]);
    builtFrom = treeHash(tmp);
    rmSync(tmp, { recursive: true, force: true });
    writeFileSync(srcHashPath, `${builtFrom}\n`);
  }
  if (builtFrom !== srcHash) {
    console.error(`[build-plugin] ❌ plugin/ changed but ${zipName} is already published. Bump the version in plugin/.claude-plugin/plugin.json.`);
    process.exit(1);
  }
  console.log(`[build-plugin] ${zipName} unchanged, keeping the published archive`);
} else {
  // -X drops extra file attributes so the archive is reproducible across machines.
  execFileSync('zip', ['-qrX', zipPath, '.', '-x', '*.DS_Store', '-x', '__pycache__/*', '-x', '*/__pycache__/*'], {
    cwd: pluginDir,
  });
  writeFileSync(srcHashPath, `${srcHash}\n`);
}
const sha256 = createHash('sha256').update(readFileSync(zipPath)).digest('hex');

const marketplace = {
  name: 'ainative',
  owner: { name: manifest.author?.name ?? 'Neo', url: manifest.author?.url ?? 'https://github.com/0xNeoTian' },
  metadata: {
    description: 'AI Native 手册的配套插件：体检、安装配置、推荐、新项目、坑检查、复盘提炼',
    version,
  },
  plugins: [
    {
      name: manifest.name,
      source: { source: 'archive', url: `${siteUrl}/plugin/${zipName}`, sha256 },
      description: manifest.description,
      version,
      author: manifest.author,
      homepage: manifest.homepage ?? siteUrl,
      license: manifest.license ?? 'MIT',
      keywords: manifest.keywords ?? [],
    },
  ],
};
writeFileSync(join(root, 'public/marketplace.json'), `${JSON.stringify(marketplace, null, 2)}\n`);
console.log(`[build-plugin] ${zipName} sha256=${sha256.slice(0, 12)}… and public/marketplace.json written`);
