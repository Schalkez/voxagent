import React, { type HTMLAttributes, type ElementType } from 'react';

export type TextVariant = 'body' | 'label' | 'headline' | 'mono';

export interface TextProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType;
  variant?: TextVariant;
  className?: string;
  children: React.ReactNode;
}

export const Text: React.FC<TextProps> = ({
  as: Component = 'span',
  variant = 'body',
  className = '',
  children,
  ...props
}) => {
  const variantClasses = {
    body: 'font-sans text-text-on-surface-variant',
    label: 'font-sans text-xs uppercase tracking-wider text-text-on-surface-variant',
    headline: 'font-sans tracking-tight text-text-on-surface font-bold',
    mono: 'font-mono',
  };

  return (
    <Component className={`${variantClasses[variant]} ${className}`} {...props}>
      {children}
    </Component>
  );
};
