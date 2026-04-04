import { useCallback, useEffect, useState } from 'react';
import { fetchApi } from '@shared/api/client';
import type { DashboardStatus } from '@features/dashboard/types';

const POLL_INTERVAL_MS = 5_000;

const DEFAULT_STATUS: DashboardStatus = {
  status: 'offline',
  listening: false,
  skills: { active: 0, total: 0 },
  providers: { llm: [], stt: [], tts: [] },
  stats: { daily_commands: 0, avg_latency_ms: 0, uptime_seconds: 0 },
};

export function useDashboardStatus() {
  const [status, setStatus] = useState<DashboardStatus>(DEFAULT_STATUS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchApi<DashboardStatus>('/api/status');
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed');
      setStatus((prev) => ({ ...prev, status: 'offline' }));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  return { status, loading, error, refresh };
}
