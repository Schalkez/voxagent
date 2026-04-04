import React from 'react';
import { Text, Icon } from '@shared/components';

interface BentoGridProps {
  dailyCommands: number;
  avgLatencyMs: number;
  activeSkills: number;
  totalSkills: number;
  loading?: boolean;
}

export const BentoGrid: React.FC<BentoGridProps> = ({
  dailyCommands,
  avgLatencyMs,
  activeSkills,
  totalSkills,
  loading = false,
}) => {
  const latencyDisplay = avgLatencyMs > 0 ? `${(avgLatencyMs / 1000).toFixed(1)}s` : '—';
  const commandsDisplay = dailyCommands > 0 ? dailyCommands.toString() : '—';
  const commandsChange = dailyCommands > 0 ? '+12%' : 'No data';

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div className="bg-surface-base border border-outline-variant/30 rounded-lg p-6 hover:border-primary-container/30 transition-all">
        <div className="flex justify-between items-start mb-4">
          <Text as="span" variant="mono" className="text-[11px] font-bold uppercase tracking-widest text-text-on-surface-variant">
            Daily Commands
          </Text>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-sm ${
            dailyCommands > 0 ? 'bg-[#00E472]/10 text-secondary-fixed-dim' : 'bg-zinc-500/10 text-zinc-500'
          }`}>
            {commandsChange}
          </span>
        </div>
        <div className={`text-4xl font-medium text-white font-mono ${loading ? 'animate-pulse' : ''}`}>
          {commandsDisplay}
        </div>
        <div className="mt-4 h-1 bg-white/5 rounded-full overflow-hidden">
          <div
            className="h-full bg-primary-container transition-all duration-500"
            style={{ width: dailyCommands > 0 ? '70%' : '0%' }}
          />
        </div>
      </div>

      <div className="bg-surface-base border border-outline-variant/30 rounded-lg p-6 hover:border-primary-container/30 transition-all">
        <div className="flex justify-between items-start mb-4">
          <Text as="span" variant="mono" className="text-[11px] font-bold uppercase tracking-widest text-text-on-surface-variant">
            Avg Latency
          </Text>
          <Icon name="bolt" className="text-text-on-surface-variant/50 text-lg" />
        </div>
        <div className={`text-4xl font-medium text-white font-mono ${loading ? 'animate-pulse' : ''}`}>
          {latencyDisplay}
        </div>
        <p className="mt-4 text-[10px] text-text-on-surface-variant">Calculated over last 24h</p>
      </div>

      <div className="bg-surface-base border border-outline-variant/30 rounded-lg p-6 hover:border-primary-container/30 transition-all">
        <div className="flex justify-between items-start mb-4">
          <Text as="span" variant="mono" className="text-[11px] font-bold uppercase tracking-widest text-text-on-surface-variant">
            Active Skills
          </Text>
          <Icon name="extension" className="text-text-on-surface-variant/50 text-lg" />
        </div>
        <div className={`text-4xl font-medium text-white font-mono ${loading ? 'animate-pulse' : ''}`}>
          {activeSkills} / {totalSkills}
        </div>
        <p className="mt-4 text-[10px] text-text-on-surface-variant">
          {totalSkills - activeSkills > 0
            ? `${totalSkills - activeSkills} skills in standby mode`
            : 'All skills active'}
        </p>
      </div>
    </div>
  );
};
