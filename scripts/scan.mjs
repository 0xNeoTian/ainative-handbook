#!/usr/bin/env node
// Blocks private information from reaching the public site.
// Generic patterns live here; organisation-specific terms live in .sensitive-terms.txt (git-ignored,
// one term per line, "#" for comments, "!" for allowed substrings). In CI, provide that file from a secret.
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const root = new URL('..', import.meta.url).pathname;
const targets = ['content', 'plugin', 'app', 'components', 'lib', 'marketing', 'public/marketplace.json', 'README.md', 'STANDARDS.md'];
const exts = new Set(['.mdx', '.md', '.ts', '.tsx', '.json', '.py', '.sh', '.mjs', '.txt']);
const skipDirs = new Set(['node_modules', '.next', 'out', '.source', '__pycache__']);


const generic = [
  { name: 'IPv4 地址', re: /\b(?!(?:127\.0\.0\.1|0\.0\.0\.0)\b)(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b/g },
  { name: '疑似密钥', re: /\b(?:sk|ak|pk|rk)_[A-Za-z0-9]{16,}\b/g },
  { name: 'GitHub token', re: /\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|github_pat_[A-Za-z0-9_]{20,}/g },
  { name: '云厂商 AccessKey', re: /\b(?:AKID[A-Za-z0-9]{13,}|AKIA[0-9A-Z]{16}|LTAI[A-Za-z0-9]{12,})\b/g },
  { name: '私钥', re: /-----BEGIN [A-Z ]*PRIVATE KEY-----/g },
  { name: 'Slack token', re: /\bxox[abprs]-[A-Za-z0-9-]{10,}/g },
  { name: '32 位十六进制 ID', re: /\b[0-9a-f]{32}\b/g },
];

const termsFile = join(root, '.sensitive-terms.txt');
const lines = existsSync(termsFile)
  ? readFileSync(termsFile, 'utf8')
      .split('\n')
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith('#'))
  : [];
// Lines starting with "!" are allowed substrings (public identifiers that contain a denied term).
// They live in the private file too, so the public script reveals nothing about the denylist.
const allow = lines.filter((l) => l.startsWith('!')).map((l) => l.slice(1));
const terms = lines.filter((l) => !l.startsWith('!'));
if (terms.length === 0) console.warn('[scan] ⚠️  .sensitive-terms.txt 不存在或为空，只检查通用模式');

// ASCII terms match as whole words (so a short acronym does not hit a longer word that contains it); CJK terms match as substrings.
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const termMatchers = terms.map((term) =>
  /^[\x20-\x7e]+$/.test(term)
    ? { term, re: new RegExp(`(?<![A-Za-z0-9])${escapeRe(term)}(?![A-Za-z0-9])`, 'i') }
    : { term, re: null },
);

function* walk(path) {
  const abs = join(root, path);
  if (!existsSync(abs)) return;
  const st = statSync(abs);
  if (st.isFile()) {
    yield abs;
    return;
  }
  for (const entry of readdirSync(abs)) {
    if (skipDirs.has(entry)) continue;
    yield* walk(join(path, entry));
  }
}

const findings = [];
for (const target of targets) {
  for (const file of walk(target)) {
    const ext = file.slice(file.lastIndexOf('.'));
    if (!exts.has(ext)) continue;
    const lines = readFileSync(file, 'utf8').split('\n');
    lines.forEach((line, i) => {
      let scrubbed = line;
      for (const a of allow) scrubbed = scrubbed.split(a).join(' ');
      for (const { name, re } of generic) {
        for (const m of scrubbed.matchAll(re)) findings.push({ file, line: i + 1, kind: name, hit: m[0] });
      }
      const lower = scrubbed.toLowerCase();
      for (const { term, re } of termMatchers) {
        const hit = re ? re.test(scrubbed) : lower.includes(term.toLowerCase());
        if (hit) findings.push({ file, line: i + 1, kind: '敏感词', hit: term });
      }
    });
  }
}

if (findings.length > 0) {
  console.error(`[scan] ❌ 发现 ${findings.length} 处可能的敏感信息：`);
  for (const f of findings) console.error(`  ${relative(root, f.file)}:${f.line}  [${f.kind}] ${f.hit}`);
  process.exit(1);
}
console.log(`[scan] ✅ 通过（通用模式 ${generic.length} 条，自定义词 ${terms.length} 个）`);
