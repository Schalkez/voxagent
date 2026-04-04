import React from 'react';
import { MainLayout } from '@shared/components';

const MOCK_TASKS = [
  { id: 1, name: 'Monitor Cursor progress', trigger: 'Every 5 min', status: 'scheduled', icon: '🔄' },
  { id: 2, name: 'Check email for invoices', trigger: 'On new email', status: 'idle', icon: '📧' },
  { id: 3, name: 'Backup workspace', trigger: 'Daily at 23:00', status: 'completed', icon: '💾' },
];

export const AutopilotView: React.FC = () => {
  return (
    <MainLayout breadcrumbPaths={['VOXAGENT', 'Autopilot']}>
      <div className="flex flex-col gap-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold font-headline text-[#FAFAFA]">Autopilot Tasks</h1>
            <p className="text-zinc-400 mt-1">
              Autonomous background tasks with time, event, and condition triggers.
            </p>
          </div>
          <span className="px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 text-xs font-medium border border-amber-500/20">
            Coming in Phase 3
          </span>
        </div>

        {/* Preview task list */}
        <div className="grid gap-4">
          {MOCK_TASKS.map((task) => (
            <div
              key={task.id}
              className="p-4 rounded-xl border border-outline-variant/20 bg-surface-container/40 opacity-60 cursor-not-allowed"
            >
              <div className="flex items-center gap-4">
                <span className="text-2xl">{task.icon}</span>
                <div className="flex-1">
                  <p className="text-sm font-medium text-[#FAFAFA]">{task.name}</p>
                  <p className="text-xs text-zinc-500">Trigger: {task.trigger}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  task.status === 'scheduled' ? 'bg-blue-500/10 text-blue-400' :
                  task.status === 'completed' ? 'bg-green-500/10 text-green-400' :
                  'bg-zinc-500/10 text-zinc-400'
                }`}>
                  {task.status}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="p-6 rounded-xl border border-dashed border-outline-variant/30 bg-surface-container/20 text-center">
          <p className="text-zinc-500 text-sm">
            Autopilot will support time-based, event-based, condition-based, and idle triggers.
          </p>
          <p className="text-zinc-600 text-xs mt-2">
            Example: &quot;Khi Cursor xong thì check 100% chưa, chưa thì prompt tiếp, xong thì báo tôi&quot;
          </p>
        </div>
      </div>
    </MainLayout>
  );
};
