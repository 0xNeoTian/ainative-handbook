'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

type Tag = 'ainative' | 'builtin' | 'matt' | 'gstack' | 'ui' | 'hook' | 'stack';
type TierKey = 'tool' | 'product' | 'org';

interface Item {
  tag: Tag;
  cmd: string;
  note: string;
  min?: TierKey;
}

interface Check {
  text: string;
  min?: TierKey;
}

interface Stage {
  key: string;
  name: string;
  title: string;
  why: string;
  artifact: string;
  gate: string;
  metric: string;
  href: string;
  items: Item[];
  checks: Check[];
  template?: { title: string; body: string };
}

const tierRank: Record<TierKey, number> = { tool: 0, product: 1, org: 2 };
const tierText: Record<TierKey, string> = { tool: '小工具', product: '产品', org: '组织' };

const tagMeta: Record<Tag, { text: string; className: string }> = {
  ainative: { text: '本手册插件', className: 'text-fd-primary border-fd-primary/50' },
  builtin: { text: '内置', className: 'text-sky-700 border-sky-700/40 dark:text-sky-300 dark:border-sky-300/40' },
  matt: { text: 'Matt', className: 'text-violet-700 border-violet-700/40 dark:text-violet-300 dark:border-violet-300/40' },
  gstack: { text: 'gstack', className: 'text-emerald-700 border-emerald-700/40 dark:text-emerald-300 dark:border-emerald-300/40' },
  ui: { text: 'ui-contract', className: 'text-amber-700 border-amber-700/40 dark:text-amber-300 dark:border-amber-300/40' },
  hook: { text: 'hookify', className: 'text-rose-700 border-rose-700/40 dark:text-rose-300 dark:border-rose-300/40' },
  stack: { text: '技术栈', className: 'text-slate-600 border-slate-500/40 dark:text-slate-300 dark:border-slate-300/40' },
};

