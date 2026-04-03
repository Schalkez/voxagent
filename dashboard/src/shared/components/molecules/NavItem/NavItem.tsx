import React from 'react';
import { NavLink } from 'react-router-dom';
import { Icon, type IconName } from '@shared/components';

export interface NavItemProps {
  label: string;
  iconName: IconName;
  href?: string;
  className?: string;
}

export const NavItem: React.FC<NavItemProps> = ({
  label,
  iconName,
  href = '#',
  className = ''
}) => {
  return (
    <NavLink 
      to={href}
      className={({ isActive }: { isActive: boolean }) => `flex items-center px-6 py-4 font-mono text-[11px] uppercase tracking-[0.05em] transition-all duration-200 border-l-4 ${
        isActive 
          ? 'bg-surface-high text-primary border-primary' 
          : 'text-text-on-surface-variant hover:bg-surface-high/50 hover:text-primary border-transparent'
      } ${className}`} 
    >
      <Icon name={iconName} className="mr-4 text-lg" />
      <span>{label}</span>
    </NavLink>
  );
};
