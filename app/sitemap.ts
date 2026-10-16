import type { MetadataRoute } from 'next';
import { source } from '@/lib/source';
import { siteUrl } from '@/lib/shared';

export const dynamic = 'force-static';

export default function sitemap(): MetadataRoute.Sitemap {
  const pages = source.getPages().map((page) => ({
    url: `${siteUrl}${page.url}`,
    lastModified: page.data.updated ? new Date(page.data.updated) : undefined,
    changeFrequency: 'weekly' as const,
    priority: page.slugs.length === 0 ? 0.9 : 0.6,
  }));

  return [{ url: siteUrl, changeFrequency: 'weekly', priority: 1 }, ...pages];
}
