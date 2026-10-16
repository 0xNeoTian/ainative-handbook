import { z } from 'zod';

export const evidenceValues = ['lived', 'trial', 'industry'] as const;
export const tierValues = ['tool', 'product', 'org'] as const;
export const stageValues = ['day0', 'plan', 'design', 'build', 'test', 'ship', 'maintain', 'cross'] as const;
export const cardTypeValues = ['pitfall', 'principle', 'pattern', 'tool'] as const;

export type Evidence = (typeof evidenceValues)[number];
export type Tier = (typeof tierValues)[number];
export type Stage = (typeof stageValues)[number];
export type CardType = (typeof cardTypeValues)[number];

export const evidenceSchema = z.enum(evidenceValues);
export const tierSchema = z.enum(tierValues);
export const stageSchema = z.enum(stageValues);
export const cardTypeSchema = z.enum(cardTypeValues);

export const evidenceLabel: Record<Evidence, { icon: string; text: string; hint: string }> = {
  lived: { icon: '✅', text: '亲历', hint: '作者在真实项目里用过、踩过，有复盘为证' },
  trial: { icon: '🧪', text: '试用中', hint: '作者正在试用，结论可能会变' },
  industry: { icon: '📚', text: '业界做法', hint: '来自官方文档或业界实践，作者尚未亲自验证' },
};

export const tierLabel: Record<Tier, string> = {
  tool: '小工具',
  product: '产品',
  org: '组织',
};

export const stageLabel: Record<Stage, string> = {
  day0: '起步',
  plan: '规划',
  design: '设计',
  build: '开发',
  test: '测试',
  ship: '发布',
  maintain: '运维',
  cross: '通用',
};

export const cardTypeLabel: Record<CardType, string> = {
  pitfall: '坑',
  principle: '原则',
  pattern: '模式',
  tool: '工具',
};
