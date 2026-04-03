import React from 'react';
import { MainLayout } from '../../../shared/components';

export const ProvidersView: React.FC = () => {
  return (
    <MainLayout breadcrumbPaths={['VOXAGENT', 'Providers']}>
      <div className="flex flex-col gap-8">
        <h1 className="text-2xl font-bold font-headline text-[#FAFAFA]">Model Providers</h1>
        <p className="text-zinc-400">Configure API keys and rate limits for LLM providers.</p>
        <div className="flex-1 min-h-[400px] border border-dashed border-outline-variant/30 flex items-center justify-center text-zinc-600 rounded-lg">
          [Providers Module Pending Implementation]
        </div>
      </div>
    </MainLayout>
  );
};
