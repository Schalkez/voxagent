import React from 'react';
import type { RoutingStatusChipProps } from '@features/routing/types';

export const RoutingStatusChip: React.FC<RoutingStatusChipProps> = ({
  status = 'Optimized for latency',
}) => {
  return (
    <div className="mt-16 flex items-center justify-center">
      <div className="bg-surface-high px-6 py-3 rounded-full flex items-center gap-4 border border-outline-variant/30">
        <div className="relative flex items-center justify-center">
          <div className="absolute inset-0 bg-primary/20 blur-md rounded-full animate-pulse" />
          <div className="w-3 h-3 bg-primary rounded-full relative z-10" />
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-zinc-500 font-label uppercase tracking-widest leading-none mb-1">
            Routing Engine
          </span>
          <span className="text-xs text-text-on-surface font-mono leading-none">
            Status: {status}
          </span>
        </div>
      </div>
    </div>
  );
};
