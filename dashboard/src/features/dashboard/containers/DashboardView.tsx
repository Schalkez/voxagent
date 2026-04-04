import React from 'react';
import { MainLayout } from '@shared/components';
import { HeroCard, BentoGrid, TerminalLog } from '@features/dashboard/components/organisms';
import { useDashboardStatus } from '@features/dashboard/hooks/useDashboardStatus';

export const DashboardView: React.FC = () => {
  const { status, loading, error } = useDashboardStatus();

  return (
    <MainLayout breadcrumbPaths={['VOXAGENT', 'Overview']}>
      <div className="flex flex-col gap-8">
        <HeroCard
          isListening={status.listening}
          isOnline={status.status === 'online'}
          error={error}
        />
        <BentoGrid
          dailyCommands={status.stats.daily_commands}
          avgLatencyMs={status.stats.avg_latency_ms}
          activeSkills={status.skills.active}
          totalSkills={status.skills.total}
          loading={loading}
        />
        <TerminalLog />
      </div>
    </MainLayout>
  );
};
