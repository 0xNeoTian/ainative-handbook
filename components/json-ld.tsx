import { appDescription, appName, appNameEn, author, siteUrl } from '@/lib/shared';

const person = {
  '@type': 'Person',
  name: author.name,
  url: `https://github.com/${author.github}`,
  sameAs: [`https://github.com/${author.github}`],
};

function JsonLd({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      // JSON-LD must be emitted as raw JSON; escape "<" so content cannot break out of the script tag.
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, '\\u003c') }}
    />
  );
}

export function WebsiteJsonLd() {
  return (
    <JsonLd
      data={{
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        name: appName,
        alternateName: [appNameEn, 'AI Native Handbook', 'ainative'],
        url: siteUrl,
        description: appDescription,
        inLanguage: 'zh-CN',
        author: person,
        publisher: person,
        license: 'https://creativecommons.org/licenses/by/4.0/',
      }}
    />
  );
}

interface ArticleJsonLdProps {
  title: string;
  description?: string;
  url: string;
  image: string;
  updated?: string;
  section?: string;
}

export function ArticleJsonLd({ title, description, url, image, updated, section }: ArticleJsonLdProps) {
  return (
    <JsonLd
      data={{
        '@context': 'https://schema.org',
        '@type': 'TechArticle',
        headline: title,
        description,
        url: `${siteUrl}${url}`,
        mainEntityOfPage: `${siteUrl}${url}`,
        image: `${siteUrl}${image}`,
        inLanguage: 'zh-CN',
        dateModified: updated,
        articleSection: section,
        author: person,
        publisher: person,
        isPartOf: { '@type': 'WebSite', name: appName, alternateName: appNameEn, url: siteUrl },
        license: 'https://creativecommons.org/licenses/by/4.0/',
      }}
    />
  );
}
