import { llms, loader } from 'fumadocs-core/source';
import { docsRoute } from './shared';
import { defineDocs } from 'fumadocs-mdx/macro';
import { metaSchema, pageSchema } from 'fumadocs-core/source/schema';
import { z } from 'zod';
import { cardTypeSchema, evidenceSchema, stageSchema, tierSchema } from './labels';

export const handbookPageSchema = pageSchema.extend({
  /** How well-tested the advice on this page is. */
  evidence: evidenceSchema.optional(),
  /** Project tiers the page applies to. */
  tier: z.array(tierSchema).optional(),
  /** SDLC stage the page belongs to. */
  stage: stageSchema.optional(),
  /** Card kind, only for pages under pitfalls/. */
  type: cardTypeSchema.optional(),
  /** One-line rule, rendered as a callout on card pages. */
  rule: z.string().optional(),
  /** Ready-to-post text for X; also powers the share link. */
  tweet: z.string().optional(),
  /** Last meaningful content update, YYYY-MM-DD. */
  updated: z.string().optional(),
  /** Where the claim comes from, e.g. "2026-05 复盘" or "2026-10 工作记录" (private sources stay private). */
  basis: z.string().optional(),
});

const docs = defineDocs({
  dir: 'content/docs',
  docs: {
    schema: handbookPageSchema,
    postprocess: {
      includeProcessedMarkdown: true,
    },
  },
  meta: {
    schema: metaSchema,
  },
});

// See https://fumadocs.dev/docs/headless/source-api for more info
export const source = loader({
  baseUrl: docsRoute,
  source: docs.toFumadocsSource(),
  plugins: [],
});

export const docsLlms = llms(source, {
  renderPage: async (page) => `# ${page.data.title} (${page.url})

${page.data.description ? `> ${page.data.description}\n\n` : ''}${await page.data.getText('processed')}`,
});
