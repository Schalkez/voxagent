import { forwardRef } from 'react';

export interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const Switch = forwardRef<HTMLButtonElement, SwitchProps>(
  ({ checked, onChange, disabled, className, size = 'md' }, ref) => {
    
    const sizes = {
      sm: { container: 'w-8 h-4', thumb: 'w-2.5 h-2.5', translate: 'translate-x-4' },
      md: { container: 'w-10 h-5', thumb: 'w-3.5 h-3.5', translate: 'translate-x-5' },
      lg: { container: 'w-12 h-6', thumb: 'w-4.5 h-4.5', translate: 'translate-x-6' }
    };

    return (
      <button
        ref={ref}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`
          relative inline-flex items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:ring-offset-2 focus:ring-offset-zinc-950
          ${sizes[size].container}
          ${checked ? 'bg-cyan-500/20 border-cyan-500/30 border' : 'bg-zinc-800 border-zinc-700 border'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          ${className || ''}
        `}
      >
        <span
          className={`
            inline-block transform rounded-full transition-all duration-200
            ${sizes[size].thumb}
            ${checked ? `bg-cyan-500 ${sizes[size].translate} shadow-[0_0_8px_rgba(6,182,212,0.6)]` : 'bg-zinc-400 translate-x-1'}
          `}
        />
      </button>
    );
  }
);

Switch.displayName = 'Switch';
