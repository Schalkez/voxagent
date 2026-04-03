/**
 * Permission badge style mappings.
 */

export const PERMISSION_STYLES: Record<string, string> = {
  safe: 'bg-zinc-900 text-zinc-300 border-zinc-800',
  elevated: 'bg-tertiary/10 text-tertiary border-tertiary/20',
  dangerous: 'bg-error/10 text-error border-error/20',
};

export const SKILL_CATEGORIES = ['All Categories', 'System', 'Media', 'Browser'] as const;
