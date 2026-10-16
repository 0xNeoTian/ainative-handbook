import type { Metadata, Viewport } from 'next';
import { Provider } from '@/components/provider';
import { appDescription, appName, appNameEn, appTagline, siteUrl } from '@/lib/shared';
import './global.css';

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: `${appName}（${appNameEn}）· ${appTagline}`,
    template: `%s · ${appName}`,
  },
  description: appDescription,
  applicationName: appName,
  authors: [{ name: 'Neo', url: 'https://github.com/0xNeoTian' }],
  keywords: [
    'AI Native 手册',
    'AI Native Handbook',
    'Claude Code',
    'Claude Code 实战',
    'Claude Code 最佳实践',
    'AI 原生开发',
    'AI-native SDLC',
    'superpowers',
    'Matt Pocock skills',
    'gstack',
    'harness engineering',
    'compound engineering',
    'Claude Code 插件',
    '独立开发',
    '一人公司',
  ],
  openGraph: {
    type: 'website',
    locale: 'zh_CN',
    siteName: appName,
    title: `${appName}（${appNameEn}）`,
    description: appDescription,
    url: siteUrl,
    images: ['/og/home.png'],
  },
  twitter: {
    card: 'summary_large_image',
    title: `${appName}（${appNameEn}）`,
    description: appDescription,
    images: ['/og/home.png'],
  },
  alternates: {
    canonical: '/',
  },
  icons: {
    icon: '/favicon.svg',
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f5f5f4' },
    { media: '(prefers-color-scheme: dark)', color: '#121212' },
  ],
};

export default function Layout({ children }: LayoutProps<'/'>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="flex flex-col min-h-screen">
        <Provider>{children}</Provider>
      </body>
    </html>
  );
}
