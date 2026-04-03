import React from 'react';
import { MainLayout } from '@shared/components';

export const RoutingView: React.FC = () => {
  return (
    <MainLayout breadcrumbPaths={['VOXAGENT', 'Smart Routing']}>
      <div className="flex flex-col gap-8">
        <h1 className="text-2xl font-bold font-headline text-[#FAFAFA]">Smart Routing</h1>
        <p className="text-zinc-400">Configure intelligent fallbacks and semantic routing tiers.</p>
        <div className="flex-1 min-h-[400px] border border-dashed border-outline-variant/30 flex items-center justify-center text-zinc-600 rounded-lg">
          [Routing Module Pending Implementation]
        </div>
      </div>
    </MainLayout>
  );
};
