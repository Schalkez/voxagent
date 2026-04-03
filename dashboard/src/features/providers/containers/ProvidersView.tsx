import React from 'react';
import { MainLayout } from '@shared/components';
import {
  ProviderCard,
  OllamaCard,
  QuotaStats,
} from '../components/organisms';

const CLOUD_PROVIDERS = [
  {
    id: 'openai',
    name: 'OpenAI',
    icon: 'psychology',
    status: 'connected' as const,
    apiKey: 'sk-projk283ls92js01abc1',
  },
  {
    id: 'groq',
    name: 'Groq',
    icon: 'bolt',
    status: 'connected' as const,
    apiKey: 'gsk_lS7294mZ09XnQp1wR2vA',
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    icon: 'shield',
    status: 'connected' as const,
    apiKey: 'sk-ant-api03-P2k9s01L02',
  },
  {
    id: 'gemini',
    name: 'Gemini',
    icon: 'flare',
    status: 'missing' as const,
  },
];

export const ProvidersView: React.FC = () => {
  return (
    <MainLayout breadcrumbPaths={['VOXAGENT', 'Providers']}>
      <div className="p-8 max-w-6xl w-full mx-auto space-y-12">
        {/* ── Cloud Providers ── */}
        <section>
          <div className="flex items-baseline justify-between mb-6">
            <h2 className="text-xl font-headline font-bold text-text-on-surface tracking-tight">
              Cloud Providers
            </h2>
            <span className="text-[10px] font-mono text-zinc-600 uppercase tracking-widest">
              Global Managed Services
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {CLOUD_PROVIDERS.map(({ id, ...rest }) => (
              <ProviderCard
                key={id}
                {...rest}
                onSave={(key) =>
                  console.log(`[Provider] Save ${id} key:`, key)
                }
              />
            ))}
          </div>
        </section>

        {/* ── Local Environment ── */}
        <section>
          <div className="flex items-baseline justify-between mb-6">
            <h2 className="text-xl font-headline font-bold text-text-on-surface tracking-tight">
              Local Environment
            </h2>
            <span className="text-[10px] font-mono text-zinc-600 uppercase tracking-widest">
              Self-Hosted Inference
            </span>
          </div>
          <OllamaCard
            baseUrl="http://localhost:11434"
            onTest={() => console.log('[Ollama] Test connection')}
          />
        </section>

        {/* ── Usage Quota ── */}
        <QuotaStats />
      </div>
    </MainLayout>
  );
};
