'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import {
  cardTypeLabel,
  evidenceLabel,
  stageLabel,
  stageValues,
  tierLabel,
  tierValues,
  type CardType,
  type Evidence,
  type Stage,
  type Tier,
} from '@/lib/labels';

export interface PitfallCard {
  url: string;
  title: string;
  description: string;
  rule: string;
  evidence?: Evidence;
  tier: Tier[];
  stage?: Stage;
  type?: CardType;
}

const chipBase = 'rounded-full border px-3 py-1 text-xs font-medium transition-colors';
const chipOn = 'border-fd-primary bg-fd-primary text-fd-primary-foreground';
const chipOff = 'text-fd-muted-foreground hover:bg-fd-accent hover:text-fd-accent-foreground';

export function PitfallFilter({ cards }: { cards: PitfallCard[] }) {
  const [stage, setStage] = useState<Stage | null>(null);
  const [tier, setTier] = useState<Tier | null>(null);

  const usedStages = useMemo(() => stageValues.filter((s) => cards.some((c) => c.stage === s)), [cards]);
  const visible = cards.filter((c) => (!stage || c.stage === stage) && (!tier || c.tier.includes(tier)));

  return (
    <div className="not-prose">
      <div className="mb-3 flex flex-wrap items-center gap-2" role="group" aria-label="按阶段筛选">
        <span className="mr-1 text-xs text-fd-muted-foreground">阶段</span>
        <button type="button" className={`${chipBase} ${stage === null ? chipOn : chipOff}`} onClick={() => setStage(null)}>
          全部
        </button>
        {usedStages.map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={stage === s}
            className={`${chipBase} ${stage === s ? chipOn : chipOff}`}
            onClick={() => setStage(stage === s ? null : s)}
          >
            {stageLabel[s]}
          </button>
        ))}
      </div>
      <div className="mb-6 flex flex-wrap items-center gap-2" role="group" aria-label="按档位筛选">
        <span className="mr-1 text-xs text-fd-muted-foreground">档位</span>
        <button type="button" className={`${chipBase} ${tier === null ? chipOn : chipOff}`} onClick={() => setTier(null)}>
          全部
        </button>
        {tierValues.map((t) => (
          <button
            key={t}
            type="button"
            aria-pressed={tier === t}
            className={`${chipBase} ${tier === t ? chipOn : chipOff}`}
            onClick={() => setTier(tier === t ? null : t)}
          >
            {tierLabel[t]}
          </button>
        ))}
        <span className="ml-auto text-xs text-fd-muted-foreground">
          {visible.length} / {cards.length} 张
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {visible.map((card) => (
          <Link
            key={card.url}
            href={card.url}
            className="group flex flex-col gap-2 rounded-xl border bg-fd-card p-4 transition-colors hover:border-fd-primary/50 hover:bg-fd-accent/40"
          >
            <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-fd-muted-foreground">
              {card.evidence ? (
                <span title={evidenceLabel[card.evidence].hint}>
                  {evidenceLabel[card.evidence].icon} {evidenceLabel[card.evidence].text}
                </span>
              ) : null}
              {card.type ? <span>· {cardTypeLabel[card.type]}</span> : null}
              {card.stage ? <span>· {stageLabel[card.stage]}</span> : null}
            </div>
            <div className="font-semibold leading-snug text-fd-foreground group-hover:text-fd-primary">{card.title}</div>
            {card.rule ? <p className="m-0 text-sm leading-relaxed text-fd-muted-foreground">{card.rule}</p> : null}
          </Link>
        ))}
      </div>
      {visible.length === 0 ? (
        <p className="py-8 text-center text-sm text-fd-muted-foreground">这个组合下暂时没有卡片。</p>
      ) : null}
    </div>
  );
}
