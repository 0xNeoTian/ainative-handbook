import { source } from '@/lib/source';
import { createFromSource } from 'fumadocs-core/search/server';

export const revalidate = false;

// The default `multilingual` tokenizer segments Chinese text, so no language option is set.
export const { staticGET: GET } = createFromSource(source);
