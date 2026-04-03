/**
 * React hooks for Provider API integration.
 *
 * These hooks connect the Provider dashboard to the FastAPI backend.
 * When the backend is unavailable, they gracefully fall back to mock data.
 */

import { useCallback, useEffect, useState } from 'react';
import { fetchApi } from '@shared/api/client';

// ── Types ──

export interface ProviderInfo {
  id: string;
  name: string;
  icon: string;
  provider_type: string;
  status: 'connected' | 'missing';
  has_key: boolean;
}

export interface TestResult {
  ok: boolean;
  latency_ms: number;
  message: string;
}

// ── Mock Data (fallback when API is unreachable) ──

const MOCK_PROVIDERS: ProviderInfo[] = [
  { id: 'openai', name: 'OpenAI', icon: 'psychology', provider_type: 'cloud', status: 'connected', has_key: true },
  { id: 'groq', name: 'Groq', icon: 'bolt', provider_type: 'cloud', status: 'connected', has_key: true },
  { id: 'anthropic', name: 'Anthropic', icon: 'shield', provider_type: 'cloud', status: 'connected', has_key: true },
  { id: 'gemini', name: 'Gemini', icon: 'flare', provider_type: 'cloud', status: 'missing', has_key: false },
  { id: 'ollama', name: 'Ollama', icon: 'terminal', provider_type: 'local', status: 'connected', has_key: false },
];

// ── Hooks ──

export function useProviders() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchApi<ProviderInfo[]>('/api/providers');
        if (!cancelled) {
          setProviders(data);
          setError(null);
        }
      } catch {
        // Fallback to mock data when API is unavailable
        if (!cancelled) {
          setProviders(MOCK_PROVIDERS);
          setError('API offline — using mock data');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => { cancelled = true; };
  }, []);

  return { providers, loading, error };
}

export function useSaveKey() {
  const [saving, setSaving] = useState(false);

  const saveKey = useCallback(async (providerId: string, apiKey: string) => {
    setSaving(true);
    try {
      await fetchApi(`/api/providers/${providerId}/key`, {
        method: 'POST',
        body: JSON.stringify({ api_key: apiKey }),
      });
      return { success: true };
    } catch (err) {
      console.error('[Provider] Save key failed:', err);
      return { success: false };
    } finally {
      setSaving(false);
    }
  }, []);

  return { saveKey, saving };
}

export function useTestConnection() {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);

  const testConnection = useCallback(async (providerId: string) => {
    setTesting(true);
    setResult(null);
    try {
      const data = await fetchApi<TestResult>(`/api/providers/${providerId}/test`, {
        method: 'POST',
      });
      setResult(data);
      return data;
    } catch {
      const fallback: TestResult = {
        ok: false,
        latency_ms: 0,
        message: 'API server unreachable',
      };
      setResult(fallback);
      return fallback;
    } finally {
      setTesting(false);
    }
  }, []);

  return { testConnection, testing, result };
}
