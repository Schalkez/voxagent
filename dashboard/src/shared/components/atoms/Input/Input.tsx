import { forwardRef, type InputHTMLAttributes } from 'react';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  leftIcon?: string;
  rightIcon?: string;
  onRightIconClick?: () => void;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, leftIcon, rightIcon, onRightIconClick, error, disabled, ...props }, ref) => {
    return (
      <div className={`relative flex flex-col gap-1 w-full ${className || ''}`}>
        <div className="relative group">
          {leftIcon && (
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 text-sm pointer-events-none group-focus-within:text-cyan-500 transition-colors">
              {leftIcon}
            </span>
          )}
          
          <input
            ref={ref}
            disabled={disabled}
            className={`
              w-full bg-zinc-950/50 border border-zinc-800 px-4 py-3 rounded-lg font-mono text-sm text-zinc-300
              focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/50 transition-all
              placeholder:text-zinc-600 disabled:cursor-not-allowed disabled:bg-zinc-900/30 disabled:text-zinc-700
              ${leftIcon ? 'pl-9' : ''}
              ${rightIcon ? 'pr-9' : ''}
              ${error ? 'border-error/50 focus:border-error focus:ring-error/20 text-error' : ''}
            `}
            {...props}
          />

          {rightIcon && (
            <span 
              className={`material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 text-sm transition-colors ${onRightIconClick ? 'cursor-pointer hover:text-cyan-400' : 'pointer-events-none'}`}
              onClick={onRightIconClick}
              role="button"
              tabIndex={onRightIconClick ? 0 : -1}
            >
              {rightIcon}
            </span>
          )}
        </div>
        {error && <span className="text-[10px] text-error font-mono px-1">{error}</span>}
      </div>
    );
  }
);

Input.displayName = 'Input';
