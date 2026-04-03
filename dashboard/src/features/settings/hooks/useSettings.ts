import { useCallback, useEffect, useState } from 'react';
import { fetchApi } from '@shared/api/client';
import type { SystemSettings, UpdateSettingsPayload } from '@features/settings/types';

export function useSettings() {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchApi<SystemSettings>('/api/settings');
        if (!cancelled) {
          setSettings(data);
          setIsError(false);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('[Settings] Fetch failed:', err);
          setIsError(true);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  const updateSettings = useCallback(async (payload: UpdateSettingsPayload) => {
    setIsUpdating(true);
    try {
      const resp = await fetchApi<{ success: boolean; settings: SystemSettings }>('/api/settings', {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      if (resp.success) {
        setSettings(resp.settings);
      }
      return resp.success;
    } catch (err) {
      console.error('[Settings] Update failed:', err);
      return false;
    } finally {
      setIsUpdating(false);
    }
  }, []);

  return {
    settings,
    isLoading,
    isError,
    updateSettings,
    isUpdating,
  };
}
