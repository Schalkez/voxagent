import React from 'react';
import { MainLayout } from '../../../shared/components';

export const AutopilotView: React.FC = () => {
  return (
    <MainLayout breadcrumbPaths={['VOXAGENT', 'Autopilot']}>
      <div className="flex flex-col gap-8">
        <h1 className="text-2xl font-bold font-headline text-[#FAFAFA]">Autopilot Tasks</h1>
        <p className="text-zinc-400">Manage your autonomous agents and task sequences here.</p>
        <div className="flex-1 min-h-[400px] border border-dashed border-outline-variant/30 flex items-center justify-center text-zinc-600 rounded-lg">
          [Autopilot Module Pending Implementation]
        </div>
      </div>
    </MainLayout>
  );
};
