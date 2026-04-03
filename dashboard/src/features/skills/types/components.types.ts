/**
 * Component prop types for the Skills feature.
 */

import type { SkillPermission } from './skills.types';

export interface SkillCardProps {
  name: string;
  icon: string;
  version: string;
  author: string;
  description: string;
  enabled: boolean;
  permissions: SkillPermission[];
  onToggle?: (enabled: boolean) => void;
}

export interface AddSkillCardProps {
  onClick?: () => void;
}

export interface SkillsFooterProps {
  activeCount: number;
  systemHealth: string;
  lastUpdate: string;
}
