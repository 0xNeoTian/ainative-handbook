import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { ImageResponse } from 'next/og';

const fontDir = join(process.cwd(), 'assets/fonts');
let fontsPromise: Promise<[Buffer, Buffer]> | undefined;

function loadFonts() {
  fontsPromise ??= Promise.all([
    readFile(join(fontDir, 'og-sc-bold.ttf')),
    readFile(join(fontDir, 'og-sc-regular.ttf')),
  ]);
  return fontsPromise;
}

function clamp(text: string | undefined, max: number) {
  if (!text) return undefined;
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

interface OgInput {
  title: string;
  description?: string;
  /** Small label at the top right, e.g. "坑库 · 亲历". */
  eyebrow?: string;
}

const colors = {
  paper: '#f6f3ee',
  ink: '#1d1c1a',
  body: '#57544e',
  muted: '#8a877f',
  accent: '#b5532f',
  accentSoft: '#e7cfc3',
};

export async function renderOg({ title, description, eyebrow }: OgInput) {
  const [bold, regular] = await loadFonts();
  const heading = clamp(title, 40) ?? '';
  const desc = clamp(description, 64);
  // Text box is 1024px wide and a CJK glyph is about one em wide, so size headings to fill whole lines.
  const n = heading.length;
  const headingSize = n <= 12 ? 80 : n <= 14 ? 72 : n <= 17 ? 60 : n <= 24 ? 58 : 52;

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          background: colors.paper,
          padding: '64px 80px 56px 96px',
          fontFamily: 'SC',
          position: 'relative',
        }}
      >
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 16, background: colors.accent }} />
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div
            style={{
              display: 'flex',
              width: 52,
              height: 52,
              borderRadius: 12,
              background: colors.accent,
              color: '#ffffff',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 22,
              fontWeight: 700,
            }}
          >
            AI
          </div>
          <div style={{ marginLeft: 18, fontSize: 30, fontWeight: 700, color: colors.ink }}>AI Native 手册</div>
          {eyebrow ? (
            <div
              style={{
                marginLeft: 'auto',
                display: 'flex',
                fontSize: 24,
                color: colors.accent,
                border: `2px solid ${colors.accentSoft}`,
                borderRadius: 999,
                padding: '6px 20px',
              }}
            >
              {eyebrow}
            </div>
          ) : null}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div
            style={{
              fontSize: headingSize,
              fontWeight: 700,
              color: colors.ink,
              lineHeight: 1.22,
              letterSpacing: '-0.01em',
              wordBreak: 'break-all',
            }}
          >
            {heading}
          </div>
          {desc ? (
            <div style={{ marginTop: 26, fontSize: 30, color: colors.body, lineHeight: 1.5, wordBreak: 'break-all' }}>
              {desc}
            </div>
          ) : null}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 24 }}>
          <div style={{ color: colors.muted }}>Claude Code 实战 · 从小工具到组织协同</div>
          <div style={{ color: colors.accent, fontWeight: 700 }}>ainative.jubao.ai</div>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      fonts: [
        { name: 'SC', data: bold, weight: 700, style: 'normal' },
        { name: 'SC', data: regular, weight: 400, style: 'normal' },
      ],
    },
  );
}