const STAGES: Stage[] = [
  {
    key: 'day0',
    name: '起步',
    title: '0 · 起步：骨架和护栏第一天配好',
    why: 'CLAUDE.md 只放每次都要遵守的规则，可复用的方法做成 skill，必须拦住的操作交给权限规则和 hook。第一天配好，之后每个会话都省事。',
    artifact: '仓库 + 一页 CLAUDE.md + 最小护栏',
    gate: '你确认 CLAUDE.md 不超过一页、里面没有任何密钥',
    metric: '从建仓库到第一次部署的时间',
    href: '/docs/product/day-0',
    items: [
      { tag: 'ainative', cmd: '/ainative:doctor', note: '先给当前环境体检：插件冗余、护栏缺失、配置是否被覆盖' },
      { tag: 'stack', cmd: 'mkdir {slug} && cd {slug} && git init', note: '小工具：一个空仓库就够了' },
      {
        tag: 'stack',
        cmd: 'bun create next-app {slug} --ts --tailwind --app --use-bun --yes\ncd {slug}',
        note: '产品：Next.js App Router + TypeScript + Tailwind；--yes 避免交互提问卡住，脚手架会顺手完成第一次 git 提交',
        min: 'product',
      },
      { tag: 'stack', cmd: 'gh repo create {owner}/{slug} --private --source=. --push', note: '建私有仓库并推送' },
      { tag: 'builtin', cmd: '/init', note: '生成 CLAUDE.md，然后手动删到一页以内：技术栈、常用命令、禁区、指向详细文档的指针' },
      {
        tag: 'builtin',
        cmd: '"permissions": { "deny": ["Bash(rm -rf /)", "Bash(rm -rf ~)", "Bash(sudo rm -rf *)", "Bash(git push --force origin main *)", "Bash(git reset --hard origin/main *)"] }',
        note: '写进 ~/.claude/settings.json，对所有项目生效：五条 deny 拦住删根目录、删家目录、强推 main、硬重置 main。已有 permissions 就合并进去，不要整份覆盖',
      },
      {
        tag: 'hook',
        cmd: '/hookify 禁止提交 .env* 文件；禁止 git push --force 到 main',
        note: '一句话生成只警告或直接阻止的 hook 护栏（试用中），/hookify:list 查看',
        min: 'product',
      },
      { tag: 'ainative', cmd: '/ainative:setup', note: '按档位装好推荐的插件、权限规则和 skill 设置（会先出计划、等你确认）', min: 'product' },
      {
        tag: 'matt',
        cmd: '/mattpocock-skills:setup-matt-pocock-skills',
        note: '每个仓库跑一次：配置 Issue tracker、分诊标签、文档目录',
        min: 'product',
      },
      {
        tag: 'ui',
        cmd: 'claude plugin marketplace add yannikzz/ui-contract\nclaude plugin install ui-contract@yannikzz --scope project',
        note: '有界面的项目才装，只装到当前项目',
        min: 'product',
      },
      {
        tag: 'builtin',
        cmd: '"permissions": { "additionalDirectories": ["~/Work/{slug}-ops"] }',
        note: '组织：写进代码仓的 .claude/settings.local.json（路径因人而异，不进 git），让会话能读到 ops 仓',
        min: 'org',
      },
      {
        tag: 'builtin',
        cmd: '"autoMemoryDirectory": "~/.claude/org-memory/{slug}"',
        note: '组织：写进各仓库的 .claude/settings.local.json，同一组织共用一份自动记忆',
        min: 'org',
      },
    ],
    checks: [
      { text: '仓库已建好并推到 GitHub（私有）' },
      { text: '.env* 已在 .gitignore 里，密钥只放环境变量或钥匙串' },
      { text: 'CLAUDE.md 不超过一页' },
      { text: '五条 deny 规则已写进 ~/.claude/settings.json' },
      { text: '至少一条 hookify 护栏已生效', min: 'product' },
      { text: '部署平台已选好（Vercel 还是 Cloudflare）', min: 'product' },
      { text: 'ops 仓已建好，代码仓的 CLAUDE.md 指向它（用完整 URL）', min: 'org' },
    ],
    template: {
      title: '部署平台怎么选',
      body: `选 Vercel：Next.js 全功能产品（SSR / ISR / Server Actions / 图片优化），需要每个 PR 一个预览环境
选 Cloudflare：静态页、报告、落地页；边缘 API、Webhook、定时任务；WebSocket 或有状态 agent；
              大文件分发（R2 无流量费）；需要国内访问；对成本敏感

不管选哪个，DNS、邮件路由、R2、WAF 都放在 Cloudflare
一个域名只挂一个平台`,
    },
  },
  {
    key: 'plan',
    name: '规划',
    title: '1 · 规划：动手前先写 intent',
    why: '先用一页纸说清楚做什么、为什么、有哪些约束、不做什么、怎么算成功。这本手册本身就是先被拷问清楚需求，再动手做的。',
    artifact: 'spec 的第一节 intent（docs/specs/YYYY-MM-DD_{slug}.md）',
    gate: '你本人确认这份 intent',
    metric: '从讨论到第一次提交的时间',
    href: '/docs/product/plan',
    items: [
      { tag: 'matt', cmd: '/mattpocock-skills:grill-me', note: '一轮一轮拷问需求，每题都给推荐答案，回“是”就采纳' },
      { tag: 'gstack', cmd: '/office-hours', note: '新产品、新方向：先确认这件事值不值得做', min: 'product' },
    ],
    checks: [
      { text: '写清做什么、为什么现在做', min: 'product' },
      { text: '写明约束和明确不做的部分', min: 'product' },
      { text: '写好能量化的成功指标', min: 'product' },
      { text: 'intent 已提交到 git', min: 'product' },
    ],
    template: {
      title: 'intent 模板',
      body: `## Intent: {slug}

### 做什么（一句话）
### 为什么（谁的什么问题，为什么是现在）
### 约束（技术 / 合规 / 预算 / 时间）
### 不做什么
### 成功指标（上线后看哪个数）
### 来源（想法 / 工单 / 告警）`,
    },
  },
  {
    key: 'design',
    name: '设计',
    title: '2 · 设计：从 intent 到 spec',
    why: '在一次会话里把意图变成可执行的规格，关键决策留下 ADR，术语写进术语表。',
    artifact: 'spec.md + ADR + 术语表（UI 项目再加 layout.md / design.md）',
    gate: '产品负责人签字后才进入开发',
    metric: '从 intent 到 spec 的时间',
    href: '/docs/product/design',
    items: [
      { tag: 'matt', cmd: '/mattpocock-skills:grill-with-docs', note: '边拷问边写 ADR 和术语表，留在仓库里跨会话可用', min: 'product' },
      { tag: 'matt', cmd: '/mattpocock-skills:to-spec', note: '把对话整理成 spec；以仓库里的文件为准，Issue 里贴链接', min: 'product' },
      { tag: 'matt', cmd: '/mattpocock-skills:prototype', note: '状态模型或交互拿不准时，先做一次性原型' },
      { tag: 'matt', cmd: '/mattpocock-skills:domain-modeling', note: '领域概念多、命名容易乱时用', min: 'product' },
      { tag: 'ui', cmd: '/ui-contract:ui-contract', note: '定下页面分区和“新功能放哪”的规则', min: 'product' },
      { tag: 'gstack', cmd: '/autoplan', note: '依次跑 CEO / 设计 / 工程 / DX 四个视角的评审', min: 'org' },
    ],
    checks: [
      { text: 'spec 写好，开头一节是 intent', min: 'product' },
      { text: '关键决策都有 ADR（含为什么没选另一个方案）', min: 'product' },
      { text: 'UI 项目已有 layout.md / design.md', min: 'product' },
      { text: 'spec 已签字确认', min: 'product' },
    ],
  },
  {
    key: 'build',
    name: '开发',
    title: '3 · 开发：先出计划，再写代码',
    why: '默认从 Plan mode 开始：先读 spec、确认仓库现状、出 plan，你确认后再动手。大任务拆工单，长任务分会话。',
    artifact: 'plan.md + 代码 diff + 测试',
    gate: '工程师确认计划和实现风险',
    metric: '首次合并前的返工轮数',
    href: '/docs/product/build',
    items: [
      { tag: 'builtin', cmd: 'Shift+Tab', note: '循环切换权限模式，状态栏出现 plan mode on 即进入 Plan mode（也可以直接用 /plan）：只读探索 + 出计划，确认后再执行' },
      { tag: 'matt', cmd: '/mattpocock-skills:implement', note: '按 spec 或工单逐个实现' },
      { tag: 'matt', cmd: '/mattpocock-skills:tdd', note: '先写失败的测试，再实现，再重构', min: 'product' },
      { tag: 'matt', cmd: '/mattpocock-skills:to-tickets', note: '大功能拆成可独立交付的工单，写清依赖', min: 'product' },
      { tag: 'matt', cmd: '/mattpocock-skills:wayfinder', note: '一个会话做不完的大工程，在 Issue 上维护决策地图', min: 'org' },
      { tag: 'builtin', cmd: 'claude --worktree', note: '互不依赖的任务用 worktree 隔离；实现类任务不要并行改同一批文件', min: 'product' },
      { tag: 'matt', cmd: '/mattpocock-skills:handoff', note: '上下文快满或要换会话时，压缩成交接文档', min: 'product' },
    ],
    checks: [
      { text: 'plan 已确认' },
      { text: '每张工单都写了测试要求', min: 'product' },
      { text: '冲突 30 个以上的大任务，计划和执行分开会话', min: 'product' },
    ],
  },
  {
    key: 'test',
    name: '测试',
    title: '4 · 测试：让 Claude 能自己验证',
    why: '给 agent 一个能自己跑的反馈回路，用证据而不是“我觉得没问题”判断完成。UI 改动必须亲眼看到结果。',
    artifact: '运行日志 + 测试 / eval 结果',
    gate: '代码所有者审阅行为和证据',
    metric: 'CI 首次通过率 / 线上回归次数',
    href: '/docs/product/test',
    items: [
      { tag: 'gstack', cmd: '/qa', note: '在真实浏览器里点一遍完整流程，找到问题并修复' },
      { tag: 'matt', cmd: '/mattpocock-skills:diagnosing-bugs', note: '难查的 bug：先稳定复现，再找根因' },
      { tag: 'ui', cmd: '/ui-contract:ui-contract-enforce', note: '把区域名写成类型，放错位置的代码在类型检查时报错', min: 'product' },
      { tag: 'builtin', cmd: 'claude plugin eval', note: '项目里有自写的 skill 或插件时，用它跑评测用例，并放进 CI', min: 'product' },
    ],
    checks: [
      { text: '测试、类型检查、lint 都能由 Claude 自己跑' },
      { text: 'UI 改动已真启动、亲眼看过' },
      { text: 'AI 相关改动后已重跑 eval', min: 'product' },
    ],
  },
  {
    key: 'ship',
    name: '发布',
    title: '5 · 发布：AI 审查，人来批准',
    why: '主力模型写完，另一个模型家族独立审，人最后拍板。写代码的 agent 不能批准自己。生产发布命令放进 ask 规则，每次都等人确认。',
    artifact: 'PR + 审批记录 + 发布记录',
    gate: '代码所有者和发布负责人授权',
    metric: '审查耗时 / 关卡等待时间',
    href: '/docs/product/ship',
    items: [
      { tag: 'builtin', cmd: '/code-review', note: '内置正确性审查，加 --comment 直接评论到 PR' },
      { tag: 'gstack', cmd: '/codex', note: '用另一个模型家族做独立二审（异构审查）', min: 'product' },
      { tag: 'builtin', cmd: '/security-review', note: '涉及鉴权、支付、密钥的改动必跑', min: 'product' },
      { tag: 'ainative', cmd: '/ainative:pitfall-check', note: '用坑库逐条审当前分支的改动', min: 'product' },
      { tag: 'matt', cmd: '/mattpocock-skills:pr', note: '写规范的 PR 描述', min: 'product' },
      { tag: 'gstack', cmd: '/ship', note: '合并基线、跑测试、审 diff、更新版本和 CHANGELOG、开 PR', min: 'product' },
      {
        tag: 'builtin',
        cmd: '"permissions": { "ask": ["Bash(vercel --prod *)", "Bash(wrangler deploy *)", "Bash(bunx wrangler deploy *)"] }',
        note: '写进 .claude/settings.json：上线命令每次执行都要你确认。hookify 只能警告或阻止，做不了“确认后放行”',
        min: 'product',
      },
    ],
    checks: [
      { text: '已过 /code-review' },
      { text: '重大改动已做异构模型二审', min: 'product' },
      { text: '合并前做过一次整分支终审', min: 'product' },
      { text: '发版清单逐项打勾（不只看 CI 绿）', min: 'product' },
    ],
  },
  {
    key: 'maintain',
    name: '运维',
    title: '6 · 运维：线上问题变成新的 intent',
    why: '指标异常时先只读诊断，再把问题写成新的 intent，回到规划。每次事故都要变成下一轮的规则。',
    artifact: '诊断记录 + 复盘 + 新的 intent',
    gate: '服务负责人决定处置动作',
    metric: '从事故到写出 intent 的时间',
    href: '/docs/product/maintain',
    items: [
      { tag: 'gstack', cmd: '/canary', note: '上线后盯页面报错和性能', min: 'product' },
      { tag: 'gstack', cmd: '/investigate', note: '查根因，结论写进新的 intent' },
      { tag: 'ainative', cmd: '/ainative:harvest', note: '把复盘提炼成坑卡草稿，顺便做脱敏检查', min: 'product' },
      { tag: 'gstack', cmd: '/retro', note: '每周工程复盘', min: 'product' },
      { tag: 'builtin', cmd: '/schedule', note: '定时园丁：每周读新复盘、查失效链接、检查护栏还在不在', min: 'org' },
    ],
    checks: [
      { text: '上线后有监控', min: 'product' },
      { text: '每次事故都写了复盘', min: 'product' },
      { text: '护栏定期体检（/ainative:doctor）', min: 'product' },
      { text: '园丁 agent 已排进日程', min: 'org' },
    ],
  },
];

