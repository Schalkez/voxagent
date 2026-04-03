import { forwardRef, type SelectHTMLAttributes } from 'react';

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, children, disabled, ...props }, ref) => {
    return (
      <div className={`relative flex flex-col gap-1.5 w-full ${className || ''}`}>
        {label && (
           <label className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">
             {label}
           </label>
        )}
        <div className="relative group w-full">
          <select
            ref={ref}
            disabled={disabled}
            className={`
              w-full bg-zinc-950/50 border-b border-zinc-800 py-2 px-3 text-sm text-[#E5E1E4] 
              appearance-none outline-none focus:border-cyan-500 transition-colors
              ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
              ${error ? 'border-error text-error' : ''}
            `}
            {...props}
          >
            {children}
          </select>
          <span 
            className="material-symbols-outlined absolute right-2 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none group-focus-within:text-cyan-500 transition-colors text-sm"
          >
            expand_more
          </span>
        </div>
        {error && <span className="text-[10px] text-error font-mono">{error}</span>}
      </div>
    );
  }
);

Select.displayName = 'Select';
