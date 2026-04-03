import React from 'react';
import { Dot } from '@shared/components';

export interface StatusBadgeProps {
  status: 'Online' | 'Offline' | 'Listening' | 'Idle';
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  className = ''
}) => {
  const isOnline = status === 'Online' || status === 'Listening';
  
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <Dot color={isOnline ? 'cyan' : 'gray'} pulsing={isOnline} />
      <span className="text-text-on-surface font-bold font-mono text-xs tracking-widest uppercase">{status}</span>
    </div>
  );
};
