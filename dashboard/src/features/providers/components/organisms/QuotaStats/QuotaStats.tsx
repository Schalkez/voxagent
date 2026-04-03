import React from 'react';
import { ProgressBar } from '@shared/components';

export interface QuotaStatsProps {
  dailyTokens?: { used: number; limit: number };
  monthlyCost?: { current: number; projected: number };
  activeSessions?: number;
}

export const QuotaStats: React.FC<QuotaStatsProps> = ({
  dailyTokens = { used: 1200000, limit: 5000000 },
  monthlyCost = { current: 14.82, projected: 32.0 },
  activeSessions = 8,
}) => {
  const tokenPercent = Math.round(
    (dailyTokens.used / dailyTokens.limit) * 100
  );

  const formatNumber = (n: number) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
    return String(n);
  };

  return (
    <section className="grid grid-cols-1 lg:grid-cols-3 gap-6 opacity-80">
      {/* Daily Token Limit */}
      <div className="p-6 rounded-xl bg-zinc-900/50 border border-outline-variant/30">
        <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-2">
          Daily Token Limit
        </div>
        <div className="font-mono text-2xl text-zinc-200">
          {formatNumber(dailyTokens.used)} / {formatNumber(dailyTokens.limit)}
        </div>
        <ProgressBar
          progress={tokenPercent}
          size="sm"
          colorClass="bg-primary"
          className="mt-4"
        />
      </div>

      {/* Estimated Monthly Cost */}
      <div className="p-6 rounded-xl bg-zinc-900/50 border border-outline-variant/30">
        <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-2">
          Estimated Monthly Cost
        </div>
        <div className="font-mono text-2xl text-zinc-200">
          ${monthlyCost.current.toFixed(2)}
        </div>
        <div className="text-[10px] text-zinc-600 mt-4 uppercase">
          Projected: ${monthlyCost.projected.toFixed(2)}
        </div>
      </div>

      {/* Active Sessions */}
      <div className="p-6 rounded-xl bg-zinc-900/50 border border-outline-variant/30">
        <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-2">
          Active Sessions
        </div>
        <div className="font-mono text-2xl text-zinc-200">
          {String(activeSessions).padStart(2, '0')}
        </div>
        <div className="text-[10px] text-emerald-500/70 mt-4 uppercase">
          All Systems Nominal
        </div>
      </div>
    </section>
  );
};
