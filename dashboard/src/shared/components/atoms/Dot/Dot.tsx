import React from 'react';

export interface DotProps {
  className?: string;
  pulsing?: boolean;
  color?: 'cyan' | 'red' | 'gray';
}

export const Dot: React.FC<DotProps> = ({ 
  className = '', 
  pulsing = false, 
  color = 'gray' 
}) => {
  const colorMap = {
    cyan: 'bg-secondary-fixed-dim',
    red: 'bg-error',
    gray: 'bg-surface-highest'
  };

  return (
    <div 
      className={`w-2 h-2 rounded-full ${colorMap[color]} ${pulsing ? 'animate-pulse' : ''} ${className}`}
    />
  );
};
