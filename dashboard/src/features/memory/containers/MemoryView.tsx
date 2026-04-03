import React from 'react';
import { MainLayout } from '@shared/components';

export const MemoryView: React.FC = () => {
  return (
    <MainLayout breadcrumbPaths={['VOXAGENT', 'Memory']}>
      <div className="flex flex-col gap-8">
        <h1 className="text-2xl font-bold font-headline text-[#FAFAFA]">Agent Memory</h1>
        <p className="text-zinc-400">View and manage long-term conversational memory.</p>
        <div className="flex-1 min-h-[400px] border border-dashed border-outline-variant/30 flex items-center justify-center text-zinc-600 rounded-lg">
          [Memory Module Pending Implementation]
        </div>
      </div>
    </MainLayout>
  );
};
