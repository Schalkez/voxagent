import React from 'react';
import { Text } from '@shared/components';

export const HeroCard: React.FC = () => {
  return (
    <div className="bg-surface-base border border-outline-variant/30 rounded-xl py-12 px-6 flex flex-col items-center relative overflow-hidden group">
      <div className="absolute inset-0 bg-gradient-to-tr from-[#0070f3]/5 to-transparent pointer-events-none"></div>
      <div className="relative z-10 flex flex-col items-center gap-6">
        <div className="flex items-end gap-[2px] h-8">
          <div className="w-[3px] bg-primary-container rounded-sm" style={{ height: '12px' }}></div>
          <div className="w-[3px] bg-primary-container rounded-sm" style={{ height: '18px' }}></div>
          <div className="w-[3px] bg-primary-container rounded-sm" style={{ height: '24px' }}></div>
          <div className="w-[3px] bg-primary-container rounded-sm" style={{ height: '16px' }}></div>
          <div className="w-[3px] bg-primary-container rounded-sm" style={{ height: '28px' }}></div>
          <div className="w-[3px] bg-primary-container rounded-sm" style={{ height: '20px' }}></div>
          <div className="w-[3px] bg-primary-container rounded-sm" style={{ height: '14px' }}></div>
          <div className="w-[3px] bg-primary-container rounded-sm" style={{ height: '22px' }}></div>
          <div className="w-[3px] bg-primary-container rounded-sm" style={{ height: '10px' }}></div>
        </div>
        <div className="flex flex-col items-center gap-1">
          <Text as="span" variant="mono" className="text-lg text-text-on-surface tracking-tight">Listening for wake word...</Text>
          <Text as="span" variant="mono" className="text-[11px] tracking-widest uppercase text-text-on-surface-variant">Core Intelligence Online</Text>
        </div>
      </div>
    </div>
  );
};
