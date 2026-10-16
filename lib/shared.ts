import { createGetUrl } from 'fumadocs-core/source';

export const appName = 'AI Native 手册';
export const appNameEn = 'AI Native Handbook';
export const appTagline = 'Claude Code 实战：从小工具到组织协同';
export const appSlogan = '每条规则，都标明出处';
export const appDescription =
  'AI Native 手册（AI Native Handbook）：用 Claude Code 做产品的开源实战手册（内容 CC BY 4.0，代码 MIT），首选 Claude Code，方法也适用于 Codex、Cursor、Gemini CLI 等 AI 编程工具。从小工具、产品到多仓库的组织协同，覆盖 AI-native 开发流程、工具链、护栏与 25 张来自真实复盘的坑卡，每条规则都标明可信度和出处，并附带可安装的 Claude Code 插件。';
export const siteUrl = 'https://ainative.jubao.ai';
export const docsRoute = '/docs';
export const docsImageRoute = '/og/docs';
export const docsContentRoute = '/llms.mdx/docs';

export const author = {
  name: 'Neo',
  github: '0xNeoTian',
};

export const gitConfig = {
  user: '0xNeoTian',
  repo: 'ainative-handbook',
  branch: 'main',
  isPublic: true,
};

const getContentUrl = createGetUrl(docsContentRoute);

export function getPageMarkdownUrl(page: { slugs: string[]; locale?: string }) {
  const segments = [...page.slugs, 'content.md'];

  return { segments, url: getContentUrl(segments, page.locale) };
}

const getImageUrl = createGetUrl(docsImageRoute);

export function getPageImageUrl(page: { slugs: string[]; locale?: string }) {
  const segments = [...page.slugs, 'image.png'];

  return { segments, url: getImageUrl(segments, page.locale) };
}
