import { source } from '@/lib/source';
import { notFound } from 'next/navigation';
import { getPageImageUrl } from '@/lib/shared';
import { renderOg } from '@/lib/og';
import { evidenceLabel } from '@/lib/labels';

export const revalidate = false;

export async function GET(_req: Request, { params }: RouteContext<'/og/docs/[...slug]'>) {
  const { slug } = await params;
  const page = source.getPage(slug.slice(0, -1));
  if (!page) notFound();

  const isCard = page.slugs[0] === 'pitfalls' && page.slugs.length === 2;
  const evidence = page.data.evidence ? evidenceLabel[page.data.evidence].text : undefined;
  const eyebrow = isCard ? ['坑库', evidence].filter(Boolean).join(' · ') : evidence;

  return renderOg({
    title: page.data.title,
    description: isCard && page.data.rule ? page.data.rule : page.data.description,
    eyebrow,
  });
}

export function generateStaticParams() {
  return source.getPages().map((page) => ({
    lang: page.locale,
    slug: getPageImageUrl(page).segments,
  }));
}
