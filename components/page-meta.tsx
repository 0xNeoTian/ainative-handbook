import { evidenceLabel, stageLabel, tierLabel, type Evidence, type Stage, type Tier } from '@/lib/labels';
import { siteUrl } from '@/lib/shared';

interface PageMetaProps {
  url: string;
  evidence?: Evidence;
  tier?: Tier[];
  stage?: Stage;
  updated?: string;
  basis?: string;
}

const chip =
  'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium text-fd-muted-foreground';

export function PageMeta({ evidence, tier, stage, updated, basis }: PageMetaProps) {
  if (!evidence && !tier?.length && !stage && !updated && !basis) return null;

  return (
    <div className="flex flex-wrap items-center gap-2" aria-label="页面标签">
      {evidence ? (
        <span className={`${chip} border-fd-primary/40 text-fd-foreground`} title={evidenceLabel[evidence].hint}>
          <span aria-hidden>{evidenceLabel[evidence].icon}</span>
          {evidenceLabel[evidence].text}
        </span>
      ) : null}
      {tier?.map((t) => (
        <span key={t} className={chip}>
          {tierLabel[t]}
        </span>
      ))}
      {stage ? <span className={chip}>阶段 · {stageLabel[stage]}</span> : null}
      {basis ? (
        <span className={chip} title="依据的原始记录（复盘、提交或工作记录）不公开，这里标明时间和类型">
          依据 · {basis}
        </span>
      ) : null}
      {updated ? <span className="text-xs text-fd-muted-foreground">更新于 {updated}</span> : null}
    </div>
  );
}

export function RuleCallout({ rule }: { rule: string }) {
  return (
    <div className="not-prose my-6 rounded-xl border border-fd-primary/40 bg-fd-primary/5 px-5 py-4">
      <div className="mb-1 text-xs font-semibold tracking-wide text-fd-primary">一句话规则</div>
      <p className="m-0 text-base font-medium leading-relaxed text-fd-foreground">{rule}</p>
    </div>
  );
}

export function ShareOnX({ tweet, url }: { tweet: string; url: string }) {
  const href = `https://x.com/intent/post?text=${encodeURIComponent(tweet)}&url=${encodeURIComponent(siteUrl + url)}`;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium text-fd-muted-foreground transition-colors hover:bg-fd-accent hover:text-fd-accent-foreground"
    >
      <svg aria-hidden viewBox="0 0 24 24" className="size-3.5 fill-current">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
      </svg>
      分享到 X
    </a>
  );
}
