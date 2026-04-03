import React, { type HTMLAttributes } from 'react';

export type IconName = 
  | 'dashboard' 
  | 'extension' 
  | 'settings' 
  | 'hub' 
  | 'route' 
  | 'memory' 
  | 'assignment' 
  | 'delete_sweep'
  | 'auto_awesome'
  // Add more as needed
  | string;

export interface IconProps extends HTMLAttributes<HTMLSpanElement> {
  name: IconName;
  className?: string;
}

export const Icon: React.FC<IconProps> = ({ name, className = '', ...props }) => {
  return (
    <span
      className={`material-symbols-outlined ${className}`}
      {...props}
    >
      {name}
    </span>
  );
};
