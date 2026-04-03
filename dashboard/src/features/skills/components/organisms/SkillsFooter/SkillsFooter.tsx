import React from 'react';

export interface SkillsFooterProps {
  activeCount: number;
  systemHealth: string;
  lastUpdate: string;
}

export const SkillsFooter: React.FC<SkillsFooterProps> = ({
  activeCount,
  systemHealth,
  lastUpdate,
}) => {
  return (
    <footer className="mt-auto p-8 border-t border-outline-variant/20 bg-zinc-950/30">
      <div className="flex flex-col md:flex-row gap-8 items-start md:items-center justify-between">
        <div className="flex gap-12">
          <div>
            <p className="text-[10px] font-label uppercase text-zinc-600 mb-1">
              Total Active Skills
            </p>
            <p className="text-2xl font-mono font-medium text-text-on-surface">
              {String(activeCount).padStart(2, '0')}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-label uppercase text-zinc-600 mb-1">
              System Health
            </p>
            <p className="text-2xl font-mono font-medium text-primary">
              {systemHealth}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-label uppercase text-zinc-600 mb-1">
              Last Update
            </p>
            <p className="text-sm font-mono text-zinc-400 mt-2">
              {lastUpdate}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-[10px] font-label uppercase text-zinc-600">
            Local Environment:{' '}
            <span className="text-zinc-400">Node-24-Alpha</span>
          </span>
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
        </div>
      </div>
    </footer>
  );
};
