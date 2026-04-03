import React from 'react';

export type BadgeVariant = 'success' | 'warning' | 'error' | 'neutral';

export interface BadgeProps {
  variant?: BadgeVariant;
  className?: string;
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({ 
  variant = 'neutral',
  className = '',
  children
}) => {
  let variantStyles = 'bg-surface-high text-text-on-surface-variant'; // Default neutral
  
  if (variant === 'success') variantStyles = 'bg-secondary-fixed-dim/20 text-secondary-fixed-dim';
  if (variant === 'error') variantStyles = 'bg-error/20 text-error';
  // ... more variants

  return (
    <span className={`px-2 py-1 rounded border border-outline-variant ${variantStyles} text-[9px] font-mono font-bold uppercase tracking-widest ${className}`}>
      {children}
    </span>
  );
};