function useStored<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(initial);
  useEffect(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw !== null) setValue(JSON.parse(raw) as T);
    } catch {
      // storage unavailable (private mode, blocked): keep defaults
    }
  }, [key]);
  const update = (next: T) => {
    setValue(next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      // ignore
    }
  };
  return [value, update] as const;
}

function CopyButton({ text }: { text: string }) {
  const [state, setState] = useState<'idle' | 'done' | 'fail'>('idle');
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard?.writeText(text).then(
          () => setState('done'),
          () => setState('fail'),
        );
        setTimeout(() => setState('idle'), 1400);
      }}
      className="shrink-0 rounded-md border px-2 py-1 text-xs text-fd-muted-foreground transition-colors hover:bg-fd-accent hover:text-fd-accent-foreground"
    >
      {state === 'done' ? '已复制' : state === 'fail' ? '请手动复制' : '复制'}
    </button>
  );
}

export function Launcher() {
  const [slug, setSlug] = useStored('ainative.launcher.slug', 'my-app');
  const [owner, setOwner] = useStored('ainative.launcher.owner', 'your-github');
  const [tier, setTier] = useStored<TierKey>('ainative.launcher.tier', 'product');
  const [current, setCurrent] = useStored('ainative.launcher.stage', 0);
  const [checked, setChecked] = useStored<Record<string, boolean>>('ainative.launcher.checks', {});

  const fill = (s: string) => s.replaceAll('{slug}', slug || 'my-app').replaceAll('{owner}', owner || 'your-github');
  const visible = <T extends { min?: TierKey }>(list: T[]) => list.filter((x) => tierRank[x.min ?? 'tool'] <= tierRank[tier]);

  const progress = useMemo(() => {
    let total = 0;
    let done = 0;
    STAGES.forEach((stage) =>
      stage.checks.forEach((c, i) => {
        if (tierRank[c.min ?? 'tool'] > tierRank[tier]) return;
        total += 1;
        if (checked[`${stage.key}-${i}`]) done += 1;
      }),
    );
    return total === 0 ? 0 : Math.round((done / total) * 100);
  }, [checked, tier]);

  const index = Math.min(Math.max(current, 0), STAGES.length - 1);
  const stage = STAGES[index];

  return (
    <div className="not-prose flex flex-col gap-5">
      <div className="flex flex-wrap items-end gap-4 rounded-xl border bg-fd-card p-4">
        <label className="flex flex-col gap-1 text-xs text-fd-muted-foreground">
          项目名
          <input
            value={slug}
            onChange={(e) => setSlug(e.target.value.trim().replace(/\s+/g, '-'))}
            spellCheck={false}
            className="w-40 rounded-md border bg-fd-background px-2.5 py-1.5 font-mono text-sm text-fd-foreground"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-fd-muted-foreground">
          GitHub 账号
          <input
            value={owner}
            onChange={(e) => setOwner(e.target.value.trim())}
            spellCheck={false}
            className="w-40 rounded-md border bg-fd-background px-2.5 py-1.5 font-mono text-sm text-fd-foreground"
          />
        </label>
        <div className="flex flex-col gap-1 text-xs text-fd-muted-foreground">
          档位
          <div className="inline-flex overflow-hidden rounded-md border" role="radiogroup" aria-label="项目档位">
            {(Object.keys(tierText) as TierKey[]).map((t) => (
              <button
                key={t}
                type="button"
                role="radio"
                aria-checked={tier === t}
                onClick={() => setTier(t)}
                className={`px-3 py-1.5 text-sm transition-colors ${tier === t ? 'bg-fd-primary text-fd-primary-foreground' : 'text-fd-foreground hover:bg-fd-accent'}`}
              >
                {tierText[t]}
              </button>
            ))}
          </div>
        </div>
        <div className="ml-auto flex min-w-40 flex-col gap-1 text-xs text-fd-muted-foreground">
          <span>
            进度 <b className="text-fd-foreground">{progress}%</b>
          </span>
          <div className="h-1.5 overflow-hidden rounded-full bg-fd-muted">
            <div className="h-full rounded-full bg-fd-primary transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </div>

      <nav className="flex gap-2 overflow-x-auto pb-1" aria-label="阶段">
        {STAGES.map((s, i) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setCurrent(i)}
            aria-current={i === index ? 'step' : undefined}
            className={`shrink-0 rounded-full border px-3.5 py-1.5 text-sm transition-colors ${
              i === index
                ? 'border-fd-primary bg-fd-primary/10 font-semibold text-fd-primary'
                : 'text-fd-muted-foreground hover:bg-fd-accent hover:text-fd-accent-foreground'
            }`}
          >
            <span className="mr-1 opacity-60">{i}</span>
            {s.name}
          </button>
        ))}
      </nav>

      <article className="rounded-2xl border bg-fd-card p-5 sm:p-6">
        <h2 className="m-0 text-xl font-semibold text-fd-foreground">{stage.title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-fd-muted-foreground">{stage.why}</p>

        <div className="mt-4 grid gap-2.5 sm:grid-cols-3">
          {[
            ['产物', fill(stage.artifact)],
            ['人工关卡', stage.gate],
            ['衡量指标', stage.metric],
          ].map(([k, v]) => (
            <div key={k} className="rounded-lg border bg-fd-background px-3 py-2.5">
              <div className="text-[11px] text-fd-muted-foreground">{k}</div>
              <div className="mt-0.5 text-sm text-fd-foreground">{v}</div>
            </div>
          ))}
        </div>

        <h3 className="mb-2 mt-6 text-sm font-semibold text-fd-foreground">怎么做</h3>
        <ul className="m-0 flex list-none flex-col divide-y p-0">
          {visible(stage.items).map((item, i) => (
            <li key={`${stage.key}-item-${i}`} className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 py-3">
              <span className={`mt-0.5 h-fit whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-semibold ${tagMeta[item.tag].className}`}>
                {tagMeta[item.tag].text}
              </span>
              <div className="flex min-w-0 items-start gap-2">
                <pre className="m-0 min-w-0 flex-1 overflow-x-auto rounded-md bg-fd-muted px-2.5 py-1.5 font-mono text-[13px] text-fd-foreground">
                  {fill(item.cmd)}
                </pre>
                <CopyButton text={fill(item.cmd)} />
              </div>
              <p className="col-start-2 m-0 text-sm text-fd-muted-foreground">{item.note}</p>
            </li>
          ))}
        </ul>

        {stage.template ? (
          <details className="mt-4 rounded-lg border bg-fd-background px-3 py-2" open={index === 1}>
            <summary className="cursor-pointer text-sm font-semibold text-fd-foreground">{stage.template.title}</summary>
            <div className="mt-2 flex items-start gap-2">
              <pre className="m-0 min-w-0 flex-1 overflow-x-auto whitespace-pre rounded-md bg-fd-muted p-3 font-mono text-[13px] text-fd-foreground">
                {fill(stage.template.body)}
              </pre>
              <CopyButton text={fill(stage.template.body)} />
            </div>
          </details>
        ) : null}

        {visible(stage.checks).length > 0 ? (
          <h3 className="mb-2 mt-6 text-sm font-semibold text-fd-foreground">完成清单</h3>
        ) : null}
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {stage.checks.map((c, i) => {
            if (tierRank[c.min ?? 'tool'] > tierRank[tier]) return null;
            const id = `${stage.key}-${i}`;
            const on = Boolean(checked[id]);
            return (
              <li key={id}>
                <label className="flex cursor-pointer items-start gap-2.5 py-1 text-sm">
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={(e) => setChecked({ ...checked, [id]: e.target.checked })}
                    className="mt-1 size-4 accent-[var(--color-fd-primary)]"
                  />
                  <span className={on ? 'text-fd-muted-foreground line-through' : 'text-fd-foreground'}>{c.text}</span>
                </label>
              </li>
            );
          })}
        </ul>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t pt-4">
          <button
            type="button"
            disabled={index === 0}
            onClick={() => setCurrent(index - 1)}
            className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-35"
          >
            ← 上一步
          </button>
          <Link href={stage.href} className="text-sm font-medium text-fd-primary hover:underline">
            这一阶段的完整说明 →
          </Link>
          <button
            type="button"
            disabled={index === STAGES.length - 1}
            onClick={() => setCurrent(index + 1)}
            className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-35"
          >
            下一步 →
          </button>
        </div>
      </article>
      <p className="m-0 text-xs text-fd-muted-foreground">勾选进度只保存在你的浏览器里。</p>
    </div>
  );
}
