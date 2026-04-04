import React from 'react';
import { Text } from '@shared/components';

interface HeroCardProps {
  isListening?: boolean;
  isOnline?: boolean;
  error?: string | null;
}

export const HeroCard: React.FC<HeroCardProps> = ({
  isListening = false,
  isOnline = false,
  error = null,
}) => {
  const statusText = error
    ? 'Connection Error'
    : isListening
      ? 'Listening...'
      : isOnline
        ? 'Listening for wake word...'
        : 'Offline — Start the agent';

  const statusSubtext = error
    ? error
    : isOnline
      ? 'Core Intelligence Online'
      : 'Run: voxagent start';

  const barColor = error
    ? 'bg-red-500/60'
    : isListening
      ? 'bg-green-400'
      : isOnline
        ? 'bg-primary-container'
        : 'bg-zinc-600';

  return (
    <div className="bg-surface-base border border-outline-variant/30 rounded-xl py-12 px-6 flex flex-col items-center relative overflow-hidden group">
      <div className="absolute inset-0 bg-gradient-to-tr from-[#0070f3]/5 to-transparent pointer-events-none"></div>
      <div className="relative z-10 flex flex-col items-center gap-6">
        <div className="flex items-end gap-[2px] h-8">
          {[12, 18, 24, 16, 28, 20, 14, 22, 10].map((h, i) => (
            <div
              key={i}
              className={`w-[3px] ${barColor} rounded-sm transition-all ${isListening ? 'animate-pulse' : ''}`}
              style={{ height: `${h}px` }}
            />
          ))}
        </div>
        <div className="flex flex-col items-center gap-1">
          <Text as="span" variant="mono" className="text-lg text-text-on-surface tracking-tight">
            {statusText}
          </Text>
          <Text as="span" variant="mono" className="text-[11px] tracking-widest uppercase text-text-on-surface-variant">
            {statusSubtext}
          </Text>
        </div>
      </div>
    </div>
  );
};
