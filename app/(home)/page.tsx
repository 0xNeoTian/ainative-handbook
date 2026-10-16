import Link from 'next/link';
import { source } from '@/lib/source';
import { appName, appNameEn, appSlogan, appTagline, siteUrl } from '@/lib/shared';
import { evidenceLabel } from '@/lib/labels';
import { CopyBlock } from '@/components/copy-block';
import { WebsiteJsonLd } from '@/components/json-ld';

const featured = [
  'guardrails-decay',
  'cross-model-review',
  'see-it-to-ship',
  'plugin-bloat',
  'one-process-engine',
  'config-overwrite',
];

const tiers = [
  {
    name: '小工具',
    href: '/docs/tool',
    when: '一个人、一个仓库、还没有长期用户',
    what: '30 分钟起步：一页 CLAUDE.md、最小护栏、静态站部署到 Cloudflare。',
  },
  {
    name: '产品',
    href: '/docs/product',
    when: '有了真实用户，要持续迭代',
    what: '六个阶段：规划、设计、开发、测试、发布、运维。每个阶段一个产物、一个人工关卡。',
  },
  {
    name: '组织',
    href: '/docs/org',
    when: '多个仓库、多人协作',
    what: 'ops 仓、组织级 ops agent、记忆分层，以及让规则自动回流的进化机制。',
  },
];

const steps = [
  { title: '先拷问，再动手', text: '用 grilling 一轮轮问清写给谁、公开到什么程度、怎么上线，答案就是 intent。' },
  { title: '定标准，再分工', text: '先写写作标准和任务说明，再让 6 个子 agent 按文件归属并行写作。' },
  { title: '多道审查', text: '敏感信息自动扫描，脱敏、事实、编辑三路审查，再交给另一个模型家族二审。' },
  { title: '一份源，多个出口', text: '同一份 Markdown 生成网站、llms.txt 和可安装的 Claude Code 插件。' },
];

const installCode = `claude plugin marketplace add ${siteUrl}/marketplace.json
claude plugin install ainative@ainative`;

