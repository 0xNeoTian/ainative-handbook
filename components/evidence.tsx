import { evidenceLabel, type Evidence as EvidenceKind } from '@/lib/labels';

/** Inline credibility tag for mixed pages, e.g. <Evidence kind="trial" />. */
export function Evidence({ kind }: { kind: EvidenceKind }) {
  const label = evidenceLabel[kind];

  return (
    <span
      title={label.hint}
      className="not-prose mx-0.5 inline-flex items-center gap-1 rounded-full border px-2 py-px align-middle text-[0.75em] font-medium text-fd-muted-foreground"
    >
      <span aria-hidden>{label.icon}</span>
      {label.text}
    </span>
  );
}
