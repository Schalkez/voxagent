import { type HTMLAttributes, type ReactNode } from 'react';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  variant?: 'default' | 'glow' | 'transparent';
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card = ({ 
  children, 
  variant = 'default', 
  padding = 'md', 
  className,
  ...props 
}: CardProps) => {
  
  const variants = {
    default: 'bg-surface-container-low border border-outline-variant/10 hover:border-zinc-700',
    glow: 'bg-[#18181B] border border-white/[0.03] shadow-2xl hover:border-cyan-500/20 hover:shadow-[0_0_20px_rgba(6,182,212,0.1)]',
    transparent: 'bg-zinc-900/40 border border-zinc-800/30 backdrop-blur-sm'
  };

  const paddings = {
    none: 'p-0',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8'
  };

  return (
    <div 
      className={`
        rounded-xl transition-all duration-300
        ${variants[variant]}
        ${paddings[padding]}
        ${className || ''}
      `}
      {...props}
    >
      {children}
    </div>
  );
};
