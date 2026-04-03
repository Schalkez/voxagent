/**
 * React hooks for Routing API integration.
 *
 * Manages tier routing configuration — connects the Routing dashboard
 * to the FastAPI backend. Falls back to mock data when offline.
 */

import { useCallback, useEffect, useState } from 'react';
import { fetchApi } from '@shared/api/client';
import type { PresetId } from '@features/routing/components/organisms/RoutingPresetCard/RoutingPresetCard';

// ── Types ──

export interface TierConfig {
  tier: number;
  title: string;
  description: string;
  provider: string;
  model: string;
  provider_options: string[];
  model_options: string[];
  warning?: string | undefined;
}

export interface RoutingConfig {
  preset: PresetId;
  tiers: TierConfig[];
  status: string;
}

// ── Mock Data ──

const MOCK_CONFIG: RoutingConfig = {
  preset: 'balanced',
  tiers: [
    {
      tier: 1,
      title: 'Tier 1 (Speed & Simple)',
      description:
        'Fastest. Used for simple intents, parsing, and extraction.',
      provider: 'Groq',
      model: 'llama-3.1-8b-instant',
      provider_options: ['Groq', 'OpenAI', 'Mistral'],
      model_options: [
        'llama-3.1-8b-instant',
        'mixtral-8x7b-32768',
        'gemma-7b-it',
      ],
    },
    {
      tier: 2,
      title: 'Tier 2 (Reasoning)',
      description:
        'Balanced. Used for logic, file management, and multi-step plans.',
      provider: 'Ollama',
      model: 'qwen2.5:7b',
      provider_options: ['Ollama', 'Azure AI', 'AWS Bedrock'],
      model_options: ['qwen2.5:7b', 'llama3:8b-instruct', 'mistral-v0.3'],
    },
    {
      tier: 3,
      title: 'Tier 3 (Complex & Vision)',
      description:
        'Heavy lifting. Used for code review, screen reading, and complex problem solving.',
      provider: 'Anthropic',
      model: 'claude-3-5-sonnet',
      provider_options: ['Anthropic', 'Google Vertex', 'OpenAI'],
      model_options: [
        'claude-3-5-sonnet',
        'gpt-4o-2024-08-06',
        'gemini-1.5-pro',
      ],
      warning: 'High Cost',
    },
  ],
  status: 'Optimized for latency',
};

// ── Hooks ──

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
          setConfig(MOCK_CONFIG);
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
