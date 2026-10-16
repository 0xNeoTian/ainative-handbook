import { renderOg } from '@/lib/og';

export const revalidate = false;
export const dynamic = 'force-static';

export async function GET() {
  return renderOg({
    title: '每条规则，都标明出处',
    description: '70 多篇真实复盘整理成的 Claude Code 实战手册：流程、工具链、护栏与 25 张坑卡',
    eyebrow: 'AI Native Handbook · v0.1',
  });
}
