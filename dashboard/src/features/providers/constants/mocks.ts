import type { ProviderInfo } from '@features/providers/types';

export const MOCK_PROVIDERS: ProviderInfo[] = [
  { id: 'openai', name: 'OpenAI', icon: 'psychology', provider_type: 'cloud', status: 'connected', has_key: true },
  { id: 'groq', name: 'Groq', icon: 'bolt', provider_type: 'cloud', status: 'connected', has_key: true },
  { id: 'anthropic', name: 'Anthropic', icon: 'shield', provider_type: 'cloud', status: 'connected', has_key: true },
  { id: 'gemini', name: 'Gemini', icon: 'flare', provider_type: 'cloud', status: 'missing', has_key: false },
  { id: 'ollama', name: 'Ollama', icon: 'terminal', provider_type: 'local', status: 'connected', has_key: false },
];
