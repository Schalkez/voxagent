import React from 'react';
import { NavItem, StatusBadge } from '../../molecules';
import { Text } from '../../atoms';

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 flex flex-col border-r border-outline-variant/20 bg-surface-base shrink-0">
      <div className="p-6 pb-8 border-b border-outline-variant/10 flex flex-col gap-2">
        <div className="flex items-center justify-between mt-2">
          <Text as="span" variant="mono" className="text-primary font-bold text-[13px] tracking-widest uppercase">VOXAGENT</Text>
        </div>
        <StatusBadge status="Online" className="mt-1" />
      </div>
      <nav className="flex-1 flex flex-col py-4">
        <NavItem label="Overview" iconName="dashboard" href="/dashboard" />
        <NavItem label="Autopilot" iconName="smart_toy" href="/autopilot" />
        <NavItem label="Memory" iconName="memory" href="/memory" />
        <NavItem label="Providers" iconName="hub" href="/providers" />
        <NavItem label="Routing" iconName="route" href="/routing" />
        <NavItem label="Skills" iconName="extension" href="/skills" />
        <div className="flex-1"></div>
        <NavItem label="Settings" iconName="settings" href="/settings" />
      </nav>
    </aside>
  );
};
