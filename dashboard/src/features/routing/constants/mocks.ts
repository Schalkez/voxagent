/**
 * Mock routing config for offline/dev fallback.
 */

import type { RoutingConfig } from '@features/routing/types';

export const MOCK_ROUTING_CONFIG: RoutingConfig = {
  preset: 'balanced',
  tiers: [
    {
      tier: 1,
      title: 'Tier 1 (Speed & Simple)',
      description: 'Fastest. Used for simple intents, parsing, and extraction.',
      provider: 'Groq',
      model: 'llama-3.1-8b-instant',
      provider_options: ['Groq', 'OpenAI', 'Mistral'],
      model_options: ['llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'gemma-7b-it'],
    },
    {
      tier: 2,
      title: 'Tier 2 (Reasoning)',
      description: 'Balanced. Used for logic, file management, and multi-step plans.',
      provider: 'Ollama',
      model: 'qwen2.5:7b',
      provider_options: ['Ollama', 'Azure AI', 'AWS Bedrock'],
      model_options: ['qwen2.5:7b', 'llama3:8b-instruct', 'mistral-v0.3'],
    },
    {
      tier: 3,
      title: 'Tier 3 (Complex & Vision)',
      description: 'Heavy lifting. Used for code review, screen reading, and complex problem solving.',
      provider: 'Anthropic',
      model: 'claude-3-5-sonnet',
      provider_options: ['Anthropic', 'Google Vertex', 'OpenAI'],
      model_options: ['claude-3-5-sonnet', 'gpt-4o-2024-08-06', 'gemini-1.5-pro'],
      warning: 'High Cost',
    },
  ],
  status: 'Optimized for latency',
};
