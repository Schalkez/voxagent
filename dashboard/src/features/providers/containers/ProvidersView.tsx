import React from 'react';
import { MainLayout } from '@shared/components';
import {
  ProviderCard,
  OllamaCard,
  QuotaStats,
} from '../components/organisms';
import { useProviders, useSaveKey } from '../hooks/useProviders';

export const ProvidersView: React.FC = () => {
  const { providers, loading, error } = useProviders();
  const { saveKey } = useSaveKey();

  const cloudProviders = providers.filter((p) => p.provider_type === 'cloud');
  const ollamaProvider = providers.find((p) => p.id === 'ollama');

  if (loading) {
    return (
      <MainLayout breadcrumbPaths={['VOXAGENT', 'Providers']}>
        <div className="flex items-center justify-center min-h-[400px]">
          <span className="text-zinc-500 font-mono text-sm animate-pulse uppercase tracking-widest">
            Loading providers...
          </span>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout breadcrumbPaths={['VOXAGENT', 'Providers']}>
      <div className="p-8 max-w-6xl w-full mx-auto space-y-12">
        {/* API Status Banner */}
        {error && (
          <div className="px-4 py-2 rounded-lg bg-tertiary/10 border border-tertiary/20 text-tertiary text-[11px] font-mono uppercase tracking-wider">
            {error}
          </div>
        )}

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
            {cloudProviders.map((p) => (
              <ProviderCard
                key={p.id}
                name={p.name}
                icon={p.icon}
                status={p.status}
                onSave={(key) => void saveKey(p.id, key)}
              />
            ))}
          </div>
        </section>

        {/* ── Local Environment ── */}
        {ollamaProvider && (
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
        )}

        {/* ── Usage Quota ── */}
        <QuotaStats />
      </div>
    </MainLayout>
  );
};
