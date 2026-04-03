/**
 * React hooks for Routing API integration.
 */

import { useCallback, useEffect, useState } from 'react';
import { fetchApi } from '@shared/api/client';
import type { RoutingConfig } from '@features/routing/types';
import { MOCK_ROUTING_CONFIG } from '@features/routing/constants';

export function useRoutingConfig() {
  const [config, setConfig] = useState<RoutingConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchApi<RoutingConfig>('/api/routing');
        if (!cancelled) {
          setConfig(data);
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setConfig(MOCK_ROUTING_CONFIG);
          setError('API offline — using mock data');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { config, loading, error, setConfig };
}

export function useSaveRoutingConfig() {
  const [saving, setSaving] = useState(false);

  const saveConfig = useCallback(async (config: RoutingConfig) => {
    setSaving(true);
    try {
      await fetchApi('/api/routing', {
        method: 'PUT',
        body: JSON.stringify(config),
      });
      return { success: true };
    } catch (err) {
      console.error('[Routing] Save failed:', err);
      return { success: false };
    } finally {
      setSaving(false);
    }
  }, []);

  return { saveConfig, saving };
}
