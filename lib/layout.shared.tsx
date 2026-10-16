import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { appName, gitConfig } from './shared';

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: (
        <span className="flex items-center gap-2 font-semibold">
          <span
            aria-hidden
            className="inline-flex size-6 items-center justify-center rounded-md bg-fd-primary text-[11px] font-bold text-fd-primary-foreground"
          >
            AI
          </span>
          {appName}
        </span>
      ),
    },
    links: [
      { text: '手册', url: '/docs', active: 'url' },
      { text: '启动器', url: '/docs/launcher' },
      { text: '坑库', url: '/docs/pitfalls', active: 'nested-url' },
      { text: '插件', url: '/docs/reference/plugin' },
    ],
    githubUrl: gitConfig.isPublic ? `https://github.com/${gitConfig.user}/${gitConfig.repo}` : undefined,
  };
}
