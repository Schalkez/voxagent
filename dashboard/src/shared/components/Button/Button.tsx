import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'tertiary';
  children: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', className = '', children, ...props }, ref) => {
    
    const baseStyles = "flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg text-sm font-bold transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed";
    
    let variantStyles = "";
    if (variant === 'primary') {
      variantStyles = "bg-gradient-to-br from-[#06b6d4] to-[#00424f] text-white shadow-lg shadow-primary/20 hover:scale-[1.02]";
    } else if (variant === 'secondary') {
      variantStyles = "bg-surface-container-high border border-outline-variant/30 text-on-surface hover:bg-surface-variant";
    } else {
      variantStyles = "bg-transparent text-primary hover:bg-primary/10";
    }

    return (
      <button
        ref={ref}
        className={`${baseStyles} ${variantStyles} ${className}`}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
