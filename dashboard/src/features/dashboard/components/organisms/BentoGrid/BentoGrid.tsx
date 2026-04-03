import React from 'react';
import { Text, Icon } from '@shared/components';

export const BentoGrid: React.FC = () => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div className="bg-surface-base border border-outline-variant/30 rounded-lg p-6 hover:border-primary-container/30 transition-all">
        <div className="flex justify-between items-start mb-4">
          <Text as="span" variant="mono" className="text-[11px] font-bold uppercase tracking-widest text-text-on-surface-variant">Daily Commands</Text>
          <span className="bg-[#00E472]/10 text-secondary-fixed-dim text-[10px] font-bold px-2 py-0.5 rounded-sm">+12%</span>
        </div>
        <div className="text-4xl font-medium text-white font-mono">142</div>
        <div className="mt-4 h-1 bg-white/5 rounded-full overflow-hidden">
          <div className="h-full bg-primary-container" style={{ width: '70%' }}></div>
        </div>
      </div>

      <div className="bg-surface-base border border-outline-variant/30 rounded-lg p-6 hover:border-primary-container/30 transition-all">
        <div className="flex justify-between items-start mb-4">
          <Text as="span" variant="mono" className="text-[11px] font-bold uppercase tracking-widest text-text-on-surface-variant">Avg Latency</Text>
          <Icon name="bolt" className="text-text-on-surface-variant/50 text-lg" />
        </div>
        <div className="text-4xl font-medium text-white font-mono">1.2s</div>
        <p className="mt-4 text-[10px] text-text-on-surface-variant">Calculated over last 24h</p>
      </div>

      <div className="bg-surface-base border border-outline-variant/30 rounded-lg p-6 hover:border-primary-container/30 transition-all">
        <div className="flex justify-between items-start mb-4">
          <Text as="span" variant="mono" className="text-[11px] font-bold uppercase tracking-widest text-text-on-surface-variant">Active Skills</Text>
          <Icon name="extension" className="text-text-on-surface-variant/50 text-lg" />
        </div>
        <div className="text-4xl font-medium text-white font-mono">4 / 12</div>
        <p className="mt-4 text-[10px] text-text-on-surface-variant">8 skills in standby mode</p>
      </div>
    </div>
  );
};
