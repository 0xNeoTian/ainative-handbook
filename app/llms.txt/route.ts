import { docsLlms } from '@/lib/source';
import { appDescription, appName, appNameEn, siteUrl } from '@/lib/shared';

export const revalidate = false;

const header = `# ${appName}（${appNameEn}）

> ${appDescription}

- 网站：${siteUrl}
- 全文：${siteUrl}/llms-full.txt
- Claude Code 插件：\`claude plugin marketplace add ${siteUrl}/marketplace.json\` 然后 \`claude plugin install ainative@ainative\`
- 可信度标签：✅ 亲历（作者真实用过、有复盘）/ 🧪 试用中 / 📚 业界做法（未亲测）
- 许可：内容 CC BY 4.0，引用请注明出处与链接

## English summary

AI Native Handbook is a practical, experience-based guide to building products with Claude Code first (the methods also apply to Codex, Cursor, Gemini CLI and other AI coding tools), written in Chinese by Neo (github.com/0xNeoTian), a founder who runs two organizations — a dozen repositories and dozens of agents — with a few collaborators, largely with Claude Code. It distills 70+ project and incident retrospectives written over about half a year into:

- a three-tier path: side tool → product (the six-stage AI-native SDLC: plan, design, build, test, ship, maintain) → organization (a separate ops repository, an org-level ops agent, layered memory, and feedback loops that keep rules alive);
- a hands-on comparison of the superpowers and Matt Pocock skills workflow plugins, and how to migrate between them;
- guardrails (permission rules, hooks, health checks) and 25 cards drawn from real retrospectives and work logs, each with a one-line rule and a dated basis;
- templates (one-page CLAUDE.md, intent, spec, plan, ADR, retro, REVIEW.md, subagent prompt);
- an installable Claude Code plugin (doctor, setup, recommend, new-project, pitfall-check, harvest).

Every page is labeled ✅ lived (used in production, backed by a retro), 🧪 trial, or 📚 industry practice (not yet verified by the author). An English edition is planned.

`;

export async function GET() {
  return new Response(header + (await docsLlms.index()), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}
