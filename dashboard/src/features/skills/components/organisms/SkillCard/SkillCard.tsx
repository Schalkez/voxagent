import React from 'react';
import { Switch } from '@shared/components';

export type PermissionLevel = 'safe' | 'elevated' | 'dangerous';

export interface SkillPermission {
  name: string;
  level: PermissionLevel;
}

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

const PERMISSION_STYLES: Record<PermissionLevel, string> = {
  safe: 'bg-zinc-900 text-zinc-300 border-zinc-800',
  elevated: 'bg-tertiary/10 text-tertiary border-tertiary/20',
  dangerous: 'bg-error/10 text-error border-error/20',
};

export const SkillCard: React.FC<SkillCardProps> = ({
  name,
  icon,
  version,
  author,
  description,
  enabled,
  permissions,
  onToggle,
}) => {
  return (
    <div
      className={`bg-surface-base border rounded-xl overflow-hidden flex flex-col group transition-all duration-300 ${
        enabled
          ? 'border-outline-variant/30 hover:border-primary/30'
          : 'border-outline-variant/20 hover:border-outline-variant/40'
      }`}
    >
      <div className="p-6 flex flex-col h-full">
        {/* Header: Icon + Toggle */}
        <div className="flex justify-between items-start mb-4">
          <div
            className={`p-2 rounded-lg ${
              enabled ? 'bg-primary/10' : 'bg-zinc-800'
            }`}
          >
            <span
              className={`material-symbols-outlined ${
                enabled ? 'text-primary' : 'text-zinc-400'
              }`}
            >
              {icon}
            </span>
          </div>
          <Switch
            checked={enabled}
            onChange={() => onToggle?.(!enabled)}
          />
        </div>

        {/* Name + Meta */}
        <h3
          className={`text-text-on-surface font-headline font-semibold text-lg mb-1 transition-colors ${
            enabled ? 'group-hover:text-primary' : ''
          }`}
        >
          {name}
        </h3>
        <p className="text-zinc-500 text-xs font-mono mb-4 uppercase tracking-tighter">
          {version} • by {author}
        </p>

        {/* Description */}
        <p className="text-zinc-400 text-sm font-body leading-relaxed mb-6">
          {description}
        </p>

        {/* Permissions */}
        <div className="mt-auto">
          <div className="bg-zinc-950 p-4 rounded-lg">
            <span className="text-[10px] font-label uppercase tracking-widest text-zinc-500 block mb-2">
              Requires:
            </span>
            <div className="flex flex-wrap gap-2">
              {permissions.map((perm) => (
                <span
                  key={perm.name}
                  className={`px-2 py-1 rounded text-[10px] font-mono border ${PERMISSION_STYLES[perm.level]}`}
                >
                  {perm.name}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
