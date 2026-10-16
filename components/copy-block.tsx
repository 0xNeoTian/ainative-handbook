'use client';

import { useState } from 'react';

export function CopyBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <div className="overflow-hidden rounded-xl border bg-fd-card text-left">
      <div className="flex items-center justify-between border-b px-4 py-2 text-xs text-fd-muted-foreground">
        <span>{label ?? 'Terminal'}</span>
        <button
          type="button"
          onClick={() => {
            navigator.clipboard?.writeText(code).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1400);
            });
          }}
          className="rounded-md px-2 py-0.5 transition-colors hover:bg-fd-accent hover:text-fd-accent-foreground"
        >
          {copied ? '已复制' : '复制'}
        </button>
      </div>
      <pre className="m-0 overflow-x-auto px-4 py-3 font-mono text-[13px] leading-relaxed text-fd-foreground">{code}</pre>
    </div>
  );
}
