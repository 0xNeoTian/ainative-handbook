'use client';
import SearchDialog from '@/components/search';
import { RootProvider } from 'fumadocs-ui/provider/next';
import { type ReactNode } from 'react';
import { zhUi } from '@/lib/zh-ui';

export function Provider({ children }: { children: ReactNode }) {
  return (
    <RootProvider search={{ SearchDialog }} i18n={{ locale: 'zh-CN', translations: zhUi }}>
      {children}
    </RootProvider>
  );
}