export default function HomePage() {
  const cards = featured
    .map((id) => source.getPage(['pitfalls', id]))
    .filter((page) => page && page.data.rule && page.data.rule !== 'TODO');

  return (
    <main className="flex flex-1 flex-col">
      <WebsiteJsonLd />

      <section className="mx-auto flex w-full max-w-5xl flex-col items-center px-4 pb-16 pt-20 text-center sm:px-6 sm:pt-28">
        <span className="rounded-full border px-3 py-1 text-xs font-medium text-fd-muted-foreground">
          {appNameEn} · v0.1
        </span>
        <h1 className="mt-6 text-4xl font-bold tracking-tight text-fd-foreground sm:text-6xl">{appName}</h1>
        <p className="mt-5 text-lg text-fd-muted-foreground sm:text-xl">{appTagline}</p>
        <p className="mt-3 text-base font-medium text-fd-primary sm:text-lg">{appSlogan}。</p>
        <p className="mx-auto mt-6 max-w-2xl text-[15px] leading-relaxed text-fd-muted-foreground">
          作者带着几位协作者，主要靠 Claude Code 运营两个组织、十几个代码仓库和几十个 agent。这本手册把半年里写下的
          70 多篇复盘，整理成能照着做的流程、模板、规则和插件。首选 Claude Code，方法也适用于 Codex 等 AI 编程工具。
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            href="/docs/quickstart"
            className="rounded-lg bg-fd-primary px-5 py-2.5 text-sm font-semibold text-fd-primary-foreground shadow-sm transition-opacity hover:opacity-90"
          >
            10 分钟快速开始
          </Link>
          <Link
            href="/docs"
            className="rounded-lg border px-5 py-2.5 text-sm font-semibold text-fd-foreground transition-colors hover:bg-fd-accent"
          >
            开始阅读
          </Link>
          <Link
            href="/docs/launcher"
            className="rounded-lg border px-5 py-2.5 text-sm font-semibold text-fd-foreground transition-colors hover:bg-fd-accent"
          >
            用启动器起一个新项目
          </Link>
          <Link
            href="/docs/pitfalls"
            className="rounded-lg border px-5 py-2.5 text-sm font-semibold text-fd-foreground transition-colors hover:bg-fd-accent"
          >
            看 25 张踩坑卡片
          </Link>
        </div>
        <div className="mt-10 w-full max-w-2xl">
          <CopyBlock code={installCode} label="安装配套的 Claude Code 插件" />
          <p className="mt-2 text-xs text-fd-muted-foreground">
            装好后可以让 Claude 体检你的环境、按档位配置工具链、用坑库审查改动。
            <Link href="/docs/reference/plugin" className="ml-1 text-fd-primary hover:underline">
              插件说明 →
            </Link>
          </p>
        </div>
      </section>

      <section className="border-t bg-fd-card/40">
        <div className="mx-auto w-full max-w-5xl px-4 py-14 sm:px-6">
          <h2 className="text-2xl font-semibold text-fd-foreground">先选你在哪一档</h2>
          <p className="mt-2 text-sm text-fd-muted-foreground">
            小工具不需要 ops，组织不能只靠一个 CLAUDE.md。
            <Link href="/docs/tiers" className="ml-1 text-fd-primary hover:underline">
              怎么判断 →
            </Link>
          </p>
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            {tiers.map((tier) => (
              <Link
                key={tier.name}
                href={tier.href}
                className="group flex flex-col rounded-2xl border bg-fd-background p-5 transition-colors hover:border-fd-primary/50"
              >
                <span className="text-lg font-semibold text-fd-foreground group-hover:text-fd-primary">{tier.name}</span>
                <span className="mt-1 text-xs text-fd-muted-foreground">{tier.when}</span>
                <span className="mt-3 text-sm leading-relaxed text-fd-muted-foreground">{tier.what}</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {cards.length > 0 ? (
        <section className="border-t">
          <div className="mx-auto w-full max-w-5xl px-4 py-14 sm:px-6">
            <h2 className="text-2xl font-semibold text-fd-foreground">每条规则，都标明出处</h2>
            <p className="mt-2 text-sm text-fd-muted-foreground">
              坑卡来自真实复盘和工作记录，写清楚发生了什么、为什么、怎么防；每张都标了可信度和依据的时间。
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {cards.map((page) =>
                page ? (
                  <Link
                    key={page.url}
                    href={page.url}
                    className="group flex flex-col gap-2 rounded-xl border p-4 transition-colors hover:border-fd-primary/50 hover:bg-fd-accent/30"
                  >
                    <span className="text-[11px] text-fd-muted-foreground">
                      {page.data.evidence
                        ? `${evidenceLabel[page.data.evidence].icon} ${evidenceLabel[page.data.evidence].text}`
                        : '坑库'}
                    </span>
                    <span className="font-semibold leading-snug text-fd-foreground group-hover:text-fd-primary">
                      {page.data.title}
                    </span>
                    <span className="text-sm leading-relaxed text-fd-muted-foreground">{page.data.rule}</span>
                  </Link>
                ) : null,
              )}
            </div>
            <Link href="/docs/pitfalls" className="mt-6 inline-block text-sm font-medium text-fd-primary hover:underline">
              查看全部卡片 →
            </Link>
          </div>
        </section>
      ) : null}

      <section className="border-t bg-fd-card/40">
        <div className="mx-auto w-full max-w-5xl px-4 py-14 sm:px-6">
          <h2 className="text-2xl font-semibold text-fd-foreground">这本手册是用它自己的方法做出来的</h2>
          <ol className="mt-6 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, i) => (
              <li key={step.title} className="rounded-xl border bg-fd-background p-4">
                <span className="text-xs font-semibold text-fd-primary">0{i + 1}</span>
                <div className="mt-1 font-semibold text-fd-foreground">{step.title}</div>
                <p className="mt-2 text-sm leading-relaxed text-fd-muted-foreground">{step.text}</p>
              </li>
            ))}
          </ol>
          <Link href="/docs/why" className="mt-6 inline-block text-sm font-medium text-fd-primary hover:underline">
            为什么写这本手册 →
          </Link>
        </div>
      </section>

      <footer className="border-t">
        <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-8 text-xs text-fd-muted-foreground sm:px-6">
          <span>
            {appName} · 作者 Neo（
            <a href="https://github.com/0xNeoTian" className="hover:text-fd-foreground">
              @0xNeoTian
            </a>
            ）· 内容 CC BY 4.0
          </span>
          <span className="flex gap-4">
            <Link href="/docs/reference/changelog" className="hover:text-fd-foreground">
              更新日志
            </Link>
            <a href="https://github.com/0xNeoTian/ainative-handbook" className="hover:text-fd-foreground">
              GitHub
            </a>
            <a href="/llms.txt" className="hover:text-fd-foreground">
              llms.txt
            </a>
            <Link href="/docs/reference/about" className="hover:text-fd-foreground">
              关于
            </Link>
          </span>
        </div>
      </footer>
    </main>
  );
}
