import { source } from '@/lib/source';
import { PitfallFilter, type PitfallCard } from './pitfall-filter';

/** Lists every card under content/docs/pitfalls/, filterable by stage, tier and evidence. */
export function PitfallIndex() {
  const cards: PitfallCard[] = source
    .getPages()
    .filter((page) => page.slugs[0] === 'pitfalls' && page.slugs.length === 2)
    .map((page) => ({
      url: page.url,
      title: page.data.title,
      description: page.data.description ?? '',
      rule: page.data.rule ?? '',
      evidence: page.data.evidence,
      tier: page.data.tier ?? [],
      stage: page.data.stage,
      type: page.data.type,
    }))
    .sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'));

  return <PitfallFilter cards={cards} />;
}
