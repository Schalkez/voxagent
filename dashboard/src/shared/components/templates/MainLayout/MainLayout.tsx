import React from 'react';
import { Sidebar, Topbar } from '../../organisms';

export interface MainLayoutProps {
  children: React.ReactNode;
  breadcrumbPaths: string[];
  topbarActionNode?: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ 
  children, 
  breadcrumbPaths,
  topbarActionNode
}) => {
  return (
    <div className="flex min-h-screen bg-surface-lowest text-text-on-surface">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0">
        <Topbar paths={breadcrumbPaths} actionNode={topbarActionNode} />
        <section className="flex-1 p-8 overflow-y-auto">
          {children}
        </section>
        <footer className="h-10 px-8 flex items-center justify-between border-t border-outline-variant/20 bg-surface-base/50 text-[10px] uppercase tracking-widest font-mono text-text-on-surface-variant">
          <span>Encryption: AES-256-BIT</span>
          <span>Instance: VOXAGENT_CORE_01</span>
        </footer>
      </main>
    </div>
  );
};
