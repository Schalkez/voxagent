import React from 'react';
import type { RoutingPresetCardProps } from '@features/routing/types';

export const RoutingPresetCard: React.FC<RoutingPresetCardProps> = ({
  id,
  icon,
  title,
  subtitle,
  active = false,
  onClick,
}) => {
  return (
    <button
      onClick={() => onClick?.(id)}
      className={`group flex flex-col p-6 rounded-xl border text-left transition-all relative overflow-hidden ${
        active
          ? 'border-2 border-primary bg-primary/5 shadow-[0_0_15px_rgba(6,182,212,0.2)]'
          : 'border-outline-variant/30 bg-surface-base hover:border-outline-variant/60'
      }`}
    >
      {active && (
        <div className="absolute top-0 right-0 w-24 h-24 bg-primary/10 blur-3xl -mr-8 -mt-8" />
      )}
      <div className="flex items-center justify-between mb-2">
        <span
          className={`material-symbols-outlined ${
            active ? 'text-primary' : 'text-zinc-500 group-hover:text-zinc-300'
          }`}
        >
          {icon}
        </span>
        <div
          className={`w-2 h-2 rounded-full ${
            active ? 'bg-primary animate-pulse' : 'bg-zinc-800'
          }`}
        />
      </div>
      <span className="text-text-on-surface font-bold tracking-tight mb-1">
        {title}
      </span>
      <span
        className={`text-xs font-label uppercase tracking-widest ${
          active ? 'text-primary' : 'text-zinc-500'
        }`}
      >
        {subtitle}
      </span>
    </button>
  );
};
