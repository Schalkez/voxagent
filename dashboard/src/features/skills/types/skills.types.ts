/**
 * Domain types for the Skills feature.
 */

export type PermissionLevel = 'safe' | 'elevated' | 'dangerous';

export interface SkillPermission {
  name: string;
  level: PermissionLevel;
}

export interface SkillInfo {
  id: string;
  name: string;
  icon: string;
  version: string;
  author: string;
  description: string;
  enabled: boolean;
  permissions: SkillPermission[];
}
