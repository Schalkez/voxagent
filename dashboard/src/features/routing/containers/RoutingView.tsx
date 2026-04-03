import React from 'react';
import { MainLayout } from '@shared/components';
import {
  RoutingPresetCard,
  TierCard,
  RoutingStatusChip,
} from '@features/routing/components/organisms';
import type { PresetId } from '@features/routing/types';
import { ROUTING_PRESETS } from '@features/routing/constants';
import { useRoutingConfig } from '@features/routing/hooks/useRouting';

export const RoutingView: React.FC = () => {
  const { config, loading, error, setConfig } = useRoutingConfig();

  if (loading || !config) {
    return (
      <MainLayout breadcrumbPaths={['VOXAGENT', 'Routing']}>
        <div className="flex items-center justify-center min-h-[400px]">
          <span className="text-zinc-500 font-mono text-sm animate-pulse uppercase tracking-widest">
            Loading routing config...
          </span>
        </div>
      </MainLayout>
    );
  }

  const handlePresetChange = (preset: PresetId) => {
    setConfig({ ...config, preset });
  };

  const handleTierProviderChange = (tierIndex: number, provider: string) => {
    const tiers = config.tiers.map((t, i) =>
      i === tierIndex ? { tier: t.tier, title: t.title, description: t.description, provider, model: t.model, provider_options: t.provider_options, model_options: t.model_options, warning: t.warning } : t
    );
    setConfig({ preset: config.preset, tiers, status: config.status });
  };

  const handleTierModelChange = (tierIndex: number, model: string) => {
    const tiers = config.tiers.map((t, i) =>
      i === tierIndex ? { tier: t.tier, title: t.title, description: t.description, provider: t.provider, model, provider_options: t.provider_options, model_options: t.model_options, warning: t.warning } : t
    );
    setConfig({ preset: config.preset, tiers, status: config.status });
  };

  return (
    <MainLayout breadcrumbPaths={['VOXAGENT', 'Routing']}>
      <div className="p-8 max-w-6xl w-full mx-auto">
        {error && (
          <div className="mb-8 px-4 py-2 rounded-lg bg-tertiary/10 border border-tertiary/20 text-tertiary text-[11px] font-mono uppercase tracking-wider">
            {error}
          </div>
        )}

        {/* ── Header + Presets ── */}
        <section className="mb-12">
          <div className="flex flex-col gap-2 mb-8">
            <h2 className="text-4xl font-bold text-text-on-surface font-headline tracking-tight">
              Intelligence Routing
            </h2>
            <p className="text-zinc-400 text-lg font-light">
              Configure which AI models handle different levels of task complexity.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {ROUTING_PRESETS.map((p) => (
              <RoutingPresetCard
                key={p.id}
                {...p}
                active={config.preset === p.id}
                onClick={handlePresetChange}
              />
            ))}
          </div>
        </section>

        {/* ── Tier Pipeline ── */}
        <section className="relative">
          <div className="absolute left-12 top-0 bottom-0 w-[1px] bg-gradient-to-b from-primary/50 via-zinc-800 to-transparent z-0 ml-[-0.5px]" />
          <div className="flex flex-col gap-6 relative z-10">
            {config.tiers.map((t, i) => (
              <TierCard
                key={t.tier}
                tier={t.tier}
                title={t.title}
                description={t.description}
                provider={t.provider}
                model={t.model}
                providerOptions={t.provider_options}
                modelOptions={t.model_options}
                onProviderChange={(v) => handleTierProviderChange(i, v)}
                onModelChange={(v) => handleTierModelChange(i, v)}
                {...(t.warning !== undefined ? { warning: t.warning } : {})}
              />
            ))}
          </div>
        </section>

        <RoutingStatusChip status={config.status} />
      </div>
    </MainLayout>
  );
};
